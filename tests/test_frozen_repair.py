"""The targeted repair arms must preserve the original rollout prompt."""

from __future__ import annotations

from scripts.run_frozen_repair import (
    SCHEMA_VERSION, conditions, decision_templates, merge_decisions, original_prompt, plan, prompt_hash, run, summarize,
    validate_manifest,
)
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIResponse, Provider


def _expect_value_error(message: str, callback) -> None:
    try:
        callback()
    except ValueError as exc:
        assert message in str(exc)
    else:
        raise AssertionError(f"Expected ValueError containing {message!r}")


def _record(diagnosis: str) -> dict:
    record = {
        "schema_version": SCHEMA_VERSION, "source_id": "test-run", "dataset": "silobench",
        "instance_id": "example", "question": "What is the maximum?", "gold_answer": "9",
        "answer_aliases": [], "original_model": "original/model", "original_provider": "openrouter",
        "stronger_model": "",
        "max_tokens": 4096, "temperature": 0.7, "n_agents": 2,
        "board_units": [{"unit_id": "board:0", "agent_id": 0, "text": "The value is 1."}],
        "source_contexts": [
            {"context_id": "agent-0", "agent_id": 0, "text": "Values: 1 and 9. The maximum is 9."},
            {"context_id": "agent-1", "agent_id": 1, "text": "The colour is blue."},
        ],
        "baseline": {"pred": "1", "f1": 0.0, "correct": False},
        "diagnosis": diagnosis, "reviewed_by": "annotator-1", "review_note": "checked source",
        "missing_facts": [], "volume_control": None,
    }
    if diagnosis == "evidence_gap":
        record["missing_facts"] = [{
            "text": "The maximum is 9.", "source_context_id": "agent-0", "verified_by": "annotator-1",
        }]
        record["volume_control"] = {
            "text": "The colour is blue.", "source_context_id": "agent-1", "verified_by": "annotator-1",
        }
    if diagnosis == "aggregation_gap":
        record["stronger_model"] = "stronger/model"
    record["original_prompt_sha256"] = prompt_hash(record, record["board_units"])
    return record


def test_exact_replay_uses_original_relay_prompt_and_generation_settings():
    record = _record("aggregation_gap")
    expected_user = _build_evidence_board_prompt([["The value is 1."], []], record["question"])
    assert original_prompt(record, record["board_units"]) == (_AGGREGATION_SYSTEM, expected_user)
    requests = []

    def batch(items):
        requests.extend(items)
        return [APIResponse(content="ANSWER: 9", model=item.model, provider=Provider.OPENAI,
                            request_id=item.request_id, success=True, usage={"total_tokens": 7})
                for item in items]

    rows = run([record], batch_fn=batch)
    assert [item.metadata["condition"] for item in requests] == ["exact_replay", "stronger_model"]
    assert [item.model for item in requests] == ["original/model", "stronger/model"]
    assert all(item.system_query == _AGGREGATION_SYSTEM for item in requests)
    assert all(item.user_query == expected_user for item in requests)
    assert all(item.temperature == 0.7 and item.max_tokens == 4096 for item in requests)
    assert rows[0]["f1"] == rows[1]["f1"] == 1.0


def test_retry_filter_sends_only_requested_arm():
    record = _record("aggregation_gap")
    sent = []

    def batch(items):
        sent.extend(items)
        return [APIResponse(content="ANSWER: 9", model=item.model, provider=Provider.OPENAI,
                            request_id=item.request_id, success=True, usage={"total_tokens": 7})
                for item in items]

    rows = run([record], batch_fn=batch,
               only_conditions={(record["source_id"], record["instance_id"], "exact_replay")})
    assert len(sent) == len(rows) == 1
    assert rows[0]["condition"] == "exact_replay"

    record["original_model"] = "mistralai/mistral-small-2603"
    record["original_prompt_sha256"] = prompt_hash(record, record["board_units"])
    sent.clear()
    run([record], batch_fn=batch,
        only_conditions={(record["source_id"], record["instance_id"], "exact_replay")},
        upstream_ignore="mistral")
    assert sent[0].metadata["openrouter_provider_ignore"] == ["mistral"]


def test_missing_fact_is_the_only_repair_board_change():
    record = _record("evidence_gap")
    arms = conditions(record)
    assert set(arms) == {"exact_replay", "restored_fact", "noncritical_control"}
    assert arms["restored_fact"][1][:-1] == arms["exact_replay"][1]
    assert arms["restored_fact"][1][-1]["text"] == "The maximum is 9."
    assert arms["noncritical_control"][1][-1]["text"] == "The colour is blue."
    assert all(model == "original/model" for model, _ in arms.values())
    assert plan([record])["new_api_calls"] == 3


def test_exact_repair_requires_an_explicit_literal_source_span():
    record = _record("evidence_gap")
    record["missing_facts"] = []
    _expect_value_error("Exact missing source spans required", lambda: validate_manifest([record]))
    record = _record("evidence_gap")
    record["missing_facts"][0]["text"] = "An invented maximum is 9."
    _expect_value_error("exact source span", lambda: validate_manifest([record]))
    record = _record("evidence_gap")
    record["volume_control"] = None
    validate_manifest([record])
    assert set(conditions(record)) == {"exact_replay", "restored_fact"}
    assert plan([record])["new_api_calls"] == 2


def test_source_verified_board_correction_is_appended_to_restoration():
    record = _record("evidence_gap")
    record["instance_id"] = "I-02_n5"
    record["question"] = 'Count the word "apple".'
    record["source_contexts"][0]["text"] = "['apple', 'pear', 'apple']"
    record["board_units"][0]["text"] = 'The word "apple" appears 3 times in Agent 0 data.'
    record["missing_facts"] = [{"text": "['apple', 'pear', 'apple']", "source_context_id": "agent-0",
                                "verified_by": "annotator-1"}]
    record["volume_control"] = None
    record["board_corrections"] = [{"kind": "word_count", "source_context_id": "agent-0",
                                    "corrects_unit_id": "board:0", "incorrect_value": "3",
                                    "correct_value": "2", "verified_by": "annotator-1"}]
    record["original_prompt_sha256"] = prompt_hash(record, record["board_units"])
    validate_manifest([record])
    original = conditions(record)["exact_replay"][1]
    restored = conditions(record)["restored_fact"][1]
    assert restored[:len(original)] == original
    assert restored[-1]["text"] == "Correction to Agent 0's earlier local word count: 2, not 3."
    record["board_corrections"][0]["correct_value"] = "4"
    _expect_value_error("does not match the source calculation", lambda: validate_manifest([record]))


def test_cross_interventions_keep_model_and_board_changes_separate():
    evidence = _record("evidence_gap")
    evidence["stronger_model"] = "stronger/model"
    evidence_arms = conditions(evidence, cross_interventions=True)
    assert evidence_arms["stronger_model"][0] == "stronger/model"
    assert evidence_arms["stronger_model"][1] == evidence_arms["exact_replay"][1]

    aggregation = _record("aggregation_gap")
    aggregation["source_supports"] = [{"agent_id": 0, "text": "Source evidence 9."}]
    aggregation_arms = conditions(aggregation, cross_interventions=True)
    assert set(aggregation_arms) == {"exact_replay", "stronger_model"}


def test_unreviewed_or_unsourced_facts_cannot_be_executed():
    unreviewed = _record("evidence_gap")
    unreviewed["reviewed_by"] = ""
    _expect_value_error("Human-reviewed", lambda: validate_manifest([unreviewed]))
    unsourced = _record("evidence_gap")
    unsourced["missing_facts"][0]["source_context_id"] = "unknown"
    _expect_value_error("valid source context", lambda: validate_manifest([unsourced]))
    changed_prompt = _record("evidence_gap")
    changed_prompt["question"] = "Different question"
    _expect_value_error("Original prompt changed", lambda: validate_manifest([changed_prompt]))


def test_aggregation_arm_rejects_fact_insertion_and_same_model():
    record = _record("aggregation_gap")
    record["missing_facts"] = [{"text": "Answer is 9"}]
    _expect_value_error("cannot contain missing facts", lambda: validate_manifest([record]))
    record = _record("aggregation_gap")
    record["stronger_model"] = record["original_model"]
    _expect_value_error("must differ", lambda: validate_manifest([record]))
    first, second = _record("aggregation_gap"), _record("aggregation_gap")
    second["instance_id"] = "another"
    second["stronger_model"] = "different/stronger"
    _expect_value_error("Preselect one stronger model", lambda: validate_manifest([first, second]))


def test_summary_compares_interventions_with_fresh_exact_replay():
    record = _record("evidence_gap")
    rows = []
    for condition, score in [("exact_replay", 0.0), ("restored_fact", 1.0), ("noncritical_control", 0.0)]:
        rows.append({"source_id": record["source_id"], "instance_id": record["instance_id"],
                     "dataset": "silobench", "diagnosis": "evidence_gap", "condition": condition,
                     "f1": score, "baseline_f1": 0.0, "success": True})
    report = summarize(rows)
    by_pair = {(row["condition"], row["control"]): row for row in report["summaries"]}
    assert by_pair[("restored_fact", "exact_replay")]["mean_f1_delta"] == 1.0
    assert by_pair[("noncritical_control", "exact_replay")]["mean_f1_delta"] == 0.0
    assert by_pair[("restored_fact", "noncritical_control")]["mean_f1_delta"] == 1.0
    assert by_pair[("restored_fact", "noncritical_control")]["improved"] == 1
    assert by_pair[("restored_fact", "exact_replay")]["mean_original_score"] == 0.0
    assert by_pair[("restored_fact", "exact_replay")]["mean_original_delta"] == 1.0
    assert by_pair[("restored_fact", "exact_replay")]["original_improved"] == 1


def test_summary_keeps_model_and_agent_settings_separate():
    rows = []
    for source_id, model, n_agents, repaired in (
        ("qwen_n5", "qwen/model", 5, 1.0),
        ("mistral_n10", "mistral/model", 10, 0.0),
    ):
        for condition, score in (("exact_replay", 0.0), ("stronger_model", repaired)):
            rows.append({
                "source_id": source_id, "instance_id": "same-id", "dataset": "silobench",
                "original_model": model, "n_agents": n_agents,
                "diagnosis": "aggregation_gap", "condition": condition,
                "f1": score, "baseline_f1": 0.0, "success": True,
            })
    summaries = summarize(rows)["summaries"]
    assert len(summaries) == 2
    assert {(row["original_model"], row["n_agents"], row["mean_f1_delta"])
            for row in summaries} == {("qwen/model", 5, 1.0), ("mistral/model", 10, 0.0)}


def test_summary_pools_musique_hop_counts_within_a_model():
    rows = []
    for n_agents in (2, 3, 4):
        for condition, score in (("exact_replay", 0.0), ("stronger_model", 1.0)):
            rows.append({
                "source_id": "mq_model", "instance_id": f"case-{n_agents}",
                "dataset": "musique", "original_model": "original/model", "n_agents": n_agents,
                "diagnosis": "aggregation_gap", "condition": condition,
                "f1": score, "baseline_f1": 0.0, "success": True,
            })
    summaries = summarize(rows)["summaries"]
    assert len(summaries) == 1
    assert summaries[0]["n_agents"] is None
    assert summaries[0]["n_paired"] == 3


def test_review_decisions_do_not_change_frozen_prompt_inputs():
    base = _record("evidence_gap")
    base["diagnosis"] = "needs_review"
    base["reviewed_by"] = ""
    base["missing_facts"] = []
    base["volume_control"] = None
    decision = decision_templates([_record("evidence_gap")])[0]
    merged = merge_decisions([base], [decision])[0]
    assert merged["question"] == base["question"]
    assert merged["board_units"] == base["board_units"]
    assert merged["original_prompt_sha256"] == base["original_prompt_sha256"]
    validate_manifest([merged])
    decision["question"] = "tamper"
    _expect_value_error("malformed review decision", lambda: merge_decisions([base], [decision]))


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print(f"PASS {name}")
