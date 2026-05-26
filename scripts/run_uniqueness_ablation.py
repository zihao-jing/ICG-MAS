#!/usr/bin/env python3
"""
Ablation: uniqueness-only scoring vs. combined score relay on Silo-Bench.
Addresses reviewer question: why use composite score? Does uniqueness alone suffice?

Reuses existing extraction/scoring states. Only new aggregation calls needed.
"""
from __future__ import annotations
import json, os, sys, random

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from scripts.compute_audit_metrics import reconstruct_states_and_scores
from src.eval.silo_bench_loader import load_silobench
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from src.protocols.base import count_tokens_approx, extract_answer
from utility.apis.openrouter_api import batch_request, setup_response_log
from utility.apis.base import APIRequest

SEED = 42
K_VALUES = [1, 2, 3]
MAX_TOKENS = 4096
MAX_WORKERS = 128
OUTPUT_DIR = os.path.join(_ROOT, "results", "uniqueness_ablation")

MODELS = {
    "qwen235b": {
        "model_id": "qwen/qwen3-235b-a22b-07-25",
        "run_dirs": {
            "n5":  os.path.join(_ROOT, "results", "run_qwen235b_n5"),
            "n10": os.path.join(_ROOT, "results", "run_qwen235b_n10"),
        },
    },
    "qwen36f": {
        "model_id": "qwen/qwen3.6-flash",
        "run_dirs": {
            "n5":  os.path.join(_ROOT, "results", "run_20260523_214416"),
            "n10": os.path.join(_ROOT, "results", "run_silobench_n10"),
        },
    },
}

PROTOCOLS_SELECT = {
    "random_relay":         lambda states, scores, k, rng: rng.sample(states, min(k, len(states))),
    "uniqueness_only_relay": lambda states, scores, k, rng: _topk_by_key(states, scores, k, "uniqueness"),
    "score_ranked_relay":   lambda states, scores, k, rng: _topk_by_key(states, scores, k, "overall"),
}


def _topk_by_key(states, scores, k, key):
    if not states:
        return []
    paired = sorted(zip(states, scores), key=lambda x: x[1].get(key, 0.0), reverse=True)
    return [s for s, _ in paired[:k]]


def evaluate_sb(inst, pred_text):
    pred = extract_answer(pred_text)
    gold = inst.get("answer", inst.get("expected_answer", ""))
    return float(pred.strip().lower() == str(gold).strip().lower())


def run_ablation_for_model(model_key, cfg):
    model_id = cfg["model_id"]
    print(f"\n=== Uniqueness Ablation — {model_key} ({model_id}) ===")

    all_requests = []
    request_meta = []

    for tier, run_dir in cfg["run_dirs"].items():
        n_agents = 5 if tier == "n5" else 10
        instances = load_silobench(n_agents_filter=n_agents)

        resp_path = os.path.join(run_dir, "api_responses.jsonl")
        if not os.path.exists(resp_path):
            print(f"  Missing: {resp_path}")
            continue
        with open(resp_path) as f:
            responses = [json.loads(l) for l in f if l.strip()]
        states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
        inst_by_id = {inst["id"]: inst for inst in instances}

        print(f"  {tier}: {len(states_by_id)} instances with extraction states")

        for inst_id, inst in inst_by_id.items():
            if inst_id not in states_by_id:
                continue

            inst_states = [states_by_id[inst_id].get(a, []) for a in range(n_agents)]
            inst_scores = [scores_by_id.get(inst_id, {}).get(a, []) for a in range(n_agents)]

            for protocol, select_fn in PROTOCOLS_SELECT.items():
                for k in K_VALUES:
                    rng = random.Random(f"{SEED}:{inst_id}:{protocol}")
                    selected = [select_fn(s, sc, k, rng) for s, sc in zip(inst_states, inst_scores)]
                    all_requests.append(APIRequest(
                        system_query=_AGGREGATION_SYSTEM,
                        user_query=_build_evidence_board_prompt(selected, inst["question"]),
                        model=model_id,
                        max_tokens=MAX_TOKENS,
                        metadata={
                            "tier": tier,
                            "inst_id": inst_id,
                            "protocol": protocol,
                            "k": k,
                            "phase": "uniqueness_ablation",
                        },
                    ))
                    request_meta.append({"tier": tier, "inst": inst, "protocol": protocol, "k": k})

    print(f"  Submitting {len(all_requests)} aggregation requests...")
    responses_agg = batch_request(all_requests, max_workers=MAX_WORKERS,
                                  desc=f"uniq_abl_{model_key}")

    # Aggregate
    from collections import defaultdict
    raw: dict[str, dict[str, dict[int, list]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for resp, meta in zip(responses_agg, request_meta):
        content = resp.content.strip() if resp.success and resp.content else ""
        f1 = evaluate_sb(meta["inst"], content)
        raw[meta["tier"]][meta["protocol"]][meta["k"]].append(f1)

    # Print
    print(f"\n  {'Protocol':<24} " + " ".join(f"k={k} n5%  " for k in K_VALUES))
    result = {}
    for protocol in PROTOCOLS_SELECT:
        label = protocol.replace("_relay", "").replace("_", " ").title()
        row = f"  {label:<24}"
        result[protocol] = {}
        for tier_name in ["n5", "n10", "combined"]:
            result[protocol][tier_name] = {}
            for k in K_VALUES:
                if tier_name == "combined":
                    vals = raw["n5"][protocol][k] + raw["n10"][protocol][k]
                else:
                    vals = raw[tier_name][protocol][k]
                if vals:
                    result[protocol][tier_name][k] = {"acc_pct": sum(vals)/len(vals)*100, "n": len(vals)}

        for k in K_VALUES:
            v = result[protocol].get("n5", {}).get(k)
            row += f"  {v['acc_pct']:>5.1f}   " if v else f"  {'N/A':>5}   "
        print(row)

    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_response_log(os.path.join(OUTPUT_DIR, "api_responses.jsonl"))

    all_results = {}
    for model_key, cfg in MODELS.items():
        all_results[model_key] = run_ablation_for_model(model_key, cfg)

    # Summary table
    print("\n\n=== Uniqueness Ablation Summary (combined n5+n10) ===")
    print(f"{'Protocol':<26} {'Model':<12} " + " ".join(f"k={k} Acc%" for k in K_VALUES))
    for protocol in PROTOCOLS_SELECT:
        for model_key in MODELS:
            label = protocol.replace("_relay", "").replace("_", " ").title()
            row = f"{label:<26} {model_key:<12}"
            for k in K_VALUES:
                v = all_results.get(model_key, {}).get(protocol, {}).get("combined", {}).get(k)
                row += f"  {v['acc_pct']:>6.1f}" if v else f"  {'---':>6}"
            print(row)

    out_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
