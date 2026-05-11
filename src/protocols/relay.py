"""
State relay protocols:
  - random_relay:      extract atomic states, select uniformly at random
  - csc_topk:          CSC top-k (select by composite necessity score)
  - csc_redundancy:    CSC + redundancy penalty (Eq. 4 in paper)

All three share the extraction and scoring phases, which are precomputed once
via extract_states_batch() and score_states_batch() in run_experiment.py.

The aggregation step follows the evidence-board prompt from Section 3.5 of the
paper: agents relay compact factual states, not answers or rationales.
"""

from __future__ import annotations

import concurrent.futures
import random
from typing import Callable

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1
from .base import (
    AgentShard,
    ProtocolResult,
    format_shard_context,
    extract_answer,
    count_tokens_approx,
    parse_score_json,
)


# ---------------------------------------------------------------------------
# Prompts (from paper Sections 3.3 – 3.5)
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = (
    "You are an evidence extraction assistant in a multi-agent reasoning system. "
    "Extract atomic facts from the provided evidence that may help answer the question.\n"
    "Each fact must be:\n"
    "  - Self-contained (interpretable without other context)\n"
    "  - Specific (include exact names, numbers, and dates)\n"
    "  - A factual claim, NOT a reasoning step or paraphrase of the question\n"
    "Output a numbered list of atomic facts, one per line. "
    "Do not add explanations or preamble."
)

_SCORING_SYSTEM = (
    "You are a verifier for federated reasoning. "
    "Given a question and one atomic fact extracted from a private evidence shard, "
    "score whether this fact should be communicated to other agents.\n\n"
    "Return JSON only with no extra text:\n"
    '{"relevance": <0-1>, "uniqueness": <0-1>, "criticality": <0-1>, "overall": <0-1>}'
)

_AGGREGATION_SYSTEM = (
    "You are a question-answering assistant. "
    "The following atomic facts were transmitted from private evidence shards. "
    "Use ONLY these facts to answer the question — do not rely on prior knowledge "
    "not present in the listed facts. "
    "Output your final answer as:\nANSWER: <your concise answer>\n"
    "If the facts are insufficient, write:\nANSWER: Insufficient information."
)


def _build_extraction_prompt(context: str, question: str, max_states: int) -> str:
    return (
        f"Question: {question}\n\n"
        f"Evidence shard:\n{context}\n\n"
        f"Extract up to {max_states} atomic facts from the evidence above that "
        "may be relevant to answering the question. "
        "Output a numbered list (one fact per line)."
    )


def _build_scoring_prompt(question: str, fact: str) -> str:
    # Verbatim from paper Section 3.4
    return (
        f"Question: {question}\n"
        f"Atomic fact: {fact}\n\n"
        "Score the fact on three dimensions from 0 to 1:\n"
        "1. Relevance: Does this fact relate to the question?\n"
        "2. Uniqueness: Is this fact likely unavailable to other agents?\n"
        "3. Answer-criticality: Could omitting this fact change the final answer?\n\n"
        "Return JSON only: "
        '{"relevance": ..., "uniqueness": ..., "criticality": ..., "overall": ...}'
    )


def _build_evidence_board_prompt(
    states_per_agent: list[list[str]], question: str
) -> str:
    # Verbatim from paper Section 3.5
    parts = []
    for i, states in enumerate(states_per_agent):
        if states:
            lines = "\n".join(f"  -- {s}" for s in states)
            parts.append(f"Agent {i+1} states:\n{lines}")
        else:
            parts.append(f"Agent {i+1} states:\n  (none transmitted)")
    board = "\n\n".join(parts)
    return (
        "The following facts were transmitted from private evidence shards.\n"
        "Use only these facts to answer the question.\n\n"
        f"{board}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_states(text: str, max_states: int) -> list[str]:
    """Parse a numbered list of atomic facts from LLM output."""
    import re
    lines = text.strip().split("\n")
    states: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[.):\s]+", "", line).strip()
        if cleaned:
            states.append(cleaned)
        if len(states) >= max_states:
            break
    return states


# ---------------------------------------------------------------------------
# Batched extraction (shared by random_relay, csc_topk, csc_redundancy)
# ---------------------------------------------------------------------------

def extract_states_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
    max_workers: int,
) -> tuple[list[list[list[str]]], list[int]]:
    """Extract atomic states for every (instance, agent) pair in one batch.

    Returns:
        (states, per_inst_tokens) where:
            states[inst_i][agent_j]    = list[state_str]
            per_inst_tokens[inst_i]    = sum of total_tokens for that instance
    """
    all_requests: list[APIRequest] = []
    index_map: list[tuple[int, int]] = []

    for inst_i, (instance, shards) in enumerate(zip(instances, shards_list)):
        for agent_j, shard in enumerate(shards):
            all_requests.append(
                APIRequest(
                    system_query=_EXTRACTION_SYSTEM,
                    user_query=_build_extraction_prompt(
                        format_shard_context(shard),
                        instance["question"],
                        max_states_per_agent,
                    ),
                    model=model,
                    max_tokens=max_tokens // 2,
                    metadata={
                        "instance_id": instance["id"],
                        "agent": agent_j,
                        "phase": "extraction",
                    },
                )
            )
            index_map.append((inst_i, agent_j))

    responses = batch_fn(all_requests, max_workers=max_workers)

    states: list[list[list[str]]] = [
        [[] for _ in shards] for shards in shards_list
    ]
    per_inst_tokens: list[int] = [0] * len(instances)
    for k, resp in enumerate(responses):
        inst_i, agent_j = index_map[k]
        per_inst_tokens[inst_i] += resp.usage.get("total_tokens", 0)
        if resp.success and resp.content.strip():
            states[inst_i][agent_j] = _parse_states(resp.content, max_states_per_agent)
    return states, per_inst_tokens


# ---------------------------------------------------------------------------
# Batched scoring (shared by csc_topk, csc_redundancy)
# ---------------------------------------------------------------------------

def score_states_batch(
    instances: list[dict],
    all_states: list[list[list[str]]],
    batch_fn: Callable,
    model: str,
    max_workers: int,
) -> tuple[list[list[list[dict]]], list[int]]:
    """Score every atomic state for every (instance, agent) pair in one batch.

    Returns:
        (scores, per_inst_tokens) where:
            scores[inst_i][agent_j][state_k] = score_dict {relevance, uniqueness, criticality, composite}
            per_inst_tokens[inst_i]           = sum of total_tokens for that instance
    """
    all_requests: list[APIRequest] = []
    index_map: list[tuple[int, int, int]] = []

    for inst_i, (instance, agent_states) in enumerate(zip(instances, all_states)):
        for agent_j, states in enumerate(agent_states):
            for state_k, state in enumerate(states):
                all_requests.append(
                    APIRequest(
                        system_query=_SCORING_SYSTEM,
                        user_query=_build_scoring_prompt(instance["question"], state),
                        model=model,
                        max_tokens=128,
                        temperature=0.0,
                        metadata={
                            "instance_id": instance["id"],
                            "agent": agent_j,
                            "state_idx": state_k,
                            "phase": "scoring",
                        },
                    )
                )
                index_map.append((inst_i, agent_j, state_k))

    # Build empty result structure first (handles case with no states)
    scores: list[list[list[dict]]] = [
        [[{} for _ in states] for states in agent_states]
        for agent_states in all_states
    ]
    per_inst_tokens: list[int] = [0] * len(instances)

    if not all_requests:
        return scores, per_inst_tokens

    responses = batch_fn(all_requests, max_workers=max_workers)
    for k, resp in enumerate(responses):
        inst_i, agent_j, state_k = index_map[k]
        per_inst_tokens[inst_i] += resp.usage.get("total_tokens", 0)
        if resp.success and resp.content.strip():
            scores[inst_i][agent_j][state_k] = parse_score_json(resp.content)
        else:
            scores[inst_i][agent_j][state_k] = {
                "relevance": 0.5,
                "uniqueness": 0.5,
                "criticality": 0.5,
                "composite": 0.5,
            }
    return scores, per_inst_tokens


# ---------------------------------------------------------------------------
# Selection methods
# ---------------------------------------------------------------------------

def _topk_select(states: list[str], scores: list[dict], k: int) -> list[str]:
    """Select top-k states ranked by composite necessity score (Eq. 3)."""
    if not states:
        return []
    ranked = sorted(
        zip(states, scores),
        key=lambda pair: pair[1].get("composite", 0.0),
        reverse=True,
    )
    return [s for s, _ in ranked[:k]]


def _jaccard_sim(a: str, b: str) -> float:
    """Token-level Jaccard similarity used for the redundancy penalty."""
    from src.eval.evaluate import normalize
    toks_a = set(normalize(a))
    toks_b = set(normalize(b))
    if not toks_a and not toks_b:
        return 0.0
    return len(toks_a & toks_b) / len(toks_a | toks_b)


def _redundancy_select(
    states: list[str],
    scores: list[dict],
    k: int,
    rho: float = 0.5,
) -> list[str]:
    """Greedy budgeted selection with redundancy penalty (Eq. 4 in paper).

    Iteratively picks the state that maximises:
        s(z) - rho * sum_{z' already selected} sim(z, z')
    Setting rho=0 recovers top-k selection.
    """
    if not states:
        return []

    selected_indices: list[int] = []
    remaining = list(range(len(states)))

    for _ in range(min(k, len(states))):
        if not remaining:
            break
        best_idx, best_val = None, float("-inf")
        for i in remaining:
            base_score = scores[i].get("composite", 0.0)
            penalty = rho * sum(
                _jaccard_sim(states[i], states[j]) for j in selected_indices
            )
            val = base_score - penalty
            if val > best_val:
                best_val = val
                best_idx = i
        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    return [states[i] for i in selected_indices]


# ---------------------------------------------------------------------------
# Evidence-board aggregation (shared by all three relay methods)
# ---------------------------------------------------------------------------

def _aggregate_evidence_board_batch(
    instances: list[dict],
    selected_list: list[list[list[str]]],  # [inst_i][agent_j] -> list[state]
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int,
) -> list[tuple[str, float, int, int]]:
    """Run evidence-board aggregation for all instances in one batch.

    Returns list of (pred, f1, comm_tokens, agg_total_tokens) tuples.
    """
    agg_requests: list[APIRequest] = []
    comm_tokens_list: list[int] = []

    for instance, selected in zip(instances, selected_list):
        all_states = [s for agent_states in selected for s in agent_states]
        comm_tokens_list.append(sum(count_tokens_approx(s) for s in all_states))
        agg_requests.append(
            APIRequest(
                system_query=_AGGREGATION_SYSTEM,
                user_query=_build_evidence_board_prompt(selected, instance["question"]),
                model=model,
                max_tokens=max_tokens,
                metadata={"instance_id": instance["id"], "phase": "aggregation"},
            )
        )

    responses = batch_fn(agg_requests, max_workers=max_workers)

    out: list[tuple[str, float, int, int]] = []
    for instance, resp, comm_tokens in zip(instances, responses, comm_tokens_list):
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        agg_tok = resp.usage.get("total_tokens", 0)
        out.append((pred, answer_f1(pred, instance), comm_tokens, agg_tok))
    return out


# ---------------------------------------------------------------------------
# Per-instance pipeline helpers (private)
# ---------------------------------------------------------------------------
# Instead of three sequential global barriers (extract-all → score-all →
# aggregate-all), each instance runs its own extract→score→aggregate chain
# in a single thread.  All instance threads run concurrently inside one
# ThreadPoolExecutor, so fast instances are never stalled by slow ones.

def _pipe_extract(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
) -> tuple[list[list[str]], int]:
    reqs = [
        APIRequest(
            system_query=_EXTRACTION_SYSTEM,
            user_query=_build_extraction_prompt(
                format_shard_context(shard), instance["question"], max_states_per_agent
            ),
            model=model,
            max_tokens=max_tokens // 2,
            metadata={"instance_id": instance["id"], "agent": j, "phase": "extraction"},
        )
        for j, shard in enumerate(shards)
    ]
    resps = batch_fn(reqs, max_workers=len(reqs))
    states = [
        _parse_states(r.content, max_states_per_agent)
        if r.success and r.content.strip() else []
        for r in resps
    ]
    return states, sum(r.usage.get("total_tokens", 0) for r in resps)


def _pipe_score(
    instance: dict,
    states: list[list[str]],
    batch_fn: Callable,
    model: str,
) -> tuple[list[list[dict]], int]:
    reqs: list[APIRequest] = []
    idx_map: list[tuple[int, int]] = []
    for j, agent_states in enumerate(states):
        for k, state in enumerate(agent_states):
            reqs.append(APIRequest(
                system_query=_SCORING_SYSTEM,
                user_query=_build_scoring_prompt(instance["question"], state),
                model=model,
                max_tokens=128,
                temperature=0.0,
                metadata={"instance_id": instance["id"], "agent": j, "state_idx": k, "phase": "scoring"},
            ))
            idx_map.append((j, k))

    scores: list[list[dict]] = [[{} for _ in ag] for ag in states]
    if not reqs:
        return scores, 0

    resps = batch_fn(reqs, max_workers=len(reqs))
    total_tok = 0
    for resp, (j, k) in zip(resps, idx_map):
        total_tok += resp.usage.get("total_tokens", 0)
        scores[j][k] = (
            parse_score_json(resp.content)
            if resp.success and resp.content.strip()
            else {"relevance": 0.5, "uniqueness": 0.5, "criticality": 0.5, "composite": 0.5}
        )
    return scores, total_tok


def _pipe_aggregate(
    instance: dict,
    selected: list[list[str]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
) -> tuple[str, float, int, int]:
    """Aggregate evidence board for one instance. Returns (pred, f1, comm_tok, agg_tok)."""
    all_flat = [s for ag in selected for s in ag]
    comm_tokens = sum(count_tokens_approx(s) for s in all_flat)
    [resp] = batch_fn(
        [APIRequest(
            system_query=_AGGREGATION_SYSTEM,
            user_query=_build_evidence_board_prompt(selected, instance["question"]),
            model=model,
            max_tokens=max_tokens,
            metadata={"instance_id": instance["id"], "phase": "aggregation"},
        )],
        max_workers=1,
    )
    raw = resp.content.strip() if resp.success and resp.content.strip() else ""
    pred = extract_answer(raw) if raw else ""
    return pred, answer_f1(pred, instance), comm_tokens, resp.usage.get("total_tokens", 0)


def _pipeline_random_relay(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
    pre_states: list[list[str]] | None,
    pre_extract_tok: int,
    seed: int,
) -> ProtocolResult:
    if pre_states is not None:
        states, extract_tok = pre_states, pre_extract_tok
    else:
        states, extract_tok = _pipe_extract(instance, shards, batch_fn, model, max_tokens, max_states_per_agent)

    # Per-instance RNG keyed on instance id — deterministic regardless of thread order.
    rng = random.Random(f"{seed}:{instance['id']}")
    selected = [
        rng.sample(s, min(max_states_per_agent, len(s))) if s else []
        for s in states
    ]

    pred, f1, comm_tokens, agg_tok = _pipe_aggregate(instance, selected, batch_fn, model, max_tokens)
    return ProtocolResult(
        instance_id=instance["id"], pred=pred, f1=f1,
        comm_tokens=comm_tokens,
        total_llm_tokens=extract_tok + agg_tok,
        transmitted_states=[s for ag in selected for s in ag],
    )


def _pipeline_csc(
    instance: dict,
    shards: list[AgentShard],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
    select_fn: Callable,
    pre_states: list[list[str]] | None,
    pre_scores: list[list[dict]] | None,
    pre_extract_tok: int,
    pre_score_tok: int,
) -> ProtocolResult:
    if pre_states is not None:
        states, extract_tok = pre_states, pre_extract_tok
    else:
        states, extract_tok = _pipe_extract(instance, shards, batch_fn, model, max_tokens, max_states_per_agent)

    if pre_scores is not None:
        scores, score_tok = pre_scores, pre_score_tok
    else:
        scores, score_tok = _pipe_score(instance, states, batch_fn, model)

    selected = [select_fn(s, sc) for s, sc in zip(states, scores)]
    pred, f1, comm_tokens, agg_tok = _pipe_aggregate(instance, selected, batch_fn, model, max_tokens)
    return ProtocolResult(
        instance_id=instance["id"], pred=pred, f1=f1,
        comm_tokens=comm_tokens,
        total_llm_tokens=extract_tok + score_tok + agg_tok,
        transmitted_states=[s for ag in selected for s in ag],
    )


# ---------------------------------------------------------------------------
# Batch protocol runners
# ---------------------------------------------------------------------------

def run_random_relay_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
    precomputed_states: list[list[list[str]]] | None = None,
    precomputed_extract_tokens: list[int] | None = None,
    seed: int = 42,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Random state relay: extract states, select uniformly at random, aggregate."""
    results: list[ProtocolResult | None] = [None] * len(instances)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        fs = {
            pool.submit(
                _pipeline_random_relay,
                instance, shards, batch_fn, model, max_tokens, max_states_per_agent,
                precomputed_states[i] if precomputed_states is not None else None,
                precomputed_extract_tokens[i] if precomputed_extract_tokens else 0,
                seed,
            ): i
            for i, (instance, shards) in enumerate(zip(instances, shards_list))
        }
        for f in concurrent.futures.as_completed(fs):
            results[fs[f]] = f.result()
    return results  # type: ignore[return-value]


def run_csc_topk_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
    precomputed_states: list[list[list[str]]] | None = None,
    precomputed_scores: list[list[list[dict]]] | None = None,
    precomputed_extract_tokens: list[int] | None = None,
    precomputed_score_tokens: list[int] | None = None,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """CSC top-k: extract, score, select by necessity, aggregate (Eq. 3)."""
    k = max_states_per_agent
    results: list[ProtocolResult | None] = [None] * len(instances)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        fs = {
            pool.submit(
                _pipeline_csc,
                instance, shards, batch_fn, model, max_tokens, max_states_per_agent,
                lambda s, sc, _k=k: _topk_select(s, sc, _k),
                precomputed_states[i] if precomputed_states is not None else None,
                precomputed_scores[i] if precomputed_scores is not None else None,
                precomputed_extract_tokens[i] if precomputed_extract_tokens else 0,
                precomputed_score_tokens[i] if precomputed_score_tokens else 0,
            ): i
            for i, (instance, shards) in enumerate(zip(instances, shards_list))
        }
        for f in concurrent.futures.as_completed(fs):
            results[fs[f]] = f.result()
    return results  # type: ignore[return-value]


def run_csc_redundancy_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_states_per_agent: int,
    rho: float = 0.5,
    precomputed_states: list[list[list[str]]] | None = None,
    precomputed_scores: list[list[list[dict]]] | None = None,
    precomputed_extract_tokens: list[int] | None = None,
    precomputed_score_tokens: list[int] | None = None,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """CSC + redundancy penalty: diverse evidence-board selection (Eq. 4)."""
    k, _rho = max_states_per_agent, rho
    results: list[ProtocolResult | None] = [None] * len(instances)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        fs = {
            pool.submit(
                _pipeline_csc,
                instance, shards, batch_fn, model, max_tokens, max_states_per_agent,
                lambda s, sc, _k=k, _r=_rho: _redundancy_select(s, sc, _k, _r),
                precomputed_states[i] if precomputed_states is not None else None,
                precomputed_scores[i] if precomputed_scores is not None else None,
                precomputed_extract_tokens[i] if precomputed_extract_tokens else 0,
                precomputed_score_tokens[i] if precomputed_score_tokens else 0,
            ): i
            for i, (instance, shards) in enumerate(zip(instances, shards_list))
        }
        for f in concurrent.futures.as_completed(fs):
            results[fs[f]] = f.result()
    return results  # type: ignore[return-value]
