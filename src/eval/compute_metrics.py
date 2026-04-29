"""
compute_metrics.py — Compute ROUGE, BLEU, and BERTScore on saved experiment results.

Usage:
    python -m src.eval.compute_metrics --run results/run_20260427_234239

Reads results.json from the run directory, computes per-instance ROUGE-1,
ROUGE-2, ROUGE-L, BLEU-1/4, and BERTScore (P/R/F1) for both Variant A
(pred_a) and Variant B (pred_b), then writes metrics.json and
metrics_summary.txt alongside.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from rouge_score import rouge_scorer
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.tokenize import word_tokenize
import nltk

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

from bert_score import score as bert_score_fn

from src.eval.evaluate import normalize


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _rouge(pred: str, golds: list[str]) -> dict[str, float]:
    """Max ROUGE-1/2/L F1 over gold + aliases."""
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
    best = {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
    for gold in golds:
        scores = scorer.score(gold.lower(), pred.lower())
        for k in best:
            best[k] = max(best[k], scores[k].fmeasure)
    return best


def _bleu(pred: str, golds: list[str]) -> dict[str, float]:
    """BLEU-1 and BLEU-4, max over gold + aliases.

    Uses add-1 smoothing (method1) to handle short predictions gracefully.
    """
    smooth = SmoothingFunction().method1
    try:
        hyp = word_tokenize(pred.lower()) if pred.strip() else []
    except Exception:
        hyp = pred.lower().split()

    best1, best4 = 0.0, 0.0
    for gold in golds:
        try:
            ref = [word_tokenize(gold.lower())]
        except Exception:
            ref = [gold.lower().split()]
        if not hyp or not ref[0]:
            continue
        b1 = sentence_bleu(ref, hyp, weights=(1, 0, 0, 0), smoothing_function=smooth)
        b4 = sentence_bleu(ref, hyp, weights=(0.25, 0.25, 0.25, 0.25), smoothing_function=smooth)
        best1 = max(best1, b1)
        best4 = max(best4, b4)
    return {"bleu1": best1, "bleu4": best4}


def compute_instance_metrics(pred: str, instance: dict) -> dict[str, float]:
    """Compute all metrics for one prediction against gold + aliases."""
    golds = [instance["answer"]] + instance.get("answer_aliases", [])
    r = _rouge(pred, golds)
    b = _bleu(pred, golds)
    return {**r, **b}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def compute_bertscore_batch(preds: list[str], golds: list[str]) -> list[dict[str, float]]:
    """Compute BERTScore for a list of (pred, gold) pairs in one batch call."""
    # Use empty string fallback so the batch stays aligned
    safe_preds = [p if p.strip() else "." for p in preds]
    safe_golds = [g if g.strip() else "." for g in golds]
    P, R, F = bert_score_fn(
        safe_preds, safe_golds,
        lang="en",
        model_type="distilbert-base-uncased",
        verbose=False,
    )
    return [
        {"bert_p": float(P[i]), "bert_r": float(R[i]), "bert_f": float(F[i])}
        for i in range(len(preds))
    ]


def aggregate_metrics(scored: list[dict]) -> dict[str, float]:
    keys = ["rouge1", "rouge2", "rougeL", "bleu1", "bleu4", "bert_p", "bert_r", "bert_f", "f1"]
    return {k: mean([r[k] for r in scored if k in r]) for k in keys}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Compute ROUGE/BLEU metrics on a saved experiment run."
    )
    parser.add_argument(
        "--run", required=True,
        help="Path to run directory (must contain results.json and "
             "a MuSiQue JSONL accessible via data_loader defaults)"
    )
    parser.add_argument(
        "--data", default=None,
        help="Path to MuSiQue JSONL (defaults to dev split)"
    )
    args = parser.parse_args(argv)

    results_path = os.path.join(args.run, "results.json")
    with open(results_path, encoding="utf-8") as fh:
        data = json.load(fh)

    # Load instances for gold answers
    from src.eval.data_loader import load_musique
    instances = load_musique(args.data, min_hops=1)  # load all, no hop filter
    inst_by_id = {inst["id"]: inst for inst in instances}

    metrics_output: dict = {"settings": {}}

    for setting, res in data["settings"].items():
        label = setting.upper()
        print(f"\nComputing metrics for setting {label} ...")

        scored_a, scored_b = [], []
        preds_a, preds_b, golds = [], [], []

        for r in res["instance_results"]:
            inst = inst_by_id.get(r["id"])
            if inst is None:
                continue

            ma = compute_instance_metrics(r.get("pred_a", ""), inst)
            ma["f1"] = r["f1_a"]
            scored_a.append(ma)

            mb = compute_instance_metrics(r.get("pred_b", ""), inst)
            mb["f1"] = r["f1_b"]
            scored_b.append(mb)

            preds_a.append(r.get("pred_a", ""))
            preds_b.append(r.get("pred_b", ""))
            golds.append(inst["answer"])

        # BERTScore — batch call for efficiency
        print(f"  Computing BERTScore for {len(preds_a)} instances...")
        bs_a = compute_bertscore_batch(preds_a, golds)
        bs_b = compute_bertscore_batch(preds_b, golds)
        for i, s in enumerate(scored_a):
            s.update(bs_a[i])
        for i, s in enumerate(scored_b):
            s.update(bs_b[i])

        agg_a = aggregate_metrics(scored_a)
        agg_b = aggregate_metrics(scored_b)

        metrics_output["settings"][setting] = {
            "variant_a": agg_a,
            "variant_b": agg_b,
        }

        # Print table
        header = f"{'Metric':<12} {'F1_B':>8} {'F1_A':>8} {'Delta':>8}"
        print(header)
        print("-" * len(header))
        for k in ["f1", "rouge1", "rouge2", "rougeL", "bleu1", "bleu4", "bert_p", "bert_r", "bert_f"]:
            b_val = agg_b[k]
            a_val = agg_a[k]
            print(f"{k:<12} {b_val:>8.4f} {a_val:>8.4f} {b_val - a_val:>+8.4f}")

    # Write metrics.json
    out_json = os.path.join(args.run, "metrics.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(metrics_output, fh, indent=2)
    print(f"\nMetrics written to: {out_json}")

    # Write metrics_summary.txt
    ANNOTATION = """\
Experiment: ICG MuSiQue Evaluation — Multi-metric Summary
==========================================================
Settings:
  A1  1 paragraph per agent  (effective ICG = num_hops - 1)
      Each agent sees only one supporting paragraph. Oracle best-agent F1.

  A2  2 paragraphs per agent  (effective ICG = num_hops - 2)
      Each agent sees two supporting paragraphs. Oracle best-agent F1.

  A3  3 paragraphs per agent  (effective ICG = num_hops - 3)
      One agent holds 3 paragraphs, one holds 1. Oracle best-agent F1.

  B   Centralized baseline — single agent sees all supporting paragraphs.

Delta = F1_B - F1_Ax  (positive = centralized outperforms isolated)
Metrics:
  f1        Token-level F1 (official MuSiQue metric; bag-of-words overlap)
  rouge1/2  ROUGE unigram / bigram F1 (n-gram recall-oriented)
  rougeL    ROUGE Longest Common Subsequence F1
  bleu1/4   BLEU unigram / 4-gram precision (with smoothing)
  bert_p/r  BERTScore precision / recall (contextual embedding similarity)
  bert_f    BERTScore F1 — most informative semantic similarity metric
==========================================================

"""
    out_txt = os.path.join(args.run, "metrics_summary.txt")
    with open(out_txt, "w", encoding="utf-8") as fh:
        fh.write(ANNOTATION)
        for setting, res in metrics_output["settings"].items():
            label = setting.upper()
            fh.write(f"=== Setting {label} (effective ICG = {3 - ['a1','a2','a3'].index(setting)}) ===\n")
            header = f"{'Metric':<12} {'F1_B (Central)':>16} {'F1_A (Isolated)':>16} {'Delta (B-A)':>12}\n"
            fh.write(header)
            fh.write("-" * len(header.rstrip()) + "\n")
            for k in ["f1", "rouge1", "rouge2", "rougeL", "bleu1", "bleu4", "bert_p", "bert_r", "bert_f"]:
                b_val = res["variant_b"][k]
                a_val = res["variant_a"][k]
                fh.write(f"{k:<12} {b_val:>16.4f} {a_val:>16.4f} {b_val - a_val:>+12.4f}\n")
            fh.write("\n")
    print(f"Summary written to: {out_txt}")


if __name__ == "__main__":
    main()
