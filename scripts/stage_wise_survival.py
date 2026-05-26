#!/usr/bin/env python3
"""
Stage-Wise Evidence Survival Analysis (Priority 2).

Tracks gold critical evidence through three pipeline stages for each model:
  Stage 0 (Raw shard)       : CritRec = 1.000 by definition
  Stage 1 (After extraction): CritRec across ALL extracted units before top-k selection
  Stage 2 (After transmission): CritRec of selected/transmitted units (loaded from audit_metrics.json)
  Stage 3 (AggFail given CritRec=1): aggregation failure rate

Works entirely from saved api_responses.jsonl and audit_metrics.json — no new API calls.
Outputs a multi-model stage-wise table for Silo-Bench (n5+n10 combined) and MuSiQue.

Usage:
    cd /path/to/repo
    python scripts/stage_wise_survival.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.compute_audit_metrics import (
    reconstruct_states_and_scores,
    get_gold_units,
    align_gold_to_transmitted,
    MAX_STATES,
    SEED,
)
from src.eval.silo_bench_loader import load_silobench
from src.eval.data_loader import load_musique

BASE = os.path.join(os.path.dirname(__file__), "..", "results")

# ---------------------------------------------------------------------------
# Model configuration: (label, n5_dir, n10_dir, mq_dir)
# ---------------------------------------------------------------------------
SILOBENCH_MODELS = {
    "Qwen-235B": (
        os.path.join(BASE, "run_qwen235b_n5"),
        os.path.join(BASE, "run_qwen235b_n10"),
    ),
    "Mistral-S": (
        os.path.join(BASE, "run_mistrals"),
        os.path.join(BASE, "run_mistrals_n10"),
    ),
    "Qwen-80B-T": (
        os.path.join(BASE, "run_qwen80bt"),
        os.path.join(BASE, "run_qwen80bt_n10"),
    ),
    "Qwen-3.6-Flash": (
        os.path.join(BASE, "run_20260523_214416"),
        os.path.join(BASE, "run_silobench_n10"),
    ),
}

MUSIQUE_MODELS = {
    "Qwen-235B": os.path.join(BASE, "run_qwen235b_musique"),
    "Mistral-S": os.path.join(BASE, "run_musique_mistrals"),
    "Qwen-80B-T": os.path.join(BASE, "run_musique_qwen80bt"),
    "Qwen-3.6-Flash": os.path.join(BASE, "run_musique_100"),
}

RELAY_PROTOCOLS = ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]


# ---------------------------------------------------------------------------
# Extraction-stage CritRec (before top-k selection)
# ---------------------------------------------------------------------------

def load_api_responses(run_dir: str) -> list[dict]:
    path = os.path.join(run_dir, "api_responses.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def compute_extraction_stage_cr(
    run_dir: str,
    instances: list[dict],
    n_agents: int,
) -> float | None:
    """Return mean CritRec across all instances using all extracted units (before selection)."""
    responses = load_api_responses(run_dir)
    if not responses:
        return None

    states, _ = reconstruct_states_and_scores(responses)
    if not states:
        return None

    crit_recalls = []
    for inst in instances:
        inst_id = inst["id"]
        if inst_id not in states:
            continue

        inst_states = states[inst_id]
        all_units = [u for a_units in inst_states.values() for u in a_units]
        gold_units = get_gold_units(inst)
        if not gold_units:
            continue

        alignments = align_gold_to_transmitted(gold_units, all_units)
        n_covered = sum(1 for a in alignments if a["covered"])
        crit_recalls.append(n_covered / len(gold_units))

    if not crit_recalls:
        return None
    return sum(crit_recalls) / len(crit_recalls)


# ---------------------------------------------------------------------------
# Load transmission-stage CritRec and AggFail from audit_metrics.json
# ---------------------------------------------------------------------------

def load_audit_summary(run_dir: str, protocol: str) -> dict:
    path = os.path.join(run_dir, "audit_metrics.json")
    if not os.path.exists(path):
        return {}
    try:
        d = json.load(open(path))
        return d.get("audit_summaries", {}).get(protocol, {})
    except Exception:
        return {}


def merge_audit(s1: dict, n1: int, s2: dict, n2: int) -> dict:
    """Weighted average of two audit summary dicts."""
    if not s1 and not s2:
        return {}
    if not s1:
        return dict(s2)
    if not s2:
        return dict(s1)
    n = n1 + n2
    merged = {}
    for k in ["crit_recall", "omission", "agg_fail_pct"]:
        if k in s1 or k in s2:
            merged[k] = (s1.get(k, 0) * n1 + s2.get(k, 0) * n2) / n
    merged["n"] = n
    return merged


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_silo_stage_wise() -> dict:
    """
    Returns {model_name: {protocol: {stage: value}}} for Silo-Bench (n5+n10).
    Stages: extraction_cr, transmission_cr, agg_fail_pct
    """
    results = {}

    instances_n5 = load_silobench(n_agents_filter=5)
    instances_n10 = load_silobench(n_agents_filter=10)

    for model, (n5d, n10d) in SILOBENCH_MODELS.items():
        print(f"\n  [Silo-Bench] {model}")
        model_data = {}

        # --- Extraction-stage CritRec ---
        ecr5 = compute_extraction_stage_cr(n5d, instances_n5, 5)
        ecr10 = compute_extraction_stage_cr(n10d, instances_n10, 10)

        if ecr5 is not None and ecr10 is not None:
            ext_cr_combined = (ecr5 + ecr10) / 2
        elif ecr5 is not None:
            ext_cr_combined = ecr5
        else:
            ext_cr_combined = ecr10

        ecr5_str = f"{ecr5:.3f}" if ecr5 is not None else "N/A"
        ecr10_str = f"{ecr10:.3f}" if ecr10 is not None else "N/A"
        ext_cr_str = f"{ext_cr_combined:.3f}" if ext_cr_combined is not None else "N/A"
        print(f"    Extraction CritRec: n5={ecr5_str}  n10={ecr10_str}  combined={ext_cr_str}")

        # --- Transmission-stage CritRec and AggFail (from audit_metrics.json) ---
        for protocol in RELAY_PROTOCOLS:
            a5 = load_audit_summary(n5d, protocol)
            a10 = load_audit_summary(n10d, protocol)
            merged = merge_audit(a5, a5.get("n", 26), a10, a10.get("n", 26))

            tx_cr = merged.get("crit_recall")
            af = merged.get("agg_fail_pct")
            n_inst = merged.get("n", 0)

            model_data[protocol] = {
                "extraction_cr": ext_cr_combined,
                "transmission_cr": tx_cr,
                "agg_fail_pct": af,
                "n": n_inst,
            }
            tx_cr_str = f"{tx_cr:.3f}" if tx_cr is not None else "?"
            af_str = f"{af:.1f}" if af is not None else "?"
            print(f"    {protocol}: ExtCR={ext_cr_str} TxCR={tx_cr_str} AggFail={af_str}% (n={n_inst})")

        results[model] = model_data

    return results


def compute_musique_stage_wise() -> dict:
    """Returns {model_name: {protocol: {stage: value}}} for MuSiQue."""
    results = {}

    # Load only the IDs we need
    all_mq = load_musique()
    instances_by_id = {inst["id"]: inst for inst in all_mq}

    for model, mq_dir in MUSIQUE_MODELS.items():
        print(f"\n  [MuSiQue] {model}")
        model_data = {}

        # Load which instance IDs were in the run
        res_path = os.path.join(mq_dir, "results.json")
        if not os.path.exists(res_path):
            print(f"    WARNING: no results.json")
            continue
        run_results = json.load(open(res_path))
        run_ids = {r["id"] for r in run_results.get("instance_results", {}).get("random_relay", [])}
        instances = [instances_by_id[iid] for iid in run_ids if iid in instances_by_id]

        ecr = compute_extraction_stage_cr(mq_dir, instances, n_agents=None)
        ecr_str = f"{ecr:.3f}" if ecr is not None else "N/A"
        print(f"    Extraction CritRec: {ecr_str} (n={len(instances)})")

        for protocol in RELAY_PROTOCOLS:
            a = load_audit_summary(mq_dir, protocol)
            tx_cr = a.get("crit_recall")
            af = a.get("agg_fail_pct")
            n_inst = a.get("n", 0)

            model_data[protocol] = {
                "extraction_cr": ecr,
                "transmission_cr": tx_cr,
                "agg_fail_pct": af,
                "n": n_inst,
            }
            ecr_p_str = f"{ecr:.3f}" if ecr is not None else "?"
            tx_cr_str = f"{tx_cr:.3f}" if tx_cr is not None else "?"
            af_str = f"{af:.1f}" if af is not None else "?"
            print(f"    {protocol}: ExtCR={ecr_p_str} TxCR={tx_cr_str} AggFail={af_str}% (n={n_inst})")

        results[model] = model_data

    return results


# ---------------------------------------------------------------------------
# Print combined table
# ---------------------------------------------------------------------------

def print_silo_table(sb_data: dict):
    """Average relay protocols (showing representative scalar)."""
    PROTO_LABELS = {
        "random_relay": "Random Relay",
        "score_ranked_relay": "Score-Ranked Relay",
        "redundancy_aware_relay": "Redundancy-Aware Relay",
    }
    models = list(sb_data.keys())

    print("\n=== SILO-BENCH: Stage-Wise Critical Evidence Survival (n5+n10 combined) ===\n")
    print(f"{'Model':<14} {'Protocol':<24} {'Raw':>7} {'Extracted':>10} {'Transmitted':>12} {'AggFail%':>9}")
    print("-" * 80)

    for model in models:
        first = True
        for proto, d in sb_data[model].items():
            label = PROTO_LABELS.get(proto, proto)
            ext = f"{d['extraction_cr']:.3f}" if d.get("extraction_cr") is not None else "N/A"
            tx = f"{d['transmission_cr']:.3f}" if d.get("transmission_cr") is not None else "N/A"
            af = f"{d['agg_fail_pct']:.1f}" if d.get("agg_fail_pct") is not None else "N/A"
            mname = model if first else ""
            print(f"{mname:<14} {label:<24} {'1.000':>7} {ext:>10} {tx:>12} {af:>9}")
            first = False
        print()


def print_mq_table(mq_data: dict):
    PROTO_LABELS = {
        "random_relay": "Random Relay",
        "score_ranked_relay": "Score-Ranked Relay",
        "redundancy_aware_relay": "Redundancy-Aware Relay",
    }
    models = list(mq_data.keys())

    print("\n=== MUSIQUE: Stage-Wise Critical Evidence Survival (100 instances) ===\n")
    print(f"{'Model':<14} {'Protocol':<24} {'Raw':>7} {'Extracted':>10} {'Transmitted':>12} {'AggFail%':>9}")
    print("-" * 80)

    for model in models:
        first = True
        for proto, d in mq_data.get(model, {}).items():
            label = PROTO_LABELS.get(proto, proto)
            ext = f"{d['extraction_cr']:.3f}" if d.get("extraction_cr") is not None else "N/A"
            tx = f"{d['transmission_cr']:.3f}" if d.get("transmission_cr") is not None else "N/A"
            af = f"{d['agg_fail_pct']:.1f}" if d.get("agg_fail_pct") is not None else "N/A"
            mname = model if first else ""
            print(f"{mname:<14} {label:<24} {'1.000':>7} {ext:>10} {tx:>12} {af:>9}")
            first = False
        print()


def main():
    print("Computing stage-wise evidence survival...")

    print("\n-- Silo-Bench --")
    sb_data = compute_silo_stage_wise()

    print("\n-- MuSiQue --")
    mq_data = compute_musique_stage_wise()

    print_silo_table(sb_data)
    print_mq_table(mq_data)

    # Save
    out = {"silobench": sb_data, "musique": mq_data}
    out_path = os.path.join(BASE, "stage_wise_survival.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to: {out_path}")

    return out


if __name__ == "__main__":
    main()
