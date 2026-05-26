#!/usr/bin/env python3
"""
Local importance failure analysis for Table 4.

Parses scoring-phase responses from api_responses.jsonl and computes:
  AUC, Spearman, P@3, R@3
for each local score type (Relevance, Uniqueness, Importance, Average)
against gold criticality labels.

Gold critical label: an extracted unit is gold critical if it contains
the agent's LOCAL critical value — the maximum value in that agent's
private shard.  Every agent's local max is a jointly-critical fact (the
aggregator must receive each agent's local max to find the global max).
Units that faithfully report the agent's local max get label = 1;
units reporting only irrelevant context get label = 0.

No new API calls are made — this only reads existing logged responses.

Usage:
    python scripts/local_importance_analysis.py --run-dir results/run_20260523_214416
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.eval.silo_bench_loader import load_silobench
from src.protocols.base import parse_score_json
from src.protocols.relay import _parse_units

MAX_UNITS = 3  # max extracted units per agent (matches relay protocol)

try:
    from sklearn.metrics import roc_auc_score
    _SKLEARN = True
except ImportError:
    _SKLEARN = False

try:
    from scipy.stats import spearmanr
    _SCIPY = True
except ImportError:
    _SCIPY = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _numbers_in_text(text: str) -> set[str]:
    return set(re.findall(r"-?\d+(?:\.\d+)?", text))


def _agent_local_max(shard) -> str | None:
    """Return the maximum numeric value in the agent's shard as a string."""
    if isinstance(shard, list):
        nums = [x for x in shard if isinstance(x, (int, float))]
    else:
        nums_str = _numbers_in_text(str(shard))
        nums = [float(n) for n in nums_str]
    if not nums:
        return None
    return str(int(max(nums))) if all(isinstance(x, int) for x in nums) else str(max(nums))


def _unit_contains_value(unit_text: str, target: str) -> bool:
    """True if target appears as a number token in unit_text."""
    unit_nums = _numbers_in_text(unit_text)
    return target in unit_nums


def _safe_auc(labels: list[int], scores: list[float]) -> float | None:
    if not _SKLEARN:
        return None
    if len(set(labels)) < 2:
        return None
    try:
        return roc_auc_score(labels, scores)
    except Exception:
        return None


def _safe_spearman(labels: list[int], scores: list[float]) -> float | None:
    if not _SCIPY:
        return None
    if len(scores) < 3:
        return None
    try:
        result = spearmanr(scores, labels)
        return float(result.statistic)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Load and reconstruct
# ---------------------------------------------------------------------------

def load_responses(run_dir: str):
    path = os.path.join(run_dir, "api_responses.jsonl")
    responses = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                responses.append(json.loads(line))
    return responses


def reconstruct(responses: list[dict]):
    """Return extracted_units and scores keyed by (instance_id, agent)."""
    units: dict[tuple, list[str]] = defaultdict(list)
    scores: dict[tuple, list[dict]] = defaultdict(list)

    for r in responses:
        if not r.get("success"):
            continue
        key = (r["instance_id"], r["agent"])
        if r["phase"] == "extraction":
            units[key] = _parse_units(r["content"], MAX_UNITS)
        elif r["phase"] == "scoring":
            # Parse raw JSON to get relay-prompt field names (local_importance, overall)
            # parse_score_json uses old field names (criticality, composite) — bypass it here
            sc = {"relevance": 0.5, "uniqueness": 0.5,
                  "local_importance": 0.5, "overall": 0.5}
            try:
                m = re.search(r"\{[^}]+\}", r["content"], re.DOTALL)
                if m:
                    raw = json.loads(m.group())
                    sc["relevance"] = float(raw.get("relevance", 0.5))
                    sc["uniqueness"] = float(raw.get("uniqueness", 0.5))
                    sc["local_importance"] = float(raw.get(
                        "local_importance", raw.get("criticality", 0.5)))
                    sc["overall"] = float(raw.get(
                        "overall", raw.get("composite", 0.5)))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
            scores[key].append(sc)

    return dict(units), dict(scores)


# ---------------------------------------------------------------------------
# Per-instance analysis
# ---------------------------------------------------------------------------

def analyze_instance(
    inst: dict,
    units_map: dict,
    scores_map: dict,
) -> list[dict]:
    """
    Return one record per (agent, unit_index) for this instance.
    Each record: {inst_id, agent, unit_idx, unit_text, gold_label,
                  relevance, uniqueness, local_importance, average}

    Gold label: unit contains the agent's local max (the key value the
    aggregator needs from this agent's shard).
    """
    records = []

    for ac in inst["agent_configs"]:
        agent_id = ac["agent_id"]
        key = (inst["id"], agent_id)
        agent_units = units_map.get(key, [])
        agent_scores = scores_map.get(key, [])

        # Gold critical value for this agent = max of their private shard
        local_max = _agent_local_max(ac.get("input_shard"))

        for unit_idx, unit_text in enumerate(agent_units):
            if local_max is not None:
                gold_label = int(_unit_contains_value(unit_text, local_max))
            else:
                gold_label = 0
            sc = agent_scores[unit_idx] if unit_idx < len(agent_scores) else {}
            rel = sc.get("relevance", 0.5)
            uniq = sc.get("uniqueness", 0.5)
            imp = sc.get("local_importance", 0.5)
            overall = sc.get("overall", 0.5)
            records.append({
                "inst_id": inst["id"],
                "agent": agent_id,
                "unit_idx": unit_idx,
                "unit_text": unit_text,
                "gold_label": gold_label,
                "relevance": rel,
                "uniqueness": uniq,
                "local_importance": imp,
                "overall": overall,
            })

    return records


# ---------------------------------------------------------------------------
# P@k and R@k (per instance, then averaged)
# ---------------------------------------------------------------------------

def precision_recall_at_k(
    inst_records: list[dict],
    score_key: str,
    k: int,
) -> tuple[float, float]:
    """Compute P@k and R@k for one instance's unit pool."""
    if not inst_records:
        return 0.0, 0.0
    ranked = sorted(inst_records, key=lambda r: r[score_key], reverse=True)
    top_k = ranked[:k]
    n_relevant = sum(r["gold_label"] for r in inst_records)
    if n_relevant == 0:
        return 0.0, 0.0
    hits = sum(r["gold_label"] for r in top_k)
    precision = hits / k
    recall = hits / n_relevant
    return precision, recall


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--k", type=int, default=3, help="k for P@k / R@k (default 3)")
    parser.add_argument("--n-agents", type=int, default=5)
    args = parser.parse_args(argv)

    print(f"Loading responses from: {args.run_dir}")
    responses = load_responses(args.run_dir)
    print(f"  {len(responses)} responses loaded")

    units_map, scores_map = reconstruct(responses)
    print(f"  {len(units_map)} (instance, agent) pairs with extracted units")

    print("Loading Silo-Bench instances...")
    instances = load_silobench(n_agents_filter=args.n_agents)
    print(f"  {len(instances)} instances loaded")

    all_records: list[dict] = []
    inst_records_by_id: dict[str, list[dict]] = {}
    for inst in instances:
        recs = analyze_instance(inst, units_map, scores_map)
        if recs:
            all_records.extend(recs)
            inst_records_by_id[inst["id"]] = recs

    n_total = len(all_records)
    n_gold = sum(r["gold_label"] for r in all_records)
    print(f"\n  {n_total} total units, {n_gold} gold critical ({100*n_gold/max(1,n_total):.1f}%)")

    score_keys = ["relevance", "uniqueness", "local_importance", "overall"]
    score_labels = {
        "relevance": "Relevance",
        "uniqueness": "Uniqueness",
        "local_importance": "Importance",
        "overall": "Overall (relay)",
    }

    labels_all = [r["gold_label"] for r in all_records]

    print(f"\n=== Table 4 — Local Importance Failure Analysis (P@{args.k}, R@{args.k}) ===\n")
    header = f"{'Score':<14} {'AUC':>6}  {'Spearman':>9}  {'P@'+str(args.k):>5}  {'R@'+str(args.k):>5}"
    print(header)
    print("-" * len(header))

    table4_rows = {}

    for sk in score_keys:
        scores_all = [r[sk] for r in all_records]

        auc = _safe_auc(labels_all, scores_all)
        rho = _safe_spearman(labels_all, scores_all)

        pk_list, rk_list = [], []
        for inst_id, recs in inst_records_by_id.items():
            pk, rk = precision_recall_at_k(recs, sk, args.k)
            pk_list.append(pk)
            rk_list.append(rk)

        mean_pk = sum(pk_list) / len(pk_list) if pk_list else 0.0
        mean_rk = sum(rk_list) / len(rk_list) if rk_list else 0.0

        auc_str = f"{auc:.3f}" if auc is not None else " N/A "
        rho_str = f"{rho:+.3f}" if rho is not None else "   N/A "

        label = score_labels[sk]
        print(f"{label:<14} {auc_str:>6}  {rho_str:>9}  {mean_pk:>5.3f}  {mean_rk:>5.3f}")

        table4_rows[sk] = {
            "label": label,
            "auc": auc,
            "spearman": rho,
            f"p_at_{args.k}": mean_pk,
            f"r_at_{args.k}": mean_rk,
        }

    # Random baseline
    import random as _random
    rng = _random.Random(42)
    rand_scores = [rng.random() for _ in labels_all]
    rand_auc = _safe_auc(labels_all, rand_scores)
    rand_rho = _safe_spearman(labels_all, rand_scores)
    rand_pk_list, rand_rk_list = [], []
    for inst_id, recs in inst_records_by_id.items():
        recs_copy = [{**r, "random": rng.random()} for r in recs]
        pk, rk = precision_recall_at_k(recs_copy, "random", args.k)
        rand_pk_list.append(pk)
        rand_rk_list.append(rk)
    rand_mean_pk = sum(rand_pk_list) / len(rand_pk_list) if rand_pk_list else 0.0
    rand_mean_rk = sum(rand_rk_list) / len(rand_rk_list) if rand_rk_list else 0.0

    rand_auc_str = f"{rand_auc:.3f}" if rand_auc is not None else "  0.50"
    rand_rho_str = f"{rand_rho:+.3f}" if rand_rho is not None else "  0.00 "
    print(f"{'Random':<14} {rand_auc_str:>6}  {rand_rho_str:>9}  {rand_mean_pk:>5.3f}  {rand_mean_rk:>5.3f}")

    table4_rows["random"] = {
        "label": "Random",
        "auc": rand_auc,
        "spearman": rand_rho,
        f"p_at_{args.k}": rand_mean_pk,
        f"r_at_{args.k}": rand_mean_rk,
    }

    print()
    print(f"  (Expected random AUC ≈ 0.50; Spearman ≈ 0.00)")
    print(f"  (Gold positive rate: {100*n_gold/max(1,n_total):.1f}% of all extracted units)")

    out_path = os.path.join(args.run_dir, "local_importance_metrics.json")
    with open(out_path, "w") as f:
        json.dump({
            "k": args.k,
            "n_total_units": n_total,
            "n_gold_critical_units": n_gold,
            "table4_rows": table4_rows,
            "all_records": all_records,
        }, f, indent=2)
    print(f"\nResults saved to: {out_path}")

    # Print LaTeX snippet for Table 4
    print("\n=== LaTeX snippet for Table 4 ===")
    for sk in score_keys + ["random"]:
        row = table4_rows[sk]
        auc = f"{row['auc']:.3f}" if row["auc"] is not None else "---"
        rho = f"{row['spearman']:+.3f}" if row["spearman"] is not None else "---"
        pk = f"{row[f'p_at_{args.k}']:.3f}"
        rk = f"{row[f'r_at_{args.k}']:.3f}"
        print(f"    {row['label']:<12} & {auc} & {rho} & {pk} & {rk} \\\\")


if __name__ == "__main__":
    main()
