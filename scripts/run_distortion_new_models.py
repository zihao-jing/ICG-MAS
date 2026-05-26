#!/usr/bin/env python3
"""
Distortion audit for the 4 new models on Silo-Bench.
Completes the audit table (currently distortion is missing for Gemini-FL, 
GPT-4o-m, DeepSeek-32B, Gemma-4-31B).
Runs the same LLM judge (Qwen-235B) to classify transmitted units.
"""
from __future__ import annotations
import json, os, sys, re
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

from scripts.compute_audit_metrics import reconstruct_states_and_scores, get_transmitted_units, get_gold_units, align_gold_to_transmitted
from src.eval.silo_bench_loader import load_silobench
from utility.apis.openrouter_api import batch_request
from utility.apis.base import APIRequest

JUDGE_MODEL = "qwen/qwen3-235b-a22b-07-25"
MAX_WORKERS = 64
OUTPUT_DIR = os.path.join(_ROOT, "results", "distortion_new_models")

MODELS = {
    "geminifl": {
        "run_dirs": {
            "n5":  os.path.join(_ROOT, "results", "run_geminiflashlite_n5"),
            "n10": os.path.join(_ROOT, "results", "run_geminiflashlite_n10"),
        }
    },
    "gpt4omini": {
        "run_dirs": {
            "n5":  os.path.join(_ROOT, "results", "run_gpt4omini_n5"),
            "n10": os.path.join(_ROOT, "results", "run_gpt4omini_n10"),
        }
    },
    "deepseekr1_32b": {
        "run_dirs": {
            "n5":  os.path.join(_ROOT, "results", "run_deepseekr1_32b_n5"),
            "n10": os.path.join(_ROOT, "results", "run_deepseekr1_32b_n10"),
        }
    },
    "gemma31b": {
        "run_dirs": {
            "n5":  os.path.join(_ROOT, "results", "run_gemma31b_n5"),
            "n10": os.path.join(_ROOT, "results", "run_gemma31b_n10"),
        }
    },
}

_JUDGE_SYSTEM = (
    "You are a factual-accuracy judge for distributed multi-agent reasoning tasks.\n"
    "Given a GOLD FACT (key information from an agent's private shard) and a "
    "TRANSMITTED UNIT (an atomic evidence unit extracted and sent by the agent), "
    "classify the relationship:\n\n"
    "  EXACT      — the transmitted unit contains all key information accurately\n"
    "  PARAPHRASE — all key information preserved; minor rewording or added context only\n"
    "  PARTIAL    — at least one key piece of information is present but another is missing\n"
    "  DISTORTED  — at least one key piece of information is stated incorrectly\n"
    "  NO_MATCH   — the unit does not reference the gold information at all\n\n"
    "Output exactly one label from the five above. No explanation."
)
LABELS = {"EXACT", "PARAPHRASE", "PARTIAL", "DISTORTED", "NO_MATCH"}


def run_distortion_for_model(model_key: str, run_dirs: dict) -> dict:
    print(f"\n--- {model_key} ---")
    all_records = []

    for tier, run_dir in run_dirs.items():
        n_agents = 5 if tier == "n5" else 10
        instances = load_silobench(n_agents_filter=n_agents)
        inst_by_id = {inst["id"]: inst for inst in instances}

        resp_path = os.path.join(run_dir, "api_responses.jsonl")
        if not os.path.exists(resp_path):
            resp_path = None

        if resp_path is None:
            print(f"  {tier}: no api_responses.jsonl found in {run_dir}")
            continue

        with open(resp_path) as f:
            responses = [json.loads(l) for l in f if l.strip()]
        print(f"  {tier}: {len(responses)} API responses")

        states_by_id, scores_by_id = reconstruct_states_and_scores(responses)

        judge_requests: list[APIRequest] = []
        judge_index: list[dict] = []

        for inst_id, inst in inst_by_id.items():
            if inst_id not in states_by_id:
                continue
            gold_units = get_gold_units(inst)  # (agent_id, shard_text)

            flat_tr = get_transmitted_units(
                inst_id, "score_ranked_relay", states_by_id, scores_by_id, n_agents=n_agents
            )

            if not flat_tr:
                continue

            alignments = align_gold_to_transmitted(gold_units, flat_tr)

            for (agent_id, gold_text), aln in zip(gold_units, alignments):
                best_unit = aln.get("best_unit") if isinstance(aln, dict) else None
                score = aln.get("score", 0.0) if isinstance(aln, dict) else (aln if isinstance(aln, float) else 0.0)

                base_rec = {
                    "tier": tier,
                    "inst_id": inst_id,
                    "model_key": model_key,
                    "agent_id": agent_id,
                    "score": score,
                    "best_unit": best_unit,
                }

                if score < 0.05 or best_unit is None:
                    all_records.append({**base_rec, "label": "NO_MATCH", "from_judge": False})
                    continue

                prompt = (
                    f"GOLD FACT:\n{gold_text[:400]}\n\n"
                    f"TRANSMITTED UNIT:\n{best_unit[:400]}\n\n"
                    "Classification:"
                )
                judge_requests.append(APIRequest(
                    system_query=_JUDGE_SYSTEM,
                    user_query=prompt,
                    model=JUDGE_MODEL,
                    max_tokens=8,
                    temperature=0.0,
                    metadata={
                        "tier": tier, "inst_id": inst_id,
                        "model_key": model_key, "agent_id": agent_id,
                    },
                ))
                judge_index.append({**base_rec, "label": None, "from_judge": True})

        print(f"  {tier}: {len(judge_requests)} judge requests (+{len(all_records)} no-match)")

        if judge_requests:
            resps = batch_request(judge_requests, max_workers=MAX_WORKERS,
                                  desc=f"dist_{model_key}_{tier}")
            for resp, rec in zip(resps, judge_index):
                if resp.success:
                    raw = resp.content.strip().upper()
                    label = "NO_MATCH"
                    for lbl in LABELS:
                        if lbl in raw:
                            label = lbl
                            break
                    rec["label"] = label
                else:
                    rec["label"] = "NO_MATCH"
            all_records.extend(judge_index)

    # Aggregate
    n_total = len(all_records)
    covered = [r for r in all_records if r["label"] != "NO_MATCH"]
    n_covered = len(covered)
    label_counts = defaultdict(int)
    for r in all_records:
        label_counts[r["label"]] += 1

    if n_covered == 0:
        result = {"n_total": n_total, "n_covered": 0, "coverage_rate": 0.0,
                  "distortion_strict": 0.0, "distortion_broad": 0.0,
                  "exact_paraphrase_rate": 0.0, "label_counts": dict(label_counts)}
    else:
        strict = sum(1 for r in covered if r["label"] == "DISTORTED")
        broad = sum(1 for r in covered if r["label"] in {"DISTORTED", "PARTIAL"})
        ep = sum(1 for r in covered if r["label"] in {"EXACT", "PARAPHRASE"})
        result = {
            "n_total": n_total, "n_covered": n_covered,
            "coverage_rate": n_covered / n_total,
            "distortion_strict": strict / n_covered,
            "distortion_broad": broad / n_covered,
            "exact_paraphrase_rate": ep / n_covered,
            "label_counts": dict(label_counts),
        }

    print(f"  Coverage: {result['coverage_rate']*100:.1f}%  "
          f"Strict: {result['distortion_strict']*100:.1f}%  "
          f"Exact+Para: {result['exact_paraphrase_rate']*100:.1f}%")
    return {**result, "records": all_records}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_results = {}
    for model_key, cfg in MODELS.items():
        all_results[model_key] = run_distortion_for_model(model_key, cfg["run_dirs"])

    out_path = os.path.join(OUTPUT_DIR, "distortion_results.json")
    with open(out_path, "w") as f:
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != "records"}
                   for k, v in all_results.items()}, f, indent=2)
    print(f"\nSaved to {out_path}")

    print("\n=== Distortion Summary (Score-Ranked Relay) ===")
    print(f"{'Model':<18} {'N':>5} {'Cov%':>6} {'Strict%':>8} {'Broad%':>8} {'Exact+Para%':>12}")
    for mk, res in all_results.items():
        print(f"{mk:<18} {res['n_total']:>5} {res['coverage_rate']*100:>5.1f}% "
              f"{res['distortion_strict']*100:>7.1f}% {res['distortion_broad']*100:>7.1f}% "
              f"{res['exact_paraphrase_rate']*100:>11.1f}%")


if __name__ == "__main__":
    main()
