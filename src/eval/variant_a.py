"""
variant_a.py — Distributed isolated-agent evaluation (best-agent oracle).

Two sharding settings:
    A1: 1 supporting paragraph per agent.
        num_agents = num_supporting_paragraphs
        ICG = num_supporting - 1

    A2: 2 supporting paragraphs per agent (last agent may get 1 if odd count).
        num_agents = ceil(num_supporting / 2)
        ICG = num_supporting - 2

Each agent answers independently from its private shard only (isolated
condition per the paper's Section 3.3).  The instance F1 is the maximum
F1 over all agents — the oracle upper bound on isolated distributed solving.
This is compared against Variant B (centralized, all evidence) to measure
the performance gap attributable to evidence distribution.

Token budget T is the same per agent as the single agent in Variant B.

Public API:
    run_variant_a1(instance, api_fn, model, max_tokens) -> dict
    run_variant_a2(instance, api_fn, model, max_tokens) -> dict
    run_variant_a_batch(instances, setting, api_fn, model, max_tokens,
                        max_workers) -> list[dict]
"""

from __future__ import annotations

import random
import sys
import os
from typing import Callable

# Ensure repo root is importable when run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utility.apis.base import APIRequest, APIResponse
from .data_loader import get_supporting_paragraphs
from .evaluate import answer_f1

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a question-answering assistant. "
    "Answer based only on the provided evidence. "
    "Be concise — give only the answer, no explanation."
)


def _build_user_prompt(paragraph_texts: list[str], question: str) -> str:
    """Build the user turn for one agent given its assigned paragraph(s)."""
    if len(paragraph_texts) == 1:
        evidence_block = paragraph_texts[0]
    else:
        evidence_block = "\n\n".join(
            f"[Paragraph {i+1}]\n{text}" for i, text in enumerate(paragraph_texts)
        )
    return f"Evidence:\n{evidence_block}\n\nQuestion: {question}\n\nAnswer concisely."


# ---------------------------------------------------------------------------
# Shard assignment helpers
# ---------------------------------------------------------------------------

def _assign_shards_a1(supporting_paras: list[dict]) -> list[list[dict]]:
    """A1: one paragraph per agent.  Returns a list of single-element lists."""
    return [[p] for p in supporting_paras]


def _assign_shards_a2(
    supporting_paras: list[dict], rng: random.Random
) -> list[list[dict]]:
    """A2: two paragraphs per agent (randomised order).

    Returns a list of 1- or 2-element lists (last shard may have 1 if odd).
    """
    paras = list(supporting_paras)
    rng.shuffle(paras)
    shards: list[list[dict]] = []
    i = 0
    while i < len(paras):
        shards.append(paras[i : i + 2])
        i += 2
    return shards


def _assign_shards_a3(
    supporting_paras: list[dict], rng: random.Random
) -> list[list[dict]]:
    """A3: three paragraphs per agent (randomised order).

    Returns a list of shard lists; last shard may have fewer than 3 if the
    total is not divisible by 3 (e.g. 4-hop → shards of [3, 1]).
    """
    paras = list(supporting_paras)
    rng.shuffle(paras)
    shards: list[list[dict]] = []
    i = 0
    while i < len(paras):
        shards.append(paras[i : i + 3])
        i += 3
    return shards


# ---------------------------------------------------------------------------
# Core per-instance runner
# ---------------------------------------------------------------------------

def _run_instance(
    instance: dict,
    shards: list[list[dict]],
    api_fn: Callable,
    model: str,
    max_tokens: int,
) -> dict:
    """Run isolated multi-agent evaluation for a single instance.

    Each agent answers independently from its private shard.  The instance
    score is the maximum F1 over all agents (oracle best-agent).

    Args:
        instance:   MuSiQue instance dict (must have ``question``, ``answer``,
                    ``answer_aliases``, ``icg``).
        shards:     List of shard assignments; each element is a list of
                    paragraph dicts assigned to one agent.
        api_fn:     A callable with signature matching
                    ``openrouter_api.batch_request``:
                    ``(requests: list[APIRequest], max_workers: int)
                      -> list[APIResponse]``
        model:      Model identifier string (e.g. "google/gemma-4-26b-a4b-it").
        max_tokens: Per-agent output token budget.

    Returns:
        Dict with keys:
            id, icg, num_agents, agent_answers, agent_f1s, pred, f1
        where ``pred`` is the best agent's answer and ``f1`` is max agent F1.
    """
    question = instance["question"]
    requests: list[APIRequest] = []
    for shard in shards:
        texts = [p["paragraph_text"] for p in shard]
        requests.append(
            APIRequest(
                system_query=SYSTEM_PROMPT,
                user_query=_build_user_prompt(texts, question),
                model=model,
                max_tokens=max_tokens,
                metadata={
                    "instance_id": instance["id"],
                    "num_agents": len(shards),
                },
            )
        )

    responses: list[APIResponse] = api_fn(requests, max_workers=len(shards))

    agent_answers: list[str] = []
    agent_errors: list[str | None] = []
    for resp in responses:
        if resp.success and resp.content.strip():
            agent_answers.append(resp.content.strip())
            agent_errors.append(None)
        else:
            agent_answers.append("")
            agent_errors.append(resp.error or "empty response")

    agent_f1s: list[float] = [answer_f1(ans, instance) for ans in agent_answers]

    if agent_f1s:
        best_idx = agent_f1s.index(max(agent_f1s))
        f1 = agent_f1s[best_idx]
        pred = agent_answers[best_idx]
    else:
        f1 = 0.0
        pred = ""

    # Effective ICG = num_supporting - largest shard size
    # (differs from structural ICG when shard size > 1)
    num_supporting = sum(len(s) for s in shards)
    effective_icg = num_supporting - max(len(s) for s in shards)

    return {
        "id": instance["id"],
        "icg": effective_icg,
        "structural_icg": instance["icg"],
        "num_agents": len(shards),
        "agent_answers": agent_answers,
        "agent_errors": agent_errors,
        "agent_f1s": agent_f1s,
        "agent_shards": [[p["title"] for p in shard] for shard in shards],
        "pred": pred,
        "f1": f1,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_variant_a1(
    instance: dict,
    api_fn: Callable,
    model: str = "google/gemma-4-26b-a4b-it",
    max_tokens: int = 200,
) -> dict:
    """Run Variant A1 (1 paragraph per agent) on a single instance.

    Returns result dict with keys: id, icg, num_agents, agent_answers,
    agent_f1s, pred, f1.
    """
    supporting = get_supporting_paragraphs(instance)
    shards = _assign_shards_a1(supporting)
    return _run_instance(instance, shards, api_fn, model, max_tokens)


def run_variant_a2(
    instance: dict,
    api_fn: Callable,
    model: str = "google/gemma-4-26b-a4b-it",
    max_tokens: int = 200,
    seed: int = 42,
) -> dict:
    """Run Variant A2 (2 paragraphs per agent) on a single instance."""
    rng = random.Random(seed)
    supporting = get_supporting_paragraphs(instance)
    shards = _assign_shards_a2(supporting, rng)
    return _run_instance(instance, shards, api_fn, model, max_tokens)


def run_variant_a3(
    instance: dict,
    api_fn: Callable,
    model: str = "google/gemma-4-26b-a4b-it",
    max_tokens: int = 200,
    seed: int = 42,
) -> dict:
    """Run Variant A3 (3 paragraphs per agent) on a single instance.

    For 4-hop instances this produces two agents: one with 3 paragraphs and
    one with 1, giving effective ICG = 4 - 3 = 1.
    """
    rng = random.Random(seed)
    supporting = get_supporting_paragraphs(instance)
    shards = _assign_shards_a3(supporting, rng)
    return _run_instance(instance, shards, api_fn, model, max_tokens)


def run_variant_a_batch(
    instances: list[dict],
    setting: str,
    api_fn: Callable,
    model: str = "google/gemma-4-26b-a4b-it",
    max_tokens: int = 200,
    max_workers: int = 5,
    seed: int = 42,
) -> list[dict]:
    """Run a Variant A setting over a list of instances sequentially.

    Each instance's agents are dispatched concurrently (via api_fn's own
    concurrency), but instances are processed one at a time to keep memory
    and rate-limit pressure predictable.

    Args:
        instances:   List of MuSiQue instance dicts (each must have ``icg``).
        setting:     ``"a1"`` or ``"a2"`` (case-insensitive).
        api_fn:      batch_request-compatible callable.
        model:       Model identifier string.
        max_tokens:  Per-agent output token budget.
        max_workers: Concurrency hint passed to api_fn.
        seed:        Base random seed for A2 shard shuffling; incremented per
                     instance to ensure independent shuffles.

    Returns:
        List of result dicts (same order as ``instances``), each with keys:
        id, icg, num_agents, agent_answers, agent_f1s, pred, f1.
    """
    setting = setting.lower()
    if setting not in ("a1", "a2", "a3"):
        raise ValueError(f"setting must be 'a1', 'a2', or 'a3', got {setting!r}")

    results: list[dict] = []
    for i, inst in enumerate(instances):
        if setting == "a1":
            result = run_variant_a1(inst, api_fn, model, max_tokens)
        elif setting == "a2":
            result = run_variant_a2(inst, api_fn, model, max_tokens, seed=seed + i)
        else:
            result = run_variant_a3(inst, api_fn, model, max_tokens, seed=seed + i)
        results.append(result)
    return results
