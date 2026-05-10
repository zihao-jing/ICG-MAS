"""
evaluate.py — Metrics and aggregation for the ICG MuSiQue experiment.

Functions:
    normalize(text)                  -> list[str]   tokenised, normalised tokens
    token_f1(pred, gold)             -> float       token-level F1
    answer_f1(pred, instance)        -> float       max F1 over gold + aliases
    majority_vote(answers)           -> str         most common answer string
    aggregate_results(results, strata) -> dict      per-stratum mean F1 tables
    pearson_correlation(xs, ys)      -> float
    spearman_correlation(xs, ys)     -> float
    print_results_table(agg, setting_label)
"""

from __future__ import annotations

import re
import string
from collections import Counter
from typing import Optional


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalize(text: str) -> list[str]:
    """Lowercase, strip articles/punctuation, return token list.

    Matches the SQuAD / MuSiQue official normalisation procedure.
    """
    text = text.lower()
    # Remove articles
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text.split()


# ---------------------------------------------------------------------------
# Token-level F1
# ---------------------------------------------------------------------------

def token_f1(pred: str, gold: str) -> float:
    """Compute token-level F1 between a predicted and gold answer string.

    Uses multi-set intersection (bag-of-words F1), consistent with the
    official MuSiQue / SQuAD evaluation script.

    Returns 0.0 if either prediction or gold normalises to an empty sequence.
    """
    pred_toks = normalize(pred)
    gold_toks = normalize(gold)

    if not pred_toks or not gold_toks:
        return 0.0

    pred_counts = Counter(pred_toks)
    gold_counts = Counter(gold_toks)

    # Intersection size (multi-set)
    common_count = sum(min(pred_counts[t], gold_counts[t]) for t in pred_counts if t in gold_counts)

    if common_count == 0:
        return 0.0

    precision = common_count / len(pred_toks)
    recall = common_count / len(gold_toks)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Per-instance answer F1 (primary + aliases)
# ---------------------------------------------------------------------------

def answer_f1(pred: str, instance: dict) -> float:
    """Compute max token-F1 against gold answer and all answer aliases.

    MuSiQue instances have a primary ``answer`` and an optional
    ``answer_aliases`` list.  We return the maximum F1 across all candidates,
    which is the standard MuSiQue evaluation protocol.

    Args:
        pred:     The predicted answer string.
        instance: A MuSiQue instance dict with at least ``answer`` and
                  optionally ``answer_aliases``.

    Returns:
        Float in [0.0, 1.0].
    """
    candidates = [instance["answer"]] + instance.get("answer_aliases", [])
    return max(token_f1(pred, g) for g in candidates)


# ---------------------------------------------------------------------------
# Majority vote
# ---------------------------------------------------------------------------

def majority_vote(answers: list[str]) -> str:
    """Return the most-frequent answer string from a list of agent answers.

    Normalised token comparison is used when counting votes so that minor
    surface variations collapse ("Paris" vs "paris").  The original (first
    seen) surface form is returned for readability.

    In the event of a tie, the lexicographically smallest normalised string's
    first surface form is returned (deterministic behaviour for testing).

    Args:
        answers: Non-empty list of answer strings.

    Returns:
        The winning answer string (original surface form).

    Raises:
        ValueError: if ``answers`` is empty.
    """
    if not answers:
        raise ValueError("majority_vote requires at least one answer")

    # Map normalised key → (count, first_surface_form)
    vote_map: dict[str, tuple[int, str]] = {}
    for ans in answers:
        key = " ".join(normalize(ans))
        if key not in vote_map:
            vote_map[key] = (0, ans)
        count, surface = vote_map[key]
        vote_map[key] = (count + 1, surface)

    # Pick winner: highest count, break ties by lexicographic key
    winner_key = max(vote_map, key=lambda k: (vote_map[k][0], -ord(k[0]) if k else 0))
    # On exact count tie, prefer lex-smallest key for determinism
    max_count = max(v[0] for v in vote_map.values())
    tied_keys = [k for k, (c, _) in vote_map.items() if c == max_count]
    winner_key = sorted(tied_keys)[0]

    return vote_map[winner_key][1]


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------

def pearson_correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    """Pearson r between two equal-length sequences.  Returns None if undefined."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return None
    return cov / denom


def spearman_correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    """Spearman rank correlation between two equal-length sequences."""
    n = len(xs)
    if n < 2:
        return None

    def _ranks(vals: list[float]) -> list[float]:
        sorted_vals = sorted(enumerate(vals), key=lambda iv: iv[1])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and sorted_vals[j + 1][1] == sorted_vals[j][1]:
                j += 1
            avg_rank = (i + j) / 2 + 1  # 1-based average rank
            for k in range(i, j + 1):
                ranks[sorted_vals[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = _ranks(xs)
    ry = _ranks(ys)
    return pearson_correlation(rx, ry)


# ---------------------------------------------------------------------------
# Results aggregation
# ---------------------------------------------------------------------------

def aggregate_by_stratum(
    instance_results: list[dict],
) -> dict[int, dict]:
    """Compute per-stratum mean F1 scores.

    Args:
        instance_results: List of dicts, each with:
            ``icg``      (int)   — the instance's ICG value
            ``f1_a``     (float) — oracle best-agent Answer F1 for Variant A
            ``f1_b``     (float) — Answer F1 for Variant B
            ``f1_a_mv``  (float, optional) — majority-vote Answer F1 for Variant A

    Returns:
        Dict mapping ICG → {
            "n":          int,
            "f1_a":       float,  mean oracle Answer F1 for Variant A
            "f1_b":       float,  mean Answer F1 for Variant B
            "delta":      float,  f1_b - f1_a  (oracle gap)
            "f1_a_mv":    float,  mean majority-vote Answer F1 (if available)
            "delta_mv":   float,  f1_b - f1_a_mv (majority-vote gap, if available)
        }
    """
    strata: dict[int, list[dict]] = {}
    for r in instance_results:
        strata.setdefault(r["icg"], []).append(r)

    aggregated: dict[int, dict] = {}
    for icg, rows in sorted(strata.items()):
        n = len(rows)
        mean_a = sum(r["f1_a"] for r in rows) / n
        mean_b = sum(r["f1_b"] for r in rows) / n
        entry: dict = {
            "n": n,
            "f1_a": mean_a,
            "f1_b": mean_b,
            "delta": mean_b - mean_a,
        }
        if any("f1_a_mv" in r for r in rows):
            mean_a_mv = sum(r.get("f1_a_mv", 0.0) for r in rows) / n
            entry["f1_a_mv"] = mean_a_mv
            entry["delta_mv"] = mean_b - mean_a_mv
        aggregated[icg] = entry
    return aggregated


def compute_correlation(instance_results: list[dict]) -> dict:
    """Compute per-instance ICG vs (f1_b - f1_a) correlations.

    A positive correlation means higher ICG → larger communication gain,
    which is the paper's core hypothesis.

    Args:
        instance_results: same format as ``aggregate_by_stratum``.

    Returns:
        Dict with keys ``pearson`` and ``spearman`` (float or None each).
    """
    icg_vals = [float(r["icg"]) for r in instance_results]
    delta_vals = [r["f1_b"] - r["f1_a"] for r in instance_results]
    return {
        "pearson": pearson_correlation(icg_vals, delta_vals),
        "spearman": spearman_correlation(icg_vals, delta_vals),
    }


# ---------------------------------------------------------------------------
# Pretty-print
# ---------------------------------------------------------------------------

def print_results_table(
    aggregated: dict[int, dict],
    setting_label: str = "A",
) -> None:
    """Print a formatted results table for one sharding setting.

    Shows oracle best-agent F1 columns always; appends majority-vote columns
    when ``f1_a_mv`` is present in the aggregated data.

    Args:
        aggregated:    Output of ``aggregate_by_stratum``.
        setting_label: Label inserted into the header (e.g. "A1" or "A2").
    """
    has_mv = any("f1_a_mv" in row for row in aggregated.values())

    if has_mv:
        header = (
            f"ICG  | N      | F1_B (Central) | "
            f"F1_{setting_label}_oracle | Delta_oracle | "
            f"F1_{setting_label}_mv    | Delta_mv"
        )
    else:
        header = (
            f"ICG  | N      | F1_B (Centralized) | "
            f"F1_{setting_label} (Isolated) | Delta (B-{setting_label})"
        )
    sep = "-" * len(header)
    print(header)
    print(sep)
    for icg in sorted(aggregated):
        row = aggregated[icg]
        if has_mv:
            print(
                f"{icg:<4d} | {row['n']:<6d} | {row['f1_b']:<15.4f} | "
                f"{row['f1_a']:<16.4f} | {row['delta']:+.4f}       | "
                f"{row.get('f1_a_mv', 0.0):<13.4f} | {row.get('delta_mv', 0.0):+.4f}"
            )
        else:
            print(
                f"{icg:<4d} | {row['n']:<6d} | {row['f1_b']:<19.4f} | "
                f"{row['f1_a']:<21.4f} | {row['delta']:+.4f}"
            )
    print()
