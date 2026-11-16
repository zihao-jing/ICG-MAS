"""Unit tests for the offline critical-fact validation workflow."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.audit.critical_fact_validation import (
    analyze_adjudicated_labels,
    build_adjudication_tasks,
    build_fact_templates,
    build_label_tasks,
    build_repair_manifest,
    _units_by_agent,
    cohen_kappa,
)


def _trace() -> dict:
    return {
        "schema_version": "critical-fact-validation-v1",
        "source_id": "mq_relay",
        "dataset": "musique",
        "protocol": "score_ranked_relay",
        "instance_id": "example-1",
        "question": "Who wrote the book?",
        "gold_answer": "Alice",
        "answer_f1": 0.0,
        "answer_correct": False,
        "sample_stratum": "error",
        "source_supports": [
            {"support_id": "agent-0", "agent_id": 0, "text": "Alice wrote the book in 1865."},
            {"support_id": "agent-1", "agent_id": 1, "text": "The book won an award."},
        ],
        "source_contexts": [
            {"context_id": "agent-0", "agent_id": 0, "text": "Alice wrote the book in 1865."},
            {"context_id": "agent-1", "agent_id": 1, "text": "The book won an award."},
        ],
        "checkpoints": {
            "source": [
                {"unit_id": "agent-0", "agent_id": 0, "text": "Alice wrote the book in 1865."},
                {"unit_id": "agent-1", "agent_id": 1, "text": "The book won an award."},
            ],
            "extraction": [
                {"unit_id": "extraction:a0:u0", "agent_id": 0, "text": "Alice wrote the book."},
                {"unit_id": "extraction:a1:u0", "agent_id": 1, "text": "The book won an award."},
            ],
            "transmission": [
                {"unit_id": "transmission:a0:u0", "agent_id": 0, "text": "Alice wrote the book."},
                {"unit_id": "transmission:a1:u0", "agent_id": 1, "text": "The book won an award."},
            ],
            "board": [
                {"unit_id": "board:a0:u0", "agent_id": 0, "text": "Alice wrote the book."},
                {"unit_id": "board:a1:u0", "agent_id": 1, "text": "The book won an award."},
            ],
        },
    }


def _facts() -> dict:
    return {
        "schema_version": "critical-fact-validation-v1",
        "source_id": "mq_relay",
        "instance_id": "example-1",
        "critical_facts": [
            {
                "fact_id": "author",
                "text": "Alice wrote the book in 1865.",
                "source_support_ids": ["agent-0"],
                "entities": ["Alice", "book"],
                "relation": "wrote",
                "values": ["1865"],
                "qualifiers": [],
            },
            {
                "fact_id": "award",
                "text": "The book won an award.",
                "source_support_ids": ["agent-1"],
                "entities": ["book"],
                "relation": "won",
                "values": [],
                "qualifiers": [],
            },
        ],
        "complete_support_sets": [["author", "award"]],
    }


def _adjudicated(tasks: list[dict], labels: dict[tuple[str, str], str]) -> list[dict]:
    records = []
    for task in tasks:
        record = dict(task)
        record["final_label"] = labels[(task["fact_id"], task["checkpoint"])]
        records.append(record)
    return records


def test_fact_template_has_empty_atomic_fact_list():
    template = build_fact_templates([_trace()])[0]
    assert template["critical_facts"] == []
    assert template["source_supports"][0]["support_id"] == "agent-0"


def test_summary_checkpoint_uses_one_message_per_agent():
    # Summary text must be wrapped as one unit before _units_by_agent is used;
    # otherwise a string is incorrectly expanded into one unit per character.
    messages = _units_by_agent({0: ["One complete summary."], 1: ["Another summary."]}, "summary")
    assert [message["text"] for message in messages] == ["One complete summary.", "Another summary."]


def test_label_tasks_are_blinded_to_model_outcome_and_matcher():
    tasks = build_label_tasks([_trace()], [_facts()])
    assert len(tasks) == 8
    assert "answer_correct" not in tasks[0]
    assert "legacy_match" not in tasks[0]
    source_task = next(task for task in tasks if task["checkpoint"] == "source" and task["fact_id"] == "author")
    assert [unit["unit_id"] for unit in source_task["evidence_units"]] == ["agent-0"]


def test_adjudication_autoresolves_agreement_and_reports_kappa():
    tasks = build_label_tasks([_trace()], [_facts()])
    first = [dict(task, label="faithful", annotator_id="a") for task in tasks]
    second = [dict(task, label="faithful", annotator_id="b") for task in tasks]
    merged, agreement = build_adjudication_tasks(first, second)
    assert all(record["final_label"] == "faithful" for record in merged)
    assert agreement["percent_agreement"] == pytest.approx(1.0)
    assert agreement["cohen_kappa"] == pytest.approx(1.0)
    assert cohen_kappa(["faithful", "absent"], ["faithful", "absent"]) == pytest.approx(1.0)


def test_analysis_requires_semantic_faithfulness_and_reports_proxy_error():
    tasks = build_label_tasks([_trace()], [_facts()])
    labels = {
        ("author", "source"): "faithful",
        ("award", "source"): "faithful",
        ("author", "extraction"): "faithful",
        ("award", "extraction"): "faithful",
        ("author", "transmission"): "partial",
        ("award", "transmission"): "faithful",
        ("author", "board"): "partial",
        ("award", "board"): "faithful",
    }
    report = analyze_adjudicated_labels([_trace()], [_facts()], _adjudicated(tasks, labels))
    source = report["sources"]["mq_relay"]
    assert source["semantic_fact_recall"]["board"] == pytest.approx(0.5)
    assert source["complete_support_coverage"]["board"]["rate"] == pytest.approx(0.0)
    # The legacy matcher accepts the overlapping author text, creating a false positive.
    assert source["lexical_matcher_vs_semantic_board"]["fp"] == 1
    assert source["semantic_stage_breakdown"]["counts"]["transmission_nonfaithful"] == 1
    assert source["semantic_stage_breakdown"]["counts"].get("candidate_aggregation_failure", 0) == 0


def test_analysis_rejects_unresolved_adjudication():
    tasks = build_label_tasks([_trace()], [_facts()])
    records = _adjudicated(tasks, {(task["fact_id"], task["checkpoint"]): "faithful" for task in tasks})
    records[0]["final_label"] = None
    with pytest.raises(ValueError, match="unadjudicated"):
        analyze_adjudicated_labels([_trace()], [_facts()], records)


def test_repair_manifest_freezes_board_diagnosis_and_target_source():
    tasks = build_label_tasks([_trace()], [_facts()])
    labels = {
        (task["fact_id"], task["checkpoint"]): "faithful"
        for task in tasks
    }
    labels[("author", "board")] = "absent"
    manifest = build_repair_manifest(
        [_trace()], [_facts()], _adjudicated(tasks, labels), development_size=0
    )[0]
    assert manifest["diagnosis"] == "evidence_deficient"
    assert manifest["target_support_ids"] == ["agent-0"]
    assert manifest["evaluation_split"] == "held_out"
