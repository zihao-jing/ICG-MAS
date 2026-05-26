"""
Analyze whether local LLM scores identify truly critical evidence.

Functions:
  compute_leave_one_out_importance  — LOO importance per unit
  score_gold_correlation            — AUC, Spearman, precision@k, recall@k
  find_false_negatives              — critical units with low local score
  find_false_positives              — non-critical units with high local score
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from .evidence_units import EvidenceUnit


# ---------------------------------------------------------------------------
# Leave-one-out importance
# ---------------------------------------------------------------------------

def compute_leave_one_out_importance(
    task: dict,
    evidence_units: list[EvidenceUnit],
    aggregator_fn: Callable[[dict, list[EvidenceUnit]], tuple[str, bool]],
) -> list[dict]:
    """Remove each unit from the board and measure whether the answer changes.

    Returns:
        List of dicts: {unit_id, text, loo_importance, answer_with, answer_without, correct_with, correct_without}
    """
    _, baseline_correct = aggregator_fn(task, evidence_units)
    results: list[dict] = []

    for i, unit in enumerate(evidence_units):
        board_without = [u for j, u in enumerate(evidence_units) if j != i]
        answer_without, correct_without = aggregator_fn(task, board_without)
        # Importance: 1 if removing this unit changes correctness, else 0
        loo_importance = float(baseline_correct and not correct_without)
        results.append({
            "unit_id": unit.unit_id,
            "text": unit.text,
            "is_critical": unit.is_critical,
            "loo_importance": loo_importance,
            "correct_with": int(baseline_correct),
            "correct_without": int(correct_without),
        })

    return results


# ---------------------------------------------------------------------------
# Correlation between local scores and gold criticality
# ---------------------------------------------------------------------------

def _auc_roc(scores: list[float], labels: list[int]) -> float:
    """Simple AUC-ROC via sorting."""
    if len(set(labels)) < 2:
        return 0.5
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    tp, fp = 0, 0
    auc = 0.0
    prev_fp = 0
    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
            auc += tp * (fp - prev_fp)
            prev_fp = fp
    return auc / (n_pos * n_neg)


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation."""
    n = len(xs)
    if n < 2:
        return 0.0

    def ranks(vals: list[float]) -> list[float]:
        sorted_vals = sorted(enumerate(vals), key=lambda x: x[1])
        r = [0.0] * n
        for rank, (i, _) in enumerate(sorted_vals):
            r[i] = rank + 1.0
        return r

    rx = ranks(xs)
    ry = ranks(ys)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1.0 - 6.0 * d2 / (n * (n * n - 1))


def score_gold_correlation(
    local_scores: list[float],
    gold_labels: list[int],
    loo_importances: Optional[list[float]] = None,
    k: int = 5,
) -> dict:
    """Compute AUC, Spearman, precision@k, recall@k.

    Args:
        local_scores:    Local importance score per unit (float 0-1).
        gold_labels:     1 if unit is gold critical, 0 otherwise.
        loo_importances: Optional leave-one-out importance scores.
        k:               Top-k for precision/recall.

    Returns:
        Dict with auc_vs_gold, spearman_vs_gold, precision_at_k, recall_at_k,
        and optionally spearman_vs_loo.
    """
    n = len(local_scores)
    auc = _auc_roc(local_scores, gold_labels)
    spearman_gold = _spearman(local_scores, [float(l) for l in gold_labels])

    # Precision@k and Recall@k
    top_k_indices = sorted(range(n), key=lambda i: local_scores[i], reverse=True)[:k]
    tp_at_k = sum(gold_labels[i] for i in top_k_indices)
    precision_at_k = tp_at_k / k if k > 0 else 0.0
    total_positive = sum(gold_labels)
    recall_at_k = tp_at_k / total_positive if total_positive > 0 else 0.0

    result = {
        "auc_vs_gold": auc,
        "spearman_vs_gold": spearman_gold,
        f"precision_at_{k}": precision_at_k,
        f"recall_at_{k}": recall_at_k,
        "n_units": n,
        "n_critical": total_positive,
    }

    if loo_importances is not None:
        result["spearman_vs_loo"] = _spearman(local_scores, loo_importances)

    return result


# ---------------------------------------------------------------------------
# False negative / false positive analysis
# ---------------------------------------------------------------------------

def find_false_negatives(
    local_scores: list[float],
    units: list[EvidenceUnit],
    k: int = 10,
) -> list[dict]:
    """Critical units assigned low local scores (missed by the selector)."""
    critical_units = [
        (u, local_scores[i])
        for i, u in enumerate(units)
        if u.is_critical
    ]
    critical_units.sort(key=lambda x: x[1])  # lowest scores first
    return [
        {"unit_id": u.unit_id, "text": u.text, "local_score": s, "type": "false_negative"}
        for u, s in critical_units[:k]
    ]


def find_false_positives(
    local_scores: list[float],
    units: list[EvidenceUnit],
    k: int = 10,
) -> list[dict]:
    """Non-critical units assigned high local scores (selected when shouldn't be)."""
    non_critical_units = [
        (u, local_scores[i])
        for i, u in enumerate(units)
        if not u.is_critical
    ]
    non_critical_units.sort(key=lambda x: x[1], reverse=True)  # highest scores first
    return [
        {"unit_id": u.unit_id, "text": u.text, "local_score": s, "type": "false_positive"}
        for u, s in non_critical_units[:k]
    ]


def run_local_importance_analysis(
    task: dict,
    units: list[EvidenceUnit],
    score_dicts: list[dict],
    aggregator_fn: Callable[[dict, list[EvidenceUnit]], tuple[str, bool]],
    k: int = 5,
) -> dict:
    """Run full local importance analysis for one task.

    Args:
        task:          Task dict.
        units:         All evidence units in the board.
        score_dicts:   Score dict per unit: {relevance, uniqueness, local_importance, overall}.
        aggregator_fn: Callable(task, board) -> (answer, is_correct).
        k:             Top-k for precision/recall.

    Returns:
        Dict with correlation metrics, false negatives, and false positives.
    """
    gold_labels = [int(u.is_critical) for u in units]

    # LOO importance
    loo_results = compute_leave_one_out_importance(task, units, aggregator_fn)
    loo_importances = [r["loo_importance"] for r in loo_results]

    score_keys = ["relevance", "uniqueness", "local_importance", "overall"]
    correlations: dict[str, dict] = {}
    for key in score_keys:
        scores = [s.get(key, s.get("criticality", 0.5)) for s in score_dicts]
        correlations[key] = score_gold_correlation(scores, gold_labels, loo_importances, k=k)

    # Random baseline
    import random
    rng = random.Random(42)
    rand_scores = [rng.random() for _ in units]
    correlations["random"] = score_gold_correlation(rand_scores, gold_labels, None, k=k)

    # Overall scores for FN/FP analysis
    overall_scores = [s.get("overall", s.get("composite", 0.5)) for s in score_dicts]
    false_negs = find_false_negatives(overall_scores, units, k=k)
    false_poss = find_false_positives(overall_scores, units, k=k)

    return {
        "task_id": task.get("id", "unknown"),
        "correlations": correlations,
        "loo_results": loo_results,
        "false_negatives": false_negs,
        "false_positives": false_poss,
    }
