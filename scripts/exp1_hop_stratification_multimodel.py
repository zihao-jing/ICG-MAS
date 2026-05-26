#!/usr/bin/env python3
"""
Hop-Count Stratification for MuSiQue — multi-model version.

Reads per_instance_results.jsonl and audit_metrics.json from MuSiQue runs
for all four models and stratifies results by hop count (2/3/4-hop).

Reports: Accuracy/F1 (%) and AggFail% per hop stratum.
Saves: results/exp1_hop_stratification_multimodel.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE = os.path.join(os.path.dirname(__file__), "..", "results")

MUSIQUE_MODELS = {
    "Qwen-235B":    os.path.join(BASE, "run_qwen235b_musique"),
    "Mistral-S":    os.path.join(BASE, "run_musique_mistrals"),
    "Qwen-80B-T":   os.path.join(BASE, "run_musique_qwen80bt"),
    "Qwen-3.6-Flash": os.path.join(BASE, "run_musique_100"),
}

KEY_PROTOCOLS = [
    "full_sharing",
    "summary_exchange",
    "random_relay",
    "score_ranked_relay",
    "redundancy_aware_relay",
    "confidence_gated",
    "free_form_debate",
]

LABELS = {
    "full_sharing":           "Full Evidence Sharing",
    "summary_exchange":       "Summary Exchange",
    "random_relay":           "Random Relay",
    "score_ranked_relay":     "Score-Ranked Relay",
    "redundancy_aware_relay": "Redundancy-Aware Relay",
    "confidence_gated":       "Confidence-Gated",
    "free_form_debate":       "Free-form Debate",
}

AGGFAIL_PROTOCOLS = [
    "full_sharing", "random_relay", "score_ranked_relay",
    "redundancy_aware_relay", "summary_exchange",
]


def get_hop(inst_id: str) -> str:
    if inst_id.startswith("2hop"):
        return "2-hop"
    elif inst_id.startswith("3hop"):
        return "3-hop"
    elif inst_id.startswith("4hop"):
        return "4-hop"
    return "other"


def load_per_instance(run_dir: str) -> dict[str, dict[str, dict]]:
    path = os.path.join(run_dir, "per_instance_results.jsonl")
    results: dict[str, dict[str, dict]] = defaultdict(dict)
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            results[rec["protocol"]][rec["id"]] = rec
    return dict(results)


def load_audit_records(run_dir: str) -> dict[str, dict[str, dict]]:
    path = os.path.join(run_dir, "audit_metrics.json")
    with open(path) as f:
        data = json.load(f)
    audit: dict[str, dict[str, dict]] = {}
    for protocol, records in data.get("audit_records", {}).items():
        audit[protocol] = {r["inst_id"]: r for r in records}
    return audit


def compute_stratum_stats(
    per_inst: dict[str, dict[str, dict]],
    audit: dict[str, dict[str, dict]],
    protocol: str,
    hop: str,
    pooled_acc: float | None = None,
) -> dict:
    proto_results = per_inst.get(protocol, {})
    proto_audit = audit.get(protocol, {})

    inst_ids = [iid for iid in proto_results if get_hop(iid) == hop]
    if not inst_ids:
        return {"n": 0, "acc": float("nan"), "agg_fail_pct": float("nan"),
                "crit_recall": float("nan")}

    f1_scores = [proto_results[iid].get("f1", 0.0) for iid in inst_ids]
    acc = 100.0 * sum(f1_scores) / len(f1_scores)

    if proto_audit:
        agg_fails = [proto_audit[iid]["agg_fail"] for iid in inst_ids if iid in proto_audit]
        crit_recalls = [proto_audit[iid]["crit_recall"] for iid in inst_ids if iid in proto_audit]
        agg_fail_pct = 100.0 * sum(agg_fails) / len(agg_fails) if agg_fails else float("nan")
        mean_crit_recall = sum(crit_recalls) / len(crit_recalls) if crit_recalls else float("nan")
    elif protocol == "full_sharing":
        agg_fail_pct = 100.0 - acc
        mean_crit_recall = 1.0
    else:
        agg_fail_pct = float("nan")
        mean_crit_recall = float("nan")

    return {
        "n": len(inst_ids),
        "acc": acc,
        "agg_fail_pct": agg_fail_pct,
        "crit_recall": mean_crit_recall,
    }


def nan_str(v: float, fmt: str = ".1f") -> str:
    if v != v:
        return "---"
    return format(v, fmt)


def run_model(model_name: str, run_dir: str) -> dict:
    print(f"\n{'='*60}")
    print(f"Model: {model_name}  |  Dir: {os.path.basename(run_dir)}")
    print(f"{'='*60}")

    per_inst = load_per_instance(run_dir)
    audit = load_audit_records(run_dir)

    all_ids: set[str] = set()
    for pd in per_inst.values():
        all_ids.update(pd.keys())
    hop_counts: dict[str, int] = defaultdict(int)
    for iid in all_ids:
        hop_counts[get_hop(iid)] += 1
    print(f"  {len(all_ids)} unique instances, hop distribution: {dict(hop_counts)}")

    hops = ["2-hop", "3-hop", "4-hop"]
    model_results: dict = {}

    # Accuracy table
    print(f"\n  Accuracy / mean F1 (%) by Hop Count:\n")
    hdr = f"  {'Protocol':<30} {'2-hop':>8} {'3-hop':>8} {'4-hop':>8} {'Pooled':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for proto in KEY_PROTOCOLS:
        if proto not in per_inst:
            continue
        row_data: dict = {}
        parts: list[str] = []
        for hop in hops:
            s = compute_stratum_stats(per_inst, audit, proto, hop)
            row_data[hop] = s
            parts.append(f"{nan_str(s['acc']):>8}")

        all_f1 = [per_inst[proto][iid].get("f1", 0.0) for iid in per_inst[proto]]
        pooled_acc = 100.0 * sum(all_f1) / len(all_f1) if all_f1 else float("nan")
        parts.append(f"{nan_str(pooled_acc):>8}")
        row_data["pooled_acc"] = pooled_acc

        label = LABELS.get(proto, proto)
        print(f"  {label:<30} {''.join(parts)}")
        model_results[proto] = row_data

    # AggFail table
    print(f"\n  AggFail (%) by Hop Count:\n")
    hdr2 = f"  {'Protocol':<30} {'2-hop':>8} {'3-hop':>8} {'4-hop':>8} {'Pooled':>8}"
    print(hdr2)
    print("  " + "-" * (len(hdr2) - 2))

    for proto in AGGFAIL_PROTOCOLS:
        if proto not in per_inst:
            continue
        parts = []
        for hop in hops:
            s = compute_stratum_stats(per_inst, audit, proto, hop)
            parts.append(f"{nan_str(s['agg_fail_pct']):>8}")

        proto_audit = audit.get(proto, {})
        if proto_audit:
            all_agg = [r["agg_fail"] for r in proto_audit.values()]
            pool_af = 100.0 * sum(all_agg) / len(all_agg)
        elif proto == "full_sharing":
            pa = model_results.get(proto, {}).get("pooled_acc", float("nan"))
            pool_af = 100.0 - pa if pa == pa else float("nan")
        else:
            pool_af = float("nan")
        parts.append(f"{nan_str(pool_af):>8}")

        # Save pooled agg_fail
        if proto in model_results:
            model_results[proto]["pooled_agg_fail_pct"] = pool_af

        label = LABELS.get(proto, proto)
        print(f"  {label:<30} {''.join(parts)}")

    return model_results


def main():
    all_results: dict = {}
    for model_name, run_dir in MUSIQUE_MODELS.items():
        if not os.path.isdir(run_dir):
            print(f"SKIP {model_name}: directory not found ({run_dir})")
            continue
        all_results[model_name] = run_model(model_name, run_dir)

    out_path = os.path.join(
        os.path.dirname(__file__), "..", "results", "exp1_hop_stratification_multimodel.json"
    )
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
