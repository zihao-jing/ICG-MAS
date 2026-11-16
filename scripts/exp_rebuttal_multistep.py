#!/usr/bin/env python3
"""
Exp 5 — Fixed-Budget Multi-Round Relay (1 → 2 → 3 rounds).

Compares single-round relay vs. 2-round and 3-round relay under the SAME
total evidence budget (k=3 units per agent).  Directly addresses the
single-round limitation concern from all three reviewers.

Round allocations (budget=3):
  1-round: [3]        — top-3 selected at once, no board context
  2-round: [1, 2]     — top-1, then board-aware top-2 from remainder
  3-round: [1, 1, 1]  — top-1 per round, board-aware re-scoring each time

FES row is included as the information-theoretic ceiling.

Usage:
    python scripts/exp_rebuttal_multistep.py --dataset silobench
    python scripts/exp_rebuttal_multistep.py --dataset musique --limit 100
    python scripts/exp_rebuttal_multistep.py --dataset silobench --dataset musique
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.eval.run_experiment import _get_batch_fn, _PROVIDER_DEFAULT_MODELS
from src.eval.data_loader import load_musique, load_musique_sample
from src.eval.silo_bench_loader import (
    load_silobench, shards_from_silobench, silobench_exact_match,
)
from src.eval.evaluate import answer_f1
from src.eval.metrics import build_results_table
from src.protocols.base import shard_instance, ProtocolResult
from src.protocols.relay import (
    extract_states_batch,
    score_states_batch,
    run_score_ranked_relay_batch,
    run_multistep_relay_batch,
)
from src.protocols.full_sharing import run_full_sharing_batch
from src.eval.data_loader import shards_from_musique
from scripts.exp_rebuttal_threshold import (
    get_gold_units_sb,
    compute_crit_recall,
    best_similarity,
)

TOTAL_BUDGET = 3   # units per agent


def _eval_fn_for(dataset: str):
    return silobench_exact_match if dataset == "silobench" else answer_f1


def _pack_result(result: ProtocolResult, instance: dict, eval_fn) -> dict:
    f1 = eval_fn(result.pred, instance)
    return {
        "id": result.instance_id,
        "pred": result.pred,
        "gold": str(instance.get("answer", "")),
        "f1": f1,
        "correct": f1 >= 1.0,
        "comm_tokens": result.comm_tokens,
        "total_llm_tokens": result.total_llm_tokens,
    }


def run_one_dataset(
    dataset: str,
    args: argparse.Namespace,
    batch_fn,
) -> dict:
    """Run all relay conditions on one dataset. Returns summary dict."""

    # --- Load data ---
    if dataset == "silobench":
        instances = load_silobench(n_agents_filter=args.n_agents)
        shards_list = [shards_from_silobench(inst) for inst in instances]
        eval_fn = silobench_exact_match
    else:
        if args.limit > 0:
            instances = load_musique_sample(n=args.limit, seed=args.seed)
        else:
            instances = load_musique()
        shards_list = [shards_from_musique(inst) for inst in instances]
        eval_fn = answer_f1

    if args.limit > 0:
        instances = instances[:args.limit]
        shards_list = shards_list[:args.limit]

    print(f"\n{'='*60}")
    print(f"Dataset: {dataset}  |  N={len(instances)}  |  Model: {args.model}")
    print('='*60)

    common_kw = dict(
        batch_fn=batch_fn, model=args.model,
        max_tokens=args.max_tokens, max_workers=args.max_workers,
    )

    # --- Precompute extraction and initial scores (shared across all conditions) ---
    print("[Precompute] Extracting evidence units ...")
    all_states, extract_tokens = extract_states_batch(
        instances, shards_list,
        max_states_per_agent=TOTAL_BUDGET,
        **common_kw,
    )
    print("[Precompute] Scoring evidence units ...")
    all_scores, score_tokens = score_states_batch(
        instances, all_states, **{k: v for k, v in common_kw.items()
                                   if k != "max_tokens"},
    )

    # --- Condition 1: 1-round relay (k=3, baseline) ---
    print("[Protocol] 1-round relay (k=3) ...")
    results_1r = run_score_ranked_relay_batch(
        instances, shards_list,
        max_states_per_agent=TOTAL_BUDGET,
        precomputed_states=all_states,
        precomputed_scores=all_scores,
        precomputed_extract_tokens=extract_tokens,
        precomputed_score_tokens=score_tokens,
        **common_kw,
    )

    # --- Condition 2: 2-round relay (k=1+2) ---
    print("[Protocol] 2-round relay (k=1+2, board-aware) ...")
    results_2r = run_multistep_relay_batch(
        instances, shards_list,
        total_budget_per_agent=TOTAL_BUDGET,
        n_rounds=2,
        precomputed_states=all_states,
        precomputed_scores=all_scores,
        precomputed_extract_tokens=extract_tokens,
        precomputed_score_tokens=score_tokens,
        **common_kw,
    )

    # --- Condition 3: 3-round relay (k=1+1+1) ---
    print("[Protocol] 3-round relay (k=1+1+1, board-aware) ...")
    results_3r = run_multistep_relay_batch(
        instances, shards_list,
        total_budget_per_agent=TOTAL_BUDGET,
        n_rounds=3,
        precomputed_states=all_states,
        precomputed_scores=all_scores,
        precomputed_extract_tokens=extract_tokens,
        precomputed_score_tokens=score_tokens,
        **common_kw,
    )

    # --- Full Evidence Sharing (information ceiling) ---
    print("[Protocol] Full Evidence Sharing (ceiling) ...")
    results_fes = run_full_sharing_batch(
        instances, batch_fn, args.model, args.max_tokens,
        max_workers=args.max_workers,
    )

    # --- Aggregate results ---
    def _summarize(results: list[ProtocolResult], label: str) -> dict:
        recs = [_pack_result(r, inst, eval_fn)
                for r, inst in zip(results, instances)]
        n = len(recs)
        acc = sum(r["correct"] for r in recs) / n if n else 0.0
        mean_comm = sum(r["comm_tokens"] for r in recs) / n if n else 0.0
        mean_total = sum(r["total_llm_tokens"] for r in recs) / n if n else 0.0

        # CritRec and AggFail (lexical, τ=0 default from compute_audit_metrics)
        gold_fn = get_gold_units_sb if dataset == "silobench" else (
            lambda inst: [p["paragraph_text"] for p in inst["paragraphs"]
                          if p["is_supporting"]]
        )
        crit_recalls, agg_fails = [], []
        for r, inst in zip(results, instances):
            gold = gold_fn(inst)
            transmitted = r.transmitted_states
            cr = compute_crit_recall(gold, transmitted, tau=0.0)
            correct = eval_fn(r.pred, inst) >= 1.0
            crit_recalls.append(cr)
            agg_fails.append((not correct) and (cr >= 1.0))

        return {
            "label": label,
            "n": n,
            "acc": round(acc * 100, 1),
            "mean_comm_tokens": round(mean_comm, 0),
            "mean_total_tokens": round(mean_total, 0),
            "crit_recall": round(sum(crit_recalls) / n, 3) if n else 0.0,
            "agg_fail_pct": round(100 * sum(agg_fails) / n, 1) if n else 0.0,
        }

    summaries = [
        _summarize(results_1r, "1-round relay (k=3)"),
        _summarize(results_2r, "2-round relay (k=1+2)"),
        _summarize(results_3r, "3-round relay (k=1+1+1)"),
        _summarize(results_fes, "Full Evidence Sharing (ceiling)"),
    ]

    return {"dataset": dataset, "summaries": summaries}


def print_comparison_table(all_results: list[dict]) -> None:
    print("\n\n=== Table R-ceil: Fixed-Budget Multi-Round Relay ===\n")
    for dataset_res in all_results:
        dataset = dataset_res["dataset"]
        summaries = dataset_res["summaries"]
        print(f"\n{'─'*80}")
        print(f"  {dataset.upper()}")
        print(f"{'─'*80}")
        header = (f"  {'Protocol':<30}  {'Budget':>6}  {'Acc%':>6}  "
                  f"{'CritRec':>8}  {'AggFail%':>9}  {'CommTok':>8}")
        print(header)
        print("  " + "-" * (len(header) - 2))
        budget_map = {
            "1-round relay (k=3)":         "3/agent",
            "2-round relay (k=1+2)":        "3/agent",
            "3-round relay (k=1+1+1)":      "3/agent",
            "Full Evidence Sharing (ceiling)": "full",
        }
        for s in summaries:
            budget = budget_map.get(s["label"], "?")
            print(
                f"  {s['label']:<30}  {budget:>6}  {s['acc']:>6.1f}  "
                f"{s['crit_recall']:>8.3f}  {s['agg_fail_pct']:>8.1f}%  "
                f"{s['mean_comm_tokens']:>8.0f}"
            )

    print("\n\n### Markdown (for rebuttal)\n")
    for dataset_res in all_results:
        dataset = dataset_res["dataset"]
        summaries = dataset_res["summaries"]
        print(f"\n**{dataset.upper()}**\n")
        print("| Protocol | Budget | Acc% | CritRec | AggFail% |")
        print("|---|---|---|---|---|")
        for s in summaries:
            budget = "3/agent" if "round" in s["label"] else "full"
            print(f"| {s['label']} | {budget} | {s['acc']} | {s['crit_recall']:.3f} | {s['agg_fail_pct']:.1f}% |")


def main():
    parser = argparse.ArgumentParser(
        description="Fixed-budget multi-round relay experiment (Exp 5)."
    )
    parser.add_argument("--dataset", nargs="+", default=["silobench", "musique"],
                        choices=["silobench", "musique"],
                        help="Datasets to run (default: both)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default="openrouter",
                        choices=["openrouter", "claude", "openai"])
    parser.add_argument("--n-agents", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0,
                        help="Cap instances (0 = no limit; use 52 for SB, 100 for MQ)")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-workers", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODELS[args.provider]

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    batch_fn = _get_batch_fn(args.provider)

    all_results = []
    for dataset in args.dataset:
        res = run_one_dataset(dataset, args, batch_fn)
        all_results.append(res)

    print_comparison_table(all_results)

    out_path = args.output
    if out_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(repo_root, "rebuttal", "results",
                                f"exp5_multistep_{ts}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
