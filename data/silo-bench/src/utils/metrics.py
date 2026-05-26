"""Evaluation metrics: S (Success Rate), P (Partial Correctness), C (Token Consumption), D (Communication Density).

Based on SILO-BENCH paper Section 3.3:
- S: Proportion of agents converging to correct answer
- P: Continuous measure of answer quality (task-category tailored)
- C: Computational cost per communication round
- D: Inter-agent interaction intensity
"""

from __future__ import annotations

import json
from typing import Any


def _normalize_value(val: Any) -> Any:
    """Normalize a submission value for comparison.

    Converts strings to their parsed form if possible (int, float, JSON list/dict).
    Recursively normalizes list elements.
    """
    if isinstance(val, str):
        stripped = val.strip()
        try:
            return int(stripped)
        except (ValueError, TypeError):
            pass
        try:
            return float(stripped)
        except (ValueError, TypeError):
            pass
        # Try JSON parsing for lists/dicts
        if stripped.startswith(("[", "{")):
            try:
                parsed = json.loads(stripped)
                return _normalize_value(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        return stripped
    if isinstance(val, list):
        return [_normalize_value(v) for v in val]
    return val


def compute_success_rate(
    submissions: list[dict[str, Any]],
    expected_output: dict[str, Any],
) -> float:
    """Compute S = (1/N) * Σ 1[ŷ_i = y*].

    Success Rate measures the proportion of agents converging to the correct answer.
    A task instance is successful when S = 1, indicating unanimous convergence.

    Args:
        submissions: list of {"agent_id": int, "answer": Any}
        expected_output: the expected_output dict from benchmark JSON,
            containing "per_agent_values" (list indexed by agent_id)

    Returns:
        S in [0, 1]
    """
    per_agent = expected_output["per_agent_values"]
    num_agents = len(per_agent)
    if num_agents == 0:
        return 0.0

    correct = 0
    submitted_ids = set()
    for sub in submissions:
        aid = sub["agent_id"]
        submitted_ids.add(aid)
        expected = per_agent[aid]
        actual = _normalize_value(sub["answer"])
        expected_norm = _normalize_value(expected)
        if actual == expected_norm:
            correct += 1

    return correct / num_agents


def _longest_increasing_subsequence_length(seq: list) -> int:
    """Compute length of longest increasing subsequence using binary search."""
    if not seq:
        return 0
    from bisect import bisect_left
    tails = []
    for x in seq:
        pos = bisect_left(tails, x)
        if pos == len(tails):
            tails.append(x)
        else:
            tails[pos] = x
    return len(tails)


def compute_partial_correctness(
    submissions: list[dict[str, Any]],
    expected_output: dict[str, Any],
    level: str,
    tolerance: float = 0.01,
) -> float:
    """Compute P = (1/N) * Σ q_i where q_i ∈ [0, 1] is per-agent quality score.

    Partial Correctness Score provides a continuous measure of answer quality
    tailored to each task category:

    - Level I (Aggregation): Fraction of agents within tolerance of ground truth
    - Level II (Mesh Network): Fraction of correctly computed elements per local segment
    - Level III (Global Shuffle): Longest correctly ordered subsequence relative to total length

    Together with S, this score allows isolating where coordination breaks down:
    the gap P - S quantifies performance lost at the reasoning-integration stage.

    Args:
        submissions: list of {"agent_id": int, "answer": Any}
        expected_output: the expected_output dict containing "per_agent_values"
        level: "I", "II", or "III" indicating the task paradigm
        tolerance: relative tolerance for Level-I numeric comparison (default 0.01 = 1%)

    Returns:
        P in [0, 1]
    """
    per_agent = expected_output["per_agent_values"]
    num_agents = len(per_agent)
    if num_agents == 0:
        return 0.0

    # Build mapping from agent_id to submission
    submission_map = {}
    for sub in submissions:
        submission_map[sub["agent_id"]] = sub["answer"]

    if level == "I":
        # Level I: Fraction of agents within tolerance of ground truth
        quality_scores = []
        for aid in range(num_agents):
            if aid not in submission_map:
                quality_scores.append(0.0)
                continue
            expected = _normalize_value(per_agent[aid])
            actual = _normalize_value(submission_map[aid])

            if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                # Numeric comparison with tolerance
                if expected == 0:
                    q = 1.0 if actual == 0 else 0.0
                elif abs(actual - expected) <= tolerance * abs(expected):
                    q = 1.0
                else:
                    q = 0.0
            else:
                # Exact match for non-numeric
                q = 1.0 if actual == expected else 0.0
            quality_scores.append(q)

        return sum(quality_scores) / num_agents

    elif level == "II":
        # Level II: Fraction of correctly computed elements per local segment
        total_quality = 0.0
        for aid in range(num_agents):
            if aid not in submission_map:
                continue
            expected = _normalize_value(per_agent[aid])
            actual = _normalize_value(submission_map[aid])

            if isinstance(expected, list) and isinstance(actual, list):
                if len(expected) == 0:
                    q = 1.0 if len(actual) == 0 else 0.0
                else:
                    # Count matching elements at same positions
                    matches = sum(1 for e, a in zip(expected, actual) if e == a)
                    q = matches / len(expected)
            else:
                q = 1.0 if expected == actual else 0.0
            total_quality += q

        return total_quality / num_agents

    elif level == "III":
        # Level III: Longest correctly ordered subsequence relative to total length
        # For distributed sort, we need to assess global ordering quality
        total_quality = 0.0
        for aid in range(num_agents):
            if aid not in submission_map:
                continue
            expected = _normalize_value(per_agent[aid])
            actual = _normalize_value(submission_map[aid])

            if isinstance(expected, list) and isinstance(actual, list):
                if len(expected) == 0:
                    q = 1.0 if len(actual) == 0 else 0.0
                else:
                    # Find longest subsequence of actual that appears in correct order
                    # Create position map of expected elements
                    expected_pos = {v: i for i, v in enumerate(expected)}
                    # Map actual elements to their expected positions
                    positions = []
                    for a in actual:
                        if a in expected_pos:
                            positions.append(expected_pos[a])
                    # LIS length represents longest correctly ordered subsequence
                    lis_len = _longest_increasing_subsequence_length(positions)
                    q = lis_len / len(expected)
            else:
                q = 1.0 if expected == actual else 0.0
            total_quality += q

        return total_quality / num_agents

    return 0.0


def compute_token_consumption(total_tokens: int, max_rounds: int) -> float:
    """Compute C = (Σ_i Σ_r t_i^out[r]) / R_max.

    Token Consumption quantifies computational cost per communication round.
    t_i^out[r] is the number of output tokens generated by agent i in round r.

    Args:
        total_tokens: sum of all output tokens across all agents and rounds
        max_rounds: R_max, the maximum number of rounds executed

    Returns:
        C (average tokens per round)
    """
    if max_rounds == 0:
        return 0.0
    return total_tokens / max_rounds


# Alias for backward compatibility
def compute_token_efficiency(total_tokens: int, total_rounds: int) -> float:
    """Deprecated: Use compute_token_consumption instead."""
    return compute_token_consumption(total_tokens, total_rounds)


def compute_communication_density(
    messages_count: int,
    agent_count: int,
) -> float:
    """Compute D = (Σ_i m_i) / (N * (N-1)).

    Communication Density captures inter-agent interaction intensity.
    N(N-1) is the directed-edge count when each ordered pair exchanges exactly one message.
    Values near 0 suggest sparse, targeted exchanges; D = 1 indicates one message per
    directed pair on average; values exceeding 1 reflect iterative multi-round exchanges.

    For SFS protocol, m_i counts the number of times other agents successfully read
    files written by agent i.

    Args:
        messages_count: total number of messages sent (Σ_i m_i)
        agent_count: N, the number of agents

    Returns:
        D in [0, +∞), though typically in [0, 2] range
    """
    max_messages = agent_count * (agent_count - 1)
    if max_messages == 0:
        return 0.0
    # Note: Paper allows D > 1, so we don't cap at 1.0
    return messages_count / max_messages
