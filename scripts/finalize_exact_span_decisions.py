#!/usr/bin/env python3
"""Turn completed exact-span review sheets into validated decision files."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.prepare_exact_span_review import ROOT, SETTINGS
from scripts.run_frozen_repair import merge_decisions, validate_manifest
from src.audit.critical_fact_validation import load_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    review_dir = ROOT / "exact_span_review"
    reviews = load_jsonl(review_dir / "labeled_evidence_gaps.jsonl")
    by_key = {(row["source_id"], row["instance_id"]): row for row in reviews}
    if len(by_key) != len(reviews):
        raise ValueError("Duplicate exact-span review rows")
    incomplete = []
    for key, row in by_key.items():
        if row.get("revised_diagnosis") not in {"evidence_gap", "aggregation_gap"}:
            incomplete.append((key, "diagnosis"))
        elif not row.get("reviewed_by", "").strip() or not row.get("review_note", "").strip():
            incomplete.append((key, "reviewer/note"))
        elif row["revised_diagnosis"] == "evidence_gap" and not row.get("missing_facts"):
            incomplete.append((key, "exact missing span"))
    if incomplete:
        raise ValueError(f"{len(incomplete)} incomplete exact-span reviews; first five: {incomplete[:5]}")

    finalized = {}
    for setting in SETTINGS:
        manifest = load_jsonl(ROOT / f"{setting}_review.jsonl")
        decisions = load_jsonl(ROOT / "all_run_decisions" / f"{setting}_decisions.jsonl")
        for decision in decisions:
            key = (decision["source_id"], decision["instance_id"])
            if key not in by_key:
                continue
            review = by_key[key]
            decision.update({
                "diagnosis": review["revised_diagnosis"],
                "missing_facts": review["missing_facts"],
                "board_corrections": review.get("board_corrections", []),
                "volume_control": None,
                "reviewed_by": review["reviewed_by"],
                "review_note": review["review_note"],
            })
        validate_manifest(merge_decisions(manifest, decisions))
        finalized[setting] = decisions

    args.output.mkdir(parents=True, exist_ok=False)
    for setting, decisions in finalized.items():
        write_jsonl(args.output / f"{setting}_decisions.jsonl", decisions)
    print(f"Wrote validated exact-span decisions for {len(finalized)} settings to {args.output}")


if __name__ == "__main__":
    main()
