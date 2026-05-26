#!/usr/bin/env python3
"""
Experiment 4 (extension): Communication Budget k-Sweep for Mistral-S.

Reuses extracted units from saved Mistral-S Silo-Bench runs (no new extraction).
Runs new aggregation calls at k=1,2,3 for Random Relay and Score-Ranked Relay.
k=3 should match the existing paper results (validation check).

Usage:
    python scripts/exp4_k_sweep_mistrals.py
"""

from __future__ import annotations

import json
import os
import sys
import random
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.compute_audit_metrics import reconstruct_states_and_scores
from src.eval.silo_bench_loader import load_silobench, silobench_exact_match
from src.protocols.relay import _topk_select, _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from src.protocols.base import count_tokens_approx, extract_answer
from utility.apis.openrouter_api import batch_request, setup_response_log
from utility.apis.base import APIRequest

MODEL = "mistralai/mistral-small-2603"
MAX_TOKENS = 4096
MAX_WORKERS = 64
SEED = 42
K_VALUES = [1, 2, 3]

BASE = os.path.join(os.path.dirname(__file__), "..", "results")
RUN_DIRS = {
    "n5":  os.path.join(BASE, "run_mistrals"),
    "n10": os.path.join(BASE, "run_mistrals_n10"),
}
OUTPUT_DIR = os.path.join(BASE, "exp4_k_sweep_mistrals")

# Paper baseline for Mistral-S at k=3 (from Main Table 1 / Appendix E2)
PAPER_RESULTS_K3 = {
    "random_relay": 11.5,        # from appendix multimodel results
    "score_ranked_relay": 11.5,
}


def apply_selection(inst_id, protocol, inst_states, inst_scores, k):
    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        return [rng.sample(s, min(k, len(s))) if s else [] for s in inst_states]
    elif protocol == "score_ranked_relay":
        return [_topk_select(s, sc, k) for s, sc in zip(inst_states, inst_scores)]
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


def run_k_sweep_for_tier(tier, run_dir, protocols, k_values):
    n_agents_val = 5 if tier == "n5" else 10
    print(f"\n=== K-Sweep (Mistral-S) — {tier} (n={n_agents_val}) ===")

    resp_path = os.path.join(run_dir, "api_responses.jsonl")
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]
    print(f"  {len(responses)} existing API responses")

    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
    print(f"  {len(states_by_id)} instances with extracted units")

    instances = load_silobench(n_agents_filter=n_agents_val)
    print(f"  {len(instances)} instances loaded")

    all_requests = []
    request_index = []

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
                                  desc=f"k_sweep_mistrals_{tier}")

    tier_results = defaultdict(lambda: defaultdict(list))
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
        })

    return dict(tier_results)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "api_responses.jsonl")
    setup_response_log(log_path)
    print(f"API log: {log_path}")

    protocols = ["random_relay", "score_ranked_relay"]

    all_tier_results = {}
    for tier, run_dir in RUN_DIRS.items():
        all_tier_results[tier] = run_k_sweep_for_tier(tier, run_dir, protocols, K_VALUES)

    # Combine n5 + n10
    print("\n=== Combined Results (n5+n10, Silo-Bench, Mistral-S) ===\n")
    combined = defaultdict(dict)
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
                "acc_pct": acc * 100,
                "mean_comm_tokens": mean_comm,
            }

    header = f"{'Protocol':<30} " + " ".join(f"  k={k} Acc%  k={k} Tok" for k in K_VALUES)
    print(header)
    print("-" * len(header))
    for protocol in protocols:
        label = {"random_relay": "Random Relay", "score_ranked_relay": "Score-Ranked Relay"}.get(protocol, protocol)
        row = f"{label:<30}"
        for k in K_VALUES:
            if k in combined[protocol]:
                r = combined[protocol][k]
                row += f"  {r['acc_pct']:>7.1f}  {r['mean_comm_tokens']:>7.0f}"
            else:
                row += f"  {'N/A':>7}  {'N/A':>7}"
        print(row)

    print("\n=== Validation (k=3 vs. expected Mistral-S paper results) ===")
    for protocol in protocols:
        if 3 in combined[protocol]:
            computed = combined[protocol][3]["acc_pct"]
            expected = PAPER_RESULTS_K3.get(protocol, float("nan"))
            match = abs(computed - expected) < 3.0
            print(f"  {protocol}: computed={computed:.1f}%, expected~{expected:.1f}%, "
                  f"{'OK' if match else 'check carefully'}")

    out = {
        "model": MODEL,
        "k_values": K_VALUES,
        "protocols": protocols,
        "combined": {p: dict(ks) for p, ks in combined.items()},
    }
    out_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {OUTPUT_DIR}/")
    return out


if __name__ == "__main__":
    main()
