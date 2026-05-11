"""
No-communication local baselines:
  - single_local:     one randomly selected agent answers from its shard
  - majority_vote:    plurality vote over all agents' local answers
  - best_local:       oracle best single-agent answer (upper bound on isolated perf)

All three share the same local-agent API calls to avoid redundant requests.
Use compute_local_answers_batch() to precompute answers once and reuse.
"""

from __future__ import annotations

import concurrent.futures
import random
from typing import Callable, Optional

from typing import Callable as _Callable

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1, majority_vote as _majority_vote
from .base import (
    AgentShard,
    ProtocolResult,
    format_shard_context,
    extract_answer,
    is_refusal,
)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_LOCAL_SYSTEM = (
    "You are a question-answering assistant. "
    "Answer using ONLY the provided documents — do not use background knowledge. "
    "Output your final answer on the last line as:\nANSWER: <your concise answer>\n"
    "If the documents contain insufficient information to answer, write:\n"
    "ANSWER: Insufficient information."
)


def _build_local_prompt(context: str, question: str) -> str:
    return (
        f"Documents:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer using only the documents above.\nANSWER: "
    )


# ---------------------------------------------------------------------------
# Core: run all local agents for one instance
# ---------------------------------------------------------------------------

def _run_local_agents(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int,
) -> list[str]:
    """Run all agents independently and return their answers.

    All agent requests for this instance are submitted as one batch so the
    underlying batch_fn can parallelise them.
    """
    requests = [
        APIRequest(
            system_query=_LOCAL_SYSTEM,
            user_query=_build_local_prompt(format_shard_context(s), instance["question"]),
            model=model,
            max_tokens=max_tokens,
            metadata={"instance_id": instance["id"], "agent": s.agent_idx, "phase": "local"},
        )
        for s in shards
    ]
    responses = batch_fn(requests, max_workers=max_workers)
    return [
        extract_answer(r.content) if r.success and r.content.strip() else ""
        for r in responses
    ]


# ---------------------------------------------------------------------------
# Batch precomputation (shared across all three local baselines)
# ---------------------------------------------------------------------------

def compute_local_answers_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int,
) -> tuple[list[list[str]], list[list[int]]]:
    """Compute local agent answers for all instances in one large batched call.

    Flattens all (instance × agent) requests into a single batch for maximum
    throughput, then reshapes the responses back to [instance_idx][agent_idx].

    Returns:
        (answers, per_agent_tokens) where:
            answers[inst_i][agent_j]       = answer string
            per_agent_tokens[inst_i][agent_j] = total_tokens for that call
    """
    all_requests: list[APIRequest] = []
    index_map: list[tuple[int, int]] = []  # (instance_idx, agent_idx)

    for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
        for agent_j, shard in enumerate(shards):
            # For Silo-Bench shards use prebuilt_prompt directly; otherwise wrap in QA template.
            context = format_shard_context(shard)
            user_query = (
                context if shard.prebuilt_prompt
                else _build_local_prompt(context, instance["question"])
            )
            all_requests.append(
                APIRequest(
                    system_query=_LOCAL_SYSTEM,
                    user_query=user_query,
                    model=model,
                    max_tokens=max_tokens,
                    metadata={
                        "instance_id": instance["id"],
                        "agent": agent_j,
                        "phase": "local",
                    },
                )
            )
            index_map.append((inst_i, agent_j))

    responses = batch_fn(all_requests, max_workers=max_workers)

    answers: list[list[str]] = [[""] * len(shards) for shards in shards_list]
    tokens: list[list[int]] = [[0] * len(shards) for shards in shards_list]
    for k, resp in enumerate(responses):
        inst_i, agent_j = index_map[k]
        tokens[inst_i][agent_j] = resp.usage.get("total_tokens", 0)
        if resp.success and resp.content.strip():
            answers[inst_i][agent_j] = extract_answer(resp.content)

    return answers, tokens


# ---------------------------------------------------------------------------
# Per-instance protocol runners
# ---------------------------------------------------------------------------

def run_single_local(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    rng: random.Random,
    precomputed_answers: Optional[list[str]] = None,
    max_workers: int = 5,
) -> ProtocolResult:
    """Randomly pick one agent and return its answer (comm_tokens = 0)."""
    answers = precomputed_answers or _run_local_agents(
        instance, shards, batch_fn, model, max_tokens, max_workers
    )
    idx = rng.randint(0, max(len(shards) - 1, 0))
    pred = answers[idx] if idx < len(answers) else ""
    return ProtocolResult(
        instance_id=instance["id"],
        pred=pred,
        f1=answer_f1(pred, instance),
        comm_tokens=0,
    )


def run_majority_vote_protocol(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    precomputed_answers: Optional[list[str]] = None,
    max_workers: int = 5,
) -> ProtocolResult:
    """Plurality vote over all agents' local answers (comm_tokens = 0)."""
    answers = precomputed_answers or _run_local_agents(
        instance, shards, batch_fn, model, max_tokens, max_workers
    )
    non_refusal = [a for a in answers if not is_refusal(a)]
    pred = (
        _majority_vote(non_refusal) if non_refusal else (answers[0] if answers else "")
    )
    return ProtocolResult(
        instance_id=instance["id"],
        pred=pred,
        f1=answer_f1(pred, instance),
        comm_tokens=0,
    )


def run_best_local_oracle(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    precomputed_answers: Optional[list[str]] = None,
    max_workers: int = 5,
    eval_fn: _Callable = answer_f1,
) -> ProtocolResult:
    """Oracle: return the best single-agent answer (upper bound on isolated perf)."""
    answers = precomputed_answers or _run_local_agents(
        instance, shards, batch_fn, model, max_tokens, max_workers
    )
    f1s = [eval_fn(a, instance) for a in answers]
    best_idx = f1s.index(max(f1s)) if f1s else 0
    pred = answers[best_idx] if answers else ""
    return ProtocolResult(
        instance_id=instance["id"],
        pred=pred,
        f1=max(f1s) if f1s else 0.0,
        comm_tokens=0,
    )
