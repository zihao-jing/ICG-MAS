"""
variant_b.py — Centralized single-agent baseline.

The single agent receives all supporting paragraphs concatenated and answers
with the same token budget T as each agent in Variant A.

Public API:
    run_variant_b(instance, api_fn, model, max_tokens) -> dict
    run_variant_b_batch(instances, api_fn, model, max_tokens) -> list[dict]
"""

from __future__ import annotations

import sys
import os
from typing import Callable

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utility.apis.base import APIRequest, APIResponse
from .data_loader import get_supporting_paragraphs
from .evaluate import answer_f1

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a question-answering assistant. "
    "Answer based on the provided evidence. "
    "Be concise — give only the answer, no explanation."
)


def _build_user_prompt(paragraph_texts: list[str], question: str) -> str:
    """Build the user turn for the centralized agent."""
    evidence_block = "\n\n".join(
        f"[Paragraph {i+1}]\n{text}" for i, text in enumerate(paragraph_texts)
    )
    return f"Evidence:\n{evidence_block}\n\nQuestion: {question}\n\nAnswer concisely."


# ---------------------------------------------------------------------------
# Per-instance runner
# ---------------------------------------------------------------------------

def run_variant_b(
    instance: dict,
    api_fn: Callable,
    model: str = "google/gemma-4-26b-a4b-it",
    max_tokens: int = 200,
) -> dict:
    """Run Variant B (centralized single agent) on one instance.

    The agent receives all supporting paragraphs concatenated.  Token budget
    is the same T as each individual agent in Variant A.

    Args:
        instance:   MuSiQue instance dict with ``question``, ``answer``,
                    ``answer_aliases``, ``paragraphs``, ``icg``.
        api_fn:     A single-request callable with signature matching
                    ``openrouter_api.single_request``:
                    ``(request: APIRequest) -> APIResponse``
        model:      Model identifier string.
        max_tokens: Output token budget.

    Returns:
        Dict with keys: id, icg, pred, f1.
    """
    supporting = get_supporting_paragraphs(instance)
    texts = [p["paragraph_text"] for p in supporting]
    question = instance["question"]

    request = APIRequest(
        system_query=SYSTEM_PROMPT,
        user_query=_build_user_prompt(texts, question),
        model=model,
        max_tokens=max_tokens,
        metadata={"instance_id": instance["id"]},
    )

    response: APIResponse = api_fn(request)

    pred = response.content.strip() if response.success and response.content.strip() else ""
    f1 = answer_f1(pred, instance)

    return {
        "id": instance["id"],
        "icg": instance["icg"],
        "pred": pred,
        "f1": f1,
        "error": None if (response.success and response.content.strip()) else (response.error or "empty response"),
    }


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_variant_b_batch(
    instances: list[dict],
    api_fn: Callable,
    model: str = "google/gemma-4-26b-a4b-it",
    max_tokens: int = 200,
) -> list[dict]:
    """Run Variant B over a list of instances, one at a time.

    Args:
        instances: List of MuSiQue instance dicts.
        api_fn:    single_request-compatible callable.
        model:     Model identifier string.
        max_tokens: Per-request output token budget.

    Returns:
        List of result dicts in the same order as ``instances``.
    """
    return [
        run_variant_b(inst, api_fn, model, max_tokens)
        for inst in instances
    ]
