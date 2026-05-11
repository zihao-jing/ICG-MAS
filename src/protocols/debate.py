"""
Free-form debate baseline (Du et al. 2024 style).

Protocol:
  Round 0 — Each agent independently answers from its private shard.
  Round 1..R — Each agent sees all other agents' previous answers alongside
               its own evidence and updates its answer.
  Final answer — Majority vote over the last round's answers.

comm_tokens counts tokens in all inter-agent messages (others' answers seen
per round, summed across all agents × rounds).  Round-0 answers are not
counted as communication (they are local computations).

For budget equalization with the relay methods, run with n_rounds=1.
"""

from __future__ import annotations

from typing import Callable

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1, majority_vote as _majority_vote
from .base import (
    AgentShard,
    ProtocolResult,
    format_shard_context,
    extract_answer,
    is_refusal,
    count_tokens_approx,
)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_INIT_SYSTEM = (
    "You are a question-answering assistant in a multi-agent reasoning team. "
    "Answer based only on your provided documents. "
    "Output your final answer as:\nANSWER: <answer>"
)

_DEBATE_SYSTEM = (
    "You are a question-answering assistant in a multi-agent reasoning team. "
    "You can see your own evidence and what other agents answered in the previous round. "
    "Consider whether any other agent's answer reveals evidence you lacked. "
    "Output your updated final answer as:\nANSWER: <answer>"
)


def _build_init_prompt(context: str, question: str) -> str:
    return (
        f"Your private evidence:\n{context}\n\n"
        f"Question: {question}\n\nANSWER: "
    )


def _build_debate_prompt(
    context: str,
    question: str,
    other_answers: list[str],
    round_num: int,
) -> str:
    others_block = "\n".join(
        f"  Agent {i+1}: {ans}" for i, ans in enumerate(other_answers)
    )
    return (
        f"Your private evidence:\n{context}\n\n"
        f"Other agents' answers (Round {round_num - 1}):\n{others_block}\n\n"
        f"Question: {question}\n\n"
        "Update your answer considering all available information.\nANSWER: "
    )


# ---------------------------------------------------------------------------
# Per-instance runner
# ---------------------------------------------------------------------------

def run_debate(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    n_rounds: int = 1,
    precomputed_answers: list[str] | None = None,
    max_workers: int = 5,
) -> ProtocolResult:
    """Run R-round free-form debate among all agents.

    If precomputed_answers is supplied (from the shared local-agent phase),
    round-0 answers are taken from it without extra API calls.
    """
    question = instance["question"]
    contexts = [format_shard_context(s) for s in shards]

    # Round 0: local independent answers
    if precomputed_answers is not None:
        current_answers = list(precomputed_answers)
    else:
        init_requests = [
            APIRequest(
                system_query=_INIT_SYSTEM,
                user_query=_build_init_prompt(ctx, question),
                model=model,
                max_tokens=max_tokens,
                metadata={"instance_id": instance["id"], "agent": s.agent_idx, "round": 0},
            )
            for ctx, s in zip(contexts, shards)
        ]
        init_responses = batch_fn(init_requests, max_workers=max_workers)
        current_answers = [
            extract_answer(r.content) if r.success and r.content.strip() else ""
            for r in init_responses
        ]

    comm_tokens = 0

    for round_num in range(1, n_rounds + 1):
        round_requests = []
        per_agent_comm = []

        for i, (ctx, s) in enumerate(zip(contexts, shards)):
            others = [a for j, a in enumerate(current_answers) if j != i]
            per_agent_comm.append(sum(count_tokens_approx(a) for a in others))
            round_requests.append(
                APIRequest(
                    system_query=_DEBATE_SYSTEM,
                    user_query=_build_debate_prompt(ctx, question, others, round_num),
                    model=model,
                    max_tokens=max_tokens,
                    metadata={
                        "instance_id": instance["id"],
                        "agent": s.agent_idx,
                        "round": round_num,
                    },
                )
            )

        round_responses = batch_fn(round_requests, max_workers=max_workers)
        comm_tokens += sum(per_agent_comm)

        current_answers = [
            extract_answer(r.content) if r.success and r.content.strip() else cur
            for r, cur in zip(round_responses, current_answers)
        ]

    non_refusal = [a for a in current_answers if not is_refusal(a)]
    pred = (
        _majority_vote(non_refusal) if non_refusal else (current_answers[0] if current_answers else "")
    )
    return ProtocolResult(
        instance_id=instance["id"],
        pred=pred,
        f1=answer_f1(pred, instance),
        comm_tokens=comm_tokens,
    )


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_debate_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    n_rounds: int = 1,
    precomputed_answers_list: list[list[str]] | None = None,
    precomputed_tokens_list: list[list[int]] | None = None,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Run debate for all instances; round-0 uses a single large batched call.

    Round-0 answers are batched globally (all instances × all agents at once).
    Each debate round then processes all instances' agents in one batch.
    """
    n = len(instances)
    n_agents_per_inst = [len(s) for s in shards_list]

    # ---------- Round 0: local answers ----------
    # Per-instance sum of round-0 LLM tokens (from precomputed or own call)
    r0_llm_tokens: list[int] = [0] * n

    if precomputed_answers_list is not None:
        current_answers_list = [list(a) for a in precomputed_answers_list]
        if precomputed_tokens_list is not None:
            for inst_i, agent_toks in enumerate(precomputed_tokens_list):
                r0_llm_tokens[inst_i] = sum(agent_toks)
    else:
        r0_requests: list[APIRequest] = []
        r0_index: list[tuple[int, int]] = []  # (inst_i, agent_j)

        for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
            ctx_list = [format_shard_context(s) for s in shards]
            for agent_j, (ctx, s) in enumerate(zip(ctx_list, shards)):
                r0_requests.append(
                    APIRequest(
                        system_query=_INIT_SYSTEM,
                        user_query=_build_init_prompt(ctx, instance["question"]),
                        model=model,
                        max_tokens=max_tokens,
                        metadata={
                            "instance_id": instance["id"],
                            "agent": agent_j,
                            "round": 0,
                        },
                    )
                )
                r0_index.append((inst_i, agent_j))

        r0_responses = batch_fn(r0_requests, max_workers=max_workers)
        current_answers_list = [[""] * k for k in n_agents_per_inst]
        for k, resp in enumerate(r0_responses):
            inst_i, agent_j = r0_index[k]
            r0_llm_tokens[inst_i] += resp.usage.get("total_tokens", 0)
            if resp.success and resp.content.strip():
                current_answers_list[inst_i][agent_j] = extract_answer(resp.content)

    comm_tokens_list = [0] * n
    debate_llm_tokens: list[int] = [0] * n  # tokens from debate rounds only

    # ---------- Debate rounds 1..R ----------
    for round_num in range(1, n_rounds + 1):
        rd_requests: list[APIRequest] = []
        rd_index: list[tuple[int, int]] = []
        rd_comm: list[tuple[int, int]] = []  # (inst_i, tokens)

        for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
            ctx_list = [format_shard_context(s) for s in shards]
            for agent_j, (ctx, s) in enumerate(zip(ctx_list, shards)):
                others = [
                    a
                    for j, a in enumerate(current_answers_list[inst_i])
                    if j != agent_j
                ]
                rd_comm.append((inst_i, sum(count_tokens_approx(a) for a in others)))
                rd_requests.append(
                    APIRequest(
                        system_query=_DEBATE_SYSTEM,
                        user_query=_build_debate_prompt(
                            ctx, instance["question"], others, round_num
                        ),
                        model=model,
                        max_tokens=max_tokens,
                        metadata={
                            "instance_id": instance["id"],
                            "agent": agent_j,
                            "round": round_num,
                        },
                    )
                )
                rd_index.append((inst_i, agent_j))

        rd_responses = batch_fn(rd_requests, max_workers=max_workers)

        for inst_i, tokens in rd_comm:
            comm_tokens_list[inst_i] += tokens
        for k, resp in enumerate(rd_responses):
            inst_i, _ = rd_index[k]
            debate_llm_tokens[inst_i] += resp.usage.get("total_tokens", 0)

        new_answers_list = [list(a) for a in current_answers_list]
        for k, resp in enumerate(rd_responses):
            inst_i, agent_j = rd_index[k]
            if resp.success and resp.content.strip():
                new_answers_list[inst_i][agent_j] = extract_answer(resp.content)
        current_answers_list = new_answers_list

    # ---------- Aggregate results ----------
    results = []
    for inst_i, instance in enumerate(instances):
        answers = current_answers_list[inst_i]
        non_refusal = [a for a in answers if not is_refusal(a)]
        pred = _majority_vote(non_refusal) if non_refusal else (answers[0] if answers else "")
        results.append(
            ProtocolResult(
                instance_id=instance["id"],
                pred=pred,
                f1=answer_f1(pred, instance),
                comm_tokens=comm_tokens_list[inst_i],
                total_llm_tokens=r0_llm_tokens[inst_i] + debate_llm_tokens[inst_i],
            )
        )
    return results
