"""
Gated communication baselines:
  - confidence_gated:    agents communicate when self-assessed confidence < threshold
  - disagreement_gated:  agents communicate when they disagree on the answer

Both protocols are implemented in batch mode: a single large API batch covers
the local-answer phase for all instances; then gating is applied to determine
which instances/agents need a follow-up aggregation call; those aggregations
are collected in a second batch.
"""

from __future__ import annotations

from typing import Callable, Optional
import re

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1, majority_vote as _majority_vote, normalize
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

_CONF_SYSTEM = (
    "You are a question-answering assistant. "
    "Answer using ONLY the provided documents — do not use background knowledge. "
    "After your answer, rate your confidence from 0.0 to 1.0 that the answer is correct. "
    "Use this exact format:\nANSWER: <answer>\nCONFIDENCE: <0.0-1.0>"
)

_LOCAL_PLAIN_SYSTEM = (
    "You are a question-answering assistant. "
    "Answer using ONLY the provided documents. "
    "Output:\nANSWER: <answer>"
)

_GATED_AGG_SYSTEM = (
    "You are a question-answering assistant. "
    "You have received evidence from agents that could not answer locally. "
    "Use all provided information to give the correct answer. "
    "Output your final answer as:\nANSWER: <answer>"
)


def _build_conf_prompt(context: str, question: str) -> str:
    return (
        f"Documents:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the documents above.\n"
        "ANSWER: <answer>\nCONFIDENCE: <0.0-1.0>"
    )


def _build_plain_prompt(context: str, question: str) -> str:
    return (
        f"Documents:\n{context}\n\nQuestion: {question}\n\nANSWER: "
    )


def _parse_confidence(text: str) -> float:
    match = re.search(r"CONFIDENCE:\s*([\d.]+)", text, re.IGNORECASE)
    if match:
        try:
            return max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            pass
    return 0.5


def _build_gated_agg_prompt(
    answering: list[tuple[int, str]],   # (agent_idx, answer) — high-confidence
    sending: list[tuple[int, str]],     # (agent_idx, context) — low-confidence
    question: str,
) -> str:
    parts = [f"Agent {idx+1} answer: {ans}" for idx, ans in answering]
    parts += [f"Agent {idx+1} evidence:\n{ctx}" for idx, ctx in sending]
    return "\n\n".join(parts) + f"\n\nQuestion: {question}\n\nANSWER: "


def _build_disagree_agg_prompt(
    contexts: list[tuple[int, str]],   # (agent_idx, context)
    question: str,
) -> str:
    parts = [f"Agent {idx+1} evidence:\n{ctx}" for idx, ctx in contexts]
    return (
        "\n\n".join(parts)
        + f"\n\nQuestion: {question}\n\n"
        "Multiple agents disagree. Use all evidence to give the correct answer.\n"
        "ANSWER: "
    )


# ---------------------------------------------------------------------------
# Confidence-gated batch runner
# ---------------------------------------------------------------------------

def run_confidence_gated_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    confidence_threshold: float = 0.6,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Confidence-gated communication, fully batched.

    Pass 1 — All agents generate answers + confidence scores (large batch).
    Pass 2 — For instances where any agent has low confidence, run the
              aggregator with those agents' evidence (targeted batch).
    """
    # ---------- Pass 1: local QA + confidence ----------
    p1_requests: list[APIRequest] = []
    p1_index: list[tuple[int, int]] = []

    for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
        for agent_j, shard in enumerate(shards):
            p1_requests.append(
                APIRequest(
                    system_query=_CONF_SYSTEM,
                    user_query=_build_conf_prompt(
                        format_shard_context(shard), instance["question"]
                    ),
                    model=model,
                    max_tokens=max_tokens,
                    metadata={
                        "instance_id": instance["id"],
                        "agent": agent_j,
                        "phase": "conf_local",
                    },
                )
            )
            p1_index.append((inst_i, agent_j))

    p1_responses = batch_fn(p1_requests, max_workers=max_workers)

    n_agents_per = [len(s) for s in shards_list]
    local_answers_list: list[list[str]] = [[""] * k for k in n_agents_per]
    conf_list: list[list[float]] = [[0.5] * k for k in n_agents_per]

    for k, resp in enumerate(p1_responses):
        inst_i, agent_j = p1_index[k]
        text = resp.content.strip() if resp.success and resp.content.strip() else ""
        local_answers_list[inst_i][agent_j] = extract_answer(text)
        conf_list[inst_i][agent_j] = _parse_confidence(text)

    # ---------- Gate: which instances need aggregation? ----------
    needs_agg_idx: list[int] = []
    agg_requests: list[APIRequest] = []
    agg_comm_tokens: list[int] = []

    for inst_i, instance in enumerate(instances):
        answers = local_answers_list[inst_i]
        confs = conf_list[inst_i]
        shards = shards_list[inst_i]

        low_conf = [j for j, c in enumerate(confs) if c < confidence_threshold]
        if not low_conf:
            continue  # no aggregation needed

        answering = [
            (j, answers[j]) for j in range(len(shards)) if j not in low_conf
        ]
        sending = []
        tokens = 0
        for j in low_conf:
            ctx = format_shard_context(shards[j])
            tokens += count_tokens_approx(ctx)
            sending.append((j, ctx))

        agg_comm_tokens.append(tokens)
        needs_agg_idx.append(inst_i)
        agg_requests.append(
            APIRequest(
                system_query=_GATED_AGG_SYSTEM,
                user_query=_build_gated_agg_prompt(
                    answering, sending, instance["question"]
                ),
                model=model,
                max_tokens=max_tokens,
                metadata={"instance_id": instance["id"], "phase": "conf_agg"},
            )
        )

    agg_responses = batch_fn(agg_requests, max_workers=max_workers) if agg_requests else []

    # Build per-instance p1 token sums
    p1_llm_tokens: list[int] = [0] * len(instances)
    for k, resp in enumerate(p1_responses):
        inst_i, _ = p1_index[k]
        p1_llm_tokens[inst_i] += resp.usage.get("total_tokens", 0)

    # ---------- Assemble results ----------
    agg_by_inst: dict[int, tuple[str, int, int]] = {}  # inst_i → (pred, comm, agg_tok)
    for k, resp in enumerate(agg_responses):
        inst_i = needs_agg_idx[k]
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        agg_by_inst[inst_i] = (
            extract_answer(raw) if raw else "",
            agg_comm_tokens[k],
            resp.usage.get("total_tokens", 0),
        )

    results = []
    for inst_i, instance in enumerate(instances):
        if inst_i in agg_by_inst:
            pred, comm_tokens, agg_tok = agg_by_inst[inst_i]
        else:
            answers = local_answers_list[inst_i]
            non_refusal = [a for a in answers if not is_refusal(a)]
            pred = _majority_vote(non_refusal) if non_refusal else (answers[0] if answers else "")
            comm_tokens = 0
            agg_tok = 0
        results.append(
            ProtocolResult(
                instance_id=instance["id"],
                pred=pred,
                f1=answer_f1(pred, instance),
                comm_tokens=comm_tokens,
                total_llm_tokens=p1_llm_tokens[inst_i] + agg_tok,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Disagreement-gated batch runner
# ---------------------------------------------------------------------------

def run_disagreement_gated_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    precomputed_answers_list: Optional[list[list[str]]] = None,
    precomputed_tokens_list: Optional[list[list[int]]] = None,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Disagreement-gated communication, fully batched.

    If agents agree, return majority vote (no comm).
    If they disagree, share all evidence with a central aggregator.

    Pass 1 — (optional) compute local answers if not precomputed.
    Pass 2 — For disagreeing instances, run aggregators (targeted batch).
    """
    # ---------- Pass 1: local answers ----------
    local_llm_tokens: list[int] = [0] * len(instances)
    if precomputed_answers_list is not None:
        local_answers_list = [list(a) for a in precomputed_answers_list]
        if precomputed_tokens_list is not None:
            for inst_i, agent_toks in enumerate(precomputed_tokens_list):
                local_llm_tokens[inst_i] = sum(agent_toks)
    else:
        from .local import compute_local_answers_batch
        local_answers_list, raw_tokens = compute_local_answers_batch(
            instances, shards_list, batch_fn, model, max_tokens, max_workers
        )
        for inst_i, agent_toks in enumerate(raw_tokens):
            local_llm_tokens[inst_i] = sum(agent_toks)

    # ---------- Gate: which instances disagree? ----------
    needs_agg_idx: list[int] = []
    agg_requests: list[APIRequest] = []
    agg_comm_tokens: list[int] = []

    for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
        answers = local_answers_list[inst_i]
        non_refusal = [a for a in answers if not is_refusal(a)]
        unique_norms = set(" ".join(normalize(a)) for a in non_refusal if a)

        if len(unique_norms) <= 1:
            continue  # agreement — no communication

        contexts_with_idx = [(j, format_shard_context(s)) for j, s in enumerate(shards)]
        tokens = sum(count_tokens_approx(ctx) for _, ctx in contexts_with_idx)
        agg_comm_tokens.append(tokens)
        needs_agg_idx.append(inst_i)
        agg_requests.append(
            APIRequest(
                system_query=_GATED_AGG_SYSTEM,
                user_query=_build_disagree_agg_prompt(
                    contexts_with_idx, instance["question"]
                ),
                model=model,
                max_tokens=max_tokens,
                metadata={"instance_id": instance["id"], "phase": "disagree_agg"},
            )
        )

    agg_responses = batch_fn(agg_requests, max_workers=max_workers) if agg_requests else []

    agg_by_inst: dict[int, tuple[str, int, int]] = {}
    for k, resp in enumerate(agg_responses):
        inst_i = needs_agg_idx[k]
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        agg_by_inst[inst_i] = (
            extract_answer(raw) if raw else "",
            agg_comm_tokens[k],
            resp.usage.get("total_tokens", 0),
        )

    results = []
    for inst_i, instance in enumerate(instances):
        if inst_i in agg_by_inst:
            pred, comm_tokens, agg_tok = agg_by_inst[inst_i]
        else:
            answers = local_answers_list[inst_i]
            non_refusal = [a for a in answers if not is_refusal(a)]
            pred = _majority_vote(non_refusal) if non_refusal else (answers[0] if answers else "")
            comm_tokens = 0
            agg_tok = 0
        results.append(
            ProtocolResult(
                instance_id=instance["id"],
                pred=pred,
                f1=answer_f1(pred, instance),
                comm_tokens=comm_tokens,
                total_llm_tokens=local_llm_tokens[inst_i] + agg_tok,
            )
        )
    return results
