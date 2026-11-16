#!/usr/bin/env python3
"""Compare the saved Gemini-terminal arm with the one-agent Gemini-middle arm."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from scripts.prepare_exact_span_review import SETTINGS
from src.audit.critical_fact_validation import load_jsonl


ROOT = Path("experiments/repair/results/aggregation_stage_swap_20260926")


def interval(values: list[float], *, seed: int = 42, draws: int = 2000) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(draws))
    return means[int(0.025 * (draws - 1))], means[int(0.975 * (draws - 1))]


def cluster_interval(rows: list[dict], *, seed: int = 42, draws: int = 2000) -> tuple[float, float]:
    """Resample benchmark instances, retaining their repeated baseline-model rows."""
    clusters = defaultdict(list)
    for row in rows:
        clusters[(row["dataset"], row["instance_id"])].append(row["terminal_minus_middle"])
    keys = list(clusters)
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        sampled = [clusters[rng.choice(keys)] for _ in keys]
        means.append(sum(sum(group) for group in sampled) / sum(len(group) for group in sampled))
    means.sort()
    return means[int(0.025 * (draws - 1))], means[int(0.975 * (draws - 1))]


def main() -> None:
    with (ROOT / "cohort.csv").open(encoding="utf-8") as handle:
        cohort = list(csv.DictReader(handle))
    by_key = {(r["source_id"], r["instance_id"]): r for r in cohort}
    if len(by_key) != len(cohort) or len(cohort) != 326:
        raise ValueError("Unexpected frozen cohort")
    outcomes = {}
    for setting in SETTINGS:
        path = ROOT / f"run_{setting}" / "per_instance_results.jsonl"
        if not path.exists():
            raise FileNotFoundError(path)
        for row in load_jsonl(path):
            key = (row["source_id"], row["instance_id"])
            if key in outcomes or key not in by_key:
                raise ValueError(f"Duplicate or unknown middle result: {key}")
            outcomes[key] = row
    if set(outcomes) != set(by_key):
        raise ValueError(f"Missing middle outcomes: {len(set(by_key) - set(outcomes))}")
    if any(not row["middle_success"] for row in outcomes.values()):
        raise ValueError("Failed middle responses remain; retry before summarizing")
    rows = []
    for key, frozen in by_key.items():
        middle = outcomes[key]
        if int(frozen["selected_middle_agent"]) != middle["selected_middle_agent"]:
            raise ValueError(f"Selected agent changed for {key}")
        rows.append({
            **frozen,
            "middle_gemini_prediction": middle["middle_prediction"],
            "middle_gemini_score": middle["middle_gemini_score"],
            "middle_prompt_sha256": middle["middle_prompt_sha256"],
            "terminal_minus_middle": float(frozen["terminal_gemini_score"]) - float(middle["middle_gemini_score"]),
        })
    with (ROOT / "comparison_per_case.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["setting"]].append(row)
    task_settings = {
        "MuSiQue": ("gemma31b_musique", "gpt4omini_musique", "qwen235b_musique"),
        "Silo-Bench, 5 agents": ("gemma31b_silobench_n5", "gpt4omini_silobench_n5", "qwen235b_silobench_n5"),
        "Silo-Bench, 10 agents": ("gemma31b_silobench_n10", "gpt4omini_silobench_n10", "qwen235b_silobench_n10"),
    }
    lines = [
        "# Full aggregation model-placement comparison", "",
        "All 326 frozen `aggregation_gap` cases from the revised decision sheets are included. The original and Gemini-terminal results were saved earlier; the Gemini-middle arm replaces only one preselected agent's extracted units and uses the original model for final aggregation.", "",
        "## Paper version: task averages across models", "",
        "Each task score is the unweighted mean of its three baseline-model means. `N` counts selected cases across those models. MuSiQue uses answer F1; Silo-Bench uses exact match.", "",
        "| Task | N | Original | Gemini terminal | Gemini one-agent middle | Terminal − middle |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for task, settings in task_settings.items():
        means = [
            {field: sum(float(row[field]) for row in grouped[setting]) / len(grouped[setting])
             for field in ("original_score", "terminal_gemini_score", "middle_gemini_score")}
            for setting in settings
        ]
        original = sum(item["original_score"] for item in means) / len(means)
        terminal = sum(item["terminal_gemini_score"] for item in means) / len(means)
        middle = sum(item["middle_gemini_score"] for item in means) / len(means)
        n_cases = sum(len(grouped[setting]) for setting in settings)
        lines.append(f"| {task} | {n_cases} | {original:.3f} | {terminal:.3f} | {middle:.3f} | {terminal-middle:+.3f} |")
    lines += [
        "", "## Setting-level diagnostic table", "",
        "| Setting | N | Original | Gemini terminal | Gemini one-agent middle | Terminal − middle [95% CI] | Terminal better / tied / worse |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    aggregate = []
    for setting in SETTINGS:
        group = grouped[setting]
        deltas = [row["terminal_minus_middle"] for row in group]
        low, high = interval(deltas)
        original = sum(float(row["original_score"]) for row in group) / len(group)
        terminal = sum(float(row["terminal_gemini_score"]) for row in group) / len(group)
        middle = sum(float(row["middle_gemini_score"]) for row in group) / len(group)
        wins = sum(delta > 0 for delta in deltas)
        ties = sum(delta == 0 for delta in deltas)
        losses = sum(delta < 0 for delta in deltas)
        mean = sum(deltas) / len(deltas)
        lines.append(f"| {setting} | {len(group)} | {original:.3f} | {terminal:.3f} | {middle:.3f} | {mean:+.3f} [{low:+.3f}, {high:+.3f}] | {wins} / {ties} / {losses} |")
        aggregate.extend(group)
    deltas = [row["terminal_minus_middle"] for row in aggregate]
    low, high = cluster_interval(aggregate)
    lines.append(f"| **All settings** | **{len(aggregate)}** | {sum(float(r['original_score']) for r in aggregate)/len(aggregate):.3f} | {sum(float(r['terminal_gemini_score']) for r in aggregate)/len(aggregate):.3f} | {sum(float(r['middle_gemini_score']) for r in aggregate)/len(aggregate):.3f} | {sum(deltas)/len(deltas):+.3f} [{low:+.3f}, {high:+.3f}] | {sum(d>0 for d in deltas)} / {sum(d==0 for d in deltas)} / {sum(d<0 for d in deltas)} |")
    reviewed = [row for row in aggregate if row["review_source"].startswith("codex-source-board-review")]
    if len(reviewed) != 14:
        raise ValueError(f"Expected 14 source-to-board reviewed aggregation cases, got {len(reviewed)}")
    lines += ["", f"The 14 source-to-board reviewed cases have mean terminal score {sum(float(r['terminal_gemini_score']) for r in reviewed)/14:.3f} and mean middle score {sum(float(r['middle_gemini_score']) for r in reviewed)/14:.3f}. The other 312 retained the earlier coarse audit classification.", "",
              "The comparison uses one Gemini call in each upgraded arm, but the terminal model receives the full original board while the middle model sees only one private shard. This is a model-placement comparison under a one-Gemini-call budget. It does not by itself prove that each failure was caused by aggregation, or that the audit caused any gain. The terminal responses also predate the new middle run; stochastic decoding can contribute variation. The pooled row mixes MuSiQue answer F1 with Silo-Bench exact match; its 95% CI resamples benchmark instances as clusters because the same instance can appear under several baseline models. Per-setting CIs resample cases.", "",
              "`comparison_per_case.csv` contains every paired case, selected agent, predictions, scores, and prompt hashes. Each `run_*/` directory retains extraction and aggregation responses and the substituted board.", ""]
    (ROOT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote comparison for {len(rows)} cases to {ROOT / 'summary.md'}")


if __name__ == "__main__":
    main()
