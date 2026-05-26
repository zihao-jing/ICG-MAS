#!/usr/bin/env python3
"""
K-sweep on MuSiQue: Random Relay vs Score-Ranked Relay at k=1,2,3.

Reuses saved extraction states/scores from existing MuSiQue run directories.
Only new aggregation calls are made (~2 protocols × 3 k values × 100 instances per model).

Models covered:
  - Qwen-235B       (run_qwen235b_musique)
  - Mistral-S       (run_musique_mistrals)
  - Qwen-80B-T      (run_musique_qwen80bt)
  - Qwen-3.6-Flash  (run_musique_100)
  - Gemma-4-31B     (run_musique_gemma31b)

Usage:
    cd /path/to/repo
    python scripts/exp4_k_sweep_musique.py
"""

from __future__ import annotations

import json
import os
import sys
import random
from collections import defaultdict

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
from src.eval.data_loader import load_musique, get_supporting_paragraphs
from src.eval.evaluate import answer_f1
from src.protocols.relay import _topk_select, _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from src.protocols.base import count_tokens_approx, extract_answer
from utility.apis.openrouter_api import batch_request, setup_response_log
from utility.apis.base import APIRequest

SEED = 42
K_VALUES = [1, 2, 3]
MAX_TOKENS = 4096
MAX_WORKERS = 128
BASE = os.path.join(_ROOT, "results")
OUTPUT_DIR = os.path.join(BASE, "exp4_k_sweep_musique")

# ── Model registry ──────────────────────────────────────────────────────────
MODELS = {
    "qwen235b": {
        "model_id":  "qwen/qwen3-235b-a22b-07-25",
        "run_dir":   os.path.join(BASE, "run_qwen235b_musique"),
        "paper_k3":  {"random_relay": 42.9, "score_ranked_relay": 46.7},
    },
    "mistrals": {
        "model_id":  "mistralai/mistral-small-2603",
        "run_dir":   os.path.join(BASE, "run_musique_mistrals"),
        "paper_k3":  {"random_relay": 27.4, "score_ranked_relay": 26.6},
    },
    "qwen80bt": {
        "model_id":  "qwen/qwen3-next-80b-a3b-thinking-2509",
        "run_dir":   os.path.join(BASE, "run_musique_qwen80bt"),
        "paper_k3":  {"random_relay": 31.8, "score_ranked_relay": 35.3},
    },
    "qwen36f": {
        "model_id":  "qwen/qwen3.6-flash",
        "run_dir":   os.path.join(BASE, "run_musique_100"),
        "paper_k3":  {"random_relay": 63.7, "score_ranked_relay": 65.1},
    },
    "gemma31b": {
        "model_id":  "google/gemma-4-31b-it-20260402",
        "run_dir":   os.path.join(BASE, "run_musique_gemma31b"),
        "paper_k3":  {"random_relay": 39.5, "score_ranked_relay": 35.2},
    },
}

PROTOCOLS = ["random_relay", "score_ranked_relay"]


# ── Helpers ─────────────────────────────────────────────────────────────────

def apply_selection(
    inst_id: str,
    protocol: str,
    inst_states: list[list[str]],
    inst_scores: list[list[dict]],
    k: int,
) -> list[list[str]]:
    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        return [rng.sample(s, min(k, len(s))) if s else [] for s in inst_states]
    elif protocol == "score_ranked_relay":
        return [_topk_select(s, sc, k) for s, sc in zip(inst_states, inst_scores)]
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


def run_k_sweep_for_model(
    model_key: str,
    model_id: str,
    run_dir: str,
    instances: list[dict],
    paper_k3: dict,
) -> dict[str, dict[int, dict]]:
    """Run k-sweep for one model. Returns {protocol: {k: summary_dict}}."""
    print(f"\n=== MuSiQue K-Sweep — {model_key} ({model_id}) ===")

    resp_path = os.path.join(run_dir, "api_responses.jsonl")
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]
    print(f"  {len(responses)} existing API responses")

    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
    print(f"  {len(states_by_id)} instances with extracted units")

    inst_by_id = {inst["id"]: inst for inst in instances}
    matched_ids = [iid for iid in states_by_id if iid in inst_by_id]
    print(f"  {len(matched_ids)} instances matched (run ∩ instances)")

    all_requests: list[APIRequest] = []
    request_meta: list[dict] = []

    for inst_id in matched_ids:
        inst = inst_by_id[inst_id]
        n_agents = len(get_supporting_paragraphs(inst))
        inst_states = [states_by_id[inst_id].get(a, []) for a in range(n_agents)]
        inst_scores = [scores_by_id.get(inst_id, {}).get(a, []) for a in range(n_agents)]

        for protocol in PROTOCOLS:
            for k in K_VALUES:
                selected = apply_selection(inst_id, protocol, inst_states, inst_scores, k)
                all_units = [u for ag in selected for u in ag]
                all_requests.append(APIRequest(
                    system_query=_AGGREGATION_SYSTEM,
                    user_query=_build_evidence_board_prompt(selected, inst["question"]),
                    model=model_id,
                    max_tokens=MAX_TOKENS,
                    metadata={
                        "instance_id": inst_id,
                        "protocol": protocol,
                        "k": k,
                        "phase": "k_sweep_musique_agg",
                    },
                ))
                request_meta.append({
                    "inst": inst,
                    "protocol": protocol,
                    "k": k,
                    "comm_tokens": sum(count_tokens_approx(u) for u in all_units),
                })

    print(f"  Submitting {len(all_requests)} aggregation requests...")
    responses_agg = batch_request(all_requests, max_workers=MAX_WORKERS,
                                  desc=f"k_sweep_mq_{model_key}")

    # Collect
    raw_results: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for resp, meta in zip(responses_agg, request_meta):
        inst = meta["inst"]
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        f1 = answer_f1(pred, inst)
        raw_results[meta["protocol"]][meta["k"]].append({
            "id": inst["id"],
            "pred": pred,
            "f1": f1,
            "correct": f1 >= 1.0,
            "comm_tokens": meta["comm_tokens"],
        })

    # Aggregate
    combined: dict[str, dict[int, dict]] = {}
    for protocol in PROTOCOLS:
        combined[protocol] = {}
        for k in K_VALUES:
            recs = raw_results[protocol][k]
            n = len(recs)
            if n == 0:
                continue
            acc_pct = 100 * sum(r["f1"] for r in recs) / n
            mean_comm = sum(r["comm_tokens"] for r in recs) / n
            combined[protocol][k] = {
                "n": n,
                "acc_pct": acc_pct,
                "mean_comm_tokens": mean_comm,
            }

    # Print
    print(f"\n  {'Protocol':<24} " + " ".join(f"k={k} Acc%  " for k in K_VALUES))
    print(f"  {'-'*60}")
    for protocol in PROTOCOLS:
        label = protocol.replace("_", " ").title()
        row = f"  {label:<24}"
        for k in K_VALUES:
            if k in combined.get(protocol, {}):
                row += f"  {combined[protocol][k]['acc_pct']:>6.1f}   "
            else:
                row += f"  {'N/A':>6}   "
        print(row)

    # Validation vs k=3 paper baseline
    print(f"\n  Validation (k=3 vs paper):")
    for protocol in PROTOCOLS:
        if 3 in combined.get(protocol, {}):
            computed = combined[protocol][3]["acc_pct"]
            expected = paper_k3.get(protocol, float("nan"))
            match = abs(computed - expected) < 3.0
            print(f"    {protocol}: computed={computed:.1f}%, paper={expected:.1f}%"
                  f"  {'OK' if match else 'MISMATCH'}")

    return combined


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "api_responses.jsonl")
    setup_response_log(log_path)

    # Load the 100 MuSiQue instances
    _ids_file = os.path.join(_ROOT, "data", "musique_100_ids.json")
    if os.path.exists(_ids_file):
        with open(_ids_file) as f:
            ids_100 = set(json.load(f))
    else:
        # Reconstruct from Qwen-235B run
        ids_100 = set()
        with open(os.path.join(BASE, "run_qwen235b_musique", "api_responses.jsonl")) as f:
            for line in f:
                r = json.loads(line)
                if r.get("instance_id"):
                    ids_100.add(r["instance_id"])

    all_instances = load_musique()
    instances = [inst for inst in all_instances if inst["id"] in ids_100]
    print(f"Loaded {len(instances)} MuSiQue instances")

    all_results: dict[str, dict] = {}
    for model_key, cfg in MODELS.items():
        result = run_k_sweep_for_model(
            model_key=model_key,
            model_id=cfg["model_id"],
            run_dir=cfg["run_dir"],
            instances=instances,
            paper_k3=cfg["paper_k3"],
        )
        all_results[model_key] = result

    # ── Combined summary table ───────────────────────────────────────────────
    print("\n\n=== Combined MuSiQue K-Sweep (all models) ===")
    models_order = list(MODELS.keys())

    for protocol in PROTOCOLS:
        label = protocol.replace("_relay", "").replace("_", " ").title()
        print(f"\n{label}:")
        header = f"  {'Model':<12}" + "".join(f"  k={k} Acc%" for k in K_VALUES)
        print(header)
        for model_key in models_order:
            row = f"  {model_key:<12}"
            for k in K_VALUES:
                val = all_results.get(model_key, {}).get(protocol, {}).get(k)
                row += f"  {val['acc_pct']:>7.1f} " if val else f"  {'---':>7} "
            print(row)

        # Gap row (Score-Ranked minus Random)
    print("\nGap (Score-Ranked − Random) at each k:")
    header = f"  {'Model':<12}" + "".join(f"  Δk={k}    " for k in K_VALUES)
    print(header)
    for model_key in models_order:
        row = f"  {model_key:<12}"
        for k in K_VALUES:
            sr = all_results.get(model_key, {}).get("score_ranked_relay", {}).get(k)
            rr = all_results.get(model_key, {}).get("random_relay", {}).get(k)
            if sr and rr:
                gap = sr["acc_pct"] - rr["acc_pct"]
                row += f"  {gap:>+7.1f}  "
            else:
                row += f"  {'---':>7}  "
        print(row)

    # Save
    out_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {OUTPUT_DIR}/results.json")


if __name__ == "__main__":
    main()
