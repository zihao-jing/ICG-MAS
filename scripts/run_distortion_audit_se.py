#!/usr/bin/env python3
"""
Distortion audit for Summary Exchange on Silo-Bench.

Loads NL summary responses from run_qwen235b_n5 and run_qwen235b_n10,
aligns each agent summary to its gold shard, then calls an LLM judge
to classify the relationship as EXACT/PARAPHRASE/PARTIAL/DISTORTED/NO_MATCH.

Distortion rate = fraction of covered pairs classified DISTORTED or PARTIAL.
(PARTIAL = some key value lost or vague, so it represents degradation.)

Strict distortion = fraction classified DISTORTED only.

Usage:
    cd /path/to/repo
    python scripts/run_distortion_audit_se.py [--model MODEL] [--max-workers N]

Output:
    results/distortion_audit_se/distortion_results.json
    (Prints summary table to stdout)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# Load .env
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, _ROOT)

from src.eval.silo_bench_loader import load_silobench
from utility.apis.openrouter_api import batch_request
from utility.apis.base import APIRequest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DIRS = {
    "n5": os.path.join(_ROOT, "results", "run_qwen235b_n5"),
    "n10": os.path.join(_ROOT, "results", "run_qwen235b_n10"),
}

_JUDGE_SYSTEM = (
    "You are a factual-accuracy judge for distributed multi-agent reasoning tasks.\n"
    "Given a GOLD FACT (key numerical values from one agent's private shard) and a "
    "TRANSMITTED SUMMARY (what the agent wrote to share with others), classify the relationship:\n\n"
    "  EXACT      — all key numerical values are stated correctly and explicitly\n"
    "  PARAPHRASE — all key values preserved; minor rewording or added context only\n"
    "  PARTIAL    — at least one key value is present but another is missing, vague, "
    "or expressed only as a range/approximation (e.g., 'mid-October' vs 'Oct 14')\n"
    "  DISTORTED  — at least one key numerical value is stated incorrectly or contradicted\n"
    "  NO_MATCH   — the summary does not reference the gold values at all\n\n"
    "Output exactly one label from the five above. No explanation."
)

LABELS = {"EXACT", "PARAPHRASE", "PARTIAL", "DISTORTED", "NO_MATCH"}


def _numbers_in(text: str) -> list[str]:
    return re.findall(r"-?\d+(?:\.\d+)?", text)


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_summaries(run_dir: str) -> dict[str, dict[int, str]]:
    """summaries[inst_id][agent] = summary_text"""
    summaries: dict[str, dict[int, str]] = defaultdict(dict)
    with open(os.path.join(run_dir, "api_responses.jsonl")) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("phase") == "summary" and r.get("success"):
                summaries[r["instance_id"]][r["agent"]] = r["content"]
    return dict(summaries)


def load_gold(n_agents: int) -> dict[str, dict]:
    """instances_by_id for given n_agents"""
    instances = load_silobench(n_agents_filter=n_agents)
    return {inst["id"]: inst for inst in instances}


def get_gold_shards(inst: dict) -> dict[int, str]:
    """agent_id → shard text"""
    if "agent_configs" in inst:
        return {ac["agent_id"]: str(ac["input_shard"]) for ac in inst["agent_configs"]}
    return {}


# ---------------------------------------------------------------------------
# Alignment: does summary cover the gold shard's key numbers?
# ---------------------------------------------------------------------------

def summarize_coverage(gold_shard: str, summary: str) -> dict:
    gold_nums = set(_numbers_in(gold_shard))
    summ_nums = set(_numbers_in(summary))
    if not gold_nums:
        covered = False
        coverage_score = 0.0
    else:
        overlap = len(gold_nums & summ_nums)
        coverage_score = overlap / len(gold_nums)
        covered = coverage_score > 0.0
    return {
        "covered": covered,
        "coverage_score": coverage_score,
        "gold_nums": sorted(gold_nums),
        "summ_nums": sorted(summ_nums),
    }


# ---------------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------------

def build_judge_requests(
    summaries_n5: dict, summaries_n10: dict,
    gold_n5: dict, gold_n10: dict,
    model: str,
) -> tuple[list[APIRequest], list[dict]]:
    """Return (requests, metadata_index) pairs ready for batch_request."""
    requests: list[APIRequest] = []
    index: list[dict] = []

    for tag, summaries, gold_dict in [("n5", summaries_n5, gold_n5),
                                       ("n10", summaries_n10, gold_n10)]:
        for inst_id, agent_summaries in summaries.items():
            if inst_id not in gold_dict:
                continue
            gold_shards = get_gold_shards(gold_dict[inst_id])
            for agent_id, summary_text in agent_summaries.items():
                gold_shard = gold_shards.get(agent_id, "")
                if not gold_shard:
                    continue
                cov = summarize_coverage(gold_shard, summary_text)
                if not cov["covered"]:
                    # No numeric overlap — skip judge call, record as NO_MATCH
                    index.append({
                        "tag": tag,
                        "inst_id": inst_id,
                        "agent_id": agent_id,
                        "label": "NO_MATCH",
                        "coverage": cov,
                        "from_judge": False,
                    })
                    continue

                # Represent gold as its key numbers only (compact)
                gold_repr = "Key values from shard: " + ", ".join(cov["gold_nums"][:15])
                prompt = (
                    f"GOLD FACT:\n{gold_repr}\n\n"
                    f"TRANSMITTED SUMMARY:\n{summary_text[:600]}\n\n"
                    "Classification:"
                )
                requests.append(APIRequest(
                    system_query=_JUDGE_SYSTEM,
                    user_query=prompt,
                    model=model,
                    max_tokens=8,
                    temperature=0.0,
                    metadata={
                        "tag": tag,
                        "inst_id": inst_id,
                        "agent_id": agent_id,
                        "from_judge": True,
                        "coverage": cov,
                    },
                ))
                index.append({
                    "tag": tag,
                    "inst_id": inst_id,
                    "agent_id": agent_id,
                    "label": None,  # filled after batch call
                    "coverage": cov,
                    "from_judge": True,
                    "_request_idx": len(requests) - 1,
                })

    return requests, index


# ---------------------------------------------------------------------------
# Aggregate and report
# ---------------------------------------------------------------------------

def aggregate(records: list[dict]) -> dict:
    n = len(records)
    covered = [r for r in records if r["label"] != "NO_MATCH"]
    n_covered = len(covered)

    distorted_strict = sum(1 for r in covered if r["label"] == "DISTORTED")
    distorted_broad  = sum(1 for r in covered if r["label"] in {"DISTORTED", "PARTIAL"})
    exact_para       = sum(1 for r in covered if r["label"] in {"EXACT", "PARAPHRASE"})

    label_counts = defaultdict(int)
    for r in records:
        label_counts[r["label"]] += 1

    return {
        "n_total": n,
        "n_covered": n_covered,
        "coverage_rate": n_covered / n if n > 0 else 0.0,
        "distortion_strict": distorted_strict / n_covered if n_covered > 0 else 0.0,
        "distortion_broad":  distorted_broad  / n_covered if n_covered > 0 else 0.0,
        "exact_paraphrase_rate": exact_para  / n_covered if n_covered > 0 else 0.0,
        "label_counts": dict(label_counts),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen/qwen3-235b-a22b-2507")
    parser.add_argument("--max-workers", type=int, default=32)
    parser.add_argument("--out-dir", default=os.path.join(_ROOT, "results", "distortion_audit_se"))
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("Loading Summary Exchange summaries...")
    summaries_n5  = load_summaries(RUN_DIRS["n5"])
    summaries_n10 = load_summaries(RUN_DIRS["n10"])
    print(f"  n5: {len(summaries_n5)} instances, n10: {len(summaries_n10)} instances")

    print("Loading gold shards...")
    gold_n5  = load_gold(5)
    gold_n10 = load_gold(10)
    print(f"  n5 gold: {len(gold_n5)}, n10 gold: {len(gold_n10)}")

    print("Building judge requests...")
    requests, index = build_judge_requests(
        summaries_n5, summaries_n10, gold_n5, gold_n10, args.model
    )
    print(f"  {len(requests)} judge requests (+ {sum(1 for r in index if not r['from_judge'])} NO_MATCH skipped)")

    if requests:
        print(f"Running LLM distortion judge ({args.model})...")
        responses = batch_request(requests, max_workers=args.max_workers,
                                  desc="distortion judge")
        # Fill in labels from judge responses
        judge_responses_list = list(responses)
        req_idx = 0
        for record in index:
            if record["from_judge"] and record["label"] is None:
                resp = judge_responses_list[req_idx]
                req_idx += 1
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

    # Remove internal bookkeeping key
    for r in index:
        r.pop("_request_idx", None)

    # Separate results by split
    records_n5  = [r for r in index if r["tag"] == "n5"]
    records_n10 = [r for r in index if r["tag"] == "n10"]
    agg_n5  = aggregate(records_n5)
    agg_n10 = aggregate(records_n10)
    agg_all = aggregate(index)

    print("\n=== Distortion Audit: Summary Exchange (Silo-Bench, Qwen-235B) ===")
    print(f"{'Split':<8} {'N':>5} {'Cov':>6} {'Strict%':>8} {'Broad%':>8} {'Exact/Para%':>12} Label counts")
    for split, agg, recs in [("n5", agg_n5, records_n5), ("n10", agg_n10, records_n10), ("ALL", agg_all, index)]:
        print(
            f"{split:<8} {agg['n_total']:>5} {agg['coverage_rate']:>6.3f} "
            f"{agg['distortion_strict']*100:>7.1f}% {agg['distortion_broad']*100:>7.1f}% "
            f"{agg['exact_paraphrase_rate']*100:>11.1f}%  {agg['label_counts']}"
        )

    print("\n=== Summary for Paper ===")
    print(f"Combined (n5+n10):")
    print(f"  Pairs with numeric coverage:  {agg_all['n_covered']} / {agg_all['n_total']}")
    print(f"  Coverage rate:                {agg_all['coverage_rate']:.3f}")
    print(f"  Strict Distortion rate:       {agg_all['distortion_strict']:.3f} "
          f"({agg_all['distortion_strict']*100:.1f}% of covered pairs)")
    print(f"  Broad Distortion rate (DIST+PARTIAL): {agg_all['distortion_broad']:.3f} "
          f"({agg_all['distortion_broad']*100:.1f}%)")
    print(f"  Exact/Paraphrase rate:        {agg_all['exact_paraphrase_rate']:.3f} "
          f"({agg_all['exact_paraphrase_rate']*100:.1f}%)")
    print(f"  Label distribution:           {agg_all['label_counts']}")

    # Save
    out = {
        "model": args.model,
        "summary_n5": agg_n5,
        "summary_n10": agg_n10,
        "summary_all": agg_all,
        "records": index,
    }
    out_path = os.path.join(args.out_dir, "distortion_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
