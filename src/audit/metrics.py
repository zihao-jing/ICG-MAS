"""
Evidence-flow metrics for the audit framework.

Metrics:
  critical_evidence_recall    — |S* matched in B| / |S*|
  omission_rate               — 1 - critical_recall
  distortion_rate             — distorted / transmitted critical
  redundancy_rate             — mean pairwise similarity of transmitted units
  useful_budget_share         — critical units / transmitted units
  aggregation_failure         — evidence present but answer wrong
  protocol_audit_summary      — aggregate metrics over tasks
"""

from __future__ import annotations

from typing import Callable, Optional

from .evidence_units import EvidenceUnit


# ---------------------------------------------------------------------------
# Per-task metrics
# ---------------------------------------------------------------------------

def critical_evidence_recall(
    gold_critical_units: list[EvidenceUnit],
    transmitted_units: list[EvidenceUnit],
    alignments: list[dict],
) -> float:
    """Fraction of gold critical units that are matched (EXACT/PARAPHRASE/PARTIAL) in transmitted."""
    if not gold_critical_units:
        return 1.0
    matched_labels = {"EXACT", "PARAPHRASE", "PARTIAL"}
    matched = sum(
        1 for a in alignments
        if a.get("relation") in matched_labels and a.get("candidate_unit_id") is not None
    )
    return matched / len(gold_critical_units)


def omission_rate(
    gold_critical_units: list[EvidenceUnit],
    transmitted_units: list[EvidenceUnit],
    alignments: list[dict],
) -> float:
    return 1.0 - critical_evidence_recall(gold_critical_units, transmitted_units, alignments)


def distortion_rate(
    gold_critical_units: list[EvidenceUnit],
    transmitted_units: list[EvidenceUnit],
    alignments: list[dict],
) -> float:
    """Fraction of transmitted critical units that are distorted."""
    transmitted_labels = {"EXACT", "PARAPHRASE", "PARTIAL", "DISTORTED"}
    transmitted_critical = [
        a for a in alignments
        if a.get("relation") in transmitted_labels and a.get("candidate_unit_id") is not None
    ]
    if not transmitted_critical:
        return 0.0
    distorted = sum(1 for a in transmitted_critical if a.get("relation") == "DISTORTED")
    return distorted / len(transmitted_critical)


def redundancy_rate(
    transmitted_units: list[EvidenceUnit],
    similarity_fn: Optional[Callable] = None,
) -> float:
    """Mean pairwise Jaccard similarity among transmitted evidence units."""
    if len(transmitted_units) < 2:
        return 0.0

    if similarity_fn is None:
        from src.eval.evaluate import normalize
        def similarity_fn(a: str, b: str) -> float:
            ta = set(normalize(a))
            tb = set(normalize(b))
            if not ta and not tb:
                return 0.0
            return len(ta & tb) / len(ta | tb)

    texts = [u.text for u in transmitted_units]
    n = len(texts)
    total, count = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            total += similarity_fn(texts[i], texts[j])
            count += 1
    return total / count if count > 0 else 0.0


def useful_budget_share(
    gold_critical_units: list[EvidenceUnit],
    transmitted_units: list[EvidenceUnit],
    alignments: list[dict],
) -> float:
    """Fraction of transmitted units that match a gold critical unit."""
    if not transmitted_units:
        return 0.0
    matched_candidate_ids = {
        a["candidate_unit_id"]
        for a in alignments
        if a.get("relation") in {"EXACT", "PARAPHRASE", "PARTIAL"}
        and a.get("candidate_unit_id") is not None
    }
    matched_count = sum(
        1 for u in transmitted_units if u.unit_id in matched_candidate_ids
    )
    return matched_count / len(transmitted_units)


def aggregation_failure(
    answer_correct: bool,
    crit_recall: float,
    dist_rate: float,
    recall_threshold: float = 1.0,
    distortion_threshold: float = 0.0,
) -> bool:
    """True when evidence is present and undistorted but answer is still wrong."""
    return (
        not answer_correct
        and crit_recall >= recall_threshold
        and dist_rate <= distortion_threshold
    )


# ---------------------------------------------------------------------------
# Per-task audit record
# ---------------------------------------------------------------------------

def compute_task_audit(
    task_id: str,
    protocol: str,
    answer_correct: bool,
    comm_tokens: int,
    total_tokens: int,
    gold_critical_units: list[EvidenceUnit],
    transmitted_units: list[EvidenceUnit],
    alignments: list[dict],
    similarity_fn: Optional[Callable] = None,
) -> dict:
    """Compute all audit metrics for one task/protocol run."""
    crit_recall = critical_evidence_recall(gold_critical_units, transmitted_units, alignments)
    omit_rate = omission_rate(gold_critical_units, transmitted_units, alignments)
    dist_rate = distortion_rate(gold_critical_units, transmitted_units, alignments)
    redund = redundancy_rate(transmitted_units, similarity_fn)
    useful = useful_budget_share(gold_critical_units, transmitted_units, alignments)
    agg_fail = aggregation_failure(answer_correct, crit_recall, dist_rate)

    return {
        "task_id": task_id,
        "protocol": protocol,
        "accuracy": int(answer_correct),
        "comm_tokens": comm_tokens,
        "total_tokens": total_tokens,
        "critical_recall": crit_recall,
        "omission_rate": omit_rate,
        "distortion_rate": dist_rate,
        "redundancy_rate": redund,
        "useful_budget_share": useful,
        "aggregation_failure": int(agg_fail),
    }


# ---------------------------------------------------------------------------
# Protocol-level aggregation
# ---------------------------------------------------------------------------

def protocol_audit_summary(records: list[dict]) -> dict:
    """Aggregate audit metrics over all tasks for one protocol."""
    if not records:
        return {}
    n = len(records)
    keys = [
        "accuracy", "comm_tokens", "total_tokens",
        "critical_recall", "omission_rate", "distortion_rate",
        "redundancy_rate", "useful_budget_share", "aggregation_failure",
    ]
    return {
        "n": n,
        "protocol": records[0].get("protocol", "unknown"),
        **{k: sum(r.get(k, 0) for r in records) / n for k in keys},
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

_PROTOCOL_LABELS: dict[str, str] = {
    "single_local": "Single Local",
    "majority_vote": "Majority Vote",
    "best_local": "Best-Local Oracle",
    "free_form_debate": "Free-form Debate",
    "summary_exchange": "Summary Exchange",
    "confidence_gated": "Confidence-Gated",
    "disagreement_gated": "Disagreement-Gated",
    "random_relay": "Random Evidence Relay",
    "score_ranked_relay": "Score-Ranked Evidence Relay",
    "redundancy_aware_relay": "Redundancy-Aware Evidence Relay",
    "full_sharing": "Full Evidence Sharing",
}

_DISPLAY_ORDER = [
    "single_local",
    "majority_vote",
    "free_form_debate",
    "summary_exchange",
    "confidence_gated",
    "disagreement_gated",
    "random_relay",
    "score_ranked_relay",
    "redundancy_aware_relay",
    "full_sharing",
]


def print_audit_table(summaries: dict[str, dict]) -> None:
    """Print protocol audit summary table to stdout."""
    cols = ["Acc", "CommTok", "CritRecall", "Omission", "Distortion", "Redundancy", "UsefulBudget", "AggFail"]
    widths = [34, 8, 10, 12, 12, 12, 12, 12, 9]
    header = (
        f"{'Method':<{widths[0]}} "
        + " ".join(f"{c:>{widths[i+1]}}" for i, c in enumerate(cols))
    )
    print(header)
    print("-" * len(header))

    order = [k for k in _DISPLAY_ORDER if k in summaries]
    order += [k for k in summaries if k not in _DISPLAY_ORDER]

    for name in order:
        s = summaries[name]
        label = _PROTOCOL_LABELS.get(name, name)
        print(
            f"{label:<{widths[0]}} "
            f"{s.get('accuracy', 0)*100:>{widths[1]}.1f} "
            f"{s.get('comm_tokens', 0):>{widths[2]}.0f} "
            f"{s.get('critical_recall', 0):>{widths[3]}.3f} "
            f"{s.get('omission_rate', 0):>{widths[4]}.3f} "
            f"{s.get('distortion_rate', 0):>{widths[5]}.3f} "
            f"{s.get('redundancy_rate', 0):>{widths[6]}.3f} "
            f"{s.get('useful_budget_share', 0):>{widths[7]}.3f} "
            f"{s.get('aggregation_failure', 0)*100:>{widths[8]}.1f}"
        )
    print()
