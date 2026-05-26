#!/usr/bin/env python3
"""
Multi-model local importance analysis (Priority 4).

Combines n5+n10 Silo-Bench runs for each model and computes AUC, Spearman ρ,
P@3, R@3 for each local score type (Relevance, Uniqueness, Importance, Overall).

No new API calls — reads saved api_responses.jsonl files only.

Usage:
    python scripts/local_importance_multimodel.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.local_importance_analysis import (
    load_responses, reconstruct, analyze_instance,
    _safe_auc, _safe_spearman, precision_recall_at_k,
)
from src.eval.silo_bench_loader import load_silobench

BASE = os.path.join(os.path.dirname(__file__), "..", "results")

MODELS = {
    "Qwen-235B": [
        (os.path.join(BASE, "run_qwen235b_n5"), 5),
        (os.path.join(BASE, "run_qwen235b_n10"), 10),
    ],
    "Mistral-S": [
        (os.path.join(BASE, "run_mistrals"), 5),
        (os.path.join(BASE, "run_mistrals_n10"), 10),
    ],
    "Qwen-80B-T": [
        (os.path.join(BASE, "run_qwen80bt"), 5),
        (os.path.join(BASE, "run_qwen80bt_n10"), 10),
    ],
    "Gemini-Flash-Lite": [
        (os.path.join(BASE, "run_geminiflashlite_n5"), 5),
        (os.path.join(BASE, "run_geminiflashlite_n10"), 10),
    ],
    "GPT-4o-mini": [
        (os.path.join(BASE, "run_gpt4omini_n5"), 5),
        (os.path.join(BASE, "run_gpt4omini_n10"), 10),
    ],
    "DeepSeek-R1-32B": [
        (os.path.join(BASE, "run_deepseekr1_32b_n5"), 5),
        (os.path.join(BASE, "run_deepseekr1_32b_n10"), 10),
    ],
    "Gemma-4-31B": [
        (os.path.join(BASE, "run_gemma31b_n5"), 5),
        (os.path.join(BASE, "run_gemma31b_n10"), 10),
    ],
}

SCORE_KEYS = ["relevance", "uniqueness", "local_importance", "overall"]
SCORE_LABELS = {
    "relevance":       "Relevance",
    "uniqueness":      "Uniqueness",
    "local_importance": "Importance",
    "overall":         "Overall",
}
K = 3


def run_model(model_name: str, run_specs: list[tuple[str, int]]) -> dict:
    print(f"\n  {model_name}")
    all_responses = []
    for run_dir, n_agents in run_specs:
        resps = load_responses(run_dir)
        all_responses.extend(resps)
    print(f"    {len(all_responses)} total responses")

    units_map, scores_map = reconstruct(all_responses)
    print(f"    {len(units_map)} (instance, agent) pairs with extracted units")

    all_records = []
    inst_records_by_id = {}
    for n_agents in set(na for _, na in run_specs):
        instances = load_silobench(n_agents_filter=n_agents)
        for inst in instances:
            recs = analyze_instance(inst, units_map, scores_map)
            if recs:
                all_records.extend(recs)
                inst_records_by_id[inst["id"]] = recs

    n_total = len(all_records)
    n_gold = sum(r["gold_label"] for r in all_records)
    print(f"    {n_total} units, {n_gold} gold critical ({100*n_gold/max(1,n_total):.1f}%)")

    labels_all = [r["gold_label"] for r in all_records]
    results = {"n_units": n_total, "n_gold": n_gold, "scores": {}}

    for sk in SCORE_KEYS:
        scores_all = [r[sk] for r in all_records]
        auc = _safe_auc(labels_all, scores_all)
        rho = _safe_spearman(labels_all, scores_all)
        pk_list, rk_list = [], []
        for recs in inst_records_by_id.values():
            pk, rk = precision_recall_at_k(recs, sk, K)
            pk_list.append(pk)
            rk_list.append(rk)
        mean_pk = sum(pk_list) / len(pk_list) if pk_list else 0.0
        mean_rk = sum(rk_list) / len(rk_list) if rk_list else 0.0
        results["scores"][sk] = {
            "auc": auc, "spearman": rho,
            f"p_at_{K}": mean_pk, f"r_at_{K}": mean_rk,
        }

    return results


def main():
    print("Multi-model local importance analysis (n5+n10 combined):")
    all_model_results = {}
    for model_name, run_specs in MODELS.items():
        all_model_results[model_name] = run_model(model_name, run_specs)

    # Print comparison table
    print(f"\n{'='*80}")
    print("Multi-Model Local Importance Analysis — Silo-Bench (n5+n10 combined)")
    print(f"{'='*80}\n")
    print(f"{'Score':<14}", end="")
    for model_name in MODELS:
        label = model_name[:12]
        print(f"  {label:>12} AUC  Spearman", end="")
    print()
    print("-" * (14 + 25 * len(MODELS)))

    for sk in SCORE_KEYS:
        print(f"{SCORE_LABELS[sk]:<14}", end="")
        for model_name in MODELS:
            r = all_model_results[model_name]["scores"][sk]
            auc = r["auc"]
            rho = r["spearman"]
            auc_s = f"{auc:.3f}" if auc is not None else " N/A"
            rho_s = f"{rho:+.3f}" if rho is not None else "  N/A"
            print(f"  {auc_s:>16} {rho_s:>8}", end="")
        print()

    # Compact comparison (AUC only)
    print(f"\n{'='*60}")
    print("AUC comparison (Uniqueness > Others pattern):")
    print(f"{'Score':<14} {'Qwen-235B':>10} {'Mistral-S':>10} {'Qwen-80B-T':>11}")
    print("-" * 48)
    for sk in SCORE_KEYS:
        vals = []
        for model_name in MODELS:
            auc = all_model_results[model_name]["scores"][sk]["auc"]
            vals.append(f"{auc:.3f}" if auc is not None else " N/A")
        print(f"{SCORE_LABELS[sk]:<14} {vals[0]:>10} {vals[1]:>10} {vals[2]:>11}")

    # Save
    out_path = os.path.join(BASE, "local_importance_multimodel.json")
    with open(out_path, "w") as f:
        json.dump(all_model_results, f, indent=2)
    print(f"\nSaved to: {out_path}")

    # LaTeX snippet for appendix
    print("\n=== LaTeX rows for multi-model local importance table ===")
    for model_name in MODELS:
        print(f"\n% {model_name}")
        for sk in SCORE_KEYS:
            r = all_model_results[model_name]["scores"][sk]
            auc = r["auc"]
            rho = r["spearman"]
            pk = r[f"p_at_{K}"]
            rk = r[f"r_at_{K}"]
            auc_s = f"{auc:.3f}" if auc is not None else "---"
            rho_s = f"{rho:+.3f}" if rho is not None else "---"
            label = SCORE_LABELS[sk]
            print(f"    {label:<14} & {auc_s} & {rho_s} & {pk:.3f} & {rk:.3f} \\\\")


if __name__ == "__main__":
    main()
