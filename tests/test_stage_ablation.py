"""Unit tests for the E3 checkpoint-removal routing (no model calls)."""
from src.audit.stage_ablation import route, route_changes

P = {"f1": {"status": "present", "fidelity": "faithful"}}
A = {"f1": {"status": "absent", "fidelity": "absent"}}
D = {"f1": {"status": "present", "fidelity": "distorted"}}
PA = {"f1": {"status": "partial", "fidelity": "partial"}}


def test_full_route_order():
    assert route(A, A, False) == "extraction"
    assert route(P, A, False) == "selection"
    assert route(P, D, False) == "distortion"
    assert route(P, P, False) == "aggregation"
    assert route(P, P, True) == "correct"


def test_removing_pool_hides_extraction_loss():
    assert route(A, A, False, ["pool"]) == "selection"
    assert route(A, P, True, ["pool"]) == "correct"


def test_removing_fidelity_hides_distortion():
    assert route(P, D, False, ["fidelity"]) == "aggregation"
    assert route(P, D, True, ["fidelity"]) == "correct"


def test_removing_aggregation_hides_aggregation_failure():
    assert route(P, P, False, ["aggregation"]) == "correct"


def test_all_removed_is_unrouted():
    assert route(P, P, False, ["pool", "fidelity", "aggregation"]) == "unrouted"
    assert route(A, D, False, ["pool", "fidelity", "aggregation"]) == "unrouted"


def test_partial_is_not_strict_distortion():
    assert route(P, PA, False) == "aggregation"


def test_route_changes_counts_against_full():
    traces = [
        {"extraction": A, "board": A, "answer_correct": False},
        {"extraction": P, "board": A, "answer_correct": False},
        {"extraction": P, "board": P, "answer_correct": True},
    ]
    out = route_changes(traces, ["pool"])
    assert out["n"] == 3
    assert out["changed"] == 1
    assert out["pairs"] == {("extraction", "selection"): 1}
    assert out["changed_share"] == 1 / 3