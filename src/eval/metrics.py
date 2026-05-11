"""
Experiment-level metrics for Table 1 (main results).

  utility(acc, cost)          — accuracy–cost tradeoff (Eq. 5 in paper)
  recovery(acc, acc_local, acc_full)  — fraction of local→full gap recovered
  cscov(gold_paragraphs, states)      — critical-state coverage (Eq. 7)
  build_results_table(...)    — aggregate per-protocol metrics into a table dict
  print_results_table(table)  — pretty-print Table 1
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Scalar metrics
# ---------------------------------------------------------------------------

def compute_utility(acc: float, cost: float, lambda_: float = 1e-4) -> float:
    """U = Acc - lambda * Cost  (Eq. 5, lambda = 10^{-4} by default)."""
    return acc - lambda_ * cost


def compute_recovery(
    acc_method: float,
    acc_local: float,
    acc_full: float,
    eps: float = 1e-8,
) -> float:
    """Recovery = (Acc_method - Acc_local) / (Acc_full - Acc_local + eps).

    Measures how much of the local → full accuracy gap the method recovers.
    Returns 0.0 when acc_full ≈ acc_local (no gap to recover).
    """
    return (acc_method - acc_local) / (acc_full - acc_local + eps)


def compute_cscov(
    gold_paragraphs: list[dict],
    transmitted_states: list[str],
    threshold: float = 0.15,
) -> float:
    """CSCOV = |S* ∩ E_board| / |S*|  (Eq. 7 in paper).

    A gold supporting paragraph is considered "covered" if at least one
    transmitted state has token-level Jaccard similarity ≥ threshold with it.

    Args:
        gold_paragraphs:    Supporting paragraph dicts (must have "paragraph_text").
        transmitted_states: All atomic states transmitted across all agents.
        threshold:          Minimum Jaccard similarity to count as covered.

    Returns:
        Float in [0, 1]; 1.0 when gold_paragraphs is empty.
    """
    if not gold_paragraphs:
        return 1.0
    if not transmitted_states:
        return 0.0

    from src.eval.evaluate import normalize

    covered = 0
    for para in gold_paragraphs:
        gold_tokens = set(normalize(para.get("paragraph_text", "")))
        if not gold_tokens:
            covered += 1
            continue
        for state in transmitted_states:
            state_tokens = set(normalize(state))
            if not state_tokens:
                continue
            union = gold_tokens | state_tokens
            if union and len(gold_tokens & state_tokens) / len(union) >= threshold:
                covered += 1
                break

    return covered / len(gold_paragraphs)


# ---------------------------------------------------------------------------
# Per-protocol aggregation
# ---------------------------------------------------------------------------

def aggregate_protocol_results(
    instance_results: list[dict],
) -> dict:
    """Aggregate per-instance results into mean metrics.

    Args:
        instance_results: List of dicts, each with keys:
            pred, f1, comm_tokens, cscov (optional)

    Returns:
        Dict with: n, acc (mean F1), mean_comm_tokens, utility, cscov
    """
    n = len(instance_results)
    if n == 0:
        return {"n": 0, "acc": 0.0, "mean_comm_tokens": 0.0, "mean_total_llm_tokens": 0.0, "utility": 0.0}

    acc = sum(r["f1"] for r in instance_results) / n
    mean_cost = sum(r["comm_tokens"] for r in instance_results) / n
    mean_llm = sum(r.get("total_llm_tokens", 0) for r in instance_results) / n
    utility = compute_utility(acc, mean_cost)

    result: dict = {
        "n": n,
        "acc": acc,
        "mean_comm_tokens": mean_cost,
        "mean_total_llm_tokens": mean_llm,
        "utility": utility,
    }
    if any("cscov" in r for r in instance_results):
        result["cscov"] = sum(r.get("cscov", 0.0) for r in instance_results) / n

    return result


def build_results_table(
    protocol_results: dict[str, list[dict]],
    acc_local_key: str = "single_local",
    acc_full_key: str = "full_sharing",
) -> dict[str, dict]:
    """Build the full Table 1 metric dict from per-protocol instance results.

    Args:
        protocol_results: {protocol_name: [per-instance result dicts]}
        acc_local_key:    Protocol name to use as Acc_local (denominator of recovery)
        acc_full_key:     Protocol name to use as Acc_full

    Returns:
        {protocol_name: {n, acc, mean_comm_tokens, utility, recovery, cscov?}}
    """
    aggregated: dict[str, dict] = {}
    for name, results in protocol_results.items():
        aggregated[name] = aggregate_protocol_results(results)

    acc_local = aggregated.get(acc_local_key, {}).get("acc", 0.0)
    acc_full = aggregated.get(acc_full_key, {}).get("acc", 1.0)

    for name, row in aggregated.items():
        row["recovery"] = compute_recovery(row["acc"], acc_local, acc_full)

    return aggregated


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

_PROTOCOL_LABELS: dict[str, str] = {
    "single_local": "Single local agent",
    "majority_vote": "Majority vote",
    "best_local": "Best-local oracle",
    "free_form_debate": "Free-form debate",
    "summary_exchange": "Summary exchange",
    "confidence_gated": "Confidence-gated comm.",
    "disagreement_gated": "Disagreement-gated comm.",
    "random_relay": "Random state relay",
    "full_sharing": "Full evidence sharing",
    "csc_topk": "CSC top-k (ours)",
    "csc_redundancy": "CSC + redund. penalty (ours)",
}

_DISPLAY_ORDER = [
    "single_local",
    "majority_vote",
    "best_local",
    "free_form_debate",
    "summary_exchange",
    "confidence_gated",
    "disagreement_gated",
    "random_relay",
    "full_sharing",
    "csc_topk",
    "csc_redundancy",
]


def print_results_table(table: dict[str, dict]) -> None:
    """Print Table 1 to stdout."""
    col_w = [34, 12, 14, 14, 10, 10]
    header = (
        f"{'Method':<{col_w[0]}} "
        f"{'Acc (%)':{col_w[1]}} "
        f"{'Comm.Tokens':{col_w[2]}} "
        f"{'Token Cost':{col_w[3]}} "
        f"{'Utility':{col_w[4]}} "
        f"{'Recovery':{col_w[5]}}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    order = [k for k in _DISPLAY_ORDER if k in table]
    order += [k for k in table if k not in _DISPLAY_ORDER]

    for name in order:
        row = table[name]
        label = _PROTOCOL_LABELS.get(name, name)
        acc_pct = row["acc"] * 100
        comm = row["mean_comm_tokens"]
        llm = row.get("mean_total_llm_tokens", 0.0)
        util = row["utility"]
        rec = row["recovery"]
        cscov_str = f"  cscov={row['cscov']:.3f}" if "cscov" in row else ""
        print(
            f"{label:<{col_w[0]}} "
            f"{acc_pct:>{col_w[1]}.2f} "
            f"{comm:>{col_w[2]}.1f} "
            f"{llm:>{col_w[3]}.1f} "
            f"{util:>{col_w[4]}.4f} "
            f"{rec:>{col_w[5]}.3f}"
            f"{cscov_str}"
        )
    print()
