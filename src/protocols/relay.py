"""
Evidence relay protocols:
  - random_relay:            extract evidence units, select uniformly at random
  - score_ranked_relay:      extract and score units, select by local importance score
  - redundancy_aware_relay:  score-ranked selection with redundancy penalty

All three share the extraction and scoring phases, which are precomputed once
via extract_states_batch() and score_states_batch() in run_experiment.py.

The aggregation step uses an evidence-board prompt: agents relay compact
factual units, not answers or rationales, to a shared evidence board.
"""

from __future__ import annotations

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
# Prompts
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = (
    "You are an evidence extraction assistant.\n"
    "Extract atomic factual units from the provided evidence that may help answer the question.\n"
    "Each unit must be:\n"
    "  - self-contained (interpretable without other context)\n"
    "  - specific (include exact names, numbers, and dates)\n"
    "  - factual (not a reasoning step or answer guess)\n"
    "Output a numbered list of atomic evidence units, one per line. "
    "Do not add explanations or preamble."
)

_SCORING_SYSTEM = (
    "You are scoring whether an evidence unit should be communicated in a distributed reasoning system.\n\n"
    "Return JSON only with no extra text:\n"
    '{"relevance": <0-1>, "uniqueness": <0-1>, "local_importance": <0-1>, '
    '"joint_dependency": <0-1>, "overall": <0-1>}'
)

_AGGREGATION_SYSTEM = (
    "You are a question-answering assistant. "
    "The following atomic evidence units were transmitted from private evidence shards. "
    "Use ONLY these units to answer the question — do not rely on prior knowledge "
    "not present in the listed units.\n"
    "Output:\nANSWER: <your concise answer>\n"
    "USED_EVIDENCE: <comma-separated unit numbers you relied on>\n"
    "RATIONALE: <one sentence explaining how the evidence supports the answer>\n"
    "If the units are insufficient, write:\nANSWER: Insufficient information."
)

_RESCORE_SYSTEM = (
    "You are scoring whether an evidence unit should be added to a shared evidence board.\n"
    "Some units have already been transmitted. Score the remaining units on marginal value.\n\n"
    "Return JSON only with no extra text:\n"
    '{"relevance": <0-1>, "complementarity": <0-1>, "uniqueness_given_board": <0-1>, "overall": <0-1>}'
)


def _build_rescore_prompt(question: str, unit: str, board_units: list[str]) -> str:
    if board_units:
        board_str = "\n".join(f"  - {u}" for u in board_units)
    else:
        board_str = "  (empty)"
    return (
        f"Question: {question}\n\n"
        f"Already on the evidence board:\n{board_str}\n\n"
        f"Candidate unit to add: {unit}\n\n"
        "Score this unit's marginal value given the current board:\n"
        "- relevance: Does the unit relate to the question?\n"
        "- complementarity: Would this combine with board units to help answer the question?\n"
        "- uniqueness_given_board: Is this NOT already covered by units on the board?\n\n"
        "Return JSON only: "
        '{"relevance": ..., "complementarity": ..., "uniqueness_given_board": ..., "overall": ...}'
    )


def _build_extraction_prompt(context: str, question: str, max_units: int) -> str:
    return (
        f"Question: {question}\n\n"
        f"Evidence shard:\n{context}\n\n"
        f"Extract up to {max_units} atomic evidence units from the shard above. "
        "Output a numbered list (one unit per line)."
    )


def _build_scoring_prompt(question: str, unit: str) -> str:
    return (
        f"Question: {question}\n"
        f"Evidence unit: {unit}\n\n"
        "Score from 0 to 1:\n"
        "- relevance: Does the unit relate to the question?\n"
        "- uniqueness: Is the unit likely unavailable to other agents?\n"
        "- local_importance: Could omitting this unit change the answer?\n"
        "- joint_dependency: Could this unit become important only when combined "
        "with evidence from other agents?\n\n"
        "Return JSON only: "
        '{"relevance": ..., "uniqueness": ..., "local_importance": ..., '
        '"joint_dependency": ..., "overall": ...}'
    )


def _build_evidence_board_prompt(
    units_per_agent: list[list[str]], question: str
) -> str:
    parts = []
    for i, units in enumerate(units_per_agent):
        if units:
            lines = "\n".join(f"  {j+1}. {u}" for j, u in enumerate(units))
            parts.append(f"Agent {i+1} evidence:\n{lines}")
        else:
            parts.append(f"Agent {i+1} evidence:\n  (none transmitted)")
    board = "\n\n".join(parts)
    return (
        "The following evidence units were transmitted from private shards.\n"
        "Use only these units to answer the question.\n\n"
        f"{board}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_units(text: str, max_units: int) -> list[str]:
    """Parse a numbered list of evidence units from LLM output."""
    import re
    lines = text.strip().split("\n")
    units: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[.):\s]+", "", line).strip()
        if cleaned:
            units.append(cleaned)
        if len(units) >= max_units:
            break
    return units


def _parse_states(text: str, max_states: int) -> list[str]:
    """Compatibility wrapper preserving the historical keyword argument."""
    return _parse_units(text, max_units=max_states)


# ---------------------------------------------------------------------------
# Batched extraction (shared by all relay protocols)
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
    """Extract atomic evidence units for every (instance, agent) pair in one batch.

    Returns:
        (units, per_inst_tokens) where:
            units[inst_i][agent_j]      = list[unit_str]
            per_inst_tokens[inst_i]     = sum of total_tokens for that instance
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
            states[inst_i][agent_j] = _parse_units(resp.content, max_states_per_agent)
    return states, per_inst_tokens


# ---------------------------------------------------------------------------
# Batched scoring (shared by score_ranked_relay, redundancy_aware_relay)
# ---------------------------------------------------------------------------

def score_states_batch(
    instances: list[dict],
    all_states: list[list[list[str]]],
    batch_fn: Callable,
    model: str,
    max_workers: int,
) -> tuple[list[list[list[dict]]], list[int]]:
    """Score every evidence unit for every (instance, agent) pair in one batch.

    Returns:
        (scores, per_inst_tokens) where:
            scores[inst_i][agent_j][unit_k] = score_dict
            per_inst_tokens[inst_i]         = sum of total_tokens
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
                "local_importance": 0.5,
                "overall": 0.5,
                "composite": 0.5,
            }
    return scores, per_inst_tokens


# ---------------------------------------------------------------------------
# Selection methods
# ---------------------------------------------------------------------------

def _topk_select(states: list[str], scores: list[dict], k: int) -> list[str]:
    """Select top-k units ranked by overall local importance score."""
    if not states:
        return []
    ranked = sorted(
        zip(states, scores),
        key=lambda pair: pair[1].get("overall", pair[1].get("composite", 0.0)),
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
    """Greedy budgeted selection with redundancy penalty.

    Iteratively picks the unit that maximises:
        score(u) - rho * sum_{u' already selected} sim(u, u')
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
            base_score = scores[i].get("overall", scores[i].get("composite", 0.0))
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
# Evidence-board aggregation (shared by all relay methods)
# ---------------------------------------------------------------------------

def _aggregate_evidence_board_batch(
    instances: list[dict],
    selected_list: list[list[list[str]]],
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
        all_units = [u for agent_units in selected for u in agent_units]
        comm_tokens_list.append(sum(count_tokens_approx(u) for u in all_units))
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
# Per-instance pipeline helpers
# ---------------------------------------------------------------------------

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
        _parse_units(r.content, max_states_per_agent)
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
            else {"relevance": 0.5, "uniqueness": 0.5, "local_importance": 0.5, "overall": 0.5}
        )
    return scores, total_tok


def _pipe_aggregate(
    instance: dict,
    selected: list[list[str]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
) -> tuple[str, float, int, int]:
    all_flat = [u for ag in selected for u in ag]
    comm_tokens = sum(count_tokens_approx(u) for u in all_flat)
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


def _pipeline_scored_relay(
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


# Keep old internal name as alias for any external callers
_pipeline_csc = _pipeline_scored_relay


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
    """Random evidence relay: extract units, select uniformly at random, aggregate.

    All N aggregation requests are submitted in a single batch (1 API round trip).
    """
    # Phase 1: states (1 RTT if not precomputed)
    if precomputed_states is not None:
        all_states = precomputed_states
        extract_tokens = precomputed_extract_tokens or [0] * len(instances)
    else:
        all_states, extract_tokens = extract_states_batch(
            instances, shards_list, batch_fn, model, max_tokens, max_states_per_agent, max_workers
        )

    # Phase 2: selection (CPU only — no API call)
    all_selected: list[list[list[str]]] = []
    for instance, states in zip(instances, all_states):
        rng = random.Random(f"{seed}:{instance['id']}")
        all_selected.append([
            rng.sample(s, min(max_states_per_agent, len(s))) if s else []
            for s in states
        ])

    # Phase 3: aggregate all N instances in ONE batch (1 RTT)
    agg_results = _aggregate_evidence_board_batch(
        instances, all_selected, batch_fn, model, max_tokens, max_workers
    )

    return [
        ProtocolResult(
            instance_id=instance["id"],
            pred=pred,
            f1=f1,
            comm_tokens=comm_tokens,
            total_llm_tokens=extract_tokens[i] + agg_tok,
            transmitted_states=[s for ag in selected for s in ag],
        )
        for i, (instance, selected, (pred, f1, comm_tokens, agg_tok)) in enumerate(
            zip(instances, all_selected, agg_results)
        )
    ]


def run_score_ranked_relay_batch(
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
    """Score-ranked evidence relay: extract, score by local importance, select top-k, aggregate.

    All N aggregation requests are submitted in a single batch (1 API round trip).
    """
    k = max_states_per_agent

    # Phase 1a: states
    if precomputed_states is not None:
        all_states = precomputed_states
        extract_tokens = precomputed_extract_tokens or [0] * len(instances)
    else:
        all_states, extract_tokens = extract_states_batch(
            instances, shards_list, batch_fn, model, max_tokens, max_states_per_agent, max_workers
        )

    # Phase 1b: scores
    if precomputed_scores is not None:
        all_scores = precomputed_scores
        score_tokens = precomputed_score_tokens or [0] * len(instances)
    else:
        all_scores, score_tokens = score_states_batch(
            instances, all_states, batch_fn, model, max_workers
        )

    # Phase 2: selection (CPU only)
    all_selected = [
        [_topk_select(states, scores, k) for states, scores in zip(inst_states, inst_scores)]
        for inst_states, inst_scores in zip(all_states, all_scores)
    ]

    # Phase 3: aggregate all N in ONE batch (1 RTT)
    agg_results = _aggregate_evidence_board_batch(
        instances, all_selected, batch_fn, model, max_tokens, max_workers
    )

    return [
        ProtocolResult(
            instance_id=instance["id"],
            pred=pred,
            f1=f1,
            comm_tokens=comm_tokens,
            total_llm_tokens=extract_tokens[i] + score_tokens[i] + agg_tok,
            transmitted_states=[s for ag in selected for s in ag],
        )
        for i, (instance, selected, (pred, f1, comm_tokens, agg_tok)) in enumerate(
            zip(instances, all_selected, agg_results)
        )
    ]


def run_redundancy_aware_relay_batch(
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
    """Redundancy-aware evidence relay: scored selection with diversity penalty.

    All N aggregation requests are submitted in a single batch (1 API round trip).
    """
    k = max_states_per_agent

    # Phase 1a: states
    if precomputed_states is not None:
        all_states = precomputed_states
        extract_tokens = precomputed_extract_tokens or [0] * len(instances)
    else:
        all_states, extract_tokens = extract_states_batch(
            instances, shards_list, batch_fn, model, max_tokens, max_states_per_agent, max_workers
        )

    # Phase 1b: scores
    if precomputed_scores is not None:
        all_scores = precomputed_scores
        score_tokens = precomputed_score_tokens or [0] * len(instances)
    else:
        all_scores, score_tokens = score_states_batch(
            instances, all_states, batch_fn, model, max_workers
        )

    # Phase 2: selection (CPU only)
    all_selected = [
        [_redundancy_select(states, scores, k, rho) for states, scores in zip(inst_states, inst_scores)]
        for inst_states, inst_scores in zip(all_states, all_scores)
    ]

    # Phase 3: aggregate all N in ONE batch (1 RTT)
    agg_results = _aggregate_evidence_board_batch(
        instances, all_selected, batch_fn, model, max_tokens, max_workers
    )

    return [
        ProtocolResult(
            instance_id=instance["id"],
            pred=pred,
            f1=f1,
            comm_tokens=comm_tokens,
            total_llm_tokens=extract_tokens[i] + score_tokens[i] + agg_tok,
            transmitted_states=[s for ag in selected for s in ag],
        )
        for i, (instance, selected, (pred, f1, comm_tokens, agg_tok)) in enumerate(
            zip(instances, all_selected, agg_results)
        )
    ]


# Backward-compatible aliases
run_csc_topk_batch = run_score_ranked_relay_batch
run_csc_redundancy_batch = run_redundancy_aware_relay_batch


# ---------------------------------------------------------------------------
# Multi-round relay (fixed total budget k per agent across n_rounds)
# ---------------------------------------------------------------------------

def _rescore_round(
    instance: dict,
    remaining_units: list[list[str]],     # per agent: units not yet selected
    current_board: list[str],             # all units transmitted so far
    batch_fn: Callable,
    model: str,
    max_workers: int,
) -> list[list[dict]]:
    """Score each agent's remaining units given the current board (board-aware)."""
    all_requests: list[APIRequest] = []
    index_map: list[tuple[int, int]] = []

    for agent_j, units in enumerate(remaining_units):
        for unit_k, unit in enumerate(units):
            all_requests.append(APIRequest(
                system_query=_RESCORE_SYSTEM,
                user_query=_build_rescore_prompt(instance["question"], unit, current_board),
                model=model,
                max_tokens=128,
                temperature=0.0,
                metadata={"instance_id": instance["id"], "agent": agent_j,
                           "unit_idx": unit_k, "phase": "rescore"},
            ))
            index_map.append((agent_j, unit_k))

    new_scores: list[list[dict]] = [[{} for _ in units] for units in remaining_units]
    if not all_requests:
        return new_scores

    responses = batch_fn(all_requests, max_workers=max_workers)
    total_tok = 0
    for resp, (agent_j, unit_k) in zip(responses, index_map):
        total_tok += resp.usage.get("total_tokens", 0)
        new_scores[agent_j][unit_k] = (
            parse_score_json(resp.content)
            if resp.success and resp.content.strip()
            else {"relevance": 0.5, "complementarity": 0.5,
                  "uniqueness_given_board": 0.5, "overall": 0.5}
        )
    return new_scores, total_tok


def run_multistep_relay_batch(
    instances: list[dict],
    shards_list: list[list[AgentShard]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    total_budget_per_agent: int = 3,
    n_rounds: int = 2,
    precomputed_states: list[list[list[str]]] | None = None,
    precomputed_scores: list[list[list[dict]]] | None = None,
    precomputed_extract_tokens: list[int] | None = None,
    precomputed_score_tokens: list[int] | None = None,
    max_workers: int = 5,
) -> list[ProtocolResult]:
    """Fixed-budget multi-round evidence relay.

    Each agent transmits exactly `total_budget_per_agent` units spread across
    `n_rounds` rounds.  In rounds 2+, agents see the cumulative board and
    re-score their remaining units for board-aware selection.

    Round allocations (total_budget_per_agent=3):
      n_rounds=1: [3]
      n_rounds=2: [1, 2]
      n_rounds=3: [1, 1, 1]

    All final aggregation happens once after all rounds complete.
    """
    assert n_rounds >= 1, "n_rounds must be >= 1"

    # Distribute budget across rounds: round 1 gets 1 unit, remainder split over later rounds
    if n_rounds == 1:
        round_budgets = [total_budget_per_agent]
    else:
        # Give 1 unit to each intermediate round; last round gets the remainder
        per_round = [1] * (n_rounds - 1)
        per_round.append(total_budget_per_agent - sum(per_round))
        round_budgets = per_round

    # Phase 1: extract
    if precomputed_states is not None:
        all_states = precomputed_states
        extract_tokens = precomputed_extract_tokens or [0] * len(instances)
    else:
        all_states, extract_tokens = extract_states_batch(
            instances, shards_list, batch_fn, model, max_tokens,
            total_budget_per_agent, max_workers
        )

    # Phase 2: initial score (round 1, no board context)
    if precomputed_scores is not None:
        all_scores = precomputed_scores
        score_tokens = precomputed_score_tokens or [0] * len(instances)
    else:
        all_scores, score_tokens = score_states_batch(
            instances, all_states, batch_fn, model, max_workers
        )

    rescore_tokens_total = [0] * len(instances)

    # Phase 3: multi-round selection
    # all_selected[inst_i][agent_j] = accumulated selected units after all rounds
    all_selected: list[list[list[str]]] = [
        [[] for _ in shards] for shards in shards_list
    ]
    # remaining[inst_i][agent_j] = units not yet selected
    all_remaining: list[list[list[str]]] = [
        [list(states) for states in inst_states]
        for inst_states in all_states
    ]
    all_remaining_scores: list[list[list[dict]]] = [
        [list(scores) for scores in inst_scores]
        for inst_scores in all_scores
    ]

    for round_idx, k_this_round in enumerate(round_budgets):
        is_first_round = (round_idx == 0)

        if not is_first_round:
            # Re-score all remaining units using current board context
            rescore_requests: list[APIRequest] = []
            rescore_index: list[tuple[int, int, int]] = []

            for inst_i, (instance, remaining) in enumerate(
                zip(instances, all_remaining)
            ):
                current_board = [u for ag in all_selected[inst_i] for u in ag]
                for agent_j, units in enumerate(remaining):
                    for unit_k, unit in enumerate(units):
                        rescore_requests.append(APIRequest(
                            system_query=_RESCORE_SYSTEM,
                            user_query=_build_rescore_prompt(
                                instance["question"], unit, current_board
                            ),
                            model=model,
                            max_tokens=128,
                            temperature=0.0,
                            metadata={
                                "instance_id": instance["id"],
                                "agent": agent_j,
                                "unit_idx": unit_k,
                                "phase": f"rescore_r{round_idx + 1}",
                            },
                        ))
                        rescore_index.append((inst_i, agent_j, unit_k))

            if rescore_requests:
                rescore_responses = batch_fn(rescore_requests, max_workers=max_workers)
                for resp, (inst_i, agent_j, unit_k) in zip(rescore_responses, rescore_index):
                    rescore_tokens_total[inst_i] += resp.usage.get("total_tokens", 0)
                    all_remaining_scores[inst_i][agent_j][unit_k] = (
                        parse_score_json(resp.content)
                        if resp.success and resp.content.strip()
                        else {"relevance": 0.5, "complementarity": 0.5,
                              "uniqueness_given_board": 0.5, "overall": 0.5}
                    )

        # Select k_this_round units per agent from remaining pool
        for inst_i in range(len(instances)):
            for agent_j in range(len(all_remaining[inst_i])):
                remaining = all_remaining[inst_i][agent_j]
                rem_scores = all_remaining_scores[inst_i][agent_j]
                if not remaining:
                    continue
                selected_this_round = _topk_select(remaining, rem_scores, k_this_round)
                all_selected[inst_i][agent_j].extend(selected_this_round)
                # Remove selected from remaining pool
                selected_set = set(selected_this_round)
                new_rem, new_scores = [], []
                for u, sc in zip(remaining, rem_scores):
                    if u not in selected_set:
                        new_rem.append(u)
                        new_scores.append(sc)
                    else:
                        selected_set.discard(u)  # handle duplicates
                all_remaining[inst_i][agent_j] = new_rem
                all_remaining_scores[inst_i][agent_j] = new_scores

    # Phase 4: aggregate once over all collected units
    agg_results = _aggregate_evidence_board_batch(
        instances, all_selected, batch_fn, model, max_tokens, max_workers
    )

    return [
        ProtocolResult(
            instance_id=instance["id"],
            pred=pred,
            f1=f1,
            comm_tokens=comm_tokens,
            total_llm_tokens=(
                extract_tokens[i] + score_tokens[i] +
                rescore_tokens_total[i] + agg_tok
            ),
            transmitted_states=[s for ag in selected for s in ag],
        )
        for i, (instance, selected, (pred, f1, comm_tokens, agg_tok)) in enumerate(
            zip(instances, all_selected, agg_results)
        )
    ]
