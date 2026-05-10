"""
run_experiment.py — CLI entry point for the ICG MuSiQue evaluation.

Usage:
    python -m src.eval.run_experiment [OPTIONS]

    --data PATH         Path to MuSiQue JSONL (default: dev split)
    --model MODEL       OpenRouter model string (default: openai/gpt-4.1-mini)
    --max-tokens N      Per-agent / single-agent token budget (default: 500)
    --max-workers N     API concurrency (default: 5)
    --limit N           Cap number of instances per stratum (0 = no limit)
    --seed N            Random seed for A2 shard shuffling (default: 42)
    --setting {a1,a2,both}  Which Variant A setting to run (default: both)
    --skip-b            Skip Variant B (useful for quick A-only runs)
    --output PATH       Write JSON results to this file
                        (default: results/run_<timestamp>.json)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

# Ensure repo root is importable when run as a module or script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utility.apis import openrouter_api
from .data_loader import load_musique, stratify_by_icg
from .variant_a import run_variant_a_batch
from .variant_b import run_variant_b_batch
from .evaluate import (
    aggregate_by_stratum,
    compute_correlation,
    print_results_table,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_results(
    a_results: list[dict],
    b_results: list[dict],
) -> list[dict]:
    """Merge per-instance A and B results into a joint list.

    Both lists must be in the same order (same instances).  Returns a list
    of dicts with keys: id, icg, f1_a, f1_a_mv, f1_b.
    """
    b_by_id = {r["id"]: r for r in b_results}
    merged: list[dict] = []
    for a in a_results:
        b = b_by_id.get(a["id"])
        merged.append({
            "id": a["id"],
            "icg": a["icg"],
            "f1_a": a["f1"],
            "f1_a_mv": a.get("majority_vote_f1", 0.0),
            "f1_b": b["f1"] if b else 0.0,
            "pred_a": a["pred"],
            "majority_vote_pred": a.get("majority_vote_pred", ""),
            "pred_b": b["pred"] if b else "",
            "agent_answers": a.get("agent_answers", []),
            "agent_errors": a.get("agent_errors", []),
            "agent_f1s": a.get("agent_f1s", []),
            "agent_shards": a.get("agent_shards", []),
            "num_agents": a.get("num_agents", 1),
            "error_b": b["error"] if b else None,
        })
    return merged


def _cap_instances(instances: list[dict], limit: int) -> list[dict]:
    """Return at most ``limit`` instances (0 = no cap)."""
    if limit <= 0:
        return instances
    return instances[:limit]


def _write_detail_log(
    merged: list[dict],
    instances_by_id: dict[str, dict],
    setting_label: str,
    path: str,
) -> None:
    """Write a per-instance human-readable detail log.

    For each instance shows: question, gold answer, supporting paragraphs
    (labelled by agent assignment), per-agent answers with F1, and the
    centralized Variant B answer.
    """
    SEP = "=" * 72

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"Setting: {setting_label}  |  {len(merged)} instances\n")
        fh.write(f"{SEP}\n\n")

        for r in merged:
            inst = instances_by_id.get(r["id"], {})
            supporting = [p for p in inst.get("paragraphs", []) if p["is_supporting"]]

            fh.write(f"ID:       {r['id']}\n")
            fh.write(f"ICG:      {r['icg']}  |  Hops: {len(supporting)}  |  Agents: {r['num_agents']}\n")
            fh.write(f"Question: {inst.get('question', 'N/A')}\n")
            fh.write(f"Gold:     {inst.get('answer', 'N/A')}")
            aliases = inst.get("answer_aliases", [])
            if aliases:
                fh.write(f"  (aliases: {', '.join(aliases)})")
            fh.write("\n\n")

            fh.write("--- Supporting Paragraphs (by agent assignment) ---\n")
            para_by_title = {p["title"]: p["paragraph_text"] for p in supporting}
            agent_shards = r.get("agent_shards", [])
            if agent_shards:
                for i, shard_titles in enumerate(agent_shards):
                    for title in shard_titles:
                        fh.write(f"[Agent {i+1} | {title}]\n")
                        fh.write(f"{para_by_title.get(title, '(text not found)')}\n\n")
            else:
                # Fallback for old results without agent_shards
                for i, para in enumerate(supporting):
                    fh.write(f"[Agent {i+1} | {para['title']}]\n")
                    fh.write(f"{para['paragraph_text']}\n\n")

            fh.write(f"--- Variant {setting_label} (Isolated) ---\n")
            agent_answers = r.get("agent_answers", [])
            agent_errors = r.get("agent_errors") or []
            agent_f1s = r.get("agent_f1s") or []
            for i, ans in enumerate(agent_answers):
                f1_str = f"{agent_f1s[i]:.3f}" if i < len(agent_f1s) else "N/A"
                err = agent_errors[i] if i < len(agent_errors) else None
                if err:
                    fh.write(f"Agent {i+1}: [API ERROR: {err}]\n")
                else:
                    fh.write(f"Agent {i+1}: {repr(ans)}  [F1: {f1_str}]\n")
            fh.write(f"Oracle pred:       {repr(r['pred_a'])}  [F1: {r['f1_a']:.3f}]\n")
            fh.write(f"Majority-vote pred: {repr(r.get('majority_vote_pred', ''))}  [F1: {r.get('f1_a_mv', 0.0):.3f}]\n\n")

            fh.write("--- Variant B (Centralized) ---\n")
            error_b = r.get("error_b")
            if error_b:
                fh.write(f"pred_b: [API ERROR: {error_b}]  [F1: {r['f1_b']:.3f}]\n")
            else:
                fh.write(f"pred_b: {repr(r['pred_b'])}  [F1: {r['f1_b']:.3f}]\n")

            fh.write(f"\n{SEP}\n\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run ICG MuSiQue evaluation (Variant A vs Variant B)."
    )
    parser.add_argument("--data", default=None, help="Path to MuSiQue JSONL file")
    parser.add_argument(
        "--min-hops", type=int, default=2,
        help="Minimum number of supporting paragraphs per instance (default: 2)"
    )
    parser.add_argument(
        "--model", default="anthropic/claude-3.5-haiku",
        help="OpenRouter model string (default: anthropic/claude-3.5-haiku)"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=4096,
        help="Per-agent output token budget (default: 4096)"
    )
    parser.add_argument(
        "--max-workers", type=int, default=2,
        help="API concurrency (default: 2)"
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Cap instances per stratum (0 = no limit)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Base random seed for A2 paragraph shuffling (default: 42)"
    )
    parser.add_argument(
        "--setting", choices=["a1", "a2", "a3", "all"], default="a1",
        help="Variant A sharding setting to run (default: a1)"
    )
    parser.add_argument(
        "--skip-b", action="store_true",
        help="Skip Variant B (centralized baseline)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Run output directory (default: results/run_<timestamp>/)"
    )
    args = parser.parse_args(argv)

    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
            "results",
            f"run_{timestamp}",
        )

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print(f"Loading MuSiQue data from: {args.data or '(default dev split)'} (min_hops={args.min_hops})")
    instances = load_musique(args.data, min_hops=args.min_hops)
    strata = stratify_by_icg(instances)
    print(f"Loaded {len(instances)} instances across ICG strata: "
          f"{ {k: len(v) for k, v in sorted(strata.items())} }")

    # Apply per-stratum cap
    if args.limit > 0:
        instances = []
        for icg, group in sorted(strata.items()):
            instances.extend(group[: args.limit])
        print(f"After cap: {len(instances)} instances")

    instances_by_id = {inst["id"]: inst for inst in instances}

    # ------------------------------------------------------------------
    # API functions
    # ------------------------------------------------------------------
    batch_fn = lambda reqs, max_workers=5: openrouter_api.batch_request(
        reqs, max_workers=max_workers
    )
    single_fn = openrouter_api.single_request

    # ------------------------------------------------------------------
    # Run Variant B once (shared across both A settings)
    # ------------------------------------------------------------------
    b_results: list[dict] = []
    if not args.skip_b:
        print(f"\nRunning Variant B (centralized, {len(instances)} instances)...")
        b_results = run_variant_b_batch(
            instances, single_fn, args.model, args.max_tokens,
            max_workers=args.max_workers,
        )
        b_mean_f1 = sum(r["f1"] for r in b_results) / max(len(b_results), 1)
        print(f"  Variant B mean F1: {b_mean_f1:.4f}")
        b_errors = sum(1 for r in b_results if r.get("error") is not None)
        if b_errors:
            print(f"  WARNING: {b_errors} Variant B API call(s) failed (answer recorded as empty)")

    all_output: dict = {"settings": {}}

    # ------------------------------------------------------------------
    # Run Variant A settings
    # ------------------------------------------------------------------
    settings_to_run = (
        ["a1", "a2", "a3"] if args.setting == "all" else [args.setting]
    )

    for setting in settings_to_run:
        print(f"\nRunning Variant A ({setting.upper()}, {len(instances)} instances)...")
        a_results = run_variant_a_batch(
            instances,
            setting=setting,
            api_fn=batch_fn,
            model=args.model,
            max_tokens=args.max_tokens,
            max_workers=args.max_workers,
            seed=args.seed,
        )
        a_mean_f1 = sum(r["f1"] for r in a_results) / max(len(a_results), 1)
        print(f"  Variant {setting.upper()} mean F1: {a_mean_f1:.4f}")
        a_errors = sum(
            1 for r in a_results
            for e in r.get("agent_errors", []) if e is not None
        )
        if a_errors:
            print(f"  WARNING: {a_errors} agent API call(s) failed (answer recorded as empty)")

        # Merge with B results
        if b_results:
            merged = _merge_results(a_results, b_results)
        else:
            # Skip-B mode: fill f1_b with 0 placeholder
            merged = [
                {
                    "id": r["id"], "icg": r["icg"],
                    "f1_a": r["f1"], "f1_a_mv": r.get("majority_vote_f1", 0.0),
                    "f1_b": 0.0,
                    "pred_a": r["pred"], "majority_vote_pred": r.get("majority_vote_pred", ""),
                    "pred_b": "",
                    "agent_answers": r.get("agent_answers", []),
                    "agent_errors": r.get("agent_errors", []),
                    "agent_shards": r.get("agent_shards", []),
                    "num_agents": r.get("num_agents", 1),
                    "error_b": None,
                }
                for r in a_results
            ]

        # Aggregate and display
        agg = aggregate_by_stratum(merged)
        label = setting.upper()
        print(f"\n=== Results: Setting {label} ===")
        print_results_table(agg, setting_label=label)

        # Oracle correlation — all instances
        corr = compute_correlation(merged)
        print(f"  Oracle  Pearson(ICG, Δ):  {corr['pearson']}")
        print(f"  Oracle  Spearman(ICG, Δ): {corr['spearman']}")

        # Majority-vote correlation — remap f1_a_mv → f1_a for reuse
        merged_mv = [{**r, "f1_a": r.get("f1_a_mv", 0.0)} for r in merged]
        corr_mv = compute_correlation(merged_mv)
        print(f"  MajVote Pearson(ICG, Δ):  {corr_mv['pearson']}")
        print(f"  MajVote Spearman(ICG, Δ): {corr_mv['spearman']}")

        # Filtered correlations — exclude single-paragraph-sufficient instances
        # (oracle F1_A > 0 means one shard was self-sufficient; not an ICG test)
        filtered = [r for r in merged if r["f1_a"] == 0]
        filtered_corr = compute_correlation(filtered)
        filtered_mv = [{**r, "f1_a": r.get("f1_a_mv", 0.0)} for r in filtered]
        filtered_corr_mv = compute_correlation(filtered_mv)
        n_filtered = len(filtered)
        n_removed = len(merged) - n_filtered
        print(f"  Filtered ({n_removed} self-sufficient removed, n={n_filtered}):")
        print(f"    Oracle  Pearson(ICG, Δ):  {filtered_corr['pearson']}")
        print(f"    Oracle  Spearman(ICG, Δ): {filtered_corr['spearman']}")
        print(f"    MajVote Pearson(ICG, Δ):  {filtered_corr_mv['pearson']}")
        print(f"    MajVote Spearman(ICG, Δ): {filtered_corr_mv['spearman']}")

        all_output["settings"][setting] = {
            "aggregated": {str(k): v for k, v in agg.items()},
            "correlation": corr,
            "correlation_mv": corr_mv,
            "filtered_correlation": filtered_corr,
            "filtered_correlation_mv": filtered_corr_mv,
            "n_self_sufficient": n_removed,
            "instance_results": merged,
        }

    # ------------------------------------------------------------------
    # Cross-setting pooled correlation (meaningful when >1 setting run)
    # ------------------------------------------------------------------
    if len(all_output["settings"]) > 1:
        pooled = []
        for res in all_output["settings"].values():
            pooled.extend(res["instance_results"])
        cross_corr = compute_correlation(pooled)
        pooled_filtered = [r for r in pooled if r["f1_a"] == 0]
        cross_corr_filtered = compute_correlation(pooled_filtered)
        all_output["cross_setting_correlation"] = cross_corr
        all_output["cross_setting_correlation_filtered"] = cross_corr_filtered
        print(f"\n=== Cross-setting correlation (pooled, ICG vs Δ) ===")
        print(f"  Pearson:  {cross_corr['pearson']}")
        print(f"  Spearman: {cross_corr['spearman']}")
        print(f"  Filtered (n={len(pooled_filtered)}):")
        print(f"    Pearson:  {cross_corr_filtered['pearson']}")
        print(f"    Spearman: {cross_corr_filtered['spearman']}")

    # ------------------------------------------------------------------
    # Save output
    # ------------------------------------------------------------------
    if args.output:
        run_dir = args.output
        os.makedirs(run_dir, exist_ok=True)

        # results.json
        json_path = os.path.join(run_dir, "results.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(all_output, fh, indent=2)
        print(f"\nResults written to: {json_path}")

        # summary.txt
        ANNOTATION = """\
Experiment: ICG MuSiQue Evaluation — Variant A (Isolated) vs Variant B (Centralized)
======================================================================================
Design:
  A1  1 paragraph per agent  —  ICG = num_supporting - 1
      Each supporting paragraph is held by exactly one agent. Agents answer
      independently using ONLY their assigned paragraph (strict grounding;
      no outside knowledge permitted).

  A2  2 paragraphs per agent  —  effective ICG = num_supporting - 2
      Agents hold 2 supporting paragraphs each (last agent may hold 1 if odd).
      Crucially, 2-hop instances under A2 collapse to a single agent holding
      all evidence (ICG=0), providing a natural zero-ICG control group.

  Both A settings report two metrics:
    - Oracle F1:       max F1 over all agents (upper bound on isolated perf)
    - Majority-vote F1: F1 of the plurality answer after filtering refusals
                        (reflects the actual multi-agent system output)

  B   Centralized baseline — single agent sees all supporting paragraphs,
      strictly grounded to provided evidence only, with explicit step-by-step
      multi-hop reasoning instruction.

ICG variation:
  A1: ICG varies naturally via hop count (ICG=1,2,3 for 2/3/4-hop instances).
  A2: ICG varies naturally (ICG=0,1,2 for 2/3/4-hop instances), including
      the critical ICG=0 control point where Delta should approach zero.

Filtering:
  Single-paragraph-sufficient instances (oracle F1_A > 0) are excluded from
  the filtered correlation. With strict grounding, this reliably indicates
  the shard contained self-sufficient information — not an ICG test.
  Correlations are reported both with and without this filter.

Delta = F1_B - F1_A  (positive = centralized outperforms isolated)
Hypothesis: Delta grows with ICG (higher hop count → larger gap).
======================================================================================

"""
        summary_path = os.path.join(run_dir, "summary.txt")
        with open(summary_path, "w", encoding="utf-8") as fh:
            fh.write(ANNOTATION)
            fh.write(f"Model: {args.model}\n")
            fh.write(f"Max tokens: {args.max_tokens}\n")
            fh.write(f"Data: {args.data or '(default dev split)'}\n")
            fh.write(f"Min hops: {args.min_hops}\n")
            fh.write(f"Instances per stratum: {args.limit if args.limit > 0 else 'all'}\n\n")
            for setting, res in all_output["settings"].items():
                label = setting.upper()
                fh.write(f"=== Setting {label} ===\n")
                has_mv = any(
                    "f1_a_mv" in row
                    for row in res["aggregated"].values()
                )
                if has_mv:
                    header = (
                        f"ICG  | N      | F1_B (Central) | "
                        f"F1_{label}_oracle | Delta_oracle | "
                        f"F1_{label}_mv    | Delta_mv\n"
                    )
                else:
                    header = (
                        f"ICG  | N      | F1_B (Centralized) | "
                        f"F1_{label} (Isolated) | Delta (B-{label})\n"
                    )
                fh.write(header)
                fh.write("-" * len(header.rstrip()) + "\n")
                for icg_str, row in sorted(res["aggregated"].items(), key=lambda x: int(x[0])):
                    if has_mv:
                        fh.write(
                            f"{int(icg_str):<4d} | {row['n']:<6d} | {row['f1_b']:<15.4f} | "
                            f"{row['f1_a']:<16.4f} | {row['delta']:+.4f}       | "
                            f"{row.get('f1_a_mv', 0.0):<13.4f} | {row.get('delta_mv', 0.0):+.4f}\n"
                        )
                    else:
                        fh.write(
                            f"{int(icg_str):<4d} | {row['n']:<6d} | {row['f1_b']:<19.4f} | "
                            f"{row['f1_a']:<21.4f} | {row['delta']:+.4f}\n"
                        )
                corr = res["correlation"]
                corr_mv = res.get("correlation_mv", {})
                fh.write(f"\n  Oracle  Pearson(ICG, Δ):  {corr['pearson']}\n")
                fh.write(f"  Oracle  Spearman(ICG, Δ): {corr['spearman']}\n")
                if corr_mv:
                    fh.write(f"  MajVote Pearson(ICG, Δ):  {corr_mv.get('pearson')}\n")
                    fh.write(f"  MajVote Spearman(ICG, Δ): {corr_mv.get('spearman')}\n")
                filtered_corr = res.get("filtered_correlation", {})
                filtered_corr_mv = res.get("filtered_correlation_mv", {})
                n_removed = res.get("n_self_sufficient", 0)
                n_filtered = sum(row["n"] for row in res["aggregated"].values()) - n_removed
                fh.write(f"  Self-sufficient removed: {n_removed}  (filtered n={n_filtered})\n")
                fh.write(f"  Oracle  Pearson(ICG, Δ)  [filtered]: {filtered_corr.get('pearson')}\n")
                fh.write(f"  Oracle  Spearman(ICG, Δ) [filtered]: {filtered_corr.get('spearman')}\n")
                if filtered_corr_mv:
                    fh.write(f"  MajVote Pearson(ICG, Δ)  [filtered]: {filtered_corr_mv.get('pearson')}\n")
                    fh.write(f"  MajVote Spearman(ICG, Δ) [filtered]: {filtered_corr_mv.get('spearman')}\n")
                fh.write("\n")
            if "cross_setting_correlation" in all_output:
                cross_corr = all_output["cross_setting_correlation"]
                cross_corr_f = all_output.get("cross_setting_correlation_filtered", {})
                fh.write(f"=== Cross-setting correlation (pooled, ICG vs Δ) ===\n")
                fh.write(f"  Pearson:  {cross_corr['pearson']}\n")
                fh.write(f"  Spearman: {cross_corr['spearman']}\n")
                fh.write(f"  Pearson  [filtered]: {cross_corr_f.get('pearson')}\n")
                fh.write(f"  Spearman [filtered]: {cross_corr_f.get('spearman')}\n")
        print(f"Summary written to:       {summary_path}")

        # detail_<setting>.txt — one per setting
        for setting, res in all_output["settings"].items():
            label = setting.upper()
            detail_path = os.path.join(run_dir, f"detail_{setting}.txt")
            _write_detail_log(
                res["instance_results"],
                instances_by_id,
                label,
                detail_path,
            )
            print(f"Detail log written to:    {detail_path}")


if __name__ == "__main__":
    main()
