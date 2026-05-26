"""
Shared types and utilities for all communication protocols.
"""

from __future__ import annotations

import json
import re
import random
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class AgentShard:
    """One agent's private evidence slice."""
    agent_idx: int
    paragraphs: list[dict]  # [{idx, title, paragraph_text, is_supporting}]
    question: str
    instance_id: str
    # For Silo-Bench: the pre-formatted agent prompt (replaces paragraph-based formatting)
    prebuilt_prompt: str = ""


@dataclass
class ProtocolResult:
    """Outcome of running a protocol on one instance."""
    instance_id: str
    pred: str
    f1: float
    comm_tokens: int
    total_llm_tokens: int = 0       # all API tokens consumed by this protocol
    transmitted_states: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sharding
# ---------------------------------------------------------------------------

def shard_instance(
    instance: dict,
    n_agents: int = 3,
    seed: int = 42,
    distractors_per_agent: int = 2,
) -> list[AgentShard]:
    """Partition supporting paragraphs across n_agents with round-robin assignment.

    Supporting paragraphs are shuffled, then distributed round-robin so that
    the minimal support set (S*) is spread across agents.  Each agent also
    receives up to distractors_per_agent non-supporting paragraphs.
    """
    rng = random.Random(seed)
    supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
    distractors = [p for p in instance["paragraphs"] if not p["is_supporting"]]

    shuffled_support = list(supporting)
    rng.shuffle(shuffled_support)
    rng.shuffle(distractors)

    shards = [
        AgentShard(
            agent_idx=i,
            paragraphs=[],
            question=instance["question"],
            instance_id=instance["id"],
        )
        for i in range(n_agents)
    ]

    for i, para in enumerate(shuffled_support):
        shards[i % n_agents].paragraphs.append(para)

    for i, shard in enumerate(shards):
        start = i * distractors_per_agent
        shard.paragraphs.extend(distractors[start : start + distractors_per_agent])

    return shards


def get_supporting_from_shards(shards: list[AgentShard]) -> list[dict]:
    """Return all supporting paragraphs across all shards."""
    result = []
    for shard in shards:
        for p in shard.paragraphs:
            if p.get("is_supporting"):
                result.append(p)
    return result


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def format_shard_context(shard: AgentShard) -> str:
    """Format an agent's evidence as a text block.

    For Silo-Bench shards (prebuilt_prompt set) returns the pre-formatted prompt
    directly so all protocol runners work without change.
    """
    if shard.prebuilt_prompt:
        return shard.prebuilt_prompt
    if not shard.paragraphs:
        return "(no evidence available)"
    parts = [
        f"[Document {i+1}: {p['title']}]\n{p['paragraph_text']}"
        for i, p in enumerate(shard.paragraphs)
    ]
    return "\n\n".join(parts)


def extract_answer(text: str) -> str:
    """Extract the last 'ANSWER: <text>' line from an LLM response."""
    matches = re.findall(r"ANSWER:\s*(.+)", text, re.IGNORECASE)
    return matches[-1].strip() if matches else text.strip()


def is_refusal(ans: str) -> bool:
    """Return True if the answer is empty or an 'insufficient information' refusal."""
    return not ans.strip() or bool(
        re.search(r"insufficient\s+information", ans, re.IGNORECASE)
    )


def count_tokens_approx(text: str) -> int:
    """Approximate token count using the ~4 chars/token heuristic."""
    return max(1, len(text) // 4) if text else 0


# ---------------------------------------------------------------------------
# JSON score parsing
# ---------------------------------------------------------------------------

def parse_score_json(text: str) -> dict[str, float]:
    """Parse verifier JSON response; fall back to uniform 0.5 scores on error."""
    try:
        match = re.search(r"\{[^}]+\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            rel = float(data.get("relevance", 0.5))
            uniq = float(data.get("uniqueness", 0.5))
            crit = float(data.get("criticality", 0.5))
            return {
                "relevance": rel,
                "uniqueness": uniq,
                "criticality": crit,
                "composite": (rel + uniq + crit) / 3.0,
            }
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return {"relevance": 0.5, "uniqueness": 0.5, "criticality": 0.5, "composite": 0.5}
