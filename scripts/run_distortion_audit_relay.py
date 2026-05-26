#!/usr/bin/env python3
"""
Relay distortion label breakdown — Silo-Bench (Qwen-235B).

For each relay-transmitted unit that aligns to a gold agent shard,
calls an LLM judge to classify: EXACT / PARAPHRASE / PARTIAL / DISTORTED / NO_MATCH.

Produces a comparison table alongside the SE distortion audit (Table 7),
showing that structured atomic relay preserves numerical content better
than free-form summaries.

Gold alignment strategy (Silo-Bench):
  Each agent's private shard is a gold critical unit.
  A transmitted relay unit "covers" it if any gold numeric value appears in the unit.
  Among covered pairs, the LLM judge classifies fidelity.

Usage:
    cd /path/to/repo
    python scripts/run_distortion_audit_relay.py [--max-workers N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from scripts.compute_audit_metrics import reconstruct_states_and_scores, get_transmitted_units
from src.eval.silo_bench_loader import load_silobench
from utility.apis.openrouter_api import batch_request
from utility.apis.base import APIRequest

JUDGE_MODEL = "qwen/qwen3-235b-a22b-07-25"
PROTOCOLS = ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]
SEED = 42
MAX_STATES = 3
LABELS = {"EXACT", "PARAPHRASE", "PARTIAL", "DISTORTED", "NO_MATCH"}

RUN_DIRS = {
    "n5":  os.path.join(_ROOT, "results", "run_qwen235b_n5"),
    "n10": os.path.join(_ROOT, "results", "run_qwen235b_n10"),
}

OUT_DIR = os.path.join(_ROOT, "results", "distortion_audit_relay")

_JUDGE_SYSTEM = (
    "You are a factual-accuracy judge for distributed multi-agent reasoning tasks.\n"
    "Given a GOLD FACT (key numerical values from an agent's private shard) and a "
    "TRANSMITTED UNIT (an atomic evidence unit extracted and sent by the agent), "
    "classify the relationship:\n\n"
    "  EXACT      — all key numerical values are stated correctly and explicitly\n"
    "  PARAPHRASE — all key values preserved; minor rewording or added context only\n"
    "  PARTIAL    — at least one key value is present but another is missing, vague, "
    "or expressed only as a range/approximation\n"
    "  DISTORTED  — at least one key numerical value is stated incorrectly or contradicted\n"
    "  NO_MATCH   — the unit does not reference the gold values at all\n\n"
    "Output exactly one label from the five above. No explanation."
)


def _numbers_in(text: str) -> set[str]:
    return set(re.findall(r"-?\d+(?:\.\d+)?", text))


def _coverage(gold_shard: str, unit: str) -> dict:
    """Does the unit contain any of the gold numeric values?"""
    gold_nums = _numbers_in(gold_shard)
    unit_nums = _numbers_in(unit)
    if not gold_nums:
        return {"covered": False, "coverage_score": 0.0, "gold_nums": [], "unit_nums": []}
    overlap = len(gold_nums & unit_nums)
    score = overlap / len(gold_nums)
    return {
        "covered": score > 0.0,
        "coverage_score": score,
        "gold_nums": sorted(gold_nums),
        "unit_nums": sorted(unit_nums),
    }


def get_gold_shards(inst: dict) -> dict[int, str]:
    """agent_id → shard text."""
    return {ac["agent_id"]: str(ac["input_shard"]) for ac in inst["agent_configs"]}


def run_distortion_for_tier(
    tier: str,
    run_dir: str,
    instances: list[dict],
    max_workers: int,
) -> list[dict]:
    """Run distortion audit for one Silo-Bench tier. Returns list of record dicts."""
    n_agents = 5 if tier == "n5" else 10
    print(f"\n--- Tier {tier} (n={n_agents}) ---")

    resp_path = os.path.join(run_dir, "api_responses.jsonl")
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]
    print(f"  {len(responses)} API responses")

    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
    inst_by_id = {inst["id"]: inst for inst in instances}

    # Build judge requests
    judge_requests: list[APIRequest] = []
    judge_index: list[dict] = []
    no_match_records: list[dict] = []

    for inst_id, inst in inst_by_id.items():
        if inst_id not in states_by_id:
            continue
        gold_shards = get_gold_shards(inst)

        for protocol in PROTOCOLS:
            transmitted = get_transmitted_units(
                inst_id, protocol, states_by_id, scores_by_id, n_agents=n_agents
            )

            # For each gold unit (agent shard), find best matching transmitted unit
            for agent_id, gold_text in gold_shards.items():
                gold_nums = _numbers_in(gold_text)
                if not gold_nums:
                    continue

                # Find best matching transmitted unit (by numeric overlap)
                best_unit = None
                best_score = 0.0
                for unit in transmitted:
                    cov = _coverage(gold_text, unit)
                    if cov["coverage_score"] > best_score:
                        best_score = cov["coverage_score"]
                        best_unit = unit

                base_record = {
                    "tier": tier,
                    "inst_id": inst_id,
                    "protocol": protocol,
                    "agent_id": agent_id,
                    "coverage_score": best_score,
                    "best_unit": best_unit,
                }

                if best_score == 0.0 or best_unit is None:
                    # Not covered — record NO_MATCH without LLM call
                    no_match_records.append({**base_record, "label": "NO_MATCH", "from_judge": False})
                    continue

                # Build judge prompt
                gold_repr = "Key values from shard: " + ", ".join(sorted(gold_nums)[:15])
                prompt = (
                    f"GOLD FACT:\n{gold_repr}\n\n"
                    f"TRANSMITTED UNIT:\n{best_unit[:600]}\n\n"
                    "Classification:"
                )
                judge_requests.append(APIRequest(
                    system_query=_JUDGE_SYSTEM,
                    user_query=prompt,
                    model=JUDGE_MODEL,
                    max_tokens=8,
                    temperature=0.0,
                    metadata={
                        "tier": tier,
                        "inst_id": inst_id,
                        "protocol": protocol,
                        "agent_id": agent_id,
                    },
                ))
                judge_index.append({**base_record, "label": None, "from_judge": True})

    print(f"  Submitting {len(judge_requests)} judge requests "
          f"(+{len(no_match_records)} NO_MATCH without judge)...")

    if judge_requests:
        responses_judge = batch_request(judge_requests, max_workers=max_workers,
                                        desc=f"relay_dist_{tier}")
        for resp, record in zip(responses_judge, judge_index):
            if resp.success:
                raw = resp.content.strip().upper()
                label = "NO_MATCH"
                for lbl in LABELS:
                    if lbl in raw:
                        label = lbl
                        break
                record["label"] = label
            else:
                record["label"] = "NO_MATCH"

    return no_match_records + judge_index


def aggregate_by_protocol(records: list[dict], protocol: str) -> dict:
    """Compute distortion statistics for one protocol."""
    recs = [r for r in records if r["protocol"] == protocol]
    n_total = len(recs)
    if n_total == 0:
        return {"n_total": 0}

    covered = [r for r in recs if r["label"] != "NO_MATCH"]
    n_covered = len(covered)

    label_counts: dict[str, int] = defaultdict(int)
    for r in recs:
        label_counts[r["label"]] += 1

    if n_covered == 0:
        return {
            "n_total": n_total,
            "n_covered": 0,
            "coverage_rate": 0.0,
            "distortion_strict": 0.0,
            "distortion_broad": 0.0,
            "exact_paraphrase_rate": 0.0,
            "label_counts": dict(label_counts),
        }

    strict_dist = sum(1 for r in covered if r["label"] == "DISTORTED")
    broad_dist = sum(1 for r in covered if r["label"] in {"DISTORTED", "PARTIAL"})
    exact_para = sum(1 for r in covered if r["label"] in {"EXACT", "PARAPHRASE"})

    return {
        "n_total": n_total,
        "n_covered": n_covered,
        "coverage_rate": n_covered / n_total,
        "distortion_strict": strict_dist / n_covered,
        "distortion_broad": broad_dist / n_covered,
        "exact_paraphrase_rate": exact_para / n_covered,
        "label_counts": dict(label_counts),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=64)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    # Load Silo-Bench instances
    instances_n5 = load_silobench(n_agents_filter=5)
    instances_n10 = load_silobench(n_agents_filter=10)
    print(f"Silo-Bench: n5={len(instances_n5)}, n10={len(instances_n10)}")

    all_records: list[dict] = []
    all_records.extend(run_distortion_for_tier("n5", RUN_DIRS["n5"], instances_n5, args.max_workers))
    all_records.extend(run_distortion_for_tier("n10", RUN_DIRS["n10"], instances_n10, args.max_workers))

    # ── Aggregate ────────────────────────────────────────────────────────────
    print("\n\n=== Relay Distortion Audit: Silo-Bench (Qwen-235B) ===")
    print(f"{'Protocol':<30} {'N':>5} {'Cov%':>6} {'Strict%':>8} {'Broad%':>8} "
          f"{'Exact/Para%':>12}  Label counts")
    print("-" * 95)

    results: dict[str, dict] = {}
    for protocol in PROTOCOLS:
        agg = aggregate_by_protocol(all_records, protocol)
        results[protocol] = agg
        label = protocol.replace("_relay", "").replace("_", " ").title() + " Relay"
        n = agg.get("n_total", 0)
        cov = agg.get("coverage_rate", 0.0)
        strict = agg.get("distortion_strict", 0.0)
        broad = agg.get("distortion_broad", 0.0)
        ep = agg.get("exact_paraphrase_rate", 0.0)
        lcounts = agg.get("label_counts", {})
        print(f"{label:<30} {n:>5} {cov*100:>5.1f}% {strict*100:>7.1f}% {broad*100:>7.1f}% "
              f"{ep*100:>11.1f}%  {lcounts}")

    # Also show SE (from existing results) for comparison
    se_path = os.path.join(_ROOT, "results", "distortion_audit_se", "distortion_results.json")
    if os.path.exists(se_path):
        se_data = json.load(open(se_path))
        se_all = se_data["summary_all"]
        print(f"\n{'Summary Exchange (existing):':<30} "
              f"{se_all['n_total']:>5} {se_all['coverage_rate']*100:>5.1f}% "
              f"{se_all['distortion_strict']*100:>7.1f}% {se_all['distortion_broad']*100:>7.1f}% "
              f"{se_all['exact_paraphrase_rate']*100:>11.1f}%  {se_all['label_counts']}")

    # ── Save ─────────────────────────────────────────────────────────────────
    out = {
        "judge_model": JUDGE_MODEL,
        "protocols": PROTOCOLS,
        "results_by_protocol": results,
        "records": all_records,
    }
    out_path = os.path.join(OUT_DIR, "distortion_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {out_path}")

    # Print paper-ready summary
    print("\n=== Summary for Paper ===")
    print("Protocol                        Coverage  Strict-Dist  Broad-Dist  Exact+Para")
    for protocol in PROTOCOLS:
        agg = results[protocol]
        label = protocol.replace("_relay", "").replace("_", " ").title() + " Relay"
        print(f"{label:<32} {agg.get('coverage_rate',0)*100:>7.1f}%  "
              f"{agg.get('distortion_strict',0)*100:>9.1f}%  "
              f"{agg.get('distortion_broad',0)*100:>9.1f}%  "
              f"{agg.get('exact_paraphrase_rate',0)*100:>9.1f}%")
    if os.path.exists(se_path):
        se = json.load(open(se_path))["summary_all"]
        print(f"{'Summary Exchange':<32} {se['coverage_rate']*100:>7.1f}%  "
              f"{se['distortion_strict']*100:>9.1f}%  "
              f"{se['distortion_broad']*100:>9.1f}%  "
              f"{se['exact_paraphrase_rate']*100:>9.1f}%")


if __name__ == "__main__":
    main()
