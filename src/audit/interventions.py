"""
Controlled evidence deletion / intervention experiments.

Functions:
  remove_critical_units    — remove k critical units from an oracle board
  remove_distractor_units  — remove k non-critical units
  remove_redundant_units   — remove k units judged redundant with others
  remove_random_units      — remove k randomly chosen units
  run_deletion_curve       — evaluate accuracy under controlled deletion at k=0..K
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from .evidence_units import EvidenceUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jaccard_sim(a: str, b: str) -> float:
    from src.eval.evaluate import normalize
    ta = set(normalize(a))
    tb = set(normalize(b))
    if not ta and not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _find_redundant_indices(
    units: list[EvidenceUnit],
    threshold: float = 0.5,
) -> list[int]:
    """Return indices of units considered redundant (high similarity to another unit)."""
    n = len(units)
    redundant: set[int] = set()
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard_sim(units[i].text, units[j].text) >= threshold:
                # Mark the later one as redundant
                redundant.add(j)
    return sorted(redundant)


# ---------------------------------------------------------------------------
# Removal functions
# ---------------------------------------------------------------------------

def remove_critical_units(
    board: list[EvidenceUnit],
    gold_critical_units: list[EvidenceUnit],
    k: int,
    strategy: str = "random",
    seed: int = 42,
) -> list[EvidenceUnit]:
    """Remove k critical units from an oracle/full evidence board.

    Critical units are identified by matching against gold_critical_units
    (unit_id match or text match via is_gold_support / is_critical flag).
    """
    rng = random.Random(seed)
    gold_ids = {u.unit_id for u in gold_critical_units}
    gold_texts = {u.text.strip().lower() for u in gold_critical_units}

    critical_in_board = [
        u for u in board
        if u.unit_id in gold_ids
        or u.is_critical
        or u.text.strip().lower() in gold_texts
    ]
    non_critical = [u for u in board if u not in critical_in_board]

    to_remove = rng.sample(critical_in_board, min(k, len(critical_in_board)))
    keep = [u for u in board if u not in to_remove]
    return keep


def remove_distractor_units(
    board: list[EvidenceUnit],
    gold_critical_units: list[EvidenceUnit],
    k: int,
    strategy: str = "random",
    seed: int = 42,
) -> list[EvidenceUnit]:
    """Remove k non-critical (distractor) units from the board."""
    rng = random.Random(seed)
    gold_ids = {u.unit_id for u in gold_critical_units}
    gold_texts = {u.text.strip().lower() for u in gold_critical_units}

    distractors = [
        u for u in board
        if u.unit_id not in gold_ids
        and not u.is_critical
        and u.text.strip().lower() not in gold_texts
    ]
    to_remove = rng.sample(distractors, min(k, len(distractors)))
    return [u for u in board if u not in to_remove]


def remove_redundant_units(
    board: list[EvidenceUnit],
    gold_critical_units: list[EvidenceUnit],
    k: int,
    redundancy_threshold: float = 0.5,
    seed: int = 42,
) -> list[EvidenceUnit]:
    """Remove units judged redundant with other board units, preferring non-critical ones."""
    rng = random.Random(seed)
    redundant_indices = _find_redundant_indices(board, redundancy_threshold)

    gold_ids = {u.unit_id for u in gold_critical_units}
    # Prefer to remove non-critical redundant units
    safe_to_remove = [
        i for i in redundant_indices
        if board[i].unit_id not in gold_ids and not board[i].is_critical
    ]
    if len(safe_to_remove) < k:
        safe_to_remove += [i for i in redundant_indices if i not in safe_to_remove]

    chosen_indices = set(rng.sample(safe_to_remove, min(k, len(safe_to_remove))))
    return [u for i, u in enumerate(board) if i not in chosen_indices]


def remove_random_units(
    board: list[EvidenceUnit],
    k: int,
    seed: int = 42,
) -> list[EvidenceUnit]:
    """Remove k randomly chosen units from the board."""
    rng = random.Random(seed)
    to_remove = set(rng.sample(range(len(board)), min(k, len(board))))
    return [u for i, u in enumerate(board) if i not in to_remove]


# ---------------------------------------------------------------------------
# Deletion curve experiment
# ---------------------------------------------------------------------------

def run_deletion_curve(
    task: dict,
    board: list[EvidenceUnit],
    gold_critical_units: list[EvidenceUnit],
    aggregator_fn: Callable[[dict, list[EvidenceUnit]], tuple[str, bool]],
    ks: tuple[int, ...] = (0, 1, 2, 3),
    seed: int = 42,
) -> list[dict]:
    """Evaluate answer accuracy under controlled evidence deletion.

    For each unit_type (critical, distractor, redundant, random) and each k,
    removes k units of that type and evaluates the aggregator.

    Args:
        task:               Task dict with question, gold answer.
        board:              Oracle / full evidence board.
        gold_critical_units: Gold critical units for the task.
        aggregator_fn:      Callable(task, board) -> (predicted_answer, is_correct).
        ks:                 Tuple of k values to evaluate.
        seed:               Random seed.

    Returns:
        List of dicts: {task_id, condition, k, accuracy, critical_recall}
    """
    task_id = task.get("id", "unknown")
    results: list[dict] = []

    removal_fns = {
        "remove_critical": lambda b, k: remove_critical_units(b, gold_critical_units, k, seed=seed),
        "remove_distractor": lambda b, k: remove_distractor_units(b, gold_critical_units, k, seed=seed),
        "remove_redundant": lambda b, k: remove_redundant_units(b, gold_critical_units, k, seed=seed),
        "remove_random": lambda b, k: remove_random_units(b, k, seed=seed),
    }

    for condition, rm_fn in removal_fns.items():
        for k in ks:
            modified_board = rm_fn(board, k)

            # Compute critical recall on modified board
            gold_ids = {u.unit_id for u in gold_critical_units}
            gold_texts = {u.text.strip().lower() for u in gold_critical_units}
            surviving_critical = sum(
                1 for u in modified_board
                if u.unit_id in gold_ids or u.text.strip().lower() in gold_texts
            )
            crit_recall = (
                surviving_critical / len(gold_critical_units)
                if gold_critical_units else 1.0
            )

            _, is_correct = aggregator_fn(task, modified_board)
            results.append({
                "task_id": task_id,
                "condition": condition,
                "k": k,
                "accuracy": int(is_correct),
                "critical_recall": crit_recall,
                "board_size": len(modified_board),
            })

    return results
