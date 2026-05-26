"""
data_loader.py — Load MuSiQue JSONL and compute ICG per instance.

Data source: data/musique/musique_ans_v1.0_dev.jsonl  (testset)

Each instance (dict) keeps the original MuSiQue schema verbatim.
ICG is injected as a computed field ``icg`` on the returned dicts.

Public API:
    load_musique(path)                -> list[dict]   raw instances
    load_musique_sample(n, seed, ...) -> list[dict]   stratified sample
    compute_icg(instance)             -> int          ICG for one instance
    stratify_by_icg(instances)        -> dict[int, list[dict]]  grouped by ICG
    shards_from_musique(instance)     -> list[AgentShard]  one shard per supporting para
"""

from __future__ import annotations

import json
import os
import random as _random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.protocols.base import AgentShard


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DEV_PATH = os.path.join(
    _REPO_ROOT, "data", "musique", "musique_ans_v1.0_dev.jsonl"
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_musique(path: Optional[str] = None, min_hops: int = 1) -> list[dict]:
    """Load MuSiQue JSONL and return a list of instance dicts.

    Each returned dict is the raw parsed JSON line, with an added ``icg``
    field (int) computed from the supporting paragraphs.

    Args:
        path:     Path to a ``.jsonl`` file.  Defaults to the dev split under
                  ``data/musique/``.
        min_hops: Minimum number of supporting paragraphs required to keep an
                  instance (default 1 = keep all).  Set to 4 to restrict to
                  4-hop instances only.

    Returns:
        List of instance dicts, each containing at minimum:
            id, question, answer, answer_aliases,
            paragraphs, question_decomposition, icg
    """
    if path is None:
        path = DEFAULT_DEV_PATH

    instances: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            instance = json.loads(line)
            supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
            if len(supporting) < min_hops:
                continue
            titles = [p["title"] for p in supporting]
            if len(titles) != len(set(titles)):
                continue  # skip instances with duplicate supporting paragraphs
            instance["icg"] = compute_icg(instance)
            instances.append(instance)
    return instances


# ---------------------------------------------------------------------------
# ICG calculation
# ---------------------------------------------------------------------------

def compute_icg(instance: dict) -> int:
    """Return the Irreducible Communication Gap for one MuSiQue instance.

    With the one-paragraph-per-agent sharding strategy:
        ICG = |S*(x)| - max_i |S*(x) ∩ U_i|
            = num_supporting_paragraphs - 1

    Each supporting paragraph is treated as one atomic evidence unit
    held by exactly one agent, so every agent contributes exactly 1 unit
    from S*(x) and the maximum is always 1.

    Args:
        instance: A parsed MuSiQue instance dict (must have ``paragraphs``).

    Returns:
        Non-negative integer ICG value.
    """
    supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
    num_supporting = len(supporting)
    # Guard: at least 1 supporting paragraph expected in answerable instances
    if num_supporting == 0:
        return 0
    return num_supporting - 1


# ---------------------------------------------------------------------------
# Stratification
# ---------------------------------------------------------------------------

def stratify_by_icg(instances: list[dict]) -> dict[int, list[dict]]:
    """Group instances by their ICG value.

    Args:
        instances: List of instance dicts (each must have an ``icg`` field,
                   e.g. as returned by ``load_musique``).

    Returns:
        Dict mapping ICG value → list of instances with that ICG.
        For MuSiQue with 2–4 supporting paragraphs the keys will be {1, 2, 3}.
    """
    strata: dict[int, list[dict]] = {}
    for inst in instances:
        key = inst["icg"]
        strata.setdefault(key, []).append(inst)
    return strata


# ---------------------------------------------------------------------------
# Convenience: extract supporting paragraphs
# ---------------------------------------------------------------------------

def get_supporting_paragraphs(instance: dict) -> list[dict]:
    """Return the supporting paragraphs for an instance, in idx order.

    Each element is a paragraph dict:
        {"idx": int, "title": str, "paragraph_text": str, "is_supporting": bool}
    """
    return [p for p in instance["paragraphs"] if p["is_supporting"]]


# ---------------------------------------------------------------------------
# Stratified sampling
# ---------------------------------------------------------------------------

# Default per-ICG allocation for a 100-instance sample.
# ICG 1 = 2-hop (most common), ICG 2 = 3-hop, ICG 3 = 4-hop.
_DEFAULT_HOP_ALLOC: dict[int, int] = {1: 50, 2: 35, 3: 15}


def load_musique_sample(
    n: int = 100,
    seed: int = 42,
    path: Optional[str] = None,
    min_hops: int = 2,
    max_hops: int = 4,
    hop_alloc: Optional[dict[int, int]] = None,
) -> list[dict]:
    """Return a reproducible stratified sample of MuSiQue instances.

    Args:
        n:          Total number of instances to return.
        seed:       Random seed for reproducible sampling.
        path:       Path to JSONL file (default: dev split).
        min_hops:   Minimum number of supporting paragraphs (default 2).
        max_hops:   Maximum number of supporting paragraphs (default 4).
        hop_alloc:  Dict mapping ICG value → count to sample from that stratum.
                    ICG = num_supporting - 1, so ICG 1 = 2-hop, etc.
                    Defaults to {1: 50, 2: 35, 3: 15} for n=100.
                    If n != 100 and hop_alloc is None, allocates proportionally.

    Returns:
        List of at most n instance dicts, each with an ``icg`` field.
    """
    all_instances = load_musique(path, min_hops=min_hops)
    # Filter by max_hops
    all_instances = [
        inst for inst in all_instances
        if len([p for p in inst["paragraphs"] if p["is_supporting"]]) <= max_hops
    ]

    strata = stratify_by_icg(all_instances)

    if hop_alloc is None:
        if n == 100:
            hop_alloc = dict(_DEFAULT_HOP_ALLOC)
        else:
            # Proportional allocation
            total = sum(len(v) for v in strata.values())
            if total == 0:
                return []
            hop_alloc = {
                k: max(1, round(n * len(v) / total))
                for k, v in strata.items()
            }

    rng = _random.Random(seed)
    sampled: list[dict] = []
    for icg_val in sorted(hop_alloc):
        count = hop_alloc[icg_val]
        pool = strata.get(icg_val, [])
        k = min(count, len(pool))
        sampled.extend(rng.sample(pool, k))

    return sampled


# ---------------------------------------------------------------------------
# Evidence sharding for MuSiQue
# ---------------------------------------------------------------------------

def shards_from_musique(
    instance: dict,
    n_distractors_per_agent: int = 3,
) -> list["AgentShard"]:
    """Create one AgentShard per supporting paragraph.

    Assignment rule:
    - Agent i receives exactly the i-th supporting paragraph as private evidence.
    - Distractor paragraphs are distributed round-robin across agents
      (up to n_distractors_per_agent per agent).
    - n_agents = len(supporting_paragraphs), so ICG = n_agents - 1.

    The ``prebuilt_prompt`` field is populated so that all protocol runners
    work with MuSiQue shards the same way they work with Silo-Bench shards.

    Args:
        instance:               A MuSiQue instance dict (must have ``paragraphs``).
        n_distractors_per_agent: Max distractor paragraphs added to each shard.

    Returns:
        List of AgentShard objects, one per supporting paragraph.
    """
    from src.protocols.base import AgentShard

    supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
    distractors = [p for p in instance["paragraphs"] if not p["is_supporting"]]
    n_agents = len(supporting)

    shards: list[AgentShard] = []
    for i, sup_para in enumerate(supporting):
        # Round-robin distractor assignment
        agent_distractors = distractors[i::n_agents][:n_distractors_per_agent]
        agent_paras = [sup_para] + agent_distractors

        context = "\n\n".join(
            f"[Document: {p['title']}]\n{p['paragraph_text']}"
            for p in agent_paras
        )
        prompt = (
            f"Question: {instance['question']}\n\n"
            f"You hold the following evidence:\n{context}"
        )
        shards.append(AgentShard(
            agent_idx=i,
            paragraphs=agent_paras,
            question=instance["question"],
            instance_id=instance["id"],
            prebuilt_prompt=prompt,
        ))
    return shards
