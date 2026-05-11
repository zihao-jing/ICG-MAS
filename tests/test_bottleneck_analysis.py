"""
Tests for src.eval.bottleneck_analysis -- Table 3 bottleneck runner.

All tests use mock API functions; no real API calls or network access.
"""

from __future__ import annotations

import argparse
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.eval.bottleneck_analysis import (
    BOTTLENECK_ROWS,
    build_ablated_board,
    run_bottleneck_analysis,
)
from src.eval.data_loader import compute_icg
from utility.apis.base import APIRequest, APIResponse, Provider


def _paragraph(idx: int, title: str, text: str, supporting: bool) -> dict:
    return {
        "idx": idx,
        "title": title,
        "paragraph_text": text,
        "is_supporting": supporting,
    }


def _instance() -> dict:
    inst = {
        "id": "bottleneck_0",
        "question": "Who wrote the book?",
        "answer": "Alice",
        "answer_aliases": [],
        "paragraphs": [
            _paragraph(0, "Support A", "Alice wrote the book.", True),
            _paragraph(1, "Support B", "The book was published in 1900.", True),
            _paragraph(2, "Distractor", "Bob wrote a different book.", False),
        ],
        "question_decomposition": [],
    }
    inst["icg"] = compute_icg(inst)
    return inst


def _silobench_instance() -> dict:
    return {
        "id": "I-01_n2",
        "question": "Find the global maximum.",
        "answer": "9",
        "answer_aliases": [],
        "paragraphs": [],
        "agent_configs": [
            {
                "agent_id": 0,
                "user_prompt": "Agent 0 data: [1, 9]",
                "input_shard": [1, 9],
                "expected_output": "9",
            },
            {
                "agent_id": 1,
                "user_prompt": "Agent 1 data: [2, 3]",
                "input_shard": [2, 3],
                "expected_output": "9",
            },
        ],
        "n_agents": 2,
        "icg": 1,
    }


def _response(content: str, request: APIRequest) -> APIResponse:
    return APIResponse(
        content=content,
        model=request.model,
        provider=Provider.OPENAI,
        request_id=request.request_id,
        success=True,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        metadata=dict(request.metadata),
    )


def test_build_ablated_board_removes_critical_units():
    inst = _instance()

    full = build_ablated_board(inst, "none", dataset="musique")
    remove_one = build_ablated_board(inst, "remove_1_critical", dataset="musique")
    remove_two = build_ablated_board(inst, "remove_2_critical", dataset="musique")

    assert any("Alice wrote the book" in unit for unit in full)
    assert any("published in 1900" in unit for unit in full)
    assert not any("Alice wrote the book" in unit for unit in remove_one)
    assert any("published in 1900" in unit for unit in remove_one)
    assert not any("Alice wrote the book" in unit for unit in remove_two)
    assert not any("published in 1900" in unit for unit in remove_two)


def test_build_ablated_board_removes_noncritical_units():
    inst = _instance()

    full = build_ablated_board(inst, "none", dataset="musique")
    no_distractor = build_ablated_board(inst, "remove_random_distractor", dataset="musique")
    no_redundant = build_ablated_board(inst, "remove_redundant_support", dataset="musique")

    assert any("different book" in unit for unit in full)
    assert not any("different book" in unit for unit in no_distractor)
    assert len(no_redundant) == len(full) - 1
    assert any("Alice wrote the book" in unit for unit in no_redundant)
    assert any("published in 1900" in unit for unit in no_redundant)


def test_build_ablated_board_rejects_unknown_variant():
    with pytest.raises(ValueError):
        build_ablated_board(_instance(), "not_a_variant", dataset="musique")


def test_build_ablated_board_defaults_to_silobench_units():
    inst = _silobench_instance()

    full = build_ablated_board(inst, "none")
    remove_one = build_ablated_board(inst, "remove_1_critical")
    no_redundant = build_ablated_board(inst, "remove_redundant_support")

    assert any("Agent 0 data" in unit for unit in full)
    assert any("Agent 1 data" in unit for unit in full)
    assert any("Distractor note" in unit for unit in full)
    assert not any("Agent 0 data" in unit for unit in remove_one)
    assert any("Agent 1 data" in unit for unit in remove_one)
    assert len(no_redundant) == len(full) - 1


def test_run_bottleneck_analysis_uses_batched_provider(monkeypatch):
    inst = _silobench_instance()
    batch_sizes: list[int] = []

    def fake_load_silobench(path=None, n_agents_filter=None):
        return [inst]

    def fake_get_batch_fn(provider: str):
        def batch_fn(requests: list[APIRequest], max_workers: int = 5):
            batch_sizes.append(len(requests))
            return [_response("ANSWER: 9", req) for req in requests]

        return batch_fn

    import src.eval.bottleneck_analysis as mod

    monkeypatch.setattr(mod, "load_silobench", fake_load_silobench)
    monkeypatch.setattr(mod, "_get_batch_fn", fake_get_batch_fn)

    args = argparse.Namespace(
        data=None,
        dataset="silobench",
        model="mock-model",
        provider="openai",
        max_tokens=256,
        max_workers=3,
        n_agents=5,
        limit=0,
        min_hops=2,
        seed=42,
        output=None,
        test=True,
    )

    output = run_bottleneck_analysis(args)

    assert set(output["table"]) == set(BOTTLENECK_ROWS)
    assert batch_sizes == [1, 1, 1, 1, 1]
    assert output["table"]["none"]["acc"] == pytest.approx(1.0)
    assert output["table"]["none"]["cscov"] == pytest.approx(1.0)
    assert output["table"]["remove_2_critical"]["cscov"] == pytest.approx(0.0)
