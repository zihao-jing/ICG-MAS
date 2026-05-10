"""
variant_b.py — Centralized single-agent baseline.

The single agent receives all supporting paragraphs concatenated and answers
with the same token budget T as each agent in Variant A.

Public API:
    run_variant_b(instance, api_fn, model, max_tokens) -> dict
    run_variant_b_batch(instances, api_fn, model, max_tokens) -> list[dict]
"""

from __future__ import annotations

import concurrent.futures
import re
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
    "You will be given multiple paragraphs. Reason step by step through all of them together "
    "to find the answer — you may chain information across paragraphs. "
    "Do NOT introduce any facts not explicitly stated in the provided paragraphs. "
    "After your reasoning, output your final answer on the last line in this exact format:\n"
    "ANSWER: <your concise answer>\n"
    "If the answer cannot be found even with this reasoning, write:\n"
    "ANSWER: Insufficient information."
)


def _build_user_prompt(paragraph_texts: list[str], question: str) -> str:
    """Build the user turn for the centralized agent."""
    evidence_block = "\n\n".join(
        f"[Paragraph {i+1}]\n{text}" for i, text in enumerate(paragraph_texts)
    )
    return (
        f"Paragraphs:\n{evidence_block}\n\n"
        f"Question: {question}\n\n"
        f"Reason step by step across all paragraphs. Do not use outside knowledge. "
        f"Then output your final answer on the last line as: ANSWER: <answer>"
    )


def _extract_answer(text: str) -> str:
    """Extract the final answer from a response that may contain reasoning.

    Looks for the last 'ANSWER: <text>' line. Falls back to the full text
    if the pattern is absent (e.g. model ignored the format instruction).
    """
    matches = re.findall(r'ANSWER:\s*(.+)', text, re.IGNORECASE)
    if matches:
        return matches[-1].strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Per-instance runner
# ---------------------------------------------------------------------------

def run_variant_b(
    instance: dict,
    api_fn: Callable,
    model: str = "anthropic/claude-3.5-haiku",
    max_tokens: int = 4096,
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

    raw = response.content.strip() if response.success and response.content.strip() else ""
    pred = _extract_answer(raw) if raw else ""
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
    model: str = "anthropic/claude-3.5-haiku",
    max_tokens: int = 4096,
    max_workers: int = 5,
) -> list[dict]:
    """Run Variant B over a list of instances concurrently.

    Args:
        instances:   List of MuSiQue instance dicts.
        api_fn:      single_request-compatible callable.
        model:       Model identifier string.
        max_tokens:  Per-request output token budget.
        max_workers: Number of concurrent instance threads.

    Returns:
        List of result dicts in the same order as ``instances``.
    """
    results: list[dict | None] = [None] * len(instances)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(run_variant_b, inst, api_fn, model, max_tokens): i
            for i, inst in enumerate(instances)
        }
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            results[i] = future.result()
    return results  # type: ignore[return-value]
