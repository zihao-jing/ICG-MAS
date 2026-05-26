#!/usr/bin/env python3
"""
Experiment 4 (extension): Communication Budget k-Sweep for 3 additional models.
  - Qwen-3.6-Flash  (qwen/qwen3.6-flash)
  - Gemma-4-31B     (google/gemma-4-31b-it)
  - Qwen-80B-T      (qwen/qwen3-next-80b-a3b-thinking)

Reuses extracted units/scores from existing Silo-Bench run dirs (no new extraction).
Only new aggregation calls at k=1,2,3 for Random Relay and Score-Ranked Relay.

Usage:
    python scripts/exp4_k_sweep_newmodels.py
"""
from __future__ import annotations

import json, os, sys, random
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.compute_audit_metrics import reconstruct_states_and_scores
from src.eval.silo_bench_loader import load_silobench, silobench_exact_match
from src.protocols.relay import _topk_select, _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from src.protocols.base import count_tokens_approx, extract_answer
from utility.apis.openrouter_api import batch_request, setup_response_log
from utility.apis.base import APIRequest

SEED = 42
K_VALUES = [1, 2, 3]
MAX_TOKENS = 4096
MAX_WORKERS = 64
BASE = os.path.join(os.path.dirname(__file__), "..", "results")

MODELS = {
    "qwen3.6flash": {
        "model_id": "qwen/qwen3.6-flash",
        "run_dirs": {
            "n5":  os.path.join(BASE, "run_20260523_214416"),
            "n10": os.path.join(BASE, "run_silobench_n10"),
        },
        "paper_k3": {"random_relay": 61.5, "score_ranked_relay": 59.6},
    },
    "gemma31b": {
        "model_id": "google/gemma-4-31b-it",
        "run_dirs": {
            "n5":  os.path.join(BASE, "run_gemma31b_n5"),
            "n10": os.path.join(BASE, "run_gemma31b_n10"),
        },
        "paper_k3": {"random_relay": 42.3, "score_ranked_relay": 36.5},
    },
    "qwen80bt": {
        "model_id": "qwen/qwen3-next-80b-a3b-thinking",
        "run_dirs": {
            "n5":  os.path.join(BASE, "run_qwen80bt"),
            "n10": os.path.join(BASE, "run_qwen80bt_n10"),
        },
        "paper_k3": {"random_relay": 17.3, "score_ranked_relay": 23.1},
    },
}


def apply_selection(inst_id, protocol, inst_states, inst_scores, k):
    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        return [rng.sample(s, min(k, len(s))) if s else [] for s in inst_states]
    elif protocol == "score_ranked_relay":
        return [_topk_select(s, sc, k) for s, sc in zip(inst_states, inst_scores)]
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


def run_k_sweep_for_tier(tier, run_dir, model_id, protocols, k_values):
    n_agents_val = 5 if tier == "n5" else 10
    print(f"\n  --- {tier} (n={n_agents_val}) ---")

    resp_path = os.path.join(run_dir, "api_responses.jsonl")
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]
    print(f"  {len(responses)} existing API responses")

    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
    print(f"  {len(states_by_id)} instances with extracted units")

    instances = load_silobench(n_agents_filter=n_agents_val)
    print(f"  {len(instances)} instances loaded")

    all_requests, request_index = [], []
    for inst in instances:
        inst_id = inst["id"]
        if inst_id not in states_by_id:
            print(f"  WARNING: no states for {inst_id}")
            continue
        n_actual = len(inst["agent_configs"])
        inst_states = [states_by_id[inst_id].get(a, []) for a in range(n_actual)]
        inst_scores = [scores_by_id.get(inst_id, {}).get(a, []) for a in range(n_actual)]

        for protocol in protocols:
            for k in k_values:
                selected = apply_selection(inst_id, protocol, inst_states, inst_scores, k)
                all_units = [u for ag in selected for u in ag]
                all_requests.append(APIRequest(
                    system_query=_AGGREGATION_SYSTEM,
                    user_query=_build_evidence_board_prompt(selected, inst["question"]),
                    model=model_id,
                    max_tokens=MAX_TOKENS,
                    metadata={"instance_id": inst_id, "protocol": protocol, "k": k},
                ))
                request_index.append({
                    "inst": inst, "protocol": protocol, "k": k,
                    "comm_tokens": sum(count_tokens_approx(u) for u in all_units),
                })

    print(f"  Submitting {len(all_requests)} aggregation requests...")
    responses_agg = batch_request(all_requests, max_workers=MAX_WORKERS,
                                  desc=f"k_sweep_{tier}")

    tier_results = defaultdict(lambda: defaultdict(list))
    for resp, meta in zip(responses_agg, request_index):
        inst = meta["inst"]
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        f1 = silobench_exact_match(pred, inst)
        tier_results[meta["protocol"]][meta["k"]].append({
            "id": inst["id"], "pred": pred, "gold": inst["answer"],
            "correct": f1 >= 1.0,
            "comm_tokens": meta["comm_tokens"],
        })
    return dict(tier_results)


def run_model(short, cfg):
    model_id = cfg["model_id"]
    print(f"\n{'='*60}")
    print(f"Model: {model_id} ({short})")
    print(f"{'='*60}")

    output_dir = os.path.join(BASE, f"exp4_k_sweep_{short}")
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "api_responses.jsonl")
    setup_response_log(log_path)

    protocols = ["random_relay", "score_ranked_relay"]
    all_tier_results = {}
    for tier, run_dir in cfg["run_dirs"].items():
        all_tier_results[tier] = run_k_sweep_for_tier(
            tier, run_dir, model_id, protocols, K_VALUES
        )

    # Combine n5 + n10
    combined = defaultdict(dict)
    for protocol in protocols:
        for k in K_VALUES:
            all_recs = []
            for tier in ["n5", "n10"]:
                all_recs.extend(all_tier_results.get(tier, {}).get(protocol, {}).get(k, []))
            if not all_recs:
                continue
            acc = sum(r["correct"] for r in all_recs) / len(all_recs)
            combined[protocol][k] = {
                "n": len(all_recs),
                "acc_pct": round(acc * 100, 1),
                "mean_comm_tokens": sum(r["comm_tokens"] for r in all_recs) / len(all_recs),
            }

    print(f"\n=== Combined Results ({short}) ===")
    header = f"{'Protocol':<24} " + "  ".join(f"k={k} Acc%" for k in K_VALUES)
    print(header)
    print("-" * 50)
    for p in protocols:
        label = {"random_relay": "Random Relay", "score_ranked_relay": "Score-Ranked Relay"}.get(p, p)
        row = f"{label:<24}"
        for k in K_VALUES:
            row += f"  {combined[p].get(k, {}).get('acc_pct', 'N/A'):>7}"
        print(row)

    print(f"\n=== Validation (k=3 vs. paper) ===")
    for p in protocols:
        if 3 in combined[p]:
            comp = combined[p][3]["acc_pct"]
            exp = cfg["paper_k3"].get(p, float("nan"))
            ok = abs(comp - exp) < 3.0
            print(f"  {p}: computed={comp:.1f}%, paper={exp:.1f}%  {'OK' if ok else 'MISMATCH'}")

    out = {
        "model": model_id, "k_values": K_VALUES, "protocols": protocols,
        "combined": {p: dict(ks) for p, ks in combined.items()},
    }
    out_path = os.path.join(output_dir, "results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Results saved to: {output_dir}/")
    return out


def main():
    all_results = {}
    for short, cfg in MODELS.items():
        all_results[short] = run_model(short, cfg)

    print("\n" + "="*70)
    print("=== SUMMARY — k-sweep for all 3 new models ===")
    print("="*70)
    for short, res in all_results.items():
        print(f"\n{short}:")
        for p in ["random_relay", "score_ranked_relay"]:
            vals = " / ".join(
                f"k={k}: {res['combined'].get(p, {}).get(k, {}).get('acc_pct', 'N/A'):.1f}%"
                for k in K_VALUES
            )
            label = "Random" if p == "random_relay" else "Score-Ranked"
            print(f"  {label}: {vals}")

    return all_results


if __name__ == "__main__":
    main()
