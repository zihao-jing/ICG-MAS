#!/usr/bin/env python3
"""
Experiment 1: Hop-Count Stratification for MuSiQue.

Reads per_instance_results.jsonl and audit_metrics.json from the
Qwen-235B MuSiQue run and stratifies results by hop count (2/3/4-hop).

Reports: Accuracy/F1 (%) and AggFail% per hop stratum for key protocols.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

MUSIQUE_RUN = os.path.join(
    os.path.dirname(__file__), "..", "results", "run_qwen235b_musique"
)

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
) -> dict:
    proto_results = per_inst.get(protocol, {})
    proto_audit = audit.get(protocol, {})  # {inst_id: record} or {}

    inst_ids = [iid for iid in proto_results if get_hop(iid) == hop]
    if not inst_ids:
        return {"n": 0, "acc": float("nan"), "agg_fail_pct": float("nan"),
                "crit_recall": float("nan")}

    # MuSiQue uses F1 score (not binary) — use mean F1 as accuracy
    f1_scores = [proto_results[iid].get("f1", 0.0) for iid in inst_ids]
    acc = 100.0 * sum(f1_scores) / len(f1_scores)

    # AggFail from audit records (relay protocols only)
    if proto_audit:
        agg_fails = [
            proto_audit[iid]["agg_fail"]
            for iid in inst_ids
            if iid in proto_audit
        ]
        crit_recalls = [
            proto_audit[iid]["crit_recall"]
            for iid in inst_ids
            if iid in proto_audit
        ]
        agg_fail_pct = 100.0 * sum(agg_fails) / len(agg_fails) if agg_fails else float("nan")
        mean_crit_recall = sum(crit_recalls) / len(crit_recalls) if crit_recalls else float("nan")
    elif protocol == "full_sharing":
        # Full sharing always has CritRec=1.0; AggFail = 1 - Acc
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


def main():
    print(f"Loading MuSiQue run from: {MUSIQUE_RUN}")
    per_inst = load_per_instance(MUSIQUE_RUN)
    audit = load_audit_records(MUSIQUE_RUN)

    all_ids = set()
    for proto_dict in per_inst.values():
        all_ids.update(proto_dict.keys())
    print(f"  {len(all_ids)} unique instances")
    hop_counts = defaultdict(int)
    for iid in all_ids:
        hop_counts[get_hop(iid)] += 1
    print(f"  Hop distribution: {dict(hop_counts)}")

    hops = ["2-hop", "3-hop", "4-hop"]
    results_for_json = {}

    # ── Accuracy table ────────────────────────────────────────────────────────
    print("\n=== Accuracy / mean F1 (%) by Hop Count — Qwen-235B MuSiQue ===\n")
    hdr = f"{'Protocol':<30} {'2-hop':>8} {'3-hop':>8} {'4-hop':>8} {'Pooled':>8}  {'(n2,n3,n4)'}"
    print(hdr)
    print("-" * len(hdr))

    for proto in KEY_PROTOCOLS:
        if proto not in per_inst:
            continue
        row_data = {}
        parts = []
        for hop in hops:
            s = compute_stratum_stats(per_inst, audit, proto, hop)
            row_data[hop] = s
            parts.append(f"{nan_str(s['acc']):>8}")

        # Pooled mean F1
        all_f1 = [per_inst[proto][iid].get("f1", 0.0) for iid in per_inst[proto]]
        pooled_acc = 100.0 * sum(all_f1) / len(all_f1) if all_f1 else float("nan")
        parts.append(f"{nan_str(pooled_acc):>8}")
        row_data["pooled_acc"] = pooled_acc

        ns = [row_data[h]["n"] for h in hops]
        label = LABELS.get(proto, proto)
        print(f"{label:<30} {''.join(parts)}  ({','.join(str(n) for n in ns)})")
        results_for_json[proto] = row_data

    # ── AggFail table ─────────────────────────────────────────────────────────
    print("\n=== AggFail (%) by Hop Count — Qwen-235B MuSiQue ===\n")
    hdr2 = f"{'Protocol':<30} {'2-hop AF%':>10} {'3-hop AF%':>10} {'4-hop AF%':>10} {'Pooled AF%':>11}"
    print(hdr2)
    print("-" * len(hdr2))

    af_protocols = ["full_sharing", "summary_exchange",
                    "random_relay", "score_ranked_relay", "redundancy_aware_relay"]

    for proto in af_protocols:
        if proto not in per_inst:
            continue
        parts = []
        for hop in hops:
            s = compute_stratum_stats(per_inst, audit, proto, hop)
            parts.append(f"{nan_str(s['agg_fail_pct']):>10}")

        # Pooled AggFail
        proto_audit = audit.get(proto, {})
        if proto_audit:
            all_agg = [r["agg_fail"] for r in proto_audit.values()]
            pool_af = 100.0 * sum(all_agg) / len(all_agg)
        elif proto == "full_sharing":
            pool_af = 100.0 - results_for_json.get(proto, {}).get("pooled_acc", float("nan"))
        else:
            pool_af = float("nan")
        parts.append(f"{nan_str(pool_af):>11}")

        label = LABELS.get(proto, proto)
        print(f"{label:<30} {''.join(parts)}")

    # ── CritRec table ─────────────────────────────────────────────────────────
    print("\n=== Critical Recall by Hop Count (relay protocols, MuSiQue) ===\n")
    hdr3 = f"{'Protocol':<30} {'2-hop CR':>10} {'3-hop CR':>10} {'4-hop CR':>10} {'Pooled CR':>10}"
    print(hdr3)
    print("-" * len(hdr3))

    for proto in ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]:
        if proto not in audit:
            continue
        proto_audit = audit[proto]
        parts = []
        for hop in hops:
            s = compute_stratum_stats(per_inst, audit, proto, hop)
            parts.append(f"{nan_str(s['crit_recall'], '.3f'):>10}")
        # Pooled
        all_cr = [r["crit_recall"] for r in proto_audit.values()]
        pool_cr = sum(all_cr) / len(all_cr) if all_cr else float("nan")
        parts.append(f"{nan_str(pool_cr, '.3f'):>10}")
        label = LABELS.get(proto, proto)
        print(f"{label:<30} {''.join(parts)}")

    # ── Save ──────────────────────────────────────────────────────────────────
    out = {}
    for proto in KEY_PROTOCOLS:
        if proto not in per_inst:
            continue
        out[proto] = {}
        for hop in hops:
            s = compute_stratum_stats(per_inst, audit, proto, hop)
            out[proto][hop] = s
        # Add pooled
        all_f1 = [per_inst[proto][iid].get("f1", 0.0) for iid in per_inst[proto]]
        out[proto]["pooled_acc"] = 100.0 * sum(all_f1) / len(all_f1) if all_f1 else float("nan")
        proto_audit = audit.get(proto, {})
        if proto_audit:
            all_agg = [r["agg_fail"] for r in proto_audit.values()]
            out[proto]["pooled_agg_fail_pct"] = 100.0 * sum(all_agg) / len(all_agg)
            all_cr = [r["crit_recall"] for r in proto_audit.values()]
            out[proto]["pooled_crit_recall"] = sum(all_cr) / len(all_cr)

    out_path = os.path.join(
        os.path.dirname(__file__), "..", "results", "exp1_hop_stratification.json"
    )
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {out_path}")
    return out


if __name__ == "__main__":
    main()
