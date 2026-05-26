"""
Tests for src.eval.ablation_study -- Table 2 ablation runner.

All tests use mock API functions; no real API calls or network access.
"""

from __future__ import annotations

import argparse
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.eval.ablation_study import (
    ABLATION_ROWS,
    _agent_coverage,
    _component_scores,
    run_ablation_study,
)
from utility.apis.base import APIRequest, APIResponse, Provider


def _silobench_instance() -> dict:
    agent_configs = [
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
    ]
    return {
        "id": "I-01_n2",
        "question": "Find the global maximum.",
        "answer": "9",
        "answer_aliases": [],
        "paragraphs": [],
        "agent_configs": agent_configs,
        "full_context": "\n\n---\n\n".join(ac["user_prompt"] for ac in agent_configs),
        "n_agents": 2,
        "icg": 1,
    }


def _response(content: str, request: APIRequest) -> APIResponse:
    if request.metadata.get("phase") == "extraction":
        content = "1. Agent shard contains value 9\n2. Agent shard contains a numeric list"
    elif request.metadata.get("phase") == "scoring":
        content = '{"relevance": 0.9, "uniqueness": 0.7, "criticality": 0.8, "overall": 0.8}'
    elif request.metadata.get("phase") == "summary":
        content = "The shard contains numeric values."
    else:
        content = "ANSWER: 9"

    return APIResponse(
        content=content,
        model=request.model,
        provider=Provider.OPENAI,
        request_id=request.request_id,
        success=True,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        metadata=dict(request.metadata),
    )


def test_agent_coverage_counts_nonempty_agent_boards():
    assert _agent_coverage([["a"], [], ["c"]]) == pytest.approx(2 / 3)
    assert _agent_coverage([]) == pytest.approx(1.0)


def test_component_scores_replaces_composite_only():
    scores = [[[{"relevance": 0.9, "uniqueness": 0.1, "criticality": 0.3, "composite": 0.4}]]]

    rel = _component_scores(scores, "relevance_only")
    crit = _component_scores(scores, "criticality_only")
    no_uniq = _component_scores(scores, "no_uniqueness")

    assert rel[0][0][0]["composite"] == pytest.approx(0.9)
    assert crit[0][0][0]["composite"] == pytest.approx(0.3)
    assert no_uniq[0][0][0]["composite"] == pytest.approx(0.6)
    assert scores[0][0][0]["composite"] == pytest.approx(0.4)


def test_run_ablation_study_uses_batched_provider(monkeypatch):
    inst = _silobench_instance()
    batch_sizes: list[int] = []

    def fake_load_silobench(path=None, n_agents_filter=None):
        return [inst]

    def fake_get_batch_fn(provider: str):
        def batch_fn(requests: list[APIRequest], max_workers: int = 5):
            batch_sizes.append(len(requests))
            return [_response("ANSWER: 9", req) for req in requests]

        return batch_fn

    import src.eval.ablation_study as mod

    monkeypatch.setattr(mod, "load_silobench", fake_load_silobench)
    monkeypatch.setattr(mod, "_get_batch_fn", fake_get_batch_fn)

    args = argparse.Namespace(
        data=None,
        model="mock-model",
        provider="openai",
        n_agents=5,
        max_states=2,
        max_tokens=256,
        max_workers=3,
        limit=0,
        seed=42,
        rho=0.5,
        output=None,
        test=True,
    )

    output = run_ablation_study(args)

    assert set(output["table"]) == set(ABLATION_ROWS)
    assert output["n_instances"] == 1
    assert output["anchors"]["single_local_acc"] == pytest.approx(1.0)
    assert output["anchors"]["full_sharing_acc"] == pytest.approx(1.0)
    assert output["table"]["csc_topk"]["acc"] == pytest.approx(1.0)
    assert output["table"]["local_scoring_fails"]["n"] == 0
    assert batch_sizes
