"""
silo_bench_loader.py — Load Silo-Bench benchmark instances.

Silo-Bench files live in data/silo-bench/benchmarks/{TASK_ID}_n{N}.json.
Each file contains one task × one agent-count configuration.

Public API
----------
load_silobench(path, n_agents_filter, paradigms)  -> list[dict]
shards_from_silobench(instance)                   -> list[AgentShard]
silobench_exact_match(pred, instance)             -> float
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from src.protocols.base import AgentShard


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_BENCH_DIR = os.path.join(_REPO_ROOT, "data", "silo-bench", "benchmarks")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_silobench(
    path: Optional[str] = None,
    n_agents_filter: Optional[int] = None,
    paradigms: Optional[list[str]] = None,
) -> list[dict]:
    """Load Silo-Bench benchmark instances from a directory of JSON files.

    Args:
        path:            Directory containing ``{TASK_ID}_n{N}.json`` files
                         (default: data/silo-bench/benchmarks/).
        n_agents_filter: If given, only load instances with this agent count.
        paradigms:       If given, only load instances from these paradigm labels
                         (e.g. ["Paradigm I", "Paradigm II"]).

    Returns:
        List of normalised instance dicts, each containing:
            id, question, answer, answer_aliases, paradigm, n_agents,
            is_segmented, paragraphs (empty), full_context, agent_configs, icg
    """
    bench_dir = path or DEFAULT_BENCH_DIR
    instances: list[dict] = []

    for fname in sorted(os.listdir(bench_dir)):
        if not fname.endswith(".json"):
            continue

        fpath = os.path.join(bench_dir, fname)
        with open(fpath, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        if "agent_configs" not in raw:
            continue

        n_agents = raw["metadata"]["num_agents"]
        paradigm = raw.get("paradigm", "")
        is_segmented = raw["metadata"].get("is_segmented", False)

        if n_agents_filter is not None and n_agents != n_agents_filter:
            continue
        if paradigms is not None and paradigm not in paradigms:
            continue

        agent_configs = raw["agent_configs"]
        expected = raw["expected_output"]

        if is_segmented:
            # Segmented tasks require per-agent evaluation and structured list
            # output comparison, which is incompatible with the single-answer
            # protocol design used for Table 1.  Excluded by design.
            continue

        answer_val = expected["per_agent_values"][0] if expected.get("per_agent_values") else ""

        full_context = "\n\n---\n\n".join(
            ac["user_prompt"] for ac in agent_configs
        )

        inst: dict = {
            "id": f"{raw['case_id']}_n{n_agents}",
            "question": raw["task_description"],
            "answer": str(answer_val),
            "answer_aliases": [],
            "paradigm": paradigm,
            "n_agents": n_agents,
            "is_segmented": is_segmented,
            "paragraphs": [],       # unused for Silo-Bench
            "full_context": full_context,
            "agent_configs": agent_configs,
            "icg": n_agents - 1,    # all agents hold disjoint shards → ICG = n-1
        }
        instances.append(inst)

    return instances


# ---------------------------------------------------------------------------
# Shard creation
# ---------------------------------------------------------------------------

def shards_from_silobench(instance: dict) -> list[AgentShard]:
    """Create AgentShard list from a Silo-Bench instance's agent_configs.

    Each shard uses the pre-formatted ``user_prompt`` as ``prebuilt_prompt``
    so that ``format_shard_context`` returns it directly and all protocol
    runners work without modification.
    """
    return [
        AgentShard(
            agent_idx=ac["agent_id"],
            paragraphs=[],
            question=instance["question"],
            instance_id=instance["id"],
            prebuilt_prompt=ac["user_prompt"],
        )
        for ac in instance["agent_configs"]
    ]


# ---------------------------------------------------------------------------
# Answer evaluation
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, strip whitespace, remove punctuation for comparison."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s.-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def silobench_exact_match(pred: str, instance: dict) -> float:
    """Return 1.0 if the prediction matches the expected answer, else 0.0.

    Comparison is case-insensitive after basic normalisation.
    """
    expected = instance["answer"]
    if _normalise(pred) == _normalise(expected):
        return 1.0
    # Try numeric comparison for numeric answers
    try:
        if float(pred.strip()) == float(expected.strip()):
            return 1.0
    except (ValueError, TypeError):
        pass
    return 0.0
