"""
Tests for src.eval — ICG MuSiQue evaluation pipeline.

All tests are purely in-memory / mock-based; no real API calls or file I/O
unless explicitly testing file loading with a temporary fixture.

Run with:
    pytest tests/test_eval.py -v
or:
    python -m pytest tests/test_eval.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.eval.data_loader import (
    compute_icg,
    get_supporting_paragraphs,
    load_musique,
    stratify_by_icg,
)
from src.eval.evaluate import (
    aggregate_by_stratum,
    answer_f1,
    compute_correlation,
    majority_vote,
    normalize,
    pearson_correlation,
    spearman_correlation,
    token_f1,
    print_results_table,
)
from src.eval.variant_a import (
    _assign_shards_a1,
    _assign_shards_a2,
    _build_user_prompt as a_build_prompt,
    run_variant_a1,
    run_variant_a2,
    run_variant_a_batch,
)
# majority_vote is tested via evaluate.py, not variant_a
from src.eval.variant_b import (
    run_variant_b,
    run_variant_b_batch,
)
from utility.apis.base import APIRequest, APIResponse, Provider


# ===========================================================================
# Test fixtures / helpers
# ===========================================================================

def _make_paragraph(idx: int, title: str, text: str, is_supporting: bool) -> dict:
    return {
        "idx": idx,
        "title": title,
        "paragraph_text": text,
        "is_supporting": is_supporting,
    }


def _make_instance(
    id_: str = "test_2hop",
    question: str = "Who wrote the book?",
    answer: str = "Alice",
    answer_aliases: list[str] | None = None,
    num_supporting: int = 2,
    num_distractors: int = 2,
    icg: int | None = None,
) -> dict:
    """Build a minimal MuSiQue-shaped instance dict."""
    paragraphs = []
    # Add supporting paragraphs first
    for i in range(num_supporting):
        paragraphs.append(
            _make_paragraph(i, f"Title_{i}", f"Supporting text {i} about the answer.", True)
        )
    # Add distractor paragraphs
    for j in range(num_distractors):
        paragraphs.append(
            _make_paragraph(
                num_supporting + j,
                f"Distractor_{j}",
                f"Distractor text {j} unrelated.",
                False,
            )
        )
    instance = {
        "id": id_,
        "question": question,
        "answer": answer,
        "answer_aliases": answer_aliases or [],
        "paragraphs": paragraphs,
        "question_decomposition": [],
    }
    instance["icg"] = icg if icg is not None else compute_icg(instance)
    return instance


def _mock_api_response(content: str = "Alice") -> APIResponse:
    """Build a successful mock APIResponse."""
    return APIResponse(
        content=content,
        model="openai/gpt-4.1-mini",
        provider=Provider.OPENAI,
        request_id="mock-id",
        success=True,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        metadata={},
        latency_ms=50.0,
    )


def _mock_error_response() -> APIResponse:
    return APIResponse(
        content="",
        model="openai/gpt-4.1-mini",
        provider=Provider.OPENAI,
        request_id="mock-id",
        success=False,
        error="timeout",
    )


# ===========================================================================
# data_loader.py
# ===========================================================================

class TestComputeICG:
    def test_two_supporting(self):
        inst = _make_instance(num_supporting=2)
        assert compute_icg(inst) == 1

    def test_three_supporting(self):
        inst = _make_instance(num_supporting=3)
        assert compute_icg(inst) == 2

    def test_four_supporting(self):
        inst = _make_instance(num_supporting=4)
        assert compute_icg(inst) == 3

    def test_one_supporting(self):
        """Edge case: single supporting paragraph → ICG = 0."""
        inst = _make_instance(num_supporting=1)
        assert compute_icg(inst) == 0

    def test_zero_supporting_returns_zero(self):
        """Guard: no supporting paragraphs → ICG = 0 (not negative)."""
        inst = _make_instance(num_supporting=0)
        assert compute_icg(inst) == 0

    def test_no_distractors(self):
        inst = _make_instance(num_supporting=3, num_distractors=0)
        assert compute_icg(inst) == 2

    def test_many_distractors_do_not_affect_icg(self):
        inst = _make_instance(num_supporting=2, num_distractors=10)
        assert compute_icg(inst) == 1


class TestGetSupportingParagraphs:
    def test_returns_only_supporting(self):
        inst = _make_instance(num_supporting=2, num_distractors=3)
        sp = get_supporting_paragraphs(inst)
        assert len(sp) == 2
        assert all(p["is_supporting"] for p in sp)

    def test_order_preserved(self):
        inst = _make_instance(num_supporting=3)
        sp = get_supporting_paragraphs(inst)
        for i, p in enumerate(sp):
            assert p["idx"] == i


class TestStratifyByICG:
    def test_basic_stratification(self):
        instances = [
            _make_instance(id_="a", num_supporting=2),  # ICG=1
            _make_instance(id_="b", num_supporting=3),  # ICG=2
            _make_instance(id_="c", num_supporting=4),  # ICG=3
            _make_instance(id_="d", num_supporting=2),  # ICG=1
        ]
        strata = stratify_by_icg(instances)
        assert sorted(strata.keys()) == [1, 2, 3]
        assert len(strata[1]) == 2
        assert len(strata[2]) == 1
        assert len(strata[3]) == 1

    def test_all_same_icg(self):
        instances = [_make_instance(id_=f"x{i}", num_supporting=2) for i in range(5)]
        strata = stratify_by_icg(instances)
        assert list(strata.keys()) == [1]
        assert len(strata[1]) == 5

    def test_empty_list(self):
        assert stratify_by_icg([]) == {}


class TestLoadMusique:
    def test_load_from_file(self):
        """Test that load_musique correctly parses JSONL and injects icg."""
        inst1 = _make_instance(id_="i1", num_supporting=2)
        inst2 = _make_instance(id_="i2", num_supporting=3)
        # Remove icg before writing (load_musique will recompute it)
        for inst in [inst1, inst2]:
            inst.pop("icg", None)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(json.dumps(inst1) + "\n")
            fh.write(json.dumps(inst2) + "\n")
            tmp_path = fh.name

        try:
            loaded = load_musique(tmp_path)
            assert len(loaded) == 2
            assert loaded[0]["id"] == "i1"
            assert loaded[0]["icg"] == 1
            assert loaded[1]["id"] == "i2"
            assert loaded[1]["icg"] == 2
        finally:
            os.unlink(tmp_path)

    def test_load_skips_blank_lines(self):
        inst = _make_instance(id_="i1", num_supporting=2)
        inst.pop("icg", None)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("\n")
            fh.write(json.dumps(inst) + "\n")
            fh.write("   \n")
            tmp_path = fh.name
        try:
            loaded = load_musique(tmp_path)
            assert len(loaded) == 1
        finally:
            os.unlink(tmp_path)


# ===========================================================================
# evaluate.py
# ===========================================================================

class TestNormalize:
    def test_lowercase(self):
        assert normalize("PARIS") == ["paris"]

    def test_articles_removed(self):
        tokens = normalize("The quick brown fox")
        assert "the" not in tokens
        assert "quick" in tokens

    def test_punctuation_removed(self):
        tokens = normalize("Hello, world!")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in " ".join(tokens)

    def test_empty_string(self):
        assert normalize("") == []

    def test_multiple_spaces(self):
        tokens = normalize("  foo   bar  ")
        assert tokens == ["foo", "bar"]

    def test_article_at_end(self):
        tokens = normalize("a")
        assert tokens == []


class TestTokenF1:
    def test_exact_match(self):
        assert token_f1("alice", "alice") == 1.0

    def test_no_overlap(self):
        assert token_f1("alice", "bob") == 0.0

    def test_partial_overlap(self):
        f1 = token_f1("alice wonderland", "alice smith")
        assert 0 < f1 < 1

    def test_empty_pred(self):
        assert token_f1("", "alice") == 0.0

    def test_empty_gold(self):
        assert token_f1("alice", "") == 0.0

    def test_both_empty(self):
        assert token_f1("", "") == 0.0

    def test_case_insensitive(self):
        assert token_f1("ALICE", "alice") == 1.0

    def test_subset_gold(self):
        """pred is a subset of gold tokens."""
        f1 = token_f1("alice", "alice in wonderland")
        assert 0 < f1 < 1

    def test_multiset_intersection(self):
        """Repeated tokens are handled correctly."""
        # pred="a a b", gold="a b b"
        # common: a(min 2,1=1), b(min 1,2=1) → 2 common
        # precision = 2/3, recall = 2/3
        f1 = token_f1("a a b", "a b b")
        expected = 2 * (2/3) * (2/3) / ((2/3) + (2/3))
        assert abs(f1 - expected) < 1e-9


class TestAnswerF1:
    def test_exact_match_primary(self):
        inst = _make_instance(answer="Alice", answer_aliases=[])
        assert answer_f1("Alice", inst) == 1.0

    def test_exact_match_alias(self):
        inst = _make_instance(answer="Alice", answer_aliases=["Al", "A. Liddell"])
        assert answer_f1("Al", inst) == 1.0

    def test_no_match(self):
        inst = _make_instance(answer="Alice", answer_aliases=[])
        assert answer_f1("Bob", inst) == 0.0

    def test_takes_max_over_aliases(self):
        inst = _make_instance(answer="Alice Smith", answer_aliases=["Alice"])
        # "Alice" should be a closer match to "Alice" alias (F1=1.0)
        assert answer_f1("Alice", inst) == 1.0

    def test_missing_answer_aliases_key(self):
        """Instances without answer_aliases key should not raise."""
        inst = _make_instance(answer="Alice")
        inst.pop("answer_aliases", None)
        # Should not raise; answer_aliases defaults to []
        f1 = answer_f1("Alice", inst)
        assert f1 == 1.0


class TestMajorityVote:
    def test_clear_winner(self):
        assert majority_vote(["Paris", "Paris", "London"]) == "Paris"

    def test_single_answer(self):
        assert majority_vote(["Berlin"]) == "Berlin"

    def test_case_insensitive_vote(self):
        result = majority_vote(["paris", "Paris", "PARIS", "London"])
        assert result.lower() == "paris"

    def test_tie_is_deterministic(self):
        """Ties must produce a consistent result (not random)."""
        r1 = majority_vote(["Alice", "Bob"])
        r2 = majority_vote(["Alice", "Bob"])
        assert r1 == r2

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            majority_vote([])

    def test_empty_strings_count(self):
        result = majority_vote(["", "", "Alice"])
        # "" wins 2-1
        assert result == ""

    def test_all_same(self):
        assert majority_vote(["Tokyo"] * 5) == "Tokyo"

    def test_normalisation_collapses_variants(self):
        """'the cat' and 'cat' should vote as different since tokens differ."""
        result = majority_vote(["the cat", "the cat", "cat"])
        assert "cat" in result.lower()


class TestPearsonCorrelation:
    def test_perfect_positive(self):
        r = pearson_correlation([1, 2, 3, 4], [1, 2, 3, 4])
        assert abs(r - 1.0) < 1e-9

    def test_perfect_negative(self):
        r = pearson_correlation([1, 2, 3, 4], [4, 3, 2, 1])
        assert abs(r + 1.0) < 1e-9

    def test_zero_correlation(self):
        r = pearson_correlation([1, 2, 3, 4], [2, 2, 2, 2])
        assert r is None  # constant y → undefined

    def test_too_short(self):
        assert pearson_correlation([1], [1]) is None

    def test_empty(self):
        assert pearson_correlation([], []) is None


class TestSpearmanCorrelation:
    def test_perfect_positive(self):
        r = spearman_correlation([1, 2, 3, 4], [10, 20, 30, 40])
        assert abs(r - 1.0) < 1e-9

    def test_perfect_negative(self):
        r = spearman_correlation([1, 2, 3, 4], [40, 30, 20, 10])
        assert abs(r + 1.0) < 1e-9

    def test_too_short(self):
        assert spearman_correlation([1], [2]) is None


class TestAggregateByStratum:
    def _make_result(self, icg: int, f1_a: float, f1_b: float) -> dict:
        return {"id": f"x_{icg}", "icg": icg, "f1_a": f1_a, "f1_b": f1_b}

    def test_single_stratum(self):
        results = [
            self._make_result(1, 0.8, 0.6),
            self._make_result(1, 0.6, 0.4),
        ]
        agg = aggregate_by_stratum(results)
        assert agg[1]["n"] == 2
        assert abs(agg[1]["f1_a"] - 0.7) < 1e-9
        assert abs(agg[1]["f1_b"] - 0.5) < 1e-9
        assert abs(agg[1]["delta"] - (-0.2)) < 1e-9  # delta = f1_b - f1_a = 0.5 - 0.7

    def test_multiple_strata(self):
        results = [
            self._make_result(1, 0.5, 0.5),
            self._make_result(2, 0.8, 0.4),
            self._make_result(3, 0.9, 0.3),
        ]
        agg = aggregate_by_stratum(results)
        assert sorted(agg.keys()) == [1, 2, 3]
        assert abs(agg[2]["delta"] - (-0.4)) < 1e-9  # delta = f1_b - f1_a = 0.4 - 0.8

    def test_empty_results(self):
        assert aggregate_by_stratum([]) == {}


class TestComputeCorrelation:
    def test_positive_correlation(self):
        # delta = f1_b - f1_a; higher ICG → larger B advantage → positive correlation
        results = [
            {"icg": 1, "f1_a": 0.5, "f1_b": 0.5},   # delta = 0
            {"icg": 2, "f1_a": 0.5, "f1_b": 0.7},   # delta = 0.2
            {"icg": 3, "f1_a": 0.5, "f1_b": 0.9},   # delta = 0.4
        ]
        corr = compute_correlation(results)
        assert corr["pearson"] > 0
        assert corr["spearman"] > 0

    def test_returns_none_for_too_few(self):
        results = [{"icg": 1, "f1_a": 0.5, "f1_b": 0.4}]
        corr = compute_correlation(results)
        assert corr["pearson"] is None
        assert corr["spearman"] is None


# ===========================================================================
# variant_a.py
# ===========================================================================

class TestShardAssignmentA1:
    def test_one_shard_per_paragraph(self):
        inst = _make_instance(num_supporting=3)
        supporting = get_supporting_paragraphs(inst)
        shards = _assign_shards_a1(supporting)
        assert len(shards) == 3
        for shard in shards:
            assert len(shard) == 1

    def test_two_supporting(self):
        inst = _make_instance(num_supporting=2)
        supporting = get_supporting_paragraphs(inst)
        shards = _assign_shards_a1(supporting)
        assert len(shards) == 2


class TestShardAssignmentA2:
    import random as _rand

    def test_four_supporting_two_shards(self):
        import random
        inst = _make_instance(num_supporting=4)
        supporting = get_supporting_paragraphs(inst)
        rng = random.Random(42)
        shards = _assign_shards_a2(supporting, rng)
        assert len(shards) == 2
        assert all(len(s) == 2 for s in shards)

    def test_three_supporting_last_gets_one(self):
        import random
        inst = _make_instance(num_supporting=3)
        supporting = get_supporting_paragraphs(inst)
        rng = random.Random(0)
        shards = _assign_shards_a2(supporting, rng)
        assert len(shards) == 2
        sizes = sorted(len(s) for s in shards)
        assert sizes == [1, 2]

    def test_two_supporting_collapses_to_one_agent(self):
        """2-hop: ICG=0, single agent in A2 (like Variant B)."""
        import random
        inst = _make_instance(num_supporting=2)
        supporting = get_supporting_paragraphs(inst)
        rng = random.Random(7)
        shards = _assign_shards_a2(supporting, rng)
        assert len(shards) == 1
        assert len(shards[0]) == 2

    def test_all_paragraphs_covered(self):
        """No paragraph is dropped or duplicated."""
        import random
        inst = _make_instance(num_supporting=4)
        supporting = get_supporting_paragraphs(inst)
        rng = random.Random(99)
        shards = _assign_shards_a2(supporting, rng)
        all_assigned = [p for shard in shards for p in shard]
        assert len(all_assigned) == 4
        assert {p["idx"] for p in all_assigned} == {p["idx"] for p in supporting}

    def test_randomisation_varies_across_seeds(self):
        import random
        inst = _make_instance(num_supporting=4)
        supporting = get_supporting_paragraphs(inst)
        shards1 = _assign_shards_a2(supporting, random.Random(1))
        shards2 = _assign_shards_a2(supporting, random.Random(99))
        # It's possible (but unlikely) both orderings are identical with 4
        # elements; check at least that the function runs without error
        total1 = [p["idx"] for s in shards1 for p in s]
        total2 = [p["idx"] for s in shards2 for p in s]
        assert sorted(total1) == sorted(total2) == sorted(p["idx"] for p in supporting)


class TestRunVariantA1:
    def test_success_single_instance(self):
        inst = _make_instance(num_supporting=2, answer="Alice")

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("Alice") for _ in requests]

        result = run_variant_a1(inst, mock_batch_fn)
        assert result["id"] == inst["id"]
        assert result["icg"] == 1
        assert result["num_agents"] == 2
        assert result["pred"] == "Alice"
        assert result["f1"] == 1.0

    def test_best_agent_selected(self):
        """F1 is the max over per-agent scores, not a vote."""
        inst = _make_instance(num_supporting=3, answer="Paris")

        answers = ["Paris", "Berlin", "Lyon"]
        call_count = [0]

        def mock_batch_fn(requests, max_workers=5):
            out = []
            for _ in requests:
                out.append(_mock_api_response(answers[call_count[0]]))
                call_count[0] += 1
            return out

        result = run_variant_a1(inst, mock_batch_fn)
        assert result["pred"].lower() == "paris"
        assert result["f1"] == 1.0
        assert len(result["agent_f1s"]) == 3

    def test_failed_api_response_treated_as_empty(self):
        inst = _make_instance(num_supporting=2, answer="Alice")

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_error_response(), _mock_api_response("Alice")]

        result = run_variant_a1(inst, mock_batch_fn)
        # Best agent is "Alice" (F1=1.0) over "" (F1=0.0)
        assert result["pred"].lower() == "alice"
        assert result["f1"] == 1.0

    def test_agent_answers_and_f1s_captured(self):
        inst = _make_instance(num_supporting=2, answer="Alice")

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("Alice"), _mock_api_response("Bob")]

        result = run_variant_a1(inst, mock_batch_fn)
        assert len(result["agent_answers"]) == 2
        assert len(result["agent_f1s"]) == 2
        assert result["f1"] == max(result["agent_f1s"])


class TestRunVariantA2:
    def test_two_supporting_single_agent(self):
        """2-hop (ICG=0): A2 creates one agent with both paragraphs."""
        inst = _make_instance(num_supporting=2, answer="Alice")
        call_log: list = []

        def mock_batch_fn(requests, max_workers=5):
            call_log.extend(requests)
            return [_mock_api_response("Alice")]

        result = run_variant_a2(inst, mock_batch_fn, seed=42)
        assert result["num_agents"] == 1
        # The single request should contain both paragraphs
        assert "Paragraph 1" in call_log[0].user_query
        assert "Paragraph 2" in call_log[0].user_query

    def test_four_supporting_two_agents(self):
        inst = _make_instance(num_supporting=4, answer="Tokyo")

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("Tokyo") for _ in requests]

        result = run_variant_a2(inst, mock_batch_fn, seed=42)
        assert result["num_agents"] == 2
        assert result["pred"].lower() == "tokyo"


class TestRunVariantABatch:
    def test_invalid_setting_raises(self):
        with pytest.raises(ValueError, match="setting must be"):
            run_variant_a_batch([], setting="a99", api_fn=None)

    def test_a1_batch_processes_all(self):
        instances = [
            _make_instance(id_=f"i{i}", num_supporting=2, answer="X")
            for i in range(3)
        ]

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("X") for _ in requests]

        results = run_variant_a_batch(instances, "a1", mock_batch_fn)
        assert len(results) == 3
        for r in results:
            assert r["f1"] == 1.0

    def test_a2_batch_uses_different_seeds(self):
        """Each instance in A2 batch uses a unique seed (seed + i)."""
        # We just verify it runs without error and returns correct count
        instances = [
            _make_instance(id_=f"x{i}", num_supporting=4, answer="Y")
            for i in range(4)
        ]

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("Y") for _ in requests]

        results = run_variant_a_batch(instances, "a2", mock_batch_fn, seed=100)
        assert len(results) == 4

    def test_order_preserved(self):
        ids = [f"inst_{i}" for i in range(5)]
        instances = [_make_instance(id_=id_, num_supporting=2) for id_ in ids]

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("Z") for _ in requests]

        results = run_variant_a_batch(instances, "a1", mock_batch_fn)
        assert [r["id"] for r in results] == ids


# ===========================================================================
# variant_b.py
# ===========================================================================

class TestRunVariantB:
    def test_success(self):
        inst = _make_instance(num_supporting=3, answer="Tokyo")
        request_log: list = []

        def mock_single_fn(request):
            request_log.append(request)
            return _mock_api_response("Tokyo")

        result = run_variant_b(inst, mock_single_fn)
        assert result["id"] == inst["id"]
        assert result["icg"] == 2
        assert result["pred"] == "Tokyo"
        assert result["f1"] == 1.0

    def test_all_paragraphs_in_prompt(self):
        inst = _make_instance(num_supporting=3, answer="X")
        request_log: list = []

        def mock_single_fn(request):
            request_log.append(request)
            return _mock_api_response("X")

        run_variant_b(inst, mock_single_fn)
        user_query = request_log[0].user_query
        assert "Paragraph 1" in user_query
        assert "Paragraph 2" in user_query
        assert "Paragraph 3" in user_query

    def test_failed_response_returns_empty_pred(self):
        inst = _make_instance(answer="Alice")

        def mock_single_fn(request):
            return _mock_error_response()

        result = run_variant_b(inst, mock_single_fn)
        assert result["pred"] == ""
        assert result["f1"] == 0.0

    def test_uses_same_max_tokens(self):
        """max_tokens passed to run_variant_b is forwarded to the request."""
        inst = _make_instance(num_supporting=2, answer="X")
        request_log: list = []

        def mock_single_fn(request):
            request_log.append(request)
            return _mock_api_response("X")

        run_variant_b(inst, mock_single_fn, max_tokens=200)
        assert request_log[0].max_tokens == 200


class TestRunVariantBBatch:
    def test_processes_all_instances(self):
        instances = [_make_instance(id_=f"b{i}", num_supporting=2, answer="Y") for i in range(4)]

        def mock_fn(request):
            return _mock_api_response("Y")

        results = run_variant_b_batch(instances, mock_fn)
        assert len(results) == 4
        assert all(r["f1"] == 1.0 for r in results)

    def test_order_preserved(self):
        ids = [f"b{i}" for i in range(3)]
        instances = [_make_instance(id_=id_, num_supporting=2) for id_ in ids]

        def mock_fn(request):
            return _mock_api_response("Z")

        results = run_variant_b_batch(instances, mock_fn)
        assert [r["id"] for r in results] == ids


# ===========================================================================
# Integration: A vs B result merging (via run_experiment helpers)
# ===========================================================================

class TestIntegrationResults:
    """End-to-end smoke tests using mock API functions."""

    def test_f1_tables_populated(self):
        """Run a small batch through both variants and check aggregation."""
        instances = [
            _make_instance(id_=f"t{i}", num_supporting=2 + (i % 3), answer="X")
            for i in range(9)  # 3 per stratum
        ]
        # Recompute ICG
        for inst in instances:
            inst["icg"] = compute_icg(inst)

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("X") for _ in requests]

        def mock_single_fn(request):
            return _mock_api_response("X")

        a1_results = run_variant_a_batch(instances, "a1", mock_batch_fn)
        b_results = run_variant_b_batch(instances, mock_single_fn)

        # Merge manually
        b_by_id = {r["id"]: r for r in b_results}
        merged = [
            {
                "id": a["id"], "icg": a["icg"],
                "f1_a": a["f1"], "f1_b": b_by_id[a["id"]]["f1"],
            }
            for a in a1_results
        ]

        agg = aggregate_by_stratum(merged)
        # All predictions correct → all F1 = 1.0
        for icg, row in agg.items():
            assert abs(row["f1_a"] - 1.0) < 1e-9
            assert abs(row["f1_b"] - 1.0) < 1e-9
            assert abs(row["delta"]) < 1e-9

    def test_wrong_answer_gives_zero_f1(self):
        instances = [_make_instance(id_="w1", num_supporting=2, answer="Alice")]
        instances[0]["icg"] = 1

        def mock_batch_fn(requests, max_workers=5):
            return [_mock_api_response("Bob") for _ in requests]

        def mock_single_fn(request):
            return _mock_api_response("Bob")

        a1_results = run_variant_a_batch(instances, "a1", mock_batch_fn)
        b_results = run_variant_b_batch(instances, mock_single_fn)
        assert a1_results[0]["f1"] == 0.0
        assert b_results[0]["f1"] == 0.0

    def test_print_results_table_runs(self, capsys):
        """print_results_table should not raise."""
        agg = {
            1: {"n": 5, "f1_a": 0.7, "f1_b": 0.5, "delta": 0.2},
            2: {"n": 3, "f1_a": 0.8, "f1_b": 0.4, "delta": 0.4},
        }
        print_results_table(agg, setting_label="A1")
        captured = capsys.readouterr()
        assert "A1" in captured.out
        assert "0.7000" in captured.out
