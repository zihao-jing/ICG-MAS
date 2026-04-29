"""
src.eval — ICG experiment evaluation for MuSiQue.

Modules:
    data_loader    — load MuSiQue JSONL, compute ICG, stratify instances
    variant_a      — distributed multi-agent majority-vote (settings A1 & A2)
    variant_b      — centralized single-agent baseline
    evaluate       — Answer F1, normalization, per-stratum aggregation, correlation
    run_experiment — CLI entry point
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
