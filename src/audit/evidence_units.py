"""
Evidence unit representation and extraction.

EvidenceUnit — core dataclass for tracking evidence through the pipeline.
load_gold_support_units — load/approximate gold critical units from benchmark metadata.
extract_candidate_units — extract atomic candidate units from one private shard.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class EvidenceUnit:
    """One atomic factual unit tracked through the distributed reasoning pipeline."""
    unit_id: str
    task_id: str
    agent_id: Optional[int]
    text: str
    # Where in the pipeline this unit lives
    source: str  # raw_shard | extracted_unit | transmitted_message | aggregator_input | final_rationale
    is_gold_support: bool = False
    is_critical: bool = False  # removal changes answerability
    parent_unit_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        flag = "[CRITICAL] " if self.is_critical else ""
        return f"EvidenceUnit({self.unit_id[:8]}… {flag}{self.source!r}: {self.text[:60]!r})"


# ---------------------------------------------------------------------------
# Gold support loaders
# ---------------------------------------------------------------------------

def load_gold_support_units(task: dict, task_id: Optional[str] = None) -> list[EvidenceUnit]:
    """Load gold support units from benchmark metadata.

    Supports MuSiQue-style tasks (paragraphs with is_supporting=True)
    and Silo-Bench tasks (gold_supports list or supporting_facts).

    Returns one EvidenceUnit per gold supporting paragraph / fact.
    """
    tid = task_id or task.get("id", str(uuid.uuid4()))
    units: list[EvidenceUnit] = []

    # MuSiQue: paragraphs list with is_supporting flag
    paragraphs = task.get("paragraphs", [])
    for para in paragraphs:
        if para.get("is_supporting"):
            uid = f"{tid}_gold_{len(units)}"
            units.append(EvidenceUnit(
                unit_id=uid,
                task_id=tid,
                agent_id=None,
                text=para.get("paragraph_text", ""),
                source="raw_shard",
                is_gold_support=True,
                is_critical=True,  # all gold supports treated as critical by default
                metadata={"title": para.get("title", ""), "para_idx": para.get("idx")},
            ))

    # Silo-Bench: gold_supports or supporting_facts
    for fact in task.get("gold_supports", []):
        text = fact if isinstance(fact, str) else fact.get("text", str(fact))
        uid = f"{tid}_gold_{len(units)}"
        units.append(EvidenceUnit(
            unit_id=uid,
            task_id=tid,
            agent_id=None,
            text=text,
            source="raw_shard",
            is_gold_support=True,
            is_critical=True,
            metadata={},
        ))

    for fact in task.get("supporting_facts", []):
        text = fact if isinstance(fact, str) else fact.get("text", str(fact))
        uid = f"{tid}_gold_{len(units)}"
        units.append(EvidenceUnit(
            unit_id=uid,
            task_id=tid,
            agent_id=None,
            text=text,
            source="raw_shard",
            is_gold_support=True,
            is_critical=True,
            metadata={},
        ))

    return units


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = (
    "You are an evidence extraction assistant.\n"
    "Extract atomic factual units from the provided evidence that may help answer the question.\n"
    "Each unit must be:\n"
    "  - self-contained (interpretable without other context)\n"
    "  - specific (include exact names, numbers, dates)\n"
    "  - factual (not a reasoning step or answer guess)\n"
    "Output a numbered list of atomic evidence units, one per line. "
    "Do not add explanations."
)


def _build_extraction_prompt(context: str, question: str, max_units: int) -> str:
    return (
        f"Question: {question}\n\n"
        f"Evidence shard:\n{context}\n\n"
        f"Extract up to {max_units} atomic factual units from the evidence above. "
        "Output a numbered list (one unit per line)."
    )


def _parse_units(text: str, max_units: int) -> list[str]:
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


def extract_candidate_units(
    task: dict,
    agent_id: int,
    shard_text: str,
    llm_client: Callable,
    model: str,
    max_units: int = 5,
    task_id: Optional[str] = None,
) -> list[EvidenceUnit]:
    """Extract atomic candidate evidence units from one private shard.

    Args:
        task:        Task dict with at least "question".
        agent_id:    Index of this agent.
        shard_text:  Formatted text of this agent's private shard.
        llm_client:  Callable(system, user, model, max_tokens) -> str response.
        model:       Model name string.
        max_units:   Maximum units to extract.
        task_id:     Override task ID (defaults to task["id"]).

    Returns:
        List of EvidenceUnit objects at source="extracted_unit".
    """
    tid = task_id or task.get("id", str(uuid.uuid4()))
    question = task.get("question", "")

    raw = llm_client(
        system=_EXTRACTION_SYSTEM,
        user=_build_extraction_prompt(shard_text, question, max_units),
        model=model,
        max_tokens=512,
    )

    texts = _parse_units(raw, max_units)
    return [
        EvidenceUnit(
            unit_id=f"{tid}_agent{agent_id}_ext{k}",
            task_id=tid,
            agent_id=agent_id,
            text=t,
            source="extracted_unit",
            metadata={"extraction_rank": k},
        )
        for k, t in enumerate(texts)
    ]
