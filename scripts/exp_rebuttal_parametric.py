#!/usr/bin/env python3
"""
Exp 2 — Parametric Knowledge Recovery.

Tests whether models can answer correctly with an empty evidence board
(zero transmitted evidence).  If accuracy is near-zero, the model cannot
recover from parametric knowledge, refuting fcWx W5.

SB result (n=26): already 0.0 from existing ablation data.
This script runs the MuSiQue condition (~100 API calls).

Usage:
    python scripts/exp_rebuttal_parametric.py
    python scripts/exp_rebuttal_parametric.py --dataset silobench
    python scripts/exp_rebuttal_parametric.py --dataset musique --limit 100
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utility.apis.base import APIRequest
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import load_silobench, shards_from_silobench, silobench_exact_match
from src.eval.data_loader import load_musique_sample, load_musique
from src.eval.run_experiment import _get_batch_fn, _PROVIDER_DEFAULT_MODELS
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from src.protocols.base import extract_answer


_EMPTY_BOARD_NOTE = (
    "No evidence units were transmitted — all agents withheld their private shards."
)


def run_no_evidence(
    instances: list[dict],
    batch_fn,
    model: str,
    max_tokens: int,
    eval_fn,
    max_workers: int = 64,
) -> list[dict]:
    """Run aggregator with completely empty evidence board for each instance."""
    requests = [
        APIRequest(
            system_query=_AGGREGATION_SYSTEM,
            user_query=(
                "The following evidence units were transmitted from private shards.\n"
                "Use only these units to answer the question.\n\n"
                f"(No evidence transmitted)\n\n"
                f"Question: {inst['question']}\n\nAnswer:"
            ),
            model=model,
            max_tokens=max_tokens,
            metadata={"instance_id": inst["id"], "phase": "no_evidence_aggregation"},
        )
        for inst in instances
    ]

    responses = batch_fn(requests, max_workers=max_workers)

    results = []
    for inst, resp in zip(instances, responses):
        raw = resp.content.strip() if resp.success and resp.content.strip() else ""
        pred = extract_answer(raw) if raw else ""
        f1 = eval_fn(pred, inst)
        correct = f1 >= 1.0
        results.append({
            "id": inst["id"],
            "question": inst["question"][:80],
            "pred": pred,
            "gold": str(inst.get("answer", "")),
            "f1": f1,
            "correct": correct,
            "total_tokens": resp.usage.get("total_tokens", 0),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Parametric knowledge recovery experiment.")
    parser.add_argument("--dataset", default="musique", choices=["musique", "silobench"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default="openrouter",
                        choices=["openrouter", "claude", "openai"])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--max-workers", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODELS[args.provider]

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Load data
    if args.dataset == "silobench":
        instances = load_silobench()
        eval_fn = silobench_exact_match
    else:
        if args.limit > 0:
            instances = load_musique_sample(n=args.limit, seed=args.seed)
        else:
            instances = load_musique()
        eval_fn = answer_f1

    if args.limit > 0:
        instances = instances[:args.limit]
    print(f"Loaded {len(instances)} {args.dataset} instances")

    batch_fn = _get_batch_fn(args.provider)

    print(f"Running no-evidence aggregation on {args.dataset} with {args.model}...")
    results = run_no_evidence(
        instances, batch_fn, args.model, args.max_tokens, eval_fn, args.max_workers
    )

    n = len(results)
    n_correct = sum(r["correct"] for r in results)
    acc = 100.0 * n_correct / n if n else 0.0
    mean_f1 = sum(r["f1"] for r in results) / n if n else 0.0

    print(f"\n=== Parametric Knowledge Recovery: {args.dataset.upper()} ===")
    print(f"Model:    {args.model}")
    print(f"N:        {n}")
    print(f"Accuracy: {acc:.1f}%  ({n_correct}/{n} correct)")
    print(f"Mean F1:  {mean_f1:.3f}")
    print()
    print("Sample predictions:")
    for r in results[:5]:
        mark = "✓" if r["correct"] else "✗"
        print(f"  {mark}  pred={r['pred'][:40]:<40}  gold={r['gold'][:30]}")

    # Load best-relay accuracy from existing results for comparison
    print("\n--- For comparison (from existing results) ---")
    if args.dataset == "musique":
        mq_path = os.path.join(repo_root, "results/run_qwen235b_musique/results.json")
        if os.path.exists(mq_path):
            with open(mq_path) as f:
                existing = json.load(f)
            for proto in ["score_ranked_relay", "full_sharing"]:
                if proto in existing.get("table", {}):
                    a = existing["table"][proto]["acc"] * 100
                    print(f"  {proto}: {a:.1f}%")
    else:
        sb_path = os.path.join(repo_root, "results/run_qwen235b_n5/results.json")
        if os.path.exists(sb_path):
            with open(sb_path) as f:
                existing = json.load(f)
            for proto in ["score_ranked_relay", "full_sharing"]:
                if proto in existing.get("table", {}):
                    a = existing["table"][proto]["acc"] * 100
                    print(f"  {proto}: {a:.1f}%")

    # Save
    out_path = args.output
    if out_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(repo_root, "rebuttal", "results",
                                f"exp2_parametric_{args.dataset}_{ts}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "dataset": args.dataset,
            "model": args.model,
            "n": n,
            "accuracy": acc,
            "mean_f1": mean_f1,
            "instance_results": results,
        }, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
