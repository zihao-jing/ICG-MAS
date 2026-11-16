#!/usr/bin/env python3
"""Combine completed frozen-prompt repair runs without pooling model settings."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from scripts.run_frozen_repair import _bootstrap_ci, summarize
from src.audit.critical_fact_validation import load_jsonl


def combine_run_dirs(run_dirs: list[Path]) -> dict:
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for run_dir in run_dirs:
        result_path = run_dir / "per_instance_results.jsonl"
        if not result_path.is_file():
            raise FileNotFoundError(result_path)
        for row in load_jsonl(result_path):
            key = (row["source_id"], row["instance_id"], row["condition"])
            if key in seen:
                raise ValueError(f"Duplicate result across runs: {key}")
            seen.add(key)
            rows.append(row)

    paired = summarize(rows)
    by_arm: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_arm[(row["source_id"], row["diagnosis"], row["condition"])].append(row)
    arm_summaries = []
    for (source_id, diagnosis, condition), group in sorted(by_arm.items()):
        successful = [row for row in group if row["success"]]
        first = group[0]
        arm_summaries.append({
            "source_id": source_id,
            "dataset": first["dataset"],
            "original_model": first.get("original_model", ""),
            "n_agents": first.get("n_agents") if first["dataset"] == "silobench" else None,
            "diagnosis": diagnosis,
            "condition": condition,
            "n_attempted": len(group),
            "n_successful": len(successful),
            "n_failed": len(group) - len(successful),
            "mean_score_successful": (
                sum(float(row["f1"]) for row in successful) / len(successful)
                if successful else None
            ),
            "total_llm_tokens": sum(int(row["total_llm_tokens"]) for row in group),
        })
    by_case: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for row in rows:
        by_case[(row["source_id"], row["instance_id"])][row["condition"]] = row
    crossed_groups: dict[tuple[str, str], list[tuple[dict, dict]]] = defaultdict(list)
    for case in by_case.values():
        first = next(iter(case.values()))
        if first["diagnosis"] == "baseline_correct":
            continue
        source_arm = "gold_support_repair" if first["dataset"] == "musique" else "source_shard_repair"
        model_row, source_row = case.get("stronger_model"), case.get(source_arm)
        if model_row is None or source_row is None or not model_row["success"] or not source_row["success"]:
            continue
        if float(model_row["baseline_f1"]) != float(source_row["baseline_f1"]):
            raise ValueError("Crossed arms have different cached original scores")
        crossed_groups[(first["source_id"], first["diagnosis"])].append((model_row, source_row))
    crossed_summaries = []
    for (source_id, diagnosis), pairs in sorted(crossed_groups.items()):
        model_deltas = [float(model["f1"]) - float(model["baseline_f1"]) for model, _ in pairs]
        source_deltas = [float(source["f1"]) - float(source["baseline_f1"]) for _, source in pairs]
        head_to_head = [float(model["f1"]) - float(source["f1"]) for model, source in pairs]
        first = pairs[0][0]
        n = len(pairs)
        crossed_summaries.append({
            "source_id": source_id,
            "dataset": first["dataset"],
            "original_model": first["original_model"],
            "n_agents": first["n_agents"] if first["dataset"] == "silobench" else None,
            "diagnosis": diagnosis,
            "n_paired": n,
            "mean_original_score": sum(float(model["baseline_f1"]) for model, _ in pairs) / n,
            "mean_model_score": sum(float(model["f1"]) for model, _ in pairs) / n,
            "mean_source_score": sum(float(source["f1"]) for _, source in pairs) / n,
            "model_gain_vs_original": sum(model_deltas) / n,
            "model_gain_95ci": _bootstrap_ci(model_deltas),
            "source_gain_vs_original": sum(source_deltas) / n,
            "source_gain_95ci": _bootstrap_ci(source_deltas),
            "model_minus_source": sum(head_to_head) / n,
            "model_minus_source_95ci": _bootstrap_ci(head_to_head),
        })
    expected_crossed = sum(
        next(iter(case.values()))["diagnosis"] != "baseline_correct"
        for case in by_case.values()
    )
    if sum(row["n_paired"] for row in crossed_summaries) != expected_crossed:
        raise ValueError("Every failure case needs successful results for both crossover interventions")
    return {
        "schema_version": "frozen-repair-matrix-v2",
        "n_run_dirs": len(run_dirs),
        "n_result_rows": len(rows),
        "n_instances": paired["n_instances"],
        "paired_summaries": paired["summaries"],
        "crossed_summaries": crossed_summaries,
        "arm_summaries": arm_summaries,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Exploratory whole-source augmentation results",
        "",
        "These historical source arms appended entire benchmark supports or input shards. They are not exact missing-span repair and must not be used as evidence that a specific omitted fact caused failure.",
        "",
        f"Combined {report['n_instances']} unique instances from {report['n_run_dirs']} run directories.",
        "Scores are exact match for Silo-Bench and answer F1 for MuSiQue. Differences compare each intervention with the cached original answer on the same cases.",
        "",
        "## Crossover comparisons",
        "",
        "| Setting | Diagnosis | N | Original | Gemini score (gain) | Whole-source score (gain) | Gemini − whole source [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["crossed_summaries"]:
        ci = row["model_minus_source_95ci"]
        lines.append(
            f"| {row['source_id']} | {row['diagnosis']} | {row['n_paired']} | "
            f"{row['mean_original_score']:.3f} | "
            f"{row['mean_model_score']:.3f} ({row['model_gain_vs_original']:+.3f}) | "
            f"{row['mean_source_score']:.3f} ({row['source_gain_vs_original']:+.3f}) | "
            f"{row['model_minus_source']:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] |"
        )
    lines += [
        "",
        "## API outcomes",
        "",
        "| Setting | Diagnosis | Arm | Attempted | Successful | Failed | Total model tokens |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report["arm_summaries"]:
        lines.append(
            f"| {row['source_id']} | {row['diagnosis']} | {row['condition']} | "
            f"{row['n_attempted']} | {row['n_successful']} | {row['n_failed']} | {row['total_llm_tokens']} |"
        )
    lines += [
        "",
        "## Interpretation notes",
        "",
        "- Case classes were accepted through a single user confirmation and remain tied to the cached lexical audit hints; the decision sheets do not contain independent per-case semantic annotations.",
        "- Silo-Bench source-shard repair appends all original task shards. It is a source-restoration test, not an atomic-fact repair. MuSiQue has no lexical evidence-gap cases in this run.",
        "- Gemini changes only the aggregation model. The historical whole-source arm appended every gold supporting paragraph on MuSiQue or every original input shard on Silo-Bench while keeping the original model. The original aggregation prompt and generation settings remained fixed.",
        "- The current runner requires exact, explicitly annotated missing source spans for a new evidence-repair run; none of the historical whole-source responses satisfy that definition.",
        "- Repair cases were selected from original failures. Silo-Bench exact match is binary, so their original-run scores are zero by construction; MuSiQue token F1 can give partial credit to an incorrect answer.",
        "- These original-run comparisons show recovery on selected failures. Because selection used the original outcome and decoding is stochastic, the difference can include run-to-run variation; exact replay remains in the per-case results and combined JSON as a diagnostic.",
        "- Failed API arms are omitted from paired comparisons and shown in the API outcomes table.",
        "- The CSV files retain separate 95% bootstrap intervals for each gain versus the original run. The table shows the paired Gemini-versus-source interval to make the intervention comparison visible.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true", help="Replace generated summary files in an existing output directory")
    args = parser.parse_args()
    report = combine_run_dirs(args.runs)
    args.output.mkdir(parents=True, exist_ok=args.overwrite)
    (args.output / "combined_results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "summary.md").write_text(render_markdown(report), encoding="utf-8")
    paired_columns = (
        "source_id", "dataset", "original_model", "n_agents", "diagnosis", "condition",
        "n_paired", "mean_original_score", "mean_arm_score", "mean_original_delta",
        "original_delta_95ci", "original_improved", "original_worsened", "original_tied",
    )
    exports = (
        ([{key: row[key] for key in paired_columns} for row in report["paired_summaries"]], "paired_comparisons.csv"),
        (report["crossed_summaries"], "crossover_comparisons.csv"),
        (report["arm_summaries"], "arm_scores.csv"),
    )
    for entries, filename in exports:
        if entries:
            with (args.output / filename).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(entries[0]))
                writer.writeheader()
                writer.writerows(entries)
    print(f"Combined {report['n_instances']} instances from {report['n_run_dirs']} runs into {args.output}")


if __name__ == "__main__":
    main()
