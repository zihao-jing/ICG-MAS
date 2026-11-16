#!/usr/bin/env python3
"""Record reviewed, verbatim source excerpts for the 20 Silo-Bench cases."""

from __future__ import annotations

import ast
import argparse
import json
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path("experiments/repair/exact_span_review")
INPUT = ROOT / "existing_evidence_gaps.jsonl"
OUTPUT = ROOT / "labeled_evidence_gaps.jsonl"
REVIEWER = "codex-source-board-review-2026-09-26"

EVIDENCE_CASES = {
    ("gemma31b_silobench_n10", "III-25_n10"),
    ("qwen235b_n5", "I-02_n5"),
    ("qwen235b_n10", "I-02_n10"),
    ("qwen235b_n10", "I-07_n10"),
    ("qwen235b_n10", "I-10_n10"),
    ("qwen235b_n10", "III-25_n10"),
}


def omitted_item_spans(source: str, board: str, *, points: bool) -> tuple[list[str], int]:
    """Return maximal contiguous runs of source list elements absent on board."""
    expression = ast.parse(source, mode="eval").body
    if not isinstance(expression, ast.List):
        raise ValueError("Expected a source list")
    missing = []
    for index, item in enumerate(expression.elts):
        raw = source[item.col_offset:item.end_col_offset]
        if points:
            if not isinstance(item, ast.List) or len(item.elts) != 2:
                raise ValueError("Expected 2D source points")
            needle = ", ".join(source[part.col_offset:part.end_col_offset] for part in item.elts)
        else:
            needle = raw
        if needle not in board:
            missing.append(index)
    runs: list[list[int]] = []
    for index in missing:
        if not runs or index != runs[-1][-1] + 1:
            runs.append([index])
        else:
            runs[-1].append(index)
    spans = [
        source[expression.elts[run[0]].col_offset:expression.elts[run[-1]].end_col_offset]
        for run in runs
    ]
    return spans, len(missing)


def label(row: dict) -> dict:
    row = dict(row)
    key = (row["source_id"], row["instance_id"])
    board_by_agent: dict[int, list[str]] = defaultdict(list)
    for unit in row["board_units"]:
        board_by_agent[int(unit["agent_id"])].append(str(unit["text"]))
    supports = {int(support["agent_id"]): str(support["text"])
                for support in row["source_supports"]}
    facts = []
    corrections = []
    details = []
    if key in EVIDENCE_CASES:
        if row["instance_id"].startswith("I-02"):
            # A complete local list supports corrections to derived counts and lengths.
            for agent, source in sorted(supports.items()):
                values = ast.literal_eval(source)
                units = [unit for unit in row["board_units"] if int(unit["agent_id"]) == agent]
                count_unit = next((unit for unit in units if re.search(r'\b(?:appears|appearing)\s+\d+\s+times\b', unit["text"])), None)
                if count_unit is None:
                    raise ValueError(f"Missing transmitted local count: {key}, agent {agent}")
                claimed = int(re.search(r'\b(?:appears|appearing)\s+(\d+)\s+times\b', count_unit["text"]).group(1))
                actual = values.count("apple")
                distorted = claimed != actual
                if distorted:
                    corrections.append({"kind": "word_count", "source_context_id": f"agent-{agent}",
                                        "corrects_unit_id": count_unit["unit_id"], "incorrect_value": str(claimed),
                                        "correct_value": str(actual), "verified_by": REVIEWER})
                    details.append(f"agent {agent}: source apple count {actual}, board count {claimed}")
                length_unit = next((unit for unit in units if re.search(r'\b(?:containing|contains)\s+\d+\s+(?:items|elements)\b', unit["text"])), None)
                if length_unit:
                    length_match = re.search(r'\b(?:containing|contains)\s+(\d+)\s+(?:items|elements)\b', length_unit["text"])
                    stated_length = int(length_match.group(1))
                    if stated_length != len(values):
                        corrections.append({"kind": "item_count", "source_context_id": f"agent-{agent}",
                                            "corrects_unit_id": length_unit["unit_id"], "incorrect_value": str(stated_length),
                                            "correct_value": str(len(values)), "verified_by": REVIEWER})
                        details.append(f"agent {agent}: source list length {len(values)}, board length {stated_length}")
                        distorted = True
                if distorted:
                    facts.append({"text": source, "source_context_id": f"agent-{agent}",
                                  "verified_by": REVIEWER})
        else:
            points = row["instance_id"].startswith("III-25")
            for agent, source in sorted(supports.items()):
                board = " ".join(board_by_agent[agent])
                spans, count = omitted_item_spans(source, board, points=points)
                for span in spans:
                    facts.append({"text": span, "source_context_id": f"agent-{agent}",
                                  "verified_by": REVIEWER})
                if count:
                    details.append(f"agent {agent}: {count} omitted {'points' if points else 'values'} in {len(spans)} source spans")
            if row["instance_id"].startswith("I-07"):
                for agent, source in sorted(supports.items()):
                    values = ast.literal_eval(source)
                    actual_sum = sum((Decimal(str(value)) for value in values), Decimal(0)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP)
                    for unit in row["board_units"]:
                        if int(unit["agent_id"]) != agent:
                            continue
                        match = re.search(r'\b(?:local sum|sum of the numbers)\b[^.]*?\b(\d+\.\d{2})\b', unit["text"], re.I)
                        if match is None:
                            continue
                        claimed = Decimal(match.group(1))
                        if claimed != actual_sum:
                            corrections.append({"kind": "local_sum", "source_context_id": f"agent-{agent}",
                                                "corrects_unit_id": unit["unit_id"], "incorrect_value": str(claimed),
                                                "correct_value": str(actual_sum), "verified_by": REVIEWER})
                            details.append(f"agent {agent}: source local sum {actual_sum}, board sum {claimed}")
        if not facts:
            raise ValueError(f"Evidence case has no missing or distorted source data: {key}")
        row["revised_diagnosis"] = "evidence_gap"
        row["missing_facts"] = facts
        row["board_corrections"] = corrections
        row["review_note"] = "Source-to-board review: " + "; ".join(details)
        if corrections:
            row["review_note"] += "; source-verified corrections are appended after exact source excerpts"
    else:
        for agent, source in supports.items():
            board = " ".join(board_by_agent[agent])
            if row["instance_id"].startswith("III-25"):
                _, count = omitted_item_spans(source, board, points=True)
                if count:
                    raise ValueError(f"Uncovered point in aggregation case {key}, agent {agent}")
            elif row["instance_id"].startswith("I-02"):
                raise ValueError(f"Unexpected word-count aggregation case: {key}")
            elif source not in board:
                raise ValueError(f"Source data missing in aggregation case {key}, agent {agent}")
        row["revised_diagnosis"] = "aggregation_gap"
        row["missing_facts"] = []
        row["board_corrections"] = []
        row["review_note"] = "Source-to-board review: all answer-relevant raw source data are already transmitted; no source span to restore."
    row["reviewed_by"] = REVIEWER
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="Regenerate the derived label file")
    args = parser.parse_args()
    if OUTPUT.exists() and not args.overwrite:
        raise FileExistsError(OUTPUT)
    rows = [label(json.loads(line)) for line in INPUT.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 20 or sum(row["revised_diagnosis"] == "evidence_gap" for row in rows) != 6:
        raise ValueError("Unexpected review counts")
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"Wrote {len(rows)} reviewed cases: 6 evidence gaps, 14 aggregation gaps: {OUTPUT}")


if __name__ == "__main__":
    main()
