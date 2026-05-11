"""
Summary exchange baseline.

Each agent generates a compressed textual summary of its private shard,
then a central aggregator reasons from all received summaries.

comm_tokens counts the total tokens in the summaries transmitted by agents.
"""

from __future__ import annotations

from typing import Callable

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1
from .base import (
    AgentShard,
    ProtocolResult,
    format_shard_context,
    extract_answer,
    count_tokens_approx,
)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = (
    "You are a summarization assistant in a multi-agent reasoning system. "
    "Given a private evidence shard and a question, produce a concise summary "
    "of the key facts in your shard that may be relevant to answering the question. "
    "Focus on factual content; do not answer the question. "
    "Be as concise as possible."
)

_AGG_SYSTEM = (
    "You are a question-answering assistant. "
    "You have received concise summary reports from multiple agents, each with "
    "access to different private evidence. "
    "Use only the information in these summaries — do not use outside knowledge. "
    "Output your final answer as:\nANSWER: <your concise answer>"
)


def _build_summary_prompt(context: str, question: str, max_words: int) -> str:
    return (
        f"Your private evidence:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Write a concise summary (at most {max_words} words) of the key facts "
        "in your evidence that are relevant to this question. "
        "Do not answer the question directly."
    )


def _build_aggregation_prompt(summaries: list[str], question: str) -> str:
    parts = [f"Agent {i+1} summary:\n{s}" for i, s in enumerate(summaries)]
    body = "\n\n".join(parts)
    return (
        f"{body}\n\n"
        f"Question: {question}\n\n"
        "Based on all agent summaries, answer the question.\nANSWER: "
    )


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_summary_exchange_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_summary_words: int = 60,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Run summary exchange for all instances using two batched API passes.

    Pass 1 — All agents generate their summaries (one large batch).
    Pass 2 — All aggregators answer from the collected summaries (one large batch).
    """
    # ---------- Pass 1: generate summaries ----------
    sum_requests: list[APIRequest] = []
    sum_index: list[tuple[int, int]] = []  # (inst_i, agent_j)

    for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
        for agent_j, shard in enumerate(shards):
            sum_requests.append(
                APIRequest(
                    system_query=_SUMMARY_SYSTEM,
                    user_query=_build_summary_prompt(
                        format_shard_context(shard),
                        instance["question"],
                        max_summary_words,
                    ),
                    model=model,
                    max_tokens=max_tokens // 2,
                    metadata={
                        "instance_id": instance["id"],
                        "agent": agent_j,
                        "phase": "summary",
                    },
                )
            )
            sum_index.append((inst_i, agent_j))

    sum_responses = batch_fn(sum_requests, max_workers=max_workers)

    n_agents_per_inst = [len(s) for s in shards_list]
    summaries_list: list[list[str]] = [[""] * k for k in n_agents_per_inst]
    for k, resp in enumerate(sum_responses):
        inst_i, agent_j = sum_index[k]
        if resp.success and resp.content.strip():
            summaries_list[inst_i][agent_j] = resp.content.strip()

    # ---------- Pass 2: aggregate ----------
    agg_requests: list[APIRequest] = []
    comm_tokens_list: list[int] = []

    for inst_i, instance in enumerate(instances):
        summaries = summaries_list[inst_i]
        comm_tokens_list.append(sum(count_tokens_approx(s) for s in summaries))
        agg_requests.append(
            APIRequest(
                system_query=_AGG_SYSTEM,
                user_query=_build_aggregation_prompt(summaries, instance["question"]),
                model=model,
                max_tokens=max_tokens,
                metadata={"instance_id": instance["id"], "phase": "summary_agg"},
            )
        )

    agg_responses = batch_fn(agg_requests, max_workers=max_workers)

    # Sum-up tokens: summary generation (pass 1) per instance
    sum_tokens_per_inst: list[int] = [0] * len(instances)
    for k, resp in enumerate(sum_responses):
        inst_i, _ = sum_index[k]
        sum_tokens_per_inst[inst_i] += resp.usage.get("total_tokens", 0)

    results = []
    for inst_i, (instance, resp) in enumerate(zip(instances, agg_responses)):
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        agg_tokens = resp.usage.get("total_tokens", 0)
        results.append(
            ProtocolResult(
                instance_id=instance["id"],
                pred=pred,
                f1=answer_f1(pred, instance),
                comm_tokens=comm_tokens_list[inst_i],
                total_llm_tokens=sum_tokens_per_inst[inst_i] + agg_tokens,
                transmitted_states=summaries_list[inst_i],
            )
        )
    return results
