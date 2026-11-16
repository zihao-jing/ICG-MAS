"""Checkpoint-removal routing for the audit (E3).

Pure functions over stored per-fact labels; no model calls.  The full route
follows the paper's diagnosis order: extraction omission, selection omission,
strict distortion, candidate aggregation.  Removing one check means that
check's evidence is ignored when the route is assigned.
"""
from __future__ import annotations

from typing import Iterable, Mapping

CHECKS = ("pool", "fidelity", "aggregation")
ROUTES = ("extraction", "selection", "distortion", "aggregation", "correct", "unrouted")


def _absent(labels: Mapping[str, Mapping]) -> bool:
    return any(v.get("status") == "absent" for v in labels.values())


def _distorted(labels: Mapping[str, Mapping]) -> bool:
    return any(v.get("fidelity") == "distorted" for v in labels.values())


def route(extraction: Mapping[str, Mapping], board: Mapping[str, Mapping],
          answer_correct: bool, removed: Iterable[str] = ()) -> str:
    """Route one trace with the named checks removed.

    ``removed`` may contain 'pool' (ignore the extraction check), 'fidelity'
    (treat distorted as faithful) and 'aggregation' (do not route a wrong
    answer with complete faithful coverage).  Removing all three leaves the
    trace unrouted.
    """
    removed = set(removed)
    if removed.issuperset(CHECKS):
        return "unrouted"
    if "pool" not in removed and _absent(extraction):
        return "extraction"
    if _absent(board):
        return "selection"
    if "fidelity" not in removed and _distorted(board):
        return "distortion"
    if "aggregation" not in removed and not answer_correct:
        return "aggregation"
    return "correct"


def route_changes(traces: list[dict], removed: Iterable[str]) -> dict:
    """Count route changes against the full audit for a list of traces.

    Each trace dict has 'extraction', 'board', 'answer_correct', and optional
    'model'/'instance'.  Returns counts and a full-route breakdown.
    """
    removed = tuple(removed)
    changed = 0
    pairs: dict[tuple[str, str], int] = {}
    for t in traces:
        full = route(t["extraction"], t["board"], t["answer_correct"])
        new = route(t["extraction"], t["board"], t["answer_correct"], removed)
        if new != full:
            changed += 1
            pairs[(full, new)] = pairs.get((full, new), 0) + 1
    return {"n": len(traces), "changed": changed,
            "changed_share": changed / len(traces) if traces else 0.0,
            "pairs": pairs}