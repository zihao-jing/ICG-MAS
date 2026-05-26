#!/usr/bin/env python3
"""
Experiment 2: Extraction Quality Analysis.

Computes Critical Recall at the EXTRACTION stage (all extracted units before
top-k selection) vs. the SELECTION stage (after top-k), to show where in the
relay pipeline evidence is lost.

Reads api_responses.jsonl from Qwen-235B n5 and n10 Silo-Bench runs.
Gold critical units are determined from agent input_shard data.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.compute_audit_metrics import (
    reconstruct_states_and_scores,
    get_gold_units,
    align_gold_to_transmitted,
    aggregate_audit,
    MAX_STATES,
    SEED,
    RHO,
)
from src.protocols.relay import _topk_select, _redundancy_select
from src.eval.silo_bench_loader import load_silobench

import random

RUN_DIRS = {
    "n5": os.path.join(os.path.dirname(__file__), "..", "results", "run_qwen235b_n5"),
    "n10": os.path.join(os.path.dirname(__file__), "..", "results", "run_qwen235b_n10"),
}


def load_responses(run_dir: str) -> list[dict]:
    with open(os.path.join(run_dir, "api_responses.jsonl")) as f:
        return [json.loads(l) for l in f if l.strip()]


def compute_extraction_crit_recall(
    inst_id: str,
    all_states: dict,
    inst: dict,
) -> float:
    """CritRec using ALL extracted units (before selection)."""
    inst_states = all_states.get(inst_id, {})
    # Flatten all extracted units across all agents
    all_units = [u for a_units in inst_states.values() for u in a_units]

    gold_units = get_gold_units(inst)
    if not gold_units:
        return 1.0

    alignments = align_gold_to_transmitted(gold_units, all_units)
    n_covered = sum(1 for a in alignments if a["covered"])
    return n_covered / len(gold_units)


def compute_selection_crit_recall(
    inst_id: str,
    protocol: str,
    all_states: dict,
    all_scores: dict,
    inst: dict,
    n_agents: int,
) -> float:
    """CritRec using TOP-K selected units (after selection)."""
    inst_states = [all_states.get(inst_id, {}).get(a, []) for a in range(n_agents)]
    inst_scores = [all_scores.get(inst_id, {}).get(a, []) for a in range(n_agents)]

    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        selected = [
            rng.sample(s, min(MAX_STATES, len(s))) if s else []
            for s in inst_states
        ]
    elif protocol == "score_ranked_relay":
        selected = [
            _topk_select(s, sc, MAX_STATES)
            for s, sc in zip(inst_states, inst_scores)
        ]
    elif protocol == "redundancy_aware_relay":
        selected = [
            _redundancy_select(s, sc, MAX_STATES, RHO)
            for s, sc in zip(inst_states, inst_scores)
        ]
    else:
        return float("nan")

    transmitted = [u for agent_units in selected for u in agent_units]
    gold_units = get_gold_units(inst)
    if not gold_units:
        return 1.0

    alignments = align_gold_to_transmitted(gold_units, transmitted)
    n_covered = sum(1 for a in alignments if a["covered"])
    return n_covered / len(gold_units)


def main():
    all_results = []

    for tier, run_dir in RUN_DIRS.items():
        n_agents = 5 if tier == "n5" else 10
        print(f"\n=== Processing {tier} (n_agents={n_agents}) ===")

        responses = load_responses(run_dir)
        print(f"  {len(responses)} API responses")

        states, scores = reconstruct_states_and_scores(responses)
        print(f"  {len(states)} instances with extracted units")

        instances = load_silobench(n_agents_filter=n_agents)
        instances_by_id = {inst["id"]: inst for inst in instances}
        print(f"  {len(instances)} instances loaded")

        for inst in instances:
            inst_id = inst["id"]
            if inst_id not in states:
                print(f"  WARNING: no extraction data for {inst_id}")
                continue

            # Extraction-stage CritRec (all extracted, before selection)
            ext_cr = compute_extraction_crit_recall(inst_id, states, inst)

            # Selection-stage CritRec for each relay protocol
            rec = {"inst_id": inst_id, "tier": tier, "n_agents": n_agents}
            rec["extraction_crit_recall"] = ext_cr

            for proto in ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]:
                sel_cr = compute_selection_crit_recall(
                    inst_id, proto, states, scores, inst, n_agents
                )
                rec[f"{proto}_crit_recall"] = sel_cr

            # Also count extracted units
            inst_states = states.get(inst_id, {})
            rec["n_extracted_total"] = sum(len(v) for v in inst_states.values())
            rec["n_gold"] = len(get_gold_units(inst))

            all_results.append(rec)

    # ── Aggregate ─────────────────────────────────────────────────────────────
    print("\n\n=== Extraction Quality Analysis ===\n")

    def mean(vals):
        vals = [v for v in vals if v == v]  # filter NaN
        return sum(vals) / len(vals) if vals else float("nan")

    n = len(all_results)
    print(f"Total instances: {n}")
    print()

    ext_cr_all = mean([r["extraction_crit_recall"] for r in all_results])
    print(f"Stage                     | Mean CritRec")
    print("-" * 50)
    print(f"{'After Extraction':<26}| {ext_cr_all:.3f}  (all extracted units, before selection)")

    for proto in ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]:
        key = f"{proto}_crit_recall"
        sel_cr = mean([r[key] for r in all_results])
        label = {
            "random_relay": "After Selection (Random)",
            "score_ranked_relay": "After Selection (Score-Ranked)",
            "redundancy_aware_relay": "After Selection (Redund.-Aware)",
        }[proto]
        print(f"{'  '+label:<26}| {sel_cr:.3f}")

    print()
    # Breakdown by n5 / n10
    for tier in ["n5", "n10"]:
        subset = [r for r in all_results if r["tier"] == tier]
        if not subset:
            continue
        n_agents_str = "n=5" if tier == "n5" else "n=10"
        print(f"  {n_agents_str}: Extraction CritRec = {mean([r['extraction_crit_recall'] for r in subset]):.3f}  "
              f"Score-Ranked Selection CritRec = {mean([r['score_ranked_relay_crit_recall'] for r in subset]):.3f}  "
              f"(n={len(subset)})")

    # ── Save ──────────────────────────────────────────────────────────────────
    out_path = os.path.join(
        os.path.dirname(__file__), "..", "results", "exp2_extraction_quality.json"
    )
    summary = {
        "n_instances": n,
        "extraction_crit_recall": ext_cr_all,
        "random_relay_selection_crit_recall": mean([r["random_relay_crit_recall"] for r in all_results]),
        "score_ranked_selection_crit_recall": mean([r["score_ranked_relay_crit_recall"] for r in all_results]),
        "redundancy_aware_selection_crit_recall": mean([r["redundancy_aware_relay_crit_recall"] for r in all_results]),
        "per_instance": all_results,
    }
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to: {out_path}")

    return summary


if __name__ == "__main__":
    main()
