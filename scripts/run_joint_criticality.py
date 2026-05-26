#!/usr/bin/env python3
"""
Joint-Criticality False Negative Analysis.

Loads the 1170 extracted unit records (n5 + n10) from local_importance_metrics.json,
then simulates top-k evidence selection at k=1, k=2, k=3 budgets.

For critical units (gold_label=1), splits into:
  - "Locally high-score critical": selected at a given budget (true positives)
  - "Locally low-score critical": dropped at a given budget (false negatives)

Computes:
  - False Negative Rate (FNR) at each budget
  - Average overall score for TP vs FN critical units
  - CritRec degradation from k=3 to k=1
  - Score gap: mean score of TP critical units vs FN critical units vs non-critical

The core finding: FN critical units have systematically lower local scores,
explaining why local importance estimation fails to identify jointly-critical facts.

Usage:
    cd /path/to/repo
    python scripts/run_joint_criticality.py

Output:
    results/joint_criticality/joint_criticality_results.json
    (Prints analysis table to stdout)
"""

from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUN_FILES = [
    os.path.join(_ROOT, "results", "run_qwen235b_n5", "local_importance_metrics.json"),
    os.path.join(_ROOT, "results", "run_qwen235b_n10", "local_importance_metrics.json"),
]

OUT_DIR = os.path.join(_ROOT, "results", "joint_criticality")


def load_records() -> list[dict]:
    all_records = []
    for path in RUN_FILES:
        with open(path) as f:
            data = json.load(f)
        all_records.extend(data["all_records"])
    return all_records


def group_by_agent(records: list[dict]) -> dict[tuple, list[dict]]:
    """Group records by (inst_id, agent)."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["inst_id"], r["agent"])].append(r)
    return dict(groups)


def simulate_topk(records: list[dict], k: int, score_key: str = "overall") -> list[dict]:
    """Sort records by score_key descending, return top-k."""
    sorted_r = sorted(records, key=lambda r: r[score_key], reverse=True)
    return sorted_r[:k]


def analyze_budget(
    groups: dict[tuple, list[dict]],
    k: int,
    score_key: str = "overall",
) -> dict:
    """
    For each (inst_id, agent) group, simulate top-k selection.
    Returns per-budget metrics.
    """
    tp_scores: list[float] = []   # critical units that ARE selected
    fn_scores: list[float] = []   # critical units that are DROPPED
    nc_scores: list[float] = []   # non-critical units

    n_total_critical = 0
    n_selected_critical = 0
    n_total_instances = 0

    # Per-instance CritRec at this budget
    inst_crit_rec: dict[str, dict] = defaultdict(lambda: {"n_gold": 0, "n_covered": 0})

    for (inst_id, agent), recs in groups.items():
        selected = simulate_topk(recs, k, score_key)
        dropped  = [r for r in recs if r not in selected]
        selected_set = set(id(r) for r in selected)

        for r in recs:
            score = r[score_key]
            if r["gold_label"] == 1:
                n_total_critical += 1
                inst_crit_rec[inst_id]["n_gold"] += 1
                if id(r) in selected_set:
                    n_selected_critical += 1
                    tp_scores.append(score)
                    inst_crit_rec[inst_id]["n_covered"] += 1
                else:
                    fn_scores.append(score)
            else:
                nc_scores.append(score)

    # Compute per-instance CritRec, then mean
    crit_recs = []
    for inst_id, d in inst_crit_rec.items():
        if d["n_gold"] > 0:
            crit_recs.append(d["n_covered"] / d["n_gold"])
            n_total_instances += 1

    mean_crit_rec = statistics.mean(crit_recs) if crit_recs else 1.0
    fnr = len(fn_scores) / n_total_critical if n_total_critical > 0 else 0.0

    def _stats(lst: list[float]) -> dict:
        if not lst:
            return {"n": 0, "mean": float("nan"), "std": float("nan"), "min": float("nan"), "max": float("nan")}
        return {
            "n": len(lst),
            "mean": statistics.mean(lst),
            "std": statistics.stdev(lst) if len(lst) > 1 else 0.0,
            "min": min(lst),
            "max": max(lst),
        }

    return {
        "k": k,
        "score_key": score_key,
        "n_total_critical": n_total_critical,
        "n_selected_critical": n_selected_critical,
        "n_fn_critical": len(fn_scores),
        "false_negative_rate": fnr,
        "mean_crit_rec": mean_crit_rec,
        "tp_score_stats": _stats(tp_scores),
        "fn_score_stats": _stats(fn_scores),
        "nc_score_stats": _stats(nc_scores),
    }


def print_analysis(results: list[dict]) -> None:
    print("\n=== Joint-Criticality False Negative Analysis ===")
    print(f"{'Budget':>7} {'CritRec':>8} {'FNR':>7} {'TP N':>6} {'FN N':>6} "
          f"{'TP AvgScore':>12} {'FN AvgScore':>12} {'Score Gap':>10}")
    print("-" * 80)
    for r in results:
        tp_mean = r["tp_score_stats"]["mean"] if r["tp_score_stats"]["n"] > 0 else float("nan")
        fn_mean = r["fn_score_stats"]["mean"] if r["fn_score_stats"]["n"] > 0 else float("nan")
        gap = tp_mean - fn_mean if not (tp_mean != tp_mean or fn_mean != fn_mean) else float("nan")
        print(
            f"k={r['k']:>5} {r['mean_crit_rec']:>8.3f} {r['false_negative_rate']:>7.3f} "
            f"{r['tp_score_stats']['n']:>6} {r['fn_score_stats']['n']:>6} "
            f"{tp_mean:>12.3f} {fn_mean if fn_mean == fn_mean else 'N/A':>12} {gap if gap == gap else 'N/A':>10}"
        )

    print("\n=== Score Distribution: TP Critical vs FN Critical vs Non-Critical (k=1) ===")
    k1 = next(r for r in results if r["k"] == 1)
    print(f"  Locally high-score critical (TP at k=1): n={k1['tp_score_stats']['n']}, "
          f"mean={k1['tp_score_stats']['mean']:.3f}, std={k1['tp_score_stats']['std']:.3f}")
    print(f"  Locally low-score critical (FN at k=1):  n={k1['fn_score_stats']['n']}, "
          f"mean={k1['fn_score_stats']['mean']:.3f}, std={k1['fn_score_stats']['std']:.3f}")
    print(f"  Non-critical:                             n={k1['nc_score_stats']['n']}, "
          f"mean={k1['nc_score_stats']['mean']:.3f}, std={k1['nc_score_stats']['std']:.3f}")

    print("\n=== CritRec Degradation Under Tighter Budgets ===")
    k3 = next(r for r in results if r["k"] == 3)
    k2 = next(r for r in results if r["k"] == 2)
    k1 = next(r for r in results if r["k"] == 1)
    print(f"  k=3 (current): CritRec={k3['mean_crit_rec']:.3f}, FNR={k3['false_negative_rate']:.3f}")
    print(f"  k=2:           CritRec={k2['mean_crit_rec']:.3f}, FNR={k2['false_negative_rate']:.3f}")
    print(f"  k=1:           CritRec={k1['mean_crit_rec']:.3f}, FNR={k1['false_negative_rate']:.3f}")
    print(f"  Delta (k=3 → k=1): ΔCritRec = {k1['mean_crit_rec'] - k3['mean_crit_rec']:.3f}")
    print(f"  Score gap (TP - FN) at k=1: "
          f"{k1['tp_score_stats']['mean']:.3f} - {k1['fn_score_stats']['mean']:.3f} = "
          f"{k1['tp_score_stats']['mean'] - k1['fn_score_stats']['mean']:.3f}")


def build_paper_table(results: list[dict]) -> str:
    """Build a simple text representation for the paper table."""
    lines = []
    lines.append("Joint-Criticality False Negative Analysis (Silo-Bench, Qwen-235B, 1170 units)")
    lines.append("")
    lines.append("Budget k | CritRec | FNR   | TP n | FN n | TP avg score | FN avg score")
    lines.append("-" * 70)
    for r in results:
        tp_m = r["tp_score_stats"]["mean"] if r["tp_score_stats"]["n"] > 0 else float("nan")
        fn_m = r["fn_score_stats"]["mean"] if r["fn_score_stats"]["n"] > 0 else float("nan")
        fn_str = f"{fn_m:.3f}" if fn_m == fn_m else "---"
        lines.append(
            f"k={r['k']}      | {r['mean_crit_rec']:.3f}   | {r['false_negative_rate']:.3f} "
            f"| {r['tp_score_stats']['n']:4d} | {r['fn_score_stats']['n']:4d} "
            f"| {tp_m:.3f}        | {fn_str}"
        )
    return "\n".join(lines)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Loading unit records from local_importance_metrics.json (n5 + n10)...")
    records = load_records()
    print(f"  {len(records)} total units loaded")
    gold_1 = sum(1 for r in records if r["gold_label"] == 1)
    gold_0 = sum(1 for r in records if r["gold_label"] == 0)
    print(f"  Critical (gold=1): {gold_1}, Non-critical (gold=0): {gold_0}")

    print("Grouping by (inst_id, agent)...")
    groups = group_by_agent(records)
    print(f"  {len(groups)} (inst_id, agent) groups")
    group_sizes = [len(v) for v in groups.values()]
    print(f"  Group sizes: min={min(group_sizes)} max={max(group_sizes)} "
          f"mean={statistics.mean(group_sizes):.1f}")

    print("\nSimulating top-k selection at k=1, 2, 3...")
    results = []
    for k in [1, 2, 3]:
        r = analyze_budget(groups, k, score_key="overall")
        results.append(r)
        print(f"  k={k}: CritRec={r['mean_crit_rec']:.3f}, FNR={r['false_negative_rate']:.3f}, "
              f"TP={r['tp_score_stats']['n']}, FN={r['fn_score_stats']['n']}")

    print_analysis(results)

    # Also analyze sub-components (relevance, uniqueness, local_importance)
    print("\n=== Score Decomposition at k=1 (per score type) ===")
    for score_key in ["relevance", "uniqueness", "local_importance", "overall"]:
        r = analyze_budget(groups, k=1, score_key=score_key)
        tp_m = r["tp_score_stats"]["mean"] if r["tp_score_stats"]["n"] > 0 else float("nan")
        fn_m = r["fn_score_stats"]["mean"] if r["fn_score_stats"]["n"] > 0 else float("nan")
        gap = (tp_m - fn_m) if (tp_m == tp_m and fn_m == fn_m) else float("nan")
        print(f"  {score_key:<20}: CritRec={r['mean_crit_rec']:.3f}, FNR={r['false_negative_rate']:.3f}, "
              f"TP avg={tp_m:.3f}, FN avg={fn_m:.3f}, gap={gap:.3f}")

    # Compute thresholded split: high-score vs low-score critical
    # Use median of all overall scores as threshold
    all_scores = [r["overall"] for r in records]
    threshold_median = statistics.median(all_scores)
    print(f"\n=== High vs Low Score Critical Unit Split (threshold=median={threshold_median:.3f}) ===")
    critical_records = [r for r in records if r["gold_label"] == 1]
    high_score_critical = [r for r in critical_records if r["overall"] >= threshold_median]
    low_score_critical  = [r for r in critical_records if r["overall"] < threshold_median]
    print(f"  Locally high-score critical (score >= {threshold_median:.3f}): {len(high_score_critical)}")
    print(f"  Locally low-score critical  (score <  {threshold_median:.3f}): {len(low_score_critical)}")

    high_scores = [r["overall"] for r in high_score_critical]
    low_scores  = [r["overall"] for r in low_score_critical]
    nc_scores   = [r["overall"] for r in records if r["gold_label"] == 0]

    print(f"  High-score critical: mean={statistics.mean(high_scores):.3f}, "
          f"std={statistics.stdev(high_scores) if len(high_scores) > 1 else 0:.3f}")
    print(f"  Low-score critical:  mean={statistics.mean(low_scores):.3f}, "
          f"std={statistics.stdev(low_scores) if len(low_scores) > 1 else 0:.3f}")
    print(f"  Non-critical:        mean={statistics.mean(nc_scores):.3f}, "
          f"std={statistics.stdev(nc_scores) if len(nc_scores) > 1 else 0:.3f}")

    # False negative rate at k=1 among low-score critical units
    # These are units that would ALWAYS be dropped under k=1 selection
    groups_k1 = group_by_agent(records)
    fn_low_count = 0
    fn_high_count = 0
    for (inst_id, agent), recs in groups_k1.items():
        selected = simulate_topk(recs, 1)
        selected_ids = set(id(r) for r in selected)
        for r in recs:
            if r["gold_label"] == 1:
                is_fn = id(r) not in selected_ids
                if r["overall"] < threshold_median:
                    fn_low_count += (1 if is_fn else 0)
                else:
                    fn_high_count += (1 if is_fn else 0)

    print(f"\n  At k=1: FN among low-score critical = {fn_low_count}/{len(low_score_critical)} "
          f"({100*fn_low_count/len(low_score_critical) if low_score_critical else 0:.1f}%)")
    print(f"  At k=1: FN among high-score critical = {fn_high_count}/{len(high_score_critical)} "
          f"({100*fn_high_count/len(high_score_critical) if high_score_critical else 0:.1f}%)")

    # Save results
    output = {
        "n_total_units": len(records),
        "n_critical": gold_1,
        "n_noncritical": gold_0,
        "n_groups": len(groups),
        "threshold_median": threshold_median,
        "n_high_score_critical": len(high_score_critical),
        "n_low_score_critical": len(low_score_critical),
        "fn_rate_low_at_k1": fn_low_count / len(low_score_critical) if low_score_critical else 0.0,
        "fn_rate_high_at_k1": fn_high_count / len(high_score_critical) if high_score_critical else 0.0,
        "budget_analysis": results,
        "score_decomposition_k1": {
            sk: analyze_budget(groups, k=1, score_key=sk)
            for sk in ["relevance", "uniqueness", "local_importance", "overall"]
        },
    }

    out_path = os.path.join(OUT_DIR, "joint_criticality_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
