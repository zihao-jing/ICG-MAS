#!/usr/bin/env python3
"""
Combine n5+n10 bottleneck results for the 4 new models and print
the LaTeX rows for app_bottleneck_multimodel.tex.
"""

from __future__ import annotations
import json, os, sys

BASE = os.path.join(os.path.dirname(__file__), "..", "results")

VARIANTS = [
    "none",
    "remove_1_critical",
    "remove_2_critical",
    "remove_random_distractor",
    "remove_redundant_support",
]

NEW_MODELS = {
    "Gemini-Flash-Lite": "geminiflashlite",
    "GPT-4o-mini":       "gpt4omini",
    "DeepSeek-R1-32B":   "deepseekr1_32b",
    "Gemma-4-31B":       "gemma31b",
}


def load_acc(short: str, split: str) -> dict[str, float] | None:
    path = os.path.join(BASE, f"bottleneck_{short}_{split}", "bottleneck_results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        d = json.load(f)
    return {v: d["table"][v]["acc"] * 100 for v in VARIANTS}


def combine(a: dict, b: dict) -> dict[str, float]:
    return {v: (a[v] + b[v]) / 2 for v in VARIANTS}


def delta_str(baseline: float, val: float) -> str:
    diff = val - baseline
    rel = 100 * diff / baseline if baseline != 0 else 0
    sign = "$-$" if diff < 0 else "$+$"
    return f"{val:.1f} \\footnotesize{{({sign}{abs(diff):.1f}, {sign}{abs(rel):.0f}\\%)}}"


def main():
    print("=== Combined n5+n10 Bottleneck Results for New Models ===\n")
    all_results = {}
    for label, short in NEW_MODELS.items():
        n5 = load_acc(short, "n5")
        n10 = load_acc(short, "n10")
        if n5 is None and n10 is None:
            print(f"{label}: NO DATA (both n5 and n10 missing)")
            continue
        elif n5 is None:
            print(f"{label}: n5 missing — using n10 only")
            combined = n10
        elif n10 is None:
            print(f"{label}: n10 missing — using n5 only")
            combined = n5
        else:
            combined = combine(n5, n10)
        all_results[label] = combined

        baseline = combined["none"]
        print(f"{label} (baseline={baseline:.1f}%):")
        for v in VARIANTS:
            print(f"  {v:<30}: {combined[v]:.1f}%")
        print()

    print("\n=== LaTeX rows (for tab:bottleneck_multimodel) ===\n")
    for label, combined in all_results.items():
        baseline = combined["none"]
        r1c = combined["remove_1_critical"]
        r2c = combined["remove_2_critical"]
        rdist = combined["remove_random_distractor"]
        rred = combined["remove_redundant_support"]
        row = (
            f"{label} & {baseline:.1f} "
            f"& {delta_str(baseline, r1c)} "
            f"& {delta_str(baseline, r2c)} "
            f"& {rdist:.1f} & {rred:.1f} \\\\"
        )
        print(row)


if __name__ == "__main__":
    main()
