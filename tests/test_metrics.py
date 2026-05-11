"""
Tests for src.eval.metrics — Table 1 metric computations.

All tests are pure in-memory; no API calls or file I/O.

Run with:
    pytest tests/test_metrics.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.eval.metrics import (
    aggregate_protocol_results,
    build_results_table,
    compute_cscov,
    compute_recovery,
    compute_utility,
    print_results_table,
)


# ===========================================================================
# compute_utility
# ===========================================================================

class TestComputeUtility:
    def test_zero_cost(self):
        assert compute_utility(acc=0.8, cost=0.0) == pytest.approx(0.8)

    def test_default_lambda(self):
        # U = 0.8 - 1e-4 * 1000 = 0.8 - 0.1 = 0.7
        assert compute_utility(acc=0.8, cost=1000.0) == pytest.approx(0.7)

    def test_custom_lambda(self):
        assert compute_utility(acc=1.0, cost=100.0, lambda_=0.01) == pytest.approx(0.0)

    def test_negative_utility_possible(self):
        result = compute_utility(acc=0.1, cost=10_000.0)
        assert result < 0


# ===========================================================================
# compute_recovery
# ===========================================================================

class TestComputeRecovery:
    def test_full_recovery(self):
        # method == full → recovery = 1.0 (modulo eps)
        r = compute_recovery(acc_method=0.9, acc_local=0.3, acc_full=0.9)
        assert r == pytest.approx(1.0, abs=1e-4)

    def test_zero_recovery(self):
        # method == local → recovery = 0.0 (modulo eps)
        r = compute_recovery(acc_method=0.3, acc_local=0.3, acc_full=0.9)
        assert r == pytest.approx(0.0, abs=1e-4)

    def test_partial_recovery(self):
        r = compute_recovery(acc_method=0.6, acc_local=0.3, acc_full=0.9)
        assert r == pytest.approx(0.5, abs=1e-4)

    def test_no_gap_returns_near_zero(self):
        # acc_full ≈ acc_local → recovery ≈ 0 (eps guard prevents divide-by-zero)
        r = compute_recovery(acc_method=0.8, acc_local=0.8, acc_full=0.8)
        assert r == pytest.approx(0.0, abs=1e-3)

    def test_negative_recovery_possible(self):
        # method worse than local
        r = compute_recovery(acc_method=0.1, acc_local=0.5, acc_full=0.9)
        assert r < 0


# ===========================================================================
# compute_cscov
# ===========================================================================

def _para(text: str) -> dict:
    return {"paragraph_text": text, "is_supporting": True}


class TestComputeCSCOV:
    def test_perfect_coverage(self):
        gold = [_para("Alice wrote the book in 1865")]
        states = ["Alice wrote the book in 1865 according to records"]
        cscov = compute_cscov(gold, states, threshold=0.1)
        assert cscov == pytest.approx(1.0)

    def test_zero_coverage_no_overlap(self):
        gold = [_para("Alice wrote the book")]
        states = ["The sky is blue on sunny days"]
        cscov = compute_cscov(gold, states, threshold=0.5)
        assert cscov == pytest.approx(0.0)

    def test_partial_coverage(self):
        gold = [_para("Fact one about Alice"), _para("Fact two about Bob")]
        states = ["Alice appeared in this story"]  # covers fact 1 but not fact 2
        cscov = compute_cscov(gold, states, threshold=0.1)
        assert 0 < cscov < 1

    def test_empty_gold_returns_one(self):
        assert compute_cscov([], ["some state"]) == pytest.approx(1.0)

    def test_empty_states_returns_zero(self):
        gold = [_para("Alice wrote the book")]
        assert compute_cscov(gold, []) == pytest.approx(0.0)

    def test_multiple_states_any_covers(self):
        gold = [_para("Alice wrote the book")]
        # First state irrelevant; second covers gold
        states = ["The weather is fine today", "Alice authored and wrote the book"]
        cscov = compute_cscov(gold, states, threshold=0.1)
        assert cscov == pytest.approx(1.0)


# ===========================================================================
# aggregate_protocol_results
# ===========================================================================

class TestAggregateProtocolResults:
    def _make_results(self, n: int, f1: float, tokens: int) -> list[dict]:
        return [{"f1": f1, "comm_tokens": tokens, "pred": "X"} for _ in range(n)]

    def test_basic_aggregation(self):
        results = self._make_results(4, 0.8, 100)
        agg = aggregate_protocol_results(results)
        assert agg["n"] == 4
        assert agg["acc"] == pytest.approx(0.8)
        assert agg["mean_comm_tokens"] == pytest.approx(100.0)
        assert agg["utility"] == pytest.approx(compute_utility(0.8, 100.0))
        assert "mean_total_llm_tokens" in agg

    def test_total_llm_tokens_averaged(self):
        results = [
            {"f1": 0.5, "comm_tokens": 50, "total_llm_tokens": 200},
            {"f1": 0.5, "comm_tokens": 50, "total_llm_tokens": 400},
        ]
        agg = aggregate_protocol_results(results)
        assert agg["mean_total_llm_tokens"] == pytest.approx(300.0)

    def test_empty_results(self):
        agg = aggregate_protocol_results([])
        assert agg["n"] == 0
        assert agg["acc"] == pytest.approx(0.0)

    def test_cscov_averaged_when_present(self):
        results = [
            {"f1": 0.5, "comm_tokens": 50, "cscov": 0.8},
            {"f1": 0.5, "comm_tokens": 50, "cscov": 0.6},
        ]
        agg = aggregate_protocol_results(results)
        assert "cscov" in agg
        assert agg["cscov"] == pytest.approx(0.7)

    def test_cscov_absent_when_not_in_results(self):
        results = self._make_results(2, 0.5, 0)
        agg = aggregate_protocol_results(results)
        assert "cscov" not in agg


# ===========================================================================
# build_results_table
# ===========================================================================

class TestBuildResultsTable:
    def _make_proto_results(self, f1: float, tokens: int, n: int = 5):
        return [{"f1": f1, "comm_tokens": tokens, "pred": "X"} for _ in range(n)]

    def test_recovery_computed(self):
        protocol_results = {
            "single_local": self._make_proto_results(0.3, 0),
            "full_sharing": self._make_proto_results(0.9, 500),
            "csc_topk": self._make_proto_results(0.6, 100),
        }
        table = build_results_table(protocol_results)
        assert "recovery" in table["csc_topk"]
        assert table["single_local"]["recovery"] == pytest.approx(0.0, abs=1e-4)
        assert table["full_sharing"]["recovery"] == pytest.approx(1.0, abs=1e-4)
        assert table["csc_topk"]["recovery"] == pytest.approx(0.5, abs=1e-4)

    def test_all_protocols_present(self):
        protocol_results = {
            "single_local": self._make_proto_results(0.3, 0),
            "full_sharing": self._make_proto_results(0.9, 500),
            "csc_topk": self._make_proto_results(0.7, 150),
        }
        table = build_results_table(protocol_results)
        assert set(table.keys()) == {"single_local", "full_sharing", "csc_topk"}

    def test_empty_input(self):
        table = build_results_table({})
        assert table == {}


# ===========================================================================
# print_results_table (smoke test — should not raise)
# ===========================================================================

class TestPrintResultsTable:
    def test_does_not_raise(self, capsys):
        table = {
            "single_local": {
                "n": 10, "acc": 0.3, "mean_comm_tokens": 0.0,
                "utility": 0.3, "recovery": 0.0,
            },
            "csc_topk": {
                "n": 10, "acc": 0.7, "mean_comm_tokens": 120.0,
                "utility": 0.688, "recovery": 0.67, "cscov": 0.8,
            },
            "full_sharing": {
                "n": 10, "acc": 0.9, "mean_comm_tokens": 500.0,
                "utility": 0.85, "recovery": 1.0,
            },
        }
        print_results_table(table)
        out = capsys.readouterr().out
        assert "csc_topk" in out.lower() or "CSC" in out
        assert "full_sharing" in out.lower() or "Full" in out

    def test_contains_accuracy_values(self, capsys):
        table = {
            "csc_topk": {
                "n": 5, "acc": 0.75, "mean_comm_tokens": 100.0,
                "utility": 0.74, "recovery": 0.8,
            },
        }
        print_results_table(table)
        out = capsys.readouterr().out
        assert "75.00" in out  # acc * 100 with 2 decimal places
