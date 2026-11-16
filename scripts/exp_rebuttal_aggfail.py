#!/usr/bin/env python3
"""
Exp 3 — AggFail Sub-categorization.

Samples AggFail instances (CritRec=1 but wrong answer) from MuSiQue
full_sharing results and classifies each into:
  - ReasFail:   multi-hop reasoning chain broken
  - FormatFail: correct value present in rationale but wrong answer format
  - PartialFail: one evidence piece used, another ignored

Usage:
    python scripts/exp_rebuttal_aggfail.py
    python scripts/exp_rebuttal_aggfail.py --mq-run results/run_qwen235b_musique \
                                            --n-sample 80
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import random
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utility.apis.base import APIRequest
from src.eval.run_experiment import _get_batch_fn, _PROVIDER_DEFAULT_MODELS
from src.eval.data_loader import load_musique
from src.eval.silo_bench_loader import load_silobench
from src.protocols.full_sharing import run_full_sharing_batch


_JUDGE_SYSTEM = """\
You are a failure-mode analyst for a question-answering system.

A model was given ALL required evidence but still answered incorrectly.
Classify the failure into exactly ONE of these categories:

REAS_FAIL   — The evidence was present but the model failed to chain the
              multi-hop reasoning correctly (missed an inference step,
              drew a wrong conclusion, or confused entities).

FORMAT_FAIL — The correct answer value appears in the model's rationale or
              working but the final ANSWER field is wrong (wrong format,
              truncated, off-by-one, or normalisation error).

PARTIAL_FAIL — The model used some evidence units but ignored at least one
               critical piece, leading to a partially-informed wrong answer.

Return JSON only:
{"category": "REAS_FAIL|FORMAT_FAIL|PARTIAL_FAIL", "confidence": 0.0-1.0,
 "reason": "one sentence explanation"}
"""


def _judge_prompt(question: str, evidence_board: list[str],
                   pred: str, gold: str, rationale: str) -> str:
    board_str = "\n".join(f"  {i+1}. {u}" for i, u in enumerate(evidence_board))
    return (
        f"Question: {question}\n\n"
        f"Evidence board (all required evidence was present):\n{board_str}\n\n"
        f"Gold answer: {gold}\n"
        f"Model prediction: {pred}\n"
        f"Model rationale: {rationale}\n\n"
        "Classify the failure mode."
    )


def _extract_rationale(raw_pred: str) -> str:
    """Pull RATIONALE line from model output if present."""
    for line in raw_pred.split("\n"):
        if line.upper().startswith("RATIONALE:"):
            return line.split(":", 1)[-1].strip()
    return ""


def load_aggfail_instances(mq_run_dir: str, audit_path: str | None,
                            n_sample: int, seed: int) -> list[dict]:
    """Load AggFail instances from full_sharing MuSiQue results."""
    with open(os.path.join(mq_run_dir, "results.json")) as f:
        run_results = json.load(f)

    # Load per-instance results for full_sharing
    fs_results = {r["id"]: r
                  for r in run_results["instance_results"].get("full_sharing", [])}

    # Load audit metrics to find instances with CritRec=1
    aggfail_ids: set[str] = set()

    audit_file = audit_path or os.path.join(mq_run_dir, "audit_metrics.json")
    if os.path.exists(audit_file):
        with open(audit_file) as f:
            audit = json.load(f)
        # Use score_ranked_relay audit as proxy: instances where crit_recall=1 and wrong
        for proto in ("score_ranked_relay", "random_relay"):
            for rec in audit.get("audit_records", {}).get(proto, []):
                if rec.get("crit_recall", 0) >= 1.0 and not rec.get("correct", True):
                    aggfail_ids.add(rec["inst_id"])
    else:
        # Fallback: use full_sharing wrong answers (CritRec=1 by definition for full sharing)
        for inst_id, r in fs_results.items():
            if not r.get("correct", True):
                aggfail_ids.add(inst_id)

    print(f"Found {len(aggfail_ids)} AggFail candidate instances")

    # Load MuSiQue to get evidence boards
    run_ids = set(fs_results.keys())
    all_mq = load_musique()
    instances_by_id = {inst["id"]: inst for inst in all_mq if inst["id"] in run_ids}

    # Build records for AggFail instances
    candidates = []
    for inst_id in aggfail_ids:
        inst = instances_by_id.get(inst_id)
        result = fs_results.get(inst_id)
        if inst is None or result is None:
            continue
        supporting = [p["paragraph_text"] for p in inst["paragraphs"] if p["is_supporting"]]
        # full_sharing evidence board = all paragraphs
        all_paras = [p["paragraph_text"] for p in inst["paragraphs"]]
        candidates.append({
            "id": inst_id,
            "question": inst["question"],
            "gold": str(inst.get("answer", "")),
            "pred": result.get("pred", ""),
            "f1": result.get("f1", 0.0),
            "evidence_board": supporting,      # gold supporting paragraphs
            "full_board": all_paras[:10],      # full board (truncated for prompt)
            "raw_pred": result.get("pred", ""),  # may contain RATIONALE if structured output
        })

    rng = random.Random(seed)
    if len(candidates) > n_sample:
        candidates = rng.sample(candidates, n_sample)
    print(f"Sampled {len(candidates)} instances for classification")
    return candidates


def classify_aggfail(
    candidates: list[dict],
    batch_fn,
    model: str,
    max_workers: int = 32,
) -> list[dict]:
    """Run LLM judge to classify each AggFail instance."""
    requests = []
    for c in candidates:
        rationale = _extract_rationale(c.get("raw_pred", ""))
        requests.append(APIRequest(
            system_query=_JUDGE_SYSTEM,
            user_query=_judge_prompt(
                c["question"],
                c["evidence_board"],
                c["pred"],
                c["gold"],
                rationale,
            ),
            model=model,
            max_tokens=200,
            temperature=0.0,
            metadata={"instance_id": c["id"], "phase": "aggfail_judge"},
        ))

    print(f"Submitting {len(requests)} judge requests...")
    responses = batch_fn(requests, max_workers=max_workers)

    results = []
    for cand, resp in zip(candidates, responses):
        category = "UNKNOWN"
        confidence = 0.0
        reason = ""
        if resp.success and resp.content.strip():
            try:
                import re
                # Strip <think>...</think> blocks (Qwen3 chain-of-thought tags)
                content = re.sub(r"<think>.*?</think>", "", resp.content, flags=re.DOTALL).strip()
                # Match the last (outermost) JSON object
                m = re.search(r"\{[^{}]*\}", content, re.DOTALL)
                if not m:
                    m = re.search(r"\{.*\}", content, re.DOTALL)
                if m:
                    d = json.loads(m.group())
                    cat = d.get("category", "UNKNOWN").upper()
                    if cat in ("REAS_FAIL", "FORMAT_FAIL", "PARTIAL_FAIL"):
                        category = cat
                    confidence = float(d.get("confidence", 0.5))
                    reason = d.get("reason", "")
            except Exception:
                pass
        results.append({**cand, "category": category, "confidence": confidence, "reason": reason})
    return results


def print_results(results: list[dict]) -> None:
    counts = Counter(r["category"] for r in results)
    n = len(results)
    print(f"\n=== AggFail Sub-categorization (n={n}) ===\n")
    print(f"{'Category':<14}  {'Count':>6}  {'%':>7}  Description")
    print("-" * 65)
    descs = {
        "REAS_FAIL":    "Multi-hop reasoning chain broken",
        "FORMAT_FAIL":  "Correct value in rationale, wrong answer format",
        "PARTIAL_FAIL": "Some evidence used, critical piece ignored",
        "UNKNOWN":      "Could not classify",
    }
    for cat in ["REAS_FAIL", "FORMAT_FAIL", "PARTIAL_FAIL", "UNKNOWN"]:
        c = counts.get(cat, 0)
        pct = 100.0 * c / n if n else 0.0
        print(f"  {cat:<12}  {c:>6}  {pct:>6.1f}%  {descs[cat]}")

    print(f"\n  Total: {n}")
    dominant = counts.most_common(1)[0] if counts else ("UNKNOWN", 0)
    print(f"\nDominant failure: {dominant[0]} ({100*dominant[1]/n:.1f}%)")

    print("\n--- Sample instances per category ---")
    shown = set()
    for cat in ["REAS_FAIL", "FORMAT_FAIL", "PARTIAL_FAIL"]:
        cat_examples = [r for r in results if r["category"] == cat][:2]
        for ex in cat_examples:
            if ex["id"] in shown:
                continue
            shown.add(ex["id"])
            print(f"\n[{cat}] Q: {ex['question'][:70]}")
            print(f"  Gold: {ex['gold']}  |  Pred: {ex['pred'][:40]}")
            print(f"  Reason: {ex['reason'][:100]}")

    # Markdown table for rebuttal
    print("\n### Table R-aggfail (for rebuttal)\n")
    print("| Category | Count | % | Interpretation |")
    print("|---|---|---|---|")
    for cat in ["REAS_FAIL", "FORMAT_FAIL", "PARTIAL_FAIL"]:
        c = counts.get(cat, 0)
        pct = 100.0 * c / n if n else 0.0
        print(f"| {cat} | {c} | {pct:.1f}% | {descs[cat]} |")


def main():
    parser = argparse.ArgumentParser(description="AggFail sub-categorization experiment.")
    parser.add_argument("--mq-run", default="results/run_qwen235b_musique")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default="openrouter",
                        choices=["openrouter", "claude", "openai"])
    parser.add_argument("--n-sample", type=int, default=80,
                        help="Number of AggFail instances to classify (default: 80)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-workers", type=int, default=32)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODELS[args.provider]

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mq_run = os.path.join(repo_root, args.mq_run)

    candidates = load_aggfail_instances(mq_run, None, args.n_sample, args.seed)
    if not candidates:
        print("No AggFail instances found. Check run directory.")
        sys.exit(1)

    batch_fn = _get_batch_fn(args.provider)
    results = classify_aggfail(candidates, batch_fn, args.model, args.max_workers)
    print_results(results)

    out_path = args.output
    if out_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(repo_root, "rebuttal", "results",
                                f"exp3_aggfail_{ts}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"model": args.model, "n": len(results),
                   "results": results}, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
