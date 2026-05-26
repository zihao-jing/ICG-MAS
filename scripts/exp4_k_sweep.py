#!/usr/bin/env python3
"""
Experiment 4: Communication Budget k-Sweep.

Runs Score-Ranked Relay and Random Relay at k=1,2,3 evidence units per agent
on Silo-Bench (Qwen-235B, n5+n10 combined).

k=3 should match existing results (validation check).
Reuses existing extracted units and scores from run_qwen235b_n5/n10.
Only the aggregation step uses the API (~2×2×52=208 new aggregation calls).

Usage:
    python scripts/exp4_k_sweep.py
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import random
from collections import defaultdict

from scripts.compute_audit_metrics import reconstruct_states_and_scores
from src.eval.silo_bench_loader import load_silobench, silobench_exact_match
from src.protocols.relay import (
    _topk_select,
    _AGGREGATION_SYSTEM,
    _build_evidence_board_prompt,
)
from src.protocols.base import count_tokens_approx, extract_answer
from utility.apis.openrouter_api import batch_request, setup_response_log
from utility.apis.base import APIRequest

MODEL = "qwen/qwen3-235b-a22b-2507"
MAX_TOKENS = 4096
MAX_WORKERS = 64
SEED = 42

K_VALUES = [1, 2, 3, 5]  # k=3 is existing baseline for validation; k=5 added

RUN_DIRS = {
    "n5":  os.path.join(os.path.dirname(__file__), "..", "results", "run_qwen235b_n5"),
    "n10": os.path.join(os.path.dirname(__file__), "..", "results", "run_qwen235b_n10"),
}

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "results", "exp4_k_sweep"
)


def apply_selection(
    inst_id: str,
    protocol: str,
    inst_states: list[list[str]],
    inst_scores: list[list[dict]],
    k: int,
) -> list[list[str]]:
    """Select up to k units per agent using the given protocol."""
    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        return [
            rng.sample(s, min(k, len(s))) if s else []
            for s in inst_states
        ]
    elif protocol == "score_ranked_relay":
        return [
            _topk_select(s, sc, k)
            for s, sc in zip(inst_states, inst_scores)
        ]
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


def run_k_sweep_for_tier(
    tier: str,
    run_dir: str,
    protocols: list[str],
    k_values: list[int],
) -> dict:
    """Run k-sweep for one tier (n5 or n10). Returns {protocol: {k: {inst_id: result}}}."""

    n_agents_val = 5 if tier == "n5" else 10
    print(f"\n=== K-Sweep — {tier} (n={n_agents_val}) ===")

    # Load existing responses
    resp_path = os.path.join(run_dir, "api_responses.jsonl")
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]
    print(f"  {len(responses)} existing API responses")

    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
    print(f"  {len(states_by_id)} instances with extracted units")

    instances = load_silobench(n_agents_filter=n_agents_val)
    print(f"  {len(instances)} instances loaded")

    # Build all aggregation requests for all (inst, protocol, k) combos
    all_requests = []
    request_index = []  # (inst, protocol, k)

    for inst in instances:
        inst_id = inst["id"]
        if inst_id not in states_by_id:
            print(f"  WARNING: no states for {inst_id}")
            continue

        n_actual = len(inst["agent_configs"])
        inst_states_by_agent = states_by_id[inst_id]
        inst_scores_by_agent = scores_by_id.get(inst_id, {})

        inst_states = [inst_states_by_agent.get(a, []) for a in range(n_actual)]
        inst_scores = [inst_scores_by_agent.get(a, []) for a in range(n_actual)]

        for protocol in protocols:
            for k in k_values:
                selected = apply_selection(inst_id, protocol, inst_states, inst_scores, k)
                all_units = [u for ag in selected for u in ag]

                all_requests.append(APIRequest(
                    system_query=_AGGREGATION_SYSTEM,
                    user_query=_build_evidence_board_prompt(selected, inst["question"]),
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    metadata={
                        "instance_id": inst_id,
                        "protocol": protocol,
                        "k": k,
                        "phase": f"k_sweep_agg_k{k}",
                    },
                ))
                request_index.append({
                    "inst": inst,
                    "protocol": protocol,
                    "k": k,
                    "selected": selected,
                    "comm_tokens": sum(count_tokens_approx(u) for u in all_units),
                })

    print(f"  Submitting {len(all_requests)} aggregation requests...")

    responses_agg = batch_request(all_requests, max_workers=MAX_WORKERS,
                                  desc=f"k_sweep_{tier}")

    # Collect results
    tier_results: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for resp, meta in zip(responses_agg, request_index):
        inst = meta["inst"]
        inst_id = inst["id"]
        protocol = meta["protocol"]
        k = meta["k"]

        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        f1 = silobench_exact_match(pred, inst)

        tier_results[protocol][k].append({
            "id": inst_id,
            "pred": pred,
            "gold": inst["answer"],
            "f1": f1,
            "correct": f1 >= 1.0,
            "comm_tokens": meta["comm_tokens"],
            "total_llm_tokens": resp.usage.get("total_tokens", 0),
        })

    return dict(tier_results)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "api_responses.jsonl")
    setup_response_log(log_path)
    print(f"API log: {log_path}")

    protocols = ["random_relay", "score_ranked_relay"]

    # Collect per-tier results
    all_tier_results: dict[str, dict] = {}
    for tier, run_dir in RUN_DIRS.items():
        all_tier_results[tier] = run_k_sweep_for_tier(
            tier, run_dir, protocols, K_VALUES
        )

    # ── Combine n5 + n10 ──────────────────────────────────────────────────────
    print("\n=== Combined Results (n5 + n10, Silo-Bench, Qwen-235B) ===\n")

    combined: dict[str, dict[int, dict]] = defaultdict(dict)
    for protocol in protocols:
        for k in K_VALUES:
            all_recs = []
            for tier in ["n5", "n10"]:
                all_recs.extend(all_tier_results.get(tier, {}).get(protocol, {}).get(k, []))
            n = len(all_recs)
            if n == 0:
                continue
            acc = sum(r["correct"] for r in all_recs) / n
            mean_comm = sum(r["comm_tokens"] for r in all_recs) / n
            combined[protocol][k] = {
                "n": n,
                "acc": acc,
                "acc_pct": acc * 100,
                "mean_comm_tokens": mean_comm,
            }

    # Print table
    header = f"{'Protocol':<30} " + " ".join(f"  k={k} Acc%  k={k} Tok" for k in K_VALUES)
    print(header)
    print("-" * len(header))

    for protocol in protocols:
        label = {
            "random_relay": "Random Relay",
            "score_ranked_relay": "Score-Ranked Relay",
        }.get(protocol, protocol)
        row = f"{label:<30}"
        for k in K_VALUES:
            if k in combined[protocol]:
                r = combined[protocol][k]
                row += f"  {r['acc_pct']:>7.1f}  {r['mean_comm_tokens']:>7.0f}"
            else:
                row += f"  {'N/A':>7}  {'N/A':>7}"
        print(row)

    # Validation check: k=3 should match existing results
    print("\n=== Validation (k=3 vs. existing paper results) ===")
    paper_results = {
        "random_relay": 17.3,
        "score_ranked_relay": 19.2,
    }
    for protocol in protocols:
        if 3 in combined[protocol]:
            computed = combined[protocol][3]["acc_pct"]
            expected = paper_results.get(protocol, float("nan"))
            match = abs(computed - expected) < 2.0
            print(f"  {protocol}: computed={computed:.1f}%, paper={expected:.1f}%, "
                  f"{'OK' if match else 'MISMATCH (check carefully)'}")

    # ── Save ──────────────────────────────────────────────────────────────────
    out = {
        "k_values": K_VALUES,
        "protocols": protocols,
        "combined": {proto: {k: v for k, v in ks.items()} for proto, ks in combined.items()},
        "per_tier": {
            tier: {
                proto: {k: recs for k, recs in ks.items()}
                for proto, ks in tier_data.items()
            }
            for tier, tier_data in all_tier_results.items()
        },
    }
    out_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {OUTPUT_DIR}/")

    return out


if __name__ == "__main__":
    main()
