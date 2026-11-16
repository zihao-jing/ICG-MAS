#!/usr/bin/env python3
"""Render all reviewed repair cases with their exact source and board text."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from scripts.run_frozen_repair import correction_text


ROOT = Path("iclr2027_paper/experiments/repair/exact_span_review")


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "labeled_evidence_gaps.jsonl").read_text(encoding="utf-8").splitlines()]
    lines = [
        "# Reviewed evidence cases",
        "",
        "All 20 original audit candidates are shown below. Six have source excerpts for exact repair; 14 are reclassified as aggregation gaps. Source and transmitted board text are reproduced from the frozen manifests.",
        "",
        "| # | Setting | Case | Revised diagnosis | Source spans | Appended corrections |",
        "| ---: | --- | --- | --- | ---: | ---: |",
    ]
    for index, row in enumerate(rows, 1):
        lines.append(f"| {index} | {row['source_id']} | {row['instance_id']} | {row['revised_diagnosis']} | {len(row['missing_facts'])} | {len(row.get('board_corrections', []))} |")
    for index, row in enumerate(rows, 1):
        lines += [
            "",
            f"## {index}. {row['source_id']} / {row['instance_id']}",
            "",
            f"**Diagnosis:** {row['revised_diagnosis']}. **Gold answer:** `{row['gold_answer']}`.",
            "",
            f"**Review:** {row['review_note']}",
            "",
            "### Task question",
            "",
            "```text",
            row["question"],
            "```",
            "",
            "### Exact excerpts selected for restoration",
            "",
        ]
        if row["missing_facts"]:
            for fact in row["missing_facts"]:
                lines += [
                    f"Source `{fact['source_context_id']}`:",
                    "",
                    "```text",
                    fact["text"],
                    "```",
                    "",
                ]
        else:
            lines += ["None; the source data needed for this task are already on the board.", ""]
        lines += ["### Corrections appended after source excerpts", ""]
        if row.get("board_corrections"):
            for correction in row["board_corrections"]:
                lines += [
                    f"Original board unit `{correction['corrects_unit_id']}`; source `{correction['source_context_id']}`:",
                    "",
                    "```text",
                    correction_text(row, correction),
                    "```",
                    "",
                ]
        else:
            lines += ["None.", ""]
        board_by_agent: dict[int, list[str]] = defaultdict(list)
        for unit in row["board_units"]:
            board_by_agent[int(unit["agent_id"])].append(str(unit["text"]))
        lines += ["### Source and transmitted board by agent", ""]
        for support in row["source_supports"]:
            agent = int(support["agent_id"])
            lines += [
                f"#### Agent {agent}",
                "",
                "Source:",
                "",
                "```text",
                str(support["text"]),
                "```",
                "",
                "Transmitted board units:",
                "",
                "```text",
                "\n".join(f"{i+1}. {text}" for i, text in enumerate(board_by_agent[agent])),
                "```",
                "",
            ]
    output = ROOT / "casebook.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(rows)} cases to {output}")


if __name__ == "__main__":
    main()
