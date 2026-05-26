"""
src.eval — Evaluation utilities for the evidence-flow audit experiment.

Modules:
    data_loader    — load MuSiQue JSONL, stratify instances
    silo_bench_loader — load Silo-Bench instances
    evaluate       — Answer F1, normalization, per-stratum aggregation
    metrics        — Protocol-level accuracy, token cost, evidence coverage
    run_experiment — CLI entry point for protocol comparison
"""

from .data_loader import load_musique, compute_icg, stratify_by_icg
from .evaluate import normalize, token_f1, answer_f1, majority_vote

__all__ = [
    "load_musique",
    "compute_icg",
    "stratify_by_icg",
    "normalize",
    "token_f1",
    "answer_f1",
    "majority_vote",
]
