#!/usr/bin/env python3
"""
Exp 1 — ROUGE/Coverage Threshold Sensitivity (no new API calls).

Recomputes CritRec for relay protocols at multiple coverage thresholds
using cached api_responses.jsonl from existing runs.

Usage:
    python scripts/exp_rebuttal_threshold.py
    python scripts/exp_rebuttal_threshold.py --sb-run results/run_qwen235b_n5 \
                                               --mq-run results/run_qwen235b_musique
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.protocols.relay import _topk_select, _parse_units
from src.protocols.base import parse_score_json

RELAY_PROTOCOLS = ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]
MAX_STATES = 3
SEED = 42
RHO = 0.5
THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.5]


# ---------------------------------------------------------------------------
# Helpers (copied & parameterized from compute_audit_metrics.py)
# ---------------------------------------------------------------------------

def _numbers_in_text(text: str) -> set[str]:
    return set(re.findall(r"-?\d+(?:\.\d+)?", text))


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(a.lower().split()), set(b.lower().split())
    if not ta and not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def reconstruct_states_and_scores(responses: list[dict]):
    states: dict[str, dict[int, list[str]]] = defaultdict(dict)
    for r in responses:
        if r["phase"] == "extraction" and r["success"]:
            states[r["instance_id"]][r["agent"]] = _parse_units(r["content"], MAX_STATES)

    scores_accum: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in responses:
        if r["phase"] == "scoring" and r["success"]:
            sc = parse_score_json(r["content"])
            if not sc:
                sc = {"relevance": 0.5, "uniqueness": 0.5, "local_importance": 0.5, "overall": 0.5}
            scores_accum[r["instance_id"]][r["agent"]].append(sc)

    return dict(states), dict(scores_accum)


def get_transmitted_units(inst_id, protocol, states, scores, n_agents=5) -> list[str]:
    inst_states = [states.get(inst_id, {}).get(a, []) for a in range(n_agents)]
    inst_scores = [scores.get(inst_id, {}).get(a, []) for a in range(n_agents)]

    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        selected = [
            rng.sample(s, min(MAX_STATES, len(s))) if s else []
            for s in inst_states
        ]
    elif protocol in ("score_ranked_relay", "redundancy_aware_relay"):
        selected = []
        for s, sc in zip(inst_states, inst_scores):
            if s and len(sc) >= len(s):
                selected.append(_topk_select(s, sc, MAX_STATES))
            elif s:
                rng = random.Random(f"{SEED}:{inst_id}:fallback")
                selected.append(rng.sample(s, min(MAX_STATES, len(s))))
            else:
                selected.append([])
    else:
        return []

    return [u for agent_units in selected for u in agent_units]


def get_gold_units_sb(inst: dict) -> list[str]:
    """Silo-Bench: gold = full shard text for each agent."""
    if "agent_configs" in inst:
        return [str(ac["input_shard"]) for ac in inst["agent_configs"]]
    return []


def get_gold_units_mq(inst: dict) -> list[str]:
    """MuSiQue: gold = supporting paragraph texts."""
    return [p["paragraph_text"] for p in inst["paragraphs"] if p["is_supporting"]]


def best_similarity(gold_text: str, transmitted: list[str]) -> float:
    """Max similarity between gold_text and any transmitted unit."""
    if not transmitted:
        return 0.0
    gold_nums = _numbers_in_text(gold_text)
    best = 0.0
    for unit in transmitted:
        unit_nums = _numbers_in_text(unit)
        if gold_nums and unit_nums:
            score = len(gold_nums & unit_nums) / len(gold_nums)
        else:
            score = 0.0
        j = _jaccard(gold_text, unit)
        score = max(score, j)
        best = max(best, score)
    return best


def compute_crit_recall(gold_units: list[str], transmitted: list[str], tau: float) -> float:
    if not gold_units:
        return 1.0
    covered = sum(1 for g in gold_units if best_similarity(g, transmitted) > tau)
    return covered / len(gold_units)


def compute_agg_fail(crit_recall: float, correct: bool) -> bool:
    return (not correct) and (crit_recall >= 1.0)


# ---------------------------------------------------------------------------
# Per-run analysis
# ---------------------------------------------------------------------------

def analyze_run(run_dir: str, is_musique: bool, thresholds: list[float]) -> dict:
    """
    Returns: {protocol: {tau: {crit_recall, agg_fail_pct, n}}}
    """
    print(f"\nLoading run: {run_dir}")
    with open(os.path.join(run_dir, "results.json")) as f:
        run_results = json.load(f)
    responses = []
    with open(os.path.join(run_dir, "api_responses.jsonl")) as f:
        for line in f:
            line = line.strip()
            if line:
                responses.append(json.loads(line))
    print(f"  {len(responses)} API responses")

    states, scores = reconstruct_states_and_scores(responses)

    if is_musique:
        from src.eval.data_loader import load_musique
        run_ids = {r["id"] for r in run_results["instance_results"].get(
            "random_relay", run_results["instance_results"].get("single_local", [])
        )}
        all_mq = load_musique()
        instances = [inst for inst in all_mq if inst["id"] in run_ids]
        get_gold = get_gold_units_mq
        n_agents = 5  # shards_from_musique gives 1 para per agent; relay uses n_agents from run
    else:
        from src.eval.silo_bench_loader import load_silobench
        n_agents = run_results["args"].get("n_agents") or 5
        instances = load_silobench(n_agents_filter=n_agents)
        get_gold = get_gold_units_sb

    instances_by_id = {inst["id"]: inst for inst in instances}
    print(f"  {len(instances)} instances matched")

    # Determine n_agents per instance for MuSiQue (varies by hop count)
    def _n_agents_for(inst_id):
        if not is_musique:
            return n_agents
        # For MuSiQue, n_agents = number of supporting paragraphs (shards_from_musique)
        inst = instances_by_id.get(inst_id)
        if inst is None:
            return n_agents
        return sum(1 for p in inst["paragraphs"] if p["is_supporting"])

    results: dict[str, dict] = {p: defaultdict(list) for p in RELAY_PROTOCOLS}

    for protocol in RELAY_PROTOCOLS:
        proto_results = {r["id"]: r for r in run_results["instance_results"][protocol]}
        for inst in instances:
            inst_id = inst["id"]
            if inst_id not in states:
                continue
            na = _n_agents_for(inst_id)
            transmitted = get_transmitted_units(inst_id, protocol, states, scores, n_agents=na)
            gold_units = get_gold(inst)
            correctness = proto_results.get(inst_id, {}).get("f1", 0.0)
            correct = correctness >= 1.0

            for tau in thresholds:
                cr = compute_crit_recall(gold_units, transmitted, tau)
                af = compute_agg_fail(cr, correct)
                results[protocol][tau].append({"crit_recall": cr, "agg_fail": af})

    # Aggregate
    out: dict[str, dict] = {}
    for protocol in RELAY_PROTOCOLS:
        out[protocol] = {}
        for tau in thresholds:
            recs = results[protocol][tau]
            n = len(recs)
            out[protocol][tau] = {
                "n": n,
                "crit_recall": sum(r["crit_recall"] for r in recs) / n if n else 0.0,
                "agg_fail_pct": 100 * sum(r["agg_fail"] for r in recs) / n if n else 0.0,
            }
    return out


# ---------------------------------------------------------------------------
# Table printing
# ---------------------------------------------------------------------------

_LABELS = {
    "random_relay": "Random Relay",
    "score_ranked_relay": "Score-Ranked Relay",
    "redundancy_aware_relay": "Redundancy-Aware Relay",
}


def print_threshold_table(sb_results: dict, mq_results: dict, thresholds: list[float]) -> None:
    tau_headers = "  ".join(f"τ={t:.1f}" for t in thresholds)
    header = f"\n{'Protocol':<26}  {tau_headers}"
    sep = "-" * len(header)

    for dataset_label, results in [("Silo-Bench — CritRec", sb_results),
                                    ("MuSiQue  — CritRec", mq_results)]:
        print(f"\n{dataset_label}")
        print(sep)
        for proto in RELAY_PROTOCOLS:
            label = _LABELS.get(proto, proto)
            vals = "  ".join(
                f"{results[proto][t]['crit_recall']:.3f}  " for t in thresholds
            )
            print(f"  {label:<26}  {vals}")

    for dataset_label, results in [("Silo-Bench — AggFail%", sb_results),
                                    ("MuSiQue  — AggFail%", mq_results)]:
        print(f"\n{dataset_label}")
        print(sep)
        for proto in RELAY_PROTOCOLS:
            label = _LABELS.get(proto, proto)
            vals = "  ".join(
                f"{results[proto][t]['agg_fail_pct']:5.1f}%  " for t in thresholds
            )
            print(f"  {label:<26}  {vals}")


def print_markdown_table(sb_results: dict, mq_results: dict, thresholds: list[float]) -> None:
    print("\n### Table R-thresh: CritRec sensitivity across coverage thresholds\n")
    tau_cols = " | ".join(f"τ={t:.1f}" for t in thresholds)
    print(f"| Protocol | Dataset | {tau_cols} |")
    print(f"|{'-'*26}|{'-'*9}|" + "|".join("-"*7 for _ in thresholds) + "|")
    for proto in RELAY_PROTOCOLS:
        label = _LABELS.get(proto, proto)
        for dset_key, results in [("SB", sb_results), ("MQ", mq_results)]:
            vals = " | ".join(f"{results[proto][t]['crit_recall']:.3f}" for t in thresholds)
            print(f"| {label:<24} | {dset_key:<7} | {vals} |")

    print()
    print("Coverage and aggregation-failure rates depend on the matching threshold; "
          "lexical overlap does not establish semantic sufficiency.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Threshold sensitivity for CritRec metric.")
    parser.add_argument("--sb-run", default="results/run_qwen235b_n5",
                        help="Path to Silo-Bench run directory")
    parser.add_argument("--mq-run", default="results/run_qwen235b_musique",
                        help="Path to MuSiQue run directory")
    parser.add_argument("--output", default="rebuttal/results/exp1_threshold.json",
                        help="Output JSON path")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sb_run = os.path.join(repo_root, args.sb_run)
    mq_run = os.path.join(repo_root, args.mq_run)

    sb_results = analyze_run(sb_run, is_musique=False, thresholds=THRESHOLDS)
    mq_results = analyze_run(mq_run, is_musique=True, thresholds=THRESHOLDS)

    print_threshold_table(sb_results, mq_results, THRESHOLDS)
    print_markdown_table(sb_results, mq_results, THRESHOLDS)

    # Save
    out_path = os.path.join(repo_root, args.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"thresholds": THRESHOLDS,
                   "silo_bench": {p: {str(t): v for t, v in tv.items()} for p, tv in sb_results.items()},
                   "musique": {p: {str(t): v for t, v in tv.items()} for p, tv in mq_results.items()}},
                  f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
