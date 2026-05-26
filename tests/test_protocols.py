"""
Tests for src.protocols — all communication protocol modules.

All tests use mock API functions; no real API calls or network access.

Run with:
    pytest tests/test_protocols.py -v
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utility.apis.base import APIRequest, APIResponse, Provider
from src.protocols.base import (
    AgentShard,
    ProtocolResult,
    count_tokens_approx,
    extract_answer,
    format_shard_context,
    is_refusal,
    parse_score_json,
    shard_instance,
)
from src.protocols.relay import (
    _jaccard_sim,
    _parse_states,
    _redundancy_select,
    _topk_select,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _make_paragraph(idx: int, title: str, text: str, supporting: bool) -> dict:
    return {"idx": idx, "title": title, "paragraph_text": text, "is_supporting": supporting}


def _make_instance(
    id_: str = "inst_0",
    question: str = "Who wrote the book?",
    answer: str = "Alice",
    answer_aliases: list[str] | None = None,
    num_supporting: int = 3,
    num_distractors: int = 3,
) -> dict:
    paras = []
    for i in range(num_supporting):
        paras.append(
            _make_paragraph(i, f"Sup_{i}", f"Supporting text {i} about Alice.", True)
        )
    for j in range(num_distractors):
        paras.append(
            _make_paragraph(
                num_supporting + j, f"Dist_{j}", f"Distractor text {j} unrelated.", False
            )
        )
    return {
        "id": id_,
        "question": question,
        "answer": answer,
        "answer_aliases": answer_aliases or [],
        "paragraphs": paras,
        "icg": num_supporting - 1,
    }


def _ok_response(content: str = "ANSWER: Alice") -> APIResponse:
    return APIResponse(
        content=content,
        model="mock",
        provider=Provider.OPENAI,
        request_id="r1",
        success=True,
        usage={"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        metadata={},
        latency_ms=10.0,
    )


def _err_response() -> APIResponse:
    return APIResponse(
        content="",
        model="mock",
        provider=Provider.OPENAI,
        request_id="r1",
        success=False,
        error="timeout",
    )


def _mock_batch(answers: list[str]):
    """Return a batch_fn that cycles through `answers` in order."""
    call_log: list[list[str]] = [[]]  # mutable container

    def batch_fn(requests: list[APIRequest], max_workers: int = 5) -> list[APIResponse]:
        out = []
        for i, req in enumerate(requests):
            idx = len(call_log[0])
            call_log[0].append(req.request_id)
            ans = answers[idx % len(answers)]
            if ans == "__error__":
                out.append(_err_response())
            else:
                out.append(_ok_response(ans))
        return out

    return batch_fn


# ===========================================================================
# base.py
# ===========================================================================

class TestShardInstance:
    def test_round_robin_distribution(self):
        inst = _make_instance(num_supporting=3, num_distractors=0)
        shards = shard_instance(inst, n_agents=3, seed=42, distractors_per_agent=0)
        assert len(shards) == 3
        sup_counts = [
            sum(1 for p in s.paragraphs if p["is_supporting"]) for s in shards
        ]
        assert sup_counts == [1, 1, 1]

    def test_all_supporting_accounted(self):
        inst = _make_instance(num_supporting=4, num_distractors=6)
        shards = shard_instance(inst, n_agents=3, seed=0, distractors_per_agent=2)
        all_sup = [
            p for s in shards for p in s.paragraphs if p["is_supporting"]
        ]
        assert len(all_sup) == 4
        assert len({p["idx"] for p in all_sup}) == 4  # no duplicates

    def test_fewer_supporting_than_agents(self):
        inst = _make_instance(num_supporting=2, num_distractors=0)
        shards = shard_instance(inst, n_agents=3, seed=0, distractors_per_agent=0)
        assert len(shards) == 3
        non_empty = [s for s in shards if s.paragraphs]
        assert len(non_empty) == 2

    def test_instance_id_propagated(self):
        inst = _make_instance(id_="xyz")
        shards = shard_instance(inst, n_agents=2, seed=0)
        for s in shards:
            assert s.instance_id == "xyz"

    def test_question_propagated(self):
        inst = _make_instance(question="What happened?")
        shards = shard_instance(inst, n_agents=2, seed=0)
        for s in shards:
            assert s.question == "What happened?"

    def test_distractors_per_agent(self):
        inst = _make_instance(num_supporting=3, num_distractors=6)
        shards = shard_instance(inst, n_agents=3, seed=0, distractors_per_agent=2)
        for s in shards:
            dist_count = sum(1 for p in s.paragraphs if not p["is_supporting"])
            assert dist_count <= 2


class TestHelpers:
    def test_extract_answer_pattern(self):
        assert extract_answer("Reasoning...\nANSWER: Paris") == "Paris"

    def test_extract_answer_last_occurrence(self):
        assert extract_answer("ANSWER: first\nANSWER: last") == "last"

    def test_extract_answer_fallback(self):
        assert extract_answer("Paris") == "Paris"

    def test_extract_answer_case_insensitive(self):
        assert extract_answer("answer: Tokyo") == "Tokyo"

    def test_is_refusal_empty(self):
        assert is_refusal("")
        assert is_refusal("   ")

    def test_is_refusal_pattern(self):
        assert is_refusal("Insufficient information.")
        assert is_refusal("INSUFFICIENT INFORMATION")
        assert not is_refusal("Alice")

    def test_count_tokens_approx(self):
        assert count_tokens_approx("") == 0
        assert count_tokens_approx("a" * 400) == 100

    def test_format_shard_context_empty(self):
        shard = AgentShard(0, [], "Q?", "i0")
        assert "no evidence" in format_shard_context(shard).lower()

    def test_format_shard_context_with_paragraphs(self):
        shard = AgentShard(
            0,
            [_make_paragraph(0, "Title A", "Body A", True)],
            "Q?",
            "i0",
        )
        ctx = format_shard_context(shard)
        assert "Title A" in ctx
        assert "Body A" in ctx


class TestParseScoreJson:
    def test_valid_json(self):
        text = '{"relevance": 0.8, "uniqueness": 0.6, "criticality": 0.7, "overall": 0.7}'
        scores = parse_score_json(text)
        assert abs(scores["relevance"] - 0.8) < 1e-9
        assert abs(scores["composite"] - (0.8 + 0.6 + 0.7) / 3) < 1e-9

    def test_json_embedded_in_text(self):
        text = 'Here is the score:\n{"relevance": 0.5, "uniqueness": 0.5, "criticality": 0.5, "overall": 0.5}'
        scores = parse_score_json(text)
        assert scores["composite"] == pytest.approx(0.5)

    def test_invalid_json_fallback(self):
        scores = parse_score_json("not valid json at all")
        assert scores["composite"] == pytest.approx(0.5)

    def test_empty_string_fallback(self):
        scores = parse_score_json("")
        assert scores["relevance"] == pytest.approx(0.5)


# ===========================================================================
# relay.py — selection utilities
# ===========================================================================

class TestParseStates:
    def test_numbered_list(self):
        text = "1. Fact one\n2. Fact two\n3. Fact three"
        states = _parse_states(text, max_states=5)
        assert states == ["Fact one", "Fact two", "Fact three"]

    def test_respects_max_states(self):
        text = "\n".join(f"{i+1}. Fact {i}" for i in range(10))
        assert len(_parse_states(text, max_states=3)) == 3

    def test_skips_blank_lines(self):
        text = "1. Fact one\n\n2. Fact two"
        assert len(_parse_states(text, max_states=5)) == 2

    def test_various_separators(self):
        text = "1) First\n2: Second\n3. Third"
        states = _parse_states(text, max_states=5)
        assert len(states) == 3

    def test_empty_input(self):
        assert _parse_states("", max_states=5) == []


class TestTopkSelect:
    def test_selects_highest_scoring(self):
        states = ["A", "B", "C"]
        scores = [
            {"composite": 0.9},
            {"composite": 0.5},
            {"composite": 0.7},
        ]
        selected = _topk_select(states, scores, k=2)
        assert selected == ["A", "C"]

    def test_k_larger_than_states(self):
        states = ["A", "B"]
        scores = [{"composite": 0.8}, {"composite": 0.6}]
        assert _topk_select(states, scores, k=5) == ["A", "B"]

    def test_empty_states(self):
        assert _topk_select([], [], k=3) == []


class TestJaccardSim:
    def test_identical(self):
        assert _jaccard_sim("the quick brown fox", "the quick brown fox") == pytest.approx(1.0)

    def test_no_overlap(self):
        assert _jaccard_sim("hello world", "goodbye moon") == pytest.approx(0.0)

    def test_partial_overlap(self):
        sim = _jaccard_sim("alice in wonderland", "alice smith")
        assert 0 < sim < 1

    def test_empty_strings(self):
        assert _jaccard_sim("", "") == pytest.approx(0.0)


class TestRedundancySelect:
    def test_rho_zero_equals_topk(self):
        states = ["A about Alice", "B about Bob", "C about Alice again"]
        scores = [{"composite": 0.9}, {"composite": 0.8}, {"composite": 0.7}]
        top = _topk_select(states, scores, k=2)
        red = _redundancy_select(states, scores, k=2, rho=0.0)
        assert top == red

    def test_rho_nonzero_promotes_diversity(self):
        # Two very similar states and one different; with rho > 0 the different
        # one should be preferred over the second similar one.
        states = ["Alice wrote the book", "Alice authored the book", "Bob invented fire"]
        scores = [{"composite": 0.9}, {"composite": 0.85}, {"composite": 0.5}]
        # With rho=0 → [state0, state1]; with high rho → [state0, state2]
        selected_low = _redundancy_select(states, scores, k=2, rho=0.0)
        selected_high = _redundancy_select(states, scores, k=2, rho=5.0)
        assert "Bob invented fire" in selected_high

    def test_k_larger_than_states_returns_all(self):
        states = ["A", "B"]
        scores = [{"composite": 0.8}, {"composite": 0.6}]
        assert len(_redundancy_select(states, scores, k=10)) == 2

    def test_empty_states(self):
        assert _redundancy_select([], [], k=3) == []


# ===========================================================================
# local.py
# ===========================================================================

class TestComputeLocalAnswersBatch:
    def test_returns_correct_shape(self):
        from src.protocols.local import compute_local_answers_batch

        instances = [_make_instance(id_=f"i{i}", num_supporting=3) for i in range(3)]
        shards_list = [
            shard_instance(inst, n_agents=3, seed=42) for inst in instances
        ]
        batch_fn = _mock_batch(["ANSWER: Alice"])

        answers, tokens = compute_local_answers_batch(
            instances, shards_list, batch_fn, model="m", max_tokens=128, max_workers=2
        )
        assert len(answers) == 3
        assert len(tokens) == 3
        for inst_answers in answers:
            assert len(inst_answers) == 3  # 3 agents each

    def test_answer_extraction(self):
        from src.protocols.local import compute_local_answers_batch

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        batch_fn = _mock_batch(["ANSWER: Bob"])

        answers, _ = compute_local_answers_batch(
            instances, shards_list, batch_fn, "m", 128, max_workers=2
        )
        assert all(a == "Bob" for a in answers[0])

    def test_error_response_gives_empty_string(self):
        from src.protocols.local import compute_local_answers_batch

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        batch_fn = _mock_batch(["__error__"])

        answers, _ = compute_local_answers_batch(
            instances, shards_list, batch_fn, "m", 128, max_workers=2
        )
        assert all(a == "" for a in answers[0])


class TestLocalBaselines:
    def _setup(self):
        import random
        inst = _make_instance(answer="Alice")
        shards = shard_instance(inst, n_agents=3, seed=42)
        return inst, shards, random.Random(0)

    def test_single_local_correct_answer(self):
        from src.protocols.local import run_single_local

        inst, shards, rng = self._setup()
        result = run_single_local(
            inst, shards, _mock_batch(["ANSWER: Alice"]),
            "m", 128, rng, precomputed_answers=["Alice", "Alice", "Alice"]
        )
        assert result.f1 == pytest.approx(1.0)
        assert result.comm_tokens == 0

    def test_majority_vote_picks_plurality(self):
        from src.protocols.local import run_majority_vote_protocol

        inst, shards, _ = self._setup()
        result = run_majority_vote_protocol(
            inst, shards, _mock_batch([]), "m", 128,
            precomputed_answers=["Alice", "Alice", "Bob"],
        )
        assert result.pred == "Alice"
        assert result.comm_tokens == 0

    def test_majority_vote_ignores_refusals(self):
        from src.protocols.local import run_majority_vote_protocol

        inst, shards, _ = self._setup()
        result = run_majority_vote_protocol(
            inst, shards, _mock_batch([]), "m", 128,
            precomputed_answers=["Alice", "Insufficient information.", "Bob"],
        )
        # Only "Alice" and "Bob" count; tie resolved deterministically
        assert result.pred in ("Alice", "Bob")
        assert result.comm_tokens == 0

    def test_best_local_oracle(self):
        from src.protocols.local import run_best_local_oracle

        inst, shards, _ = self._setup()
        result = run_best_local_oracle(
            inst, shards, _mock_batch([]), "m", 128,
            precomputed_answers=["wrong", "Alice", "also wrong"],
        )
        assert result.pred == "Alice"
        assert result.f1 == pytest.approx(1.0)
        assert result.comm_tokens == 0


# ===========================================================================
# full_sharing.py
# ===========================================================================

class TestFullSharing:
    def test_batch_returns_all_instances(self):
        from src.protocols.full_sharing import run_full_sharing_batch

        instances = [_make_instance(id_=f"fs{i}", answer="Alice") for i in range(3)]
        results = run_full_sharing_batch(
            instances, _mock_batch(["ANSWER: Alice"]), "m", 128, max_workers=2
        )
        assert len(results) == 3
        assert all(r.f1 == pytest.approx(1.0) for r in results)

    def test_comm_tokens_counts_evidence(self):
        from src.protocols.full_sharing import run_full_sharing_batch

        instances = [_make_instance()]
        results = run_full_sharing_batch(
            instances, _mock_batch(["ANSWER: Alice"]), "m", 128
        )
        assert results[0].comm_tokens > 0

    def test_error_response_gives_empty_pred(self):
        from src.protocols.full_sharing import run_full_sharing_batch

        instances = [_make_instance()]
        results = run_full_sharing_batch(
            instances, _mock_batch(["__error__"]), "m", 128
        )
        assert results[0].pred == ""


# ===========================================================================
# debate.py
# ===========================================================================

class TestDebate:
    def test_batch_one_round(self):
        from src.protocols.debate import run_debate_batch

        instances = [_make_instance(id_=f"d{i}", answer="Alice") for i in range(2)]
        shards_list = [shard_instance(inst, n_agents=2, seed=0) for inst in instances]
        # Round 0 + round 1 responses; cycle through
        results = run_debate_batch(
            instances, shards_list,
            _mock_batch(["ANSWER: Alice"]),
            "m", 128,
            n_rounds=1,
            precomputed_answers_list=[["Alice", "Alice"]] * 2,
            max_workers=2,
        )
        assert len(results) == 2

    def test_comm_tokens_positive_with_rounds(self):
        from src.protocols.debate import run_debate_batch

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        results = run_debate_batch(
            instances, shards_list,
            _mock_batch(["ANSWER: Alice"]),
            "m", 128,
            n_rounds=1,
            precomputed_answers_list=[["Alice", "Bob"]],
        )
        # After 1 round each agent sees the other's answer → comm_tokens > 0
        assert results[0].comm_tokens > 0

    def test_precomputed_answers_skips_round0_api(self):
        from src.protocols.debate import run_debate_batch

        call_count = [0]
        def counting_batch(requests, max_workers=5):
            call_count[0] += len(requests)
            return [_ok_response("ANSWER: Alice")] * len(requests)

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        run_debate_batch(
            instances, shards_list, counting_batch, "m", 128,
            n_rounds=1,
            precomputed_answers_list=[["Alice", "Alice"]],
        )
        # Only round-1 calls (n_agents=2 agents × 1 instance)
        assert call_count[0] == 2


# ===========================================================================
# summary_exchange.py
# ===========================================================================

class TestSummaryExchange:
    def test_batch_two_passes(self):
        from src.protocols.summary_exchange import run_summary_exchange_batch

        instances = [_make_instance(id_=f"se{i}", answer="Alice") for i in range(2)]
        shards_list = [shard_instance(inst, n_agents=2, seed=0) for inst in instances]
        results = run_summary_exchange_batch(
            instances, shards_list,
            _mock_batch(["Key fact: Alice wrote it.", "ANSWER: Alice"]),
            "m", 256, max_workers=2,
        )
        assert len(results) == 2

    def test_comm_tokens_from_summaries(self):
        from src.protocols.summary_exchange import run_summary_exchange_batch

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        results = run_summary_exchange_batch(
            instances, shards_list,
            _mock_batch(["Summary text here. " * 5, "ANSWER: Alice"]),
            "m", 256,
        )
        assert results[0].comm_tokens > 0

    def test_transmitted_states_captured(self):
        from src.protocols.summary_exchange import run_summary_exchange_batch

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        results = run_summary_exchange_batch(
            instances, shards_list,
            _mock_batch(["My summary.", "ANSWER: Alice"]),
            "m", 256,
        )
        assert len(results[0].transmitted_states) == 2  # one per agent


# ===========================================================================
# gated.py
# ===========================================================================

class TestConfidenceGated:
    def test_no_communication_when_all_confident(self):
        from src.protocols.gated import run_confidence_gated_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        # Both agents answer with high confidence
        results = run_confidence_gated_batch(
            instances, shards_list,
            _mock_batch(["ANSWER: Alice\nCONFIDENCE: 0.9"]),
            "m", 128, confidence_threshold=0.6,
        )
        assert results[0].comm_tokens == 0

    def test_aggregation_called_when_low_confidence(self):
        from src.protocols.gated import run_confidence_gated_batch

        call_count = [0]
        def counting_batch(requests, max_workers=5):
            call_count[0] += len(requests)
            return [_ok_response("ANSWER: Alice\nCONFIDENCE: 0.1")] * len(requests)

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        results = run_confidence_gated_batch(
            instances, shards_list, counting_batch, "m", 128,
            confidence_threshold=0.6,
        )
        # Phase 1 (local) + phase 2 (aggregation)
        assert call_count[0] > 2
        assert results[0].comm_tokens > 0


class TestDisagreementGated:
    def test_no_communication_when_agree(self):
        from src.protocols.gated import run_disagreement_gated_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        results = run_disagreement_gated_batch(
            instances, shards_list, _mock_batch([]),
            "m", 128,
            precomputed_answers_list=[["Alice", "alice"]],  # normalised same
        )
        assert results[0].comm_tokens == 0

    def test_communication_when_disagree(self):
        from src.protocols.gated import run_disagreement_gated_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        results = run_disagreement_gated_batch(
            instances, shards_list,
            _mock_batch(["ANSWER: Alice"]),  # aggregator response
            "m", 128,
            precomputed_answers_list=[["Alice", "Bob"]],
        )
        assert results[0].comm_tokens > 0


# ===========================================================================
# relay.py — batch extraction and full protocols
# ===========================================================================

class TestExtractStatesBatch:
    def test_returns_correct_shape(self):
        from src.protocols.relay import extract_states_batch

        instances = [_make_instance(id_=f"r{i}") for i in range(2)]
        shards_list = [shard_instance(inst, n_agents=2, seed=0) for inst in instances]
        batch_fn = _mock_batch(["1. Alice wrote it.\n2. In 1865."])
        states, tokens = extract_states_batch(
            instances, shards_list, batch_fn, "m", 256,
            max_states_per_agent=3, max_workers=2,
        )
        assert len(states) == 2
        assert len(tokens) == 2
        assert len(states[0]) == 2  # 2 agents

    def test_parses_numbered_list(self):
        from src.protocols.relay import extract_states_batch

        instances = [_make_instance()]
        shards_list = [shard_instance(instances[0], n_agents=1, seed=0)]
        batch_fn = _mock_batch(["1. Fact one\n2. Fact two"])
        states, _ = extract_states_batch(
            instances, shards_list, batch_fn, "m", 256,
            max_states_per_agent=5, max_workers=1,
        )
        assert states[0][0] == ["Fact one", "Fact two"]


class TestScoreStatesBatch:
    def test_returns_correct_shape(self):
        from src.protocols.relay import score_states_batch

        instances = [_make_instance()]
        all_states = [[["Fact one", "Fact two"], ["Fact three"]]]
        score_json = '{"relevance": 0.8, "uniqueness": 0.7, "criticality": 0.6, "overall": 0.7}'
        batch_fn = _mock_batch([score_json])
        scores, tokens = score_states_batch(
            instances, all_states, batch_fn, "m", max_workers=2
        )
        assert len(scores) == 1
        assert len(tokens) == 1
        assert len(scores[0]) == 2  # 2 agents
        assert len(scores[0][0]) == 2  # 2 states for agent 0

    def test_parses_scores_correctly(self):
        from src.protocols.relay import score_states_batch

        instances = [_make_instance()]
        all_states = [[["Fact A"]]]
        score_json = '{"relevance": 1.0, "uniqueness": 0.5, "criticality": 0.5, "overall": 0.67}'
        batch_fn = _mock_batch([score_json])
        scores, _ = score_states_batch(instances, all_states, batch_fn, "m", max_workers=1)
        assert abs(scores[0][0][0]["relevance"] - 1.0) < 1e-9

    def test_empty_states_no_requests(self):
        from src.protocols.relay import score_states_batch

        instances = [_make_instance()]
        all_states = [[[]]]  # no states
        call_count = [0]

        def counting_batch(reqs, max_workers=5):
            call_count[0] += len(reqs)
            return []

        scores, tokens = score_states_batch(instances, all_states, counting_batch, "m", max_workers=1)
        assert call_count[0] == 0
        assert scores == [[[]]]
        assert tokens == [0]


class TestRandomRelayBatch:
    def test_returns_all_instances(self):
        from src.protocols.relay import run_random_relay_batch

        instances = [_make_instance(id_=f"rr{i}", answer="Alice") for i in range(2)]
        shards_list = [shard_instance(inst, n_agents=2, seed=0) for inst in instances]
        precomputed = [[["Fact 1", "Fact 2"], ["Fact 3"]] for _ in instances]
        results = run_random_relay_batch(
            instances, shards_list, _mock_batch(["ANSWER: Alice"]),
            "m", 128, max_states_per_agent=2,
            precomputed_states=precomputed, max_workers=2,
        )
        assert len(results) == 2
        assert all(r.comm_tokens > 0 for r in results)

    def test_transmitted_states_not_empty(self):
        from src.protocols.relay import run_random_relay_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        precomputed = [[["Fact 1", "Fact 2"], ["Fact 3"]]]
        results = run_random_relay_batch(
            instances, shards_list, _mock_batch(["ANSWER: Alice"]),
            "m", 128, max_states_per_agent=2,
            precomputed_states=precomputed,
        )
        assert len(results[0].transmitted_states) > 0


class TestCSCTopkBatch:
    def test_returns_all_instances(self):
        from src.protocols.relay import run_csc_topk_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        precomputed_states = [[["Fact A", "Fact B"], ["Fact C"]]]
        precomputed_scores = [
            [
                [{"composite": 0.9}, {"composite": 0.3}],
                [{"composite": 0.7}],
            ]
        ]
        results = run_csc_topk_batch(
            instances, shards_list, _mock_batch(["ANSWER: Alice"]),
            "m", 128, max_states_per_agent=1,
            precomputed_states=precomputed_states,
            precomputed_scores=precomputed_scores,
        )
        assert len(results) == 1
        # Only top-1 from each agent → 2 states total
        assert len(results[0].transmitted_states) == 2

    def test_selects_highest_scoring_state(self):
        from src.protocols.relay import run_csc_topk_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=1, seed=0)]
        precomputed_states = [[["Low score fact", "High score fact"]]]
        precomputed_scores = [
            [[{"composite": 0.2}, {"composite": 0.9}]]
        ]
        results = run_csc_topk_batch(
            instances, shards_list, _mock_batch(["ANSWER: Alice"]),
            "m", 128, max_states_per_agent=1,
            precomputed_states=precomputed_states,
            precomputed_scores=precomputed_scores,
        )
        assert "High score fact" in results[0].transmitted_states


class TestCSCRedundancyBatch:
    def test_returns_all_instances(self):
        from src.protocols.relay import run_csc_redundancy_batch

        instances = [_make_instance(answer="Alice")]
        shards_list = [shard_instance(instances[0], n_agents=2, seed=0)]
        precomputed_states = [[["Fact A about Alice", "Fact B about Alice"], ["Fact C about Bob"]]]
        precomputed_scores = [
            [
                [{"composite": 0.9}, {"composite": 0.85}],
                [{"composite": 0.5}],
            ]
        ]
        results = run_csc_redundancy_batch(
            instances, shards_list, _mock_batch(["ANSWER: Alice"]),
            "m", 128, max_states_per_agent=1, rho=0.5,
            precomputed_states=precomputed_states,
            precomputed_scores=precomputed_scores,
        )
        assert len(results) == 1
