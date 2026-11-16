"""Tests for the frozen-diagnosis Extension-B repair study."""

from __future__ import annotations

from utility.apis.base import APIResponse, Provider
from src.audit.repair_study import (
    SCHEMA_VERSION, run_repair_study, study_plan, summarize_repair_results, validate_manifest,
)
from src.audit.repair_study import (
    AUDIT_SCHEMA_VERSION, audit_study_plan, run_audit_repair_study,
    summarize_audit_repair_results, _deterministic_silo_repair,
    _repair_answer_f1, _strong_repair_analysis_request, _strong_repair_final_request,
    _SILO_V3_EXECUTABLE_TASKS, _validate_musique_v3_ledger,
)


def _record(diagnosis: str = "evidence_deficient") -> dict:
    return {
        "schema_version": SCHEMA_VERSION, "source_id": "sb_relay", "dataset": "silobench",
        "protocol": "score_ranked_relay", "instance_id": "example", "question": "What is the maximum?",
        "gold_answer": "9", "diagnosis": diagnosis,
        "baseline": {"pred": "1", "f1": 0.0, "correct": False, "comm_tokens": 10, "total_llm_tokens": 20},
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "The value is 1."}],
        "source_supports": [
            {"support_id": "agent-0", "agent_id": 0, "text": "Values: 1, 9."},
            {"support_id": "agent-1", "agent_id": 1, "text": "Colour: blue."},
        ],
        "source_contexts": [
            {"context_id": "agent-0", "agent_id": 0, "text": "Values: 1, 9."},
            {"context_id": "agent-1", "agent_id": 1, "text": "Colour: blue."},
        ],
        "oracle_facts": ([{"fact_id": "max", "text": "The maximum value is 9.", "board_label": "absent", "source_support_ids": ["agent-0"], "remove_board_unit_ids": []}] if diagnosis == "evidence_deficient" else []),
        "target_support_ids": ["agent-0"] if diagnosis == "evidence_deficient" else [],
        "volume_control_text": "The colour is blue.", "volume_control_source_support_ids": ["agent-1"],
        "evaluation_split": "held_out",
    }


def _fake_batch(requests):
    responses = []
    for request in requests:
        content = "1. The maximum value is 9." if request.metadata["phase"] == "repair_reextraction" else "ANSWER: 9"
        responses.append(APIResponse(content=content, model=request.model, provider=Provider.OPENAI,
                                     request_id=request.request_id, success=True, usage={"total_tokens": 7}))
    return responses


def test_plan_counts_cached_baseline_and_practical_reextraction():
    plan = study_plan([_record()])
    assert plan["new_api_calls"] == 6
    assert plan["conditions"][0] == "baseline"


def test_validation_requires_volume_control_only_for_execution():
    record = _record()
    record["volume_control_text"] = ""
    validate_manifest([record])
    try:
        validate_manifest([record], require_volume_controls=True)
    except ValueError as exc:
        assert "volume_control_text" in str(exc)
    else:
        raise AssertionError("Expected missing volume control to block execution")


def test_validation_rejects_badly_length_mismatched_volume_control():
    record = _record()
    record["volume_control_text"] = "x" * 200
    try:
        validate_manifest([record], require_volume_controls=True)
    except ValueError as exc:
        assert "length-matched" in str(exc)
    else:
        raise AssertionError("Expected unbalanced volume control to block execution")


def test_runs_all_conditions_and_reports_paired_recovery():
    rows = run_repair_study([_record()], batch_fn=_fake_batch, model="test")
    assert {row["condition"] for row in rows} == {
        "baseline", "oracle_evidence_repair", "practical_evidence_repair", "volume_control",
        "aggregation_repair", "generic_retry",
    }
    practical = next(row for row in rows if row["condition"] == "practical_evidence_repair")
    assert practical["api_calls"] == 2
    assert practical["recovered"] is True
    report = summarize_repair_results(rows)
    oracle = next(row for row in report["summaries"] if row["condition"] == "oracle_evidence_repair")
    assert oracle["mean_delta_f1"] == 1.0
    assert oracle["recovery_rate"] == 1.0


def test_automatic_audit_path_repairs_evidence_gap_without_oracle_facts():
    record = {
        "schema_version": AUDIT_SCHEMA_VERSION, "source_id": "sb", "dataset": "silobench",
        "protocol": "score_ranked_relay", "instance_id": "example", "question": "What is the maximum?",
        "gold_answer": "9", "audit_signal": "evidence_gap",
        "audit_metrics": {"crit_recall": 0.0, "agg_fail": False},
        "baseline": {"pred": "1", "f1": 0.0, "correct": False, "comm_tokens": 10, "total_llm_tokens": 20},
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "The value is 1."}],
        "source_contexts": [{"context_id": "agent-0", "agent_id": 0, "text": "Values: 1, 9."}],
    }
    plan = audit_study_plan([record])
    assert plan["new_api_calls"] == 3  # re-extract, repaired aggregation, retry
    rows = run_audit_repair_study([record], batch_fn=_fake_batch, model="test")
    assert {row["condition"] for row in rows} == {"baseline", "audited_evidence_repair", "generic_retry"}
    repair = next(row for row in rows if row["condition"] == "audited_evidence_repair")
    assert repair["recovered"] is True
    report = summarize_audit_repair_results(rows)
    assert any(row["condition"] == "audited_evidence_repair" for row in report["summaries"])


def test_strong_two_stage_matches_audit_and_generic_inference_depth():
    record = {
        "schema_version": AUDIT_SCHEMA_VERSION, "source_id": "sb", "dataset": "silobench",
        "protocol": "score_ranked_relay", "instance_id": "example", "question": "What is the maximum?",
        "gold_answer": "9", "audit_signal": "aggregation_gap",
        "audit_metrics": {"crit_recall": 1.0, "agg_fail": True},
        "baseline": {"pred": "1", "f1": 0.0, "correct": False, "comm_tokens": 10, "total_llm_tokens": 20},
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "The value is 9."}],
        "source_contexts": [],
    }
    seen_phases = []

    def batch(requests):
        seen_phases.extend(request.metadata["phase"] for request in requests)
        return [APIResponse(content="ANSWER: 9", model=request.model, provider=Provider.OPENAI,
                            request_id=request.request_id, success=True, usage={"total_tokens": 7})
                for request in requests]

    rows = run_audit_repair_study([record], batch_fn=batch, model="test", repair_strategy="strong_two_stage")
    repair = next(row for row in rows if row["condition"] == "audited_aggregation_repair")
    retry = next(row for row in rows if row["condition"] == "generic_retry")
    assert repair["api_calls"] == retry["api_calls"] == 2
    assert seen_phases == ["audit_verification", "generic_consolidation", "strong_repair_answer", "strong_repair_answer"]


def test_deterministic_silo_repair_counts_original_shards_not_board_summaries():
    record = {
        "dataset": "silobench", "instance_id": "I-02_n5",
        "question": 'Count the TOTAL occurrences of the word "apple" across all agents\' data.',
        "source_contexts": [
            {"agent_id": 0, "text": "['apple', 'fig', 'apple']"},
            {"agent_id": 1, "text": "['apple', 'banana']"},
        ],
    }
    assert _deterministic_silo_repair(record) == "3"


def test_repair_numeric_alias_avoids_sixteen_vs_16_scoring_artifact():
    assert _repair_answer_f1("16", "sixteen") == 1.0
    assert _repair_answer_f1("17", "sixteen") == 0.0


def test_bottleneck_v2_executes_silo_reduction_and_keeps_generic_control():
    record = {
        "schema_version": AUDIT_SCHEMA_VERSION, "source_id": "sb", "dataset": "silobench",
        "protocol": "score_ranked_relay", "instance_id": "I-02_n5",
        "question": 'Count the TOTAL occurrences of the word "apple" across all agents\' data.',
        "gold_answer": "3", "audit_signal": "evidence_gap",
        "audit_metrics": {"crit_recall": 0.0, "agg_fail": False},
        "baseline": {"pred": "2", "f1": 0.0, "correct": False, "comm_tokens": 10, "total_llm_tokens": 20},
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "apple appears twice."}],
        "source_contexts": [
            {"context_id": "agent-0", "agent_id": 0, "text": "['apple', 'fig', 'apple']"},
            {"context_id": "agent-1", "agent_id": 1, "text": "['apple', 'banana']"},
        ],
    }
    phases = []

    def batch(requests):
        phases.extend(request.metadata["phase"] for request in requests)
        return [APIResponse(content="ANSWER: 3", model=request.model, provider=Provider.OPENAI,
                            request_id=request.request_id, success=True, usage={"total_tokens": 7})
                for request in requests]

    rows = run_audit_repair_study([record], batch_fn=batch, model="test", repair_strategy="bottleneck_aware_v2")
    audit = next(row for row in rows if row["condition"] == "audited_evidence_repair")
    generic = next(row for row in rows if row["condition"] == "generic_retry")
    assert audit["pred"] == "3" and audit["api_calls"] == 0 and audit["recovered"] is True
    assert generic["api_calls"] == 2
    assert phases == ["generic_consolidation", "strong_repair_answer"]


def test_musique_path_request_forbids_world_knowledge_correction():
    record = {
        "instance_id": "m", "question": "Which city?", "dataset": "musique",
    }
    request = _strong_repair_analysis_request(
        record, [{"text": "A is related to B."}], audited=True, model="test", max_tokens=64,
        condition="audited_aggregation_repair", evidence_as_given_path=True,
    )
    assert "axiom" in request.system_query
    assert "outside knowledge" in request.system_query


def test_bottleneck_v2_retries_empty_visible_extraction_once():
    record = {
        "schema_version": AUDIT_SCHEMA_VERSION, "source_id": "m", "dataset": "musique",
        "protocol": "score_ranked_relay", "instance_id": "example", "question": "Which city?",
        "gold_answer": "Paris", "audit_signal": "evidence_gap",
        "audit_metrics": {"crit_recall": 0.0, "agg_fail": False},
        "baseline": {"pred": "London", "f1": 0.0, "correct": False, "comm_tokens": 10, "total_llm_tokens": 20},
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "The country is France."}],
        "source_contexts": [{"context_id": "agent-0", "agent_id": 0, "text": "Paris is in France."}],
    }
    phases = []

    def batch(requests):
        phases.extend(request.metadata["phase"] for request in requests)
        responses = []
        for request in requests:
            content = "" if request.metadata["phase"] == "audit_reextraction" else "1. Paris is in France." if request.metadata["phase"] == "audit_reextraction_retry" else "ANSWER: Paris"
            responses.append(APIResponse(content=content, model=request.model, provider=Provider.OPENAI,
                                         request_id=request.request_id, success=True, usage={"total_tokens": 7}))
        return responses

    rows = run_audit_repair_study([record], batch_fn=batch, model="test", repair_strategy="bottleneck_aware_v2")
    repair = next(row for row in rows if row["condition"] == "audited_evidence_repair")
    assert repair["api_calls"] == 4  # initial extraction + retry + ledger + answer
    assert "audit_reextraction_retry" in phases


def test_v3_executes_structured_silo_algorithms_from_original_shards():
    difference_record = {
        "dataset": "silobench", "instance_id": "II-17_n2", "question": "Compute the difference array.",
        "source_contexts": [
            {"agent_id": 0, "text": "[3, 8]"},
            {"agent_id": 1, "text": "[2, 7]"},
        ],
    }
    matrix_record = {
        "dataset": "silobench", "instance_id": "III-30_n2", "question": "Compute C = A × B.",
        "source_contexts": [
            {"agent_id": 0, "text": "{'A_rows': [[1, 2]], 'A_row_indices': [0], 'B_matrix': [[2, 3], [5, 7]]}"},
            {"agent_id": 1, "text": "{'A_rows': [[4, 1]], 'A_row_indices': [1], 'B_matrix': [[2, 3], [5, 7]]}"},
        ],
    }
    assert _deterministic_silo_repair(difference_record, supported_task_ids=_SILO_V3_EXECUTABLE_TASKS) == "[5, -6, 5]"
    assert _deterministic_silo_repair(matrix_record, supported_task_ids=_SILO_V3_EXECUTABLE_TASKS) == "[[12, 17], [13, 19]]"


def test_v3_musique_path_validator_requires_sequential_cited_hops():
    record = {"instance_id": "2hop__example"}
    board = [{"text": "A is in B."}, {"text": "B is in C."}]
    valid_ledger = (
        "QUESTION_ENTITIES: A; answer location\nTARGET_RELATION: location\n"
        "EDGE_1: [1] A | located in | B\nEDGE_2: [2] B | located in | C\n"
        "PATH_STATUS: COMPLETE\nANSWER_CANDIDATE: C"
    )
    invalid_ledger = valid_ledger.replace("EDGE_2: [2]", "EDGE_3: [9]")
    assert _validate_musique_v3_ledger(record, board, valid_ledger)["audit_path_valid"] is True
    assert _validate_musique_v3_ledger(record, board, invalid_ledger)["audit_path_valid"] is False


def test_v3_musique_requests_use_structured_path_contract():
    record = {"instance_id": "2hop__example", "question": "Which city?", "dataset": "musique"}
    analysis = _strong_repair_analysis_request(
        record, [{"text": "A is in B."}], audited=True, model="test", max_tokens=64,
        condition="audited_aggregation_repair", structured_path=True,
    )
    final = _strong_repair_final_request(
        record, [{"text": "A is in B."}], "PATH_STATUS: INCOMPLETE", audited=True,
        model="test", max_tokens=64, condition="audited_aggregation_repair", structured_path=True,
    )
    assert "EDGE_i" in analysis.system_query and "PATH_STATUS" in analysis.system_query
    assert "PATH_STATUS" in final.system_query and "uncited" in final.system_query


def test_v3_records_path_validation_metadata_on_audited_musique_rows():
    record = {
        "schema_version": AUDIT_SCHEMA_VERSION, "source_id": "m", "dataset": "musique",
        "protocol": "score_ranked_relay", "instance_id": "2hop__example", "question": "Which city?",
        "gold_answer": "Paris", "audit_signal": "aggregation_gap",
        "audit_metrics": {"crit_recall": 1.0, "agg_fail": True},
        "baseline": {"pred": "London", "f1": 0.0, "correct": False, "comm_tokens": 10, "total_llm_tokens": 20},
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "A is in France."},
                        {"unit_id": "board:1", "agent_id": 1, "text": "France has Paris."}],
        "source_contexts": [],
    }

    def batch(requests):
        responses = []
        for request in requests:
            if request.metadata["phase"] == "audit_verification":
                content = ("QUESTION_ENTITIES: A; city\nTARGET_RELATION: location\n"
                           "EDGE_1: [1] A | located in | France\nEDGE_2: [2] France | has city | Paris\n"
                           "PATH_STATUS: COMPLETE\nANSWER_CANDIDATE: Paris")
            elif request.metadata["phase"] == "generic_consolidation":
                content = "Relevant facts are available."
            else:
                content = "ANSWER: Paris"
            responses.append(APIResponse(content=content, model=request.model, provider=Provider.OPENAI,
                                         request_id=request.request_id, success=True, usage={"total_tokens": 7}))
        return responses

    rows = run_audit_repair_study([record], batch_fn=batch, model="test", repair_strategy="bottleneck_aware_v3")
    audit = next(row for row in rows if row["condition"] == "audited_aggregation_repair")
    generic = next(row for row in rows if row["condition"] == "generic_retry")
    assert audit["audit_path_valid"] is True and audit["audit_path_hops"] == 2
    assert "audit_path_valid" not in generic
