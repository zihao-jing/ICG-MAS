#!/usr/bin/env python3
"""Export source-grounded review sheets without inventing missing facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.compute_audit_metrics import align_gold_to_transmitted
from scripts.run_frozen_repair import merge_decisions
from src.audit.critical_fact_validation import load_jsonl


ROOT = Path("experiments/repair")
SETTINGS = (
    "gemma31b_musique", "gemma31b_silobench_n5", "gemma31b_silobench_n10",
    "gpt4omini_musique", "gpt4omini_silobench_n5", "gpt4omini_silobench_n10",
    "qwen235b_musique", "qwen235b_silobench_n5", "qwen235b_silobench_n10",
)


def review_row(record: dict) -> dict:
    supports = record["source_supports"]
    board = record["board_units"]
    alignments = align_gold_to_transmitted(
        [(int(support["agent_id"]), str(support["text"])) for support in supports],
        [str(unit["text"]) for unit in board],
    )
    return {
        "source_id": record["source_id"],
        "instance_id": record["instance_id"],
        "dataset": record["dataset"],
        "current_diagnosis": record["diagnosis"],
        "question": record["question"],
        "gold_answer": record["gold_answer"],
        "original_prediction": record["baseline"]["pred"],
        "audit_hint": record["audit_hint"],
        "board_units": board,
        "source_contexts": record["source_contexts"],
        "source_supports": supports,
        "coarse_audit_matches": [
            {
                "support_id": support["support_id"],
                "agent_id": support["agent_id"],
                "covered_by_proxy": match["covered"],
                "overlap_score": match["score"],
                "best_board_unit": match["best_unit"],
            }
            for support, match in zip(supports, alignments)
        ],
        "revised_diagnosis": "",
        "missing_facts": [],
        "reviewed_by": "",
        "review_note": "",
        "instructions": (
            "If evidence is missing, set revised_diagnosis=evidence_gap and quote each exact "
            "missing substring from one source_contexts.text. For each missing_facts entry "
            "record text, source_context_id, and verified_by. Otherwise set "
            "revised_diagnosis=aggregation_gap. The coarse audit matches are overlap hints, "
            "not atomic evidence labels."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="Replace existing review sheets")
    args = parser.parse_args()
    existing_evidence = []
    gemma_n5_failures = []
    for setting in SETTINGS:
        records = merge_decisions(
            load_jsonl(ROOT / f"{setting}_review.jsonl"),
            load_jsonl(ROOT / "all_run_decisions" / f"{setting}_decisions.jsonl"),
        )
        for record in records:
            if record["diagnosis"] == "evidence_gap":
                existing_evidence.append(review_row(record))
            if setting == "gemma31b_silobench_n5" and not record["baseline"]["correct"]:
                gemma_n5_failures.append(review_row(record))
    output = ROOT / "exact_span_review"
    output.mkdir(parents=True, exist_ok=True)
    sheets = (("existing_evidence_gaps.jsonl", existing_evidence),
              ("gemma_n5_failures.jsonl", gemma_n5_failures))
    existing_paths = [output / name for name, _ in sheets if (output / name).exists()]
    if existing_paths and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite review annotations: {existing_paths}")
    for name, rows in sheets:
        path = output / name
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        print(f"{path}: {len(rows)} cases")


if __name__ == "__main__":
    main()
