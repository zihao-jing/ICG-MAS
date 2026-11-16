#!/usr/bin/env python3
"""Freeze the full aggregation-gap cohort and its archived terminal-Gemini arm."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from scripts.prepare_exact_span_review import ROOT, SETTINGS
from scripts.run_frozen_repair import merge_decisions, validate_manifest
from src.audit.critical_fact_validation import load_jsonl


RESULT_DIRS = (
    "gemma31b_musique_full", "gemma31b_silobench_n5_full",
    "gemma31b_silobench_n10_network", "gemma31b_silobench_n10_supplement",
    "gpt4omini_musique_full", "gpt4omini_silobench_n5_full",
    "gpt4omini_silobench_n10_full", "qwen235b_musique_full",
    "qwen235b_silobench_n5_full", "qwen235b_silobench_n10_full",
    *(f"{setting}_cross" for setting in SETTINGS),
)


def prepare() -> tuple[list[dict], list[dict]]:
    cohort = []
    for setting in SETTINGS:
        manifest = load_jsonl(ROOT / f"{setting}_review.jsonl")
        decisions = load_jsonl(ROOT / "exact_span_decisions" / f"{setting}_decisions.jsonl")
        records = merge_decisions(manifest, decisions)
        validate_manifest(records)
        cohort.extend((setting, record) for record in records if record["diagnosis"] == "aggregation_gap")
    if len(cohort) != 326:
        raise ValueError(f"Expected 326 revised aggregation cases, got {len(cohort)}")
    keys = {(r["source_id"], r["instance_id"]) for _, r in cohort}
    if len(keys) != len(cohort):
        raise ValueError("Duplicate cohort key")
    historical = {}
    for name in RESULT_DIRS:
        for row in load_jsonl(ROOT / "results" / name / "per_instance_results.jsonl"):
            key = (row["source_id"], row["instance_id"])
            if key not in keys or row["condition"] != "stronger_model":
                continue
            if key in historical or not row["success"]:
                raise ValueError(f"Duplicate or failed archived Gemini result: {key}")
            historical[key] = row
    if set(historical) != keys:
        raise ValueError(f"Missing archived Gemini outcomes: {len(keys - set(historical))}")
    rows = []
    for setting, record in cohort:
        old = historical[(record["source_id"], record["instance_id"])]
        if old["prompt_sha256"] != record["original_prompt_sha256"]:
            raise ValueError(f"Archived Gemini used a different frozen board: {record['source_id']}/{record['instance_id']}")
        # Freeze one middle-stage agent without using any intervention outcome.
        digest = hashlib.sha256(f"42:{record['source_id']}:{record['instance_id']}".encode()).digest()
        selected_agent = int.from_bytes(digest[:8], "big") % int(record["n_agents"])
        if not any(int(context["agent_id"]) == selected_agent for context in record["source_contexts"]):
            raise ValueError(f"Missing selected agent's source shard: {record['source_id']}/{record['instance_id']}")
        rows.append({
            "setting": setting,
            "source_id": record["source_id"], "dataset": record["dataset"],
            "instance_id": record["instance_id"], "n_agents": record["n_agents"],
            "selected_middle_agent": selected_agent,
            "original_model": record["original_model"], "middle_model": record["stronger_model"],
            "original_prediction": record["baseline"]["pred"],
            "original_score": record["baseline"]["f1"],
            "terminal_gemini_prediction": old["pred"], "terminal_gemini_score": old["f1"],
            "frozen_board_sha256": record["original_prompt_sha256"],
            "review_source": record["reviewed_by"],
        })
    counts = defaultdict(lambda: {"cases": 0, "agent_cases": 0})
    for row in rows:
        counts[row["setting"]]["cases"] += 1
        counts[row["setting"]]["agent_cases"] += row["n_agents"]
    summary = [
        {"setting": setting, "cases": counts[setting]["cases"],
         "gemini_extraction_calls": counts[setting]["cases"],
         "original_terminal_calls": counts[setting]["cases"],
         "total_new_calls": 2 * counts[setting]["cases"]}
        for setting in SETTINGS
    ]
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = prepare()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "cohort.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plan = {
        "cohort": "all revised aggregation_gap records from three baseline models and nine settings",
        "n_cases": len(rows),
        "n_agent_cases": sum(row["n_agents"] for row in rows),
        "new_calls": sum(row["total_new_calls"] for row in summary),
        "existing_terminal_gemini_cases": len(rows),
        "middle_arm": "One Gemini extraction call for the SHA-256-selected agent; replace only that agent's original board units; original model terminal aggregation",
        "agent_selection": "SHA-256 of seed 42, source_id, instance_id modulo n_agents; fixed before the new outcomes",
        "scoring": "No rescoring calls: the original pipeline extracts at most three units and transmits all three; new units keep extraction order",
        "terminal_arm": "archived Gemini terminal aggregation on the original frozen board",
        "original_arm": "saved original run on the same selected cases",
        "selection_limit": "312 cases have only coarse audit diagnosis; 14 were source-to-board reviewed. Report them separately.",
        "comparison_limit": "The archived terminal arm and new middle arm run at different times. One upgraded agent sees only one shard, whereas the upgraded terminal sees the full board; interpret this as a one-Gemini-call budget comparison.",
        "settings": summary,
    }
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_cases": plan["n_cases"], "new_calls": plan["new_calls"]}, indent=2))


if __name__ == "__main__":
    main()
