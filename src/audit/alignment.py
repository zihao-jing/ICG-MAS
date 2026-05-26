"""
Align transmitted / extracted evidence units to gold critical units.

align_units — main alignment function (embedding shortlist + LLM judge).
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from .evidence_units import EvidenceUnit


# ---------------------------------------------------------------------------
# LLM alignment judge
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = (
    "You are an evidence alignment judge.\n\n"
    "Given a gold evidence unit and a candidate transmitted unit, "
    "classify their relationship.\n\n"
    "Labels:\n"
    "- EXACT: candidate preserves the same meaning and all key entities, "
    "numbers, dates, and constraints.\n"
    "- PARAPHRASE: candidate preserves the same meaning with different wording.\n"
    "- PARTIAL: candidate preserves some information but omits a key constraint.\n"
    "- DISTORTED: candidate is related but changes a key entity, number, date, "
    "relation, negation, or condition.\n"
    "- NO_MATCH: candidate does not express the gold evidence.\n\n"
    'Return JSON only:\n{"label": "EXACT|PARAPHRASE|PARTIAL|DISTORTED|NO_MATCH", '
    '"confidence": 0.0, "reason": "short explanation"}'
)

_VALID_LABELS = {"EXACT", "PARAPHRASE", "PARTIAL", "DISTORTED", "NO_MATCH"}


def _judge_prompt(gold_text: str, candidate_text: str) -> str:
    return (
        f"Gold evidence unit:\n{gold_text}\n\n"
        f"Candidate transmitted unit:\n{candidate_text}\n\n"
        "Classify their relationship."
    )


def _parse_judge_response(text: str) -> dict:
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            data = json.loads(m.group())
            label = data.get("label", "NO_MATCH").upper()
            if label not in _VALID_LABELS:
                label = "NO_MATCH"
            return {
                "label": label,
                "confidence": float(data.get("confidence", 0.5)),
                "reason": data.get("reason", ""),
            }
    except Exception:
        pass
    return {"label": "NO_MATCH", "confidence": 0.0, "reason": "parse error"}


# ---------------------------------------------------------------------------
# Deterministic numeric / entity checks
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:[.,]\d+)*\b", text)


def _deterministic_distortion_check(gold_text: str, candidate_text: str) -> bool:
    """Return True if numbers in gold are changed in candidate (likely distortion)."""
    gold_nums = set(_extract_numbers(gold_text))
    cand_nums = set(_extract_numbers(candidate_text))
    if not gold_nums:
        return False
    # Any gold number missing from candidate numbers is a potential distortion
    return bool(gold_nums - cand_nums)


# ---------------------------------------------------------------------------
# Lexical similarity (for shortlisting without embeddings)
# ---------------------------------------------------------------------------

def _jaccard_sim(a: str, b: str) -> float:
    from src.eval.evaluate import normalize
    ta = set(normalize(a))
    tb = set(normalize(b))
    if not ta and not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ---------------------------------------------------------------------------
# Main alignment function
# ---------------------------------------------------------------------------

def align_units(
    gold_units: list[EvidenceUnit],
    candidate_units: list[EvidenceUnit],
    llm_client: Optional[Callable] = None,
    model: str = "",
    method: str = "lexical",
    top_k_shortlist: int = 3,
    match_threshold: float = 0.1,
) -> list[dict]:
    """Align gold critical units to candidate / transmitted units.

    For each gold unit, finds the best-matching candidate and classifies
    their relationship.

    Args:
        gold_units:      Gold critical evidence units.
        candidate_units: Extracted or transmitted evidence units to align against.
        llm_client:      Optional callable for LLM judge (required for method="llm").
        model:           Model name for LLM judge.
        method:          "lexical" (fast, no LLM) or "llm" (uses LLM judge).
        top_k_shortlist: Number of top lexical candidates to judge with LLM.
        match_threshold: Minimum Jaccard similarity to consider a match.

    Returns:
        List of alignment dicts, one per gold unit:
        {
            gold_unit_id, candidate_unit_id (or None),
            match_score, relation, confidence, reason
        }
    """
    alignments: list[dict] = []

    for gold in gold_units:
        if not candidate_units:
            alignments.append({
                "gold_unit_id": gold.unit_id,
                "candidate_unit_id": None,
                "match_score": 0.0,
                "relation": "NO_MATCH",
                "confidence": 1.0,
                "reason": "no candidate units",
            })
            continue

        # Lexical shortlist
        scored = sorted(
            [(c, _jaccard_sim(gold.text, c.text)) for c in candidate_units],
            key=lambda x: x[1],
            reverse=True,
        )
        best_cand, best_sim = scored[0]

        if best_sim < match_threshold:
            alignments.append({
                "gold_unit_id": gold.unit_id,
                "candidate_unit_id": None,
                "match_score": best_sim,
                "relation": "NO_MATCH",
                "confidence": 0.8,
                "reason": "below similarity threshold",
            })
            continue

        if method == "llm" and llm_client is not None:
            # Use LLM judge on top-k candidates
            top_candidates = scored[:top_k_shortlist]
            best_result = None
            best_result_sim = -1.0
            for cand, sim in top_candidates:
                raw = llm_client(
                    system=_JUDGE_SYSTEM,
                    user=_judge_prompt(gold.text, cand.text),
                    model=model,
                    max_tokens=150,
                )
                result = _parse_judge_response(raw)
                # Prefer EXACT > PARAPHRASE > PARTIAL > DISTORTED > NO_MATCH
                label_rank = {"EXACT": 5, "PARAPHRASE": 4, "PARTIAL": 3,
                              "DISTORTED": 2, "NO_MATCH": 1}
                score = label_rank.get(result["label"], 1) + sim
                if score > best_result_sim:
                    best_result_sim = score
                    best_result = {
                        "gold_unit_id": gold.unit_id,
                        "candidate_unit_id": cand.unit_id,
                        "match_score": sim,
                        **result,
                    }
                    # Deterministic override: if numbers are changed, flag as distorted
                    if result["label"] in ("EXACT", "PARAPHRASE") and \
                            _deterministic_distortion_check(gold.text, cand.text):
                        best_result["label"] = "DISTORTED"
                        best_result["reason"] += " (numeric mismatch)"
            alignments.append(best_result)
        else:
            # Lexical-only: map similarity to label
            if best_sim >= 0.6:
                label = "PARAPHRASE"
            elif best_sim >= 0.3:
                label = "PARTIAL"
            else:
                label = "NO_MATCH"

            if label in ("PARAPHRASE",) and \
                    _deterministic_distortion_check(gold.text, best_cand.text):
                label = "DISTORTED"

            alignments.append({
                "gold_unit_id": gold.unit_id,
                "candidate_unit_id": best_cand.unit_id,
                "match_score": best_sim,
                "relation": label,
                "confidence": best_sim,
                "reason": "lexical similarity",
            })

    return alignments
