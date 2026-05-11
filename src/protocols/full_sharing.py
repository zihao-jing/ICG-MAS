"""
Full evidence sharing oracle.

All supporting paragraphs from all agents are pooled and given to a single
central reasoner.  This is the communication upper bound: every bit of
evidence is transmitted, so Accuracy ≈ Acc_full.

comm_tokens counts the total tokens in the shared evidence (the cost that
would have been paid to transmit everything).
"""

from __future__ import annotations

from typing import Callable

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1
from .base import ProtocolResult, extract_answer, count_tokens_approx


_FULL_SYSTEM = (
    "You are a question-answering assistant. "
    "You have been given all evidence documents from every agent in the system. "
    "Reason step by step across all documents to find the answer. "
    "Do NOT use any facts not explicitly stated in the provided documents. "
    "Output your final answer as:\nANSWER: <your concise answer>\n"
    "If the answer cannot be found, write:\nANSWER: Insufficient information."
)


def _build_full_prompt(paragraphs: list[dict], question: str) -> str:
    parts = [
        f"[Document {i+1}: {p['title']}]\n{p['paragraph_text']}"
        for i, p in enumerate(paragraphs)
    ]
    return (
        f"All evidence documents (pooled from all agents):\n"
        + "\n\n".join(parts)
        + f"\n\nQuestion: {question}\n\n"
        "Reason step by step across all documents. Do not use outside knowledge.\n"
        "ANSWER: "
    )


def _build_full_prompt_context(full_context: str, question: str) -> str:
    """Full-sharing prompt for Silo-Bench (pre-formatted combined context)."""
    return (
        "All agents' complete evidence (pooled):\n\n"
        f"{full_context}\n\n"
        f"Task: {question}\n\n"
        "Reason across all evidence to produce the final answer.\n"
        "ANSWER: "
    )


def run_full_sharing(
    instance: dict,
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int = 5,
) -> ProtocolResult:
    """Pool all supporting paragraphs and answer from the complete evidence set."""
    supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
    comm_tokens = sum(count_tokens_approx(p["paragraph_text"]) for p in supporting)

    request = APIRequest(
        system_query=_FULL_SYSTEM,
        user_query=_build_full_prompt(supporting, instance["question"]),
        model=model,
        max_tokens=max_tokens,
        metadata={"instance_id": instance["id"], "phase": "full_sharing"},
    )
    responses = batch_fn([request], max_workers=1)
    resp = responses[0]

    raw = resp.content.strip() if resp.success and resp.content.strip() else ""
    pred = extract_answer(raw) if raw else ""

    return ProtocolResult(
        instance_id=instance["id"],
        pred=pred,
        f1=answer_f1(pred, instance),
        comm_tokens=comm_tokens,
    )


def run_full_sharing_batch(
    instances: list[dict],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Run full-sharing for all instances in one batched call.

    Supports both MuSiQue (instance has ``paragraphs``) and Silo-Bench
    (instance has ``full_context`` with all agents' prompts combined).
    """
    all_requests: list[APIRequest] = []
    comm_tokens_list: list[int] = []

    for instance in instances:
        if instance.get("full_context"):
            full_ctx = instance["full_context"]
            comm_tokens_list.append(count_tokens_approx(full_ctx))
            user_query = _build_full_prompt_context(full_ctx, instance["question"])
        else:
            supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
            comm_tokens_list.append(
                sum(count_tokens_approx(p["paragraph_text"]) for p in supporting)
            )
            user_query = _build_full_prompt(supporting, instance["question"])
        all_requests.append(
            APIRequest(
                system_query=_FULL_SYSTEM,
                user_query=user_query,
                model=model,
                max_tokens=max_tokens,
                metadata={"instance_id": instance["id"], "phase": "full_sharing"},
            )
        )

    responses = batch_fn(all_requests, max_workers=max_workers)

    results = []
    for instance, resp, comm_tokens in zip(instances, responses, comm_tokens_list):
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        results.append(
            ProtocolResult(
                instance_id=instance["id"],
                pred=pred,
                f1=answer_f1(pred, instance),
                comm_tokens=comm_tokens,
                total_llm_tokens=resp.usage.get("total_tokens", 0),
            )
        )
    return results
