#!/usr/bin/env python3
"""
MuSiQue bottleneck deletion study — parallel variant.

Runs the critical-evidence bottleneck ablation on the same 100 MuSiQue
instances used in the main experiment, for each capable model.
Only the aggregation step uses API calls (no new extraction).

Usage:
    cd /path/to/repo
    python scripts/run_bottleneck_musique.py [--model MODEL] [--workers N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Load .env so API key is available
_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from src.eval.data_loader import load_musique
from src.eval.bottleneck_analysis import (
    run_bottleneck_analysis,
    print_bottleneck_table,
    _parse_args as _bottleneck_parse_args,
)

# ── Instance ID filter (same 100 used in main MuSiQue experiment) ──────────
_IDS_FILE = os.path.join(_ROOT, "data", "musique_100_ids.json")


def _load_100_ids() -> set[str]:
    if os.path.exists(_IDS_FILE):
        with open(_IDS_FILE) as f:
            return set(json.load(f))
    # Fallback: reconstruct from Qwen-235B run
    run_path = os.path.join(_ROOT, "results", "run_qwen235b_musique", "api_responses.jsonl")
    ids: set[str] = set()
    with open(run_path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("instance_id"):
                ids.add(r["instance_id"])
    os.makedirs(os.path.dirname(_IDS_FILE), exist_ok=True)
    with open(_IDS_FILE, "w") as f:
        json.dump(sorted(ids), f)
    print(f"[Info] Saved 100 MuSiQue IDs to {_IDS_FILE}")
    return ids


# ── Models ──────────────────────────────────────────────────────────────────

MODELS = {
    "qwen235b":    "qwen/qwen3-235b-a22b-07-25",
    "mistrals":    "mistralai/mistral-small-2603",
    "qwen80bt":    "qwen/qwen3-next-80b-a3b-thinking-2509",
    "qwen36f":     "qwen/qwen3.6-flash",
    "geminifl":    "google/gemini-2.5-flash-lite",
    "gpt4omini":   "openai/gpt-4o-mini",
    "gemma31b":    "google/gemma-4-31b-it-20260402",
}

MAX_WORKERS_PER_MODEL = 128
MAX_WORKERS_PARALLEL = 2   # Run 2 models at a time to avoid rate limits


def run_one_model(model_key: str, model_id: str, ids_100: set[str], out_root: str) -> dict:
    out_dir = os.path.join(out_root, f"bottleneck_musique_{model_key}")
    os.makedirs(out_dir, exist_ok=True)

    result_path = os.path.join(out_dir, "bottleneck_results.json")
    if os.path.exists(result_path):
        print(f"[Skip] {model_key}: results already exist at {out_dir}")
        with open(result_path) as f:
            return json.load(f)

    print(f"\n[Start] {model_key} ({model_id})")
    t0 = time.time()

    # Load and filter instances
    instances = load_musique()
    instances = [inst for inst in instances if inst["id"] in ids_100]
    print(f"[{model_key}] {len(instances)} instances")

    # Build minimal args namespace
    import argparse
    args = argparse.Namespace(
        dataset="musique",
        data=None,
        model=model_id,
        provider="openrouter",
        max_tokens=4096,
        max_workers=MAX_WORKERS_PER_MODEL,
        n_agents=5,  # not used for musique
        limit=0,
        min_hops=2,
        seed=42,
        output=out_dir,
        test=False,
    )

    # Monkey-patch instance list into bottleneck_analysis to avoid re-loading
    import src.eval.bottleneck_analysis as ba
    _orig_load_musique = ba.load_musique

    def _filtered_load(path=None, min_hops=1):
        return instances

    ba.load_musique = _filtered_load
    try:
        output = ba.run_bottleneck_analysis(args)
    finally:
        ba.load_musique = _orig_load_musique

    output["elapsed_seconds"] = round(time.time() - t0, 2)
    output["model_key"] = model_key
    output["model_id"] = model_id

    with open(result_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[Done] {model_key} in {output['elapsed_seconds']:.0f}s")
    print(f"  Output: {out_dir}")
    ba.print_bottleneck_table(output["table"])

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Run only this model key")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS_PARALLEL)
    args = parser.parse_args()

    ids_100 = _load_100_ids()
    print(f"Using {len(ids_100)} MuSiQue instances")

    out_root = os.path.join(_ROOT, "results")

    models_to_run = {k: v for k, v in MODELS.items()
                     if args.model is None or k == args.model}

    print(f"\nRunning {len(models_to_run)} models with {args.workers} parallel workers")
    print("Models:", list(models_to_run.keys()))

    all_results: dict[str, dict] = {}

    if args.workers == 1:
        for model_key, model_id in models_to_run.items():
            all_results[model_key] = run_one_model(model_key, model_id, ids_100, out_root)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(run_one_model, k, v, ids_100, out_root): k
                for k, v in models_to_run.items()
            }
            for fut in as_completed(futures):
                model_key = futures[fut]
                try:
                    all_results[model_key] = fut.result()
                except Exception as e:
                    print(f"[Error] {model_key}: {e}")

    # ── Summary table ──────────────────────────────────────────────────────
    print("\n\n=== MuSiQue Bottleneck Summary (all models) ===")
    print(f"{'Model':<14} {'k=0 (none)':>12} {'k=1 (-1crit)':>14} {'k=2 (-2crit)':>14} "
          f"{'distractor':>12} {'redundant':>12}")
    print("-" * 72)

    for model_key, res in all_results.items():
        tbl = res.get("table", {})
        none_acc   = tbl.get("none", {}).get("acc", float("nan")) * 100
        k1_acc     = tbl.get("remove_1_critical", {}).get("acc", float("nan")) * 100
        k2_acc     = tbl.get("remove_2_critical", {}).get("acc", float("nan")) * 100
        dist_acc   = tbl.get("remove_random_distractor", {}).get("acc", float("nan")) * 100
        redund_acc = tbl.get("remove_redundant_support", {}).get("acc", float("nan")) * 100
        print(f"{model_key:<14} {none_acc:>12.1f} {k1_acc:>14.1f} {k2_acc:>14.1f} "
              f"{dist_acc:>12.1f} {redund_acc:>12.1f}")

    summary_path = os.path.join(out_root, "bottleneck_musique_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
