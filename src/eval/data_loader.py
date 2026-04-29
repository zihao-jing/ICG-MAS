"""
data_loader.py — Load MuSiQue JSONL and compute ICG per instance.

Data source: data/musique/musique_ans_v1.0_dev.jsonl  (testset)

Each instance (dict) keeps the original MuSiQue schema verbatim.
ICG is injected as a computed field ``icg`` on the returned dicts.

Public API:
    load_musique(path)          -> list[dict]   raw instances
    compute_icg(instance)       -> int          ICG for one instance
    stratify_by_icg(instances)  -> dict[int, list[dict]]  grouped by ICG value
"""

from __future__ import annotations

import json
import os
from typing import Optional


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
