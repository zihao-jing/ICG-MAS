"""
Combine n=5 and n=10 Silo-Bench per-instance results into a single table.

Usage:
  python scripts/combine_silobench_results.py \
    --n5-dirs  results/run_n5_model1 results/run_n5_model2 ... \
    --n10-dirs results/run_n10_model1 results/run_n10_model2 ... \
    --model-names "Model1" "Model2" ... \
    --output results/combined_table1.txt
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

PROTOCOLS = [
    "single_local",
    "majority_vote",
    "best_local",
    "free_form_debate",
    "summary_exchange",
    "confidence_gated",
    "disagreement_gated",
    "random_relay",
    "score_ranked_relay",
    "redundancy_aware_relay",
    "full_sharing",
]

PROTOCOL_LABELS = {
    "single_local":           "Single Local",
    "majority_vote":          "Majority Vote",
    "best_local":             "Best-Local Oracle",
    "free_form_debate":       "Free-form Debate",
    "summary_exchange":       "Summary Exchange",
    "confidence_gated":       "Confidence-Gated",
    "disagreement_gated":     "Disagreement-Gated",
    "random_relay":           "Random Evidence Relay",
    "score_ranked_relay":     "Score-Ranked Relay",
    "redundancy_aware_relay": "Redundancy-Aware Relay",
    "full_sharing":           "Full Evidence Sharing",
}


def load_per_instance(run_dir: str) -> dict[str, list[dict]]:
    path = os.path.join(run_dir, "per_instance_results.jsonl")
    if not os.path.exists(path):
        return {}
    by_protocol: dict[str, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            proto = row["protocol"]
            by_protocol[proto].append(row)
    return dict(by_protocol)


def combine_results(n5_dir: str, n10_dir: str) -> dict[str, dict]:
    """Combine two run directories. Returns {protocol: {acc, tok, rec}}."""
    r5 = load_per_instance(n5_dir)
    r10 = load_per_instance(n10_dir)

    combined: dict[str, dict] = {}
    all_protocols = set(r5) | set(r10)
    for proto in all_protocols:
        rows = r5.get(proto, []) + r10.get(proto, [])
        if not rows:
            continue
        n_correct = sum(1 for r in rows if r.get("correct", False))
        acc = 100.0 * n_correct / len(rows)
        tok = sum(r.get("comm_tokens", 0) for r in rows) / len(rows)
        combined[proto] = {"acc": acc, "tok": tok, "n": len(rows)}

    # Compute recovery relative to this model's own single_local and full_sharing
    single_acc = combined.get("single_local", {}).get("acc", 0.0)
    full_acc = combined.get("full_sharing", {}).get("acc", 0.0)
    denom = full_acc - single_acc
    for proto, stats in combined.items():
        if denom > 0:
            rec = (stats["acc"] - single_acc) / denom
        else:
            rec = 0.0
        stats["rec"] = rec

    return combined


def fmt(val: float | None, fmt_str: str = ".2f") -> str:
    if val is None:
        return "---"
    return format(val, fmt_str)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n5-dirs", nargs="+", required=True)
    parser.add_argument("--n10-dirs", nargs="+", required=True)
    parser.add_argument("--model-names", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    assert len(args.n5_dirs) == len(args.n10_dirs) == len(args.model_names), \
        "n5-dirs, n10-dirs, and model-names must have the same length"

    # Load combined results per model
    model_results: list[dict[str, dict]] = []
    for n5_dir, n10_dir, name in zip(args.n5_dirs, args.n10_dirs, args.model_names):
        print(f"Loading {name}: {n5_dir} + {n10_dir}")
        combined = combine_results(n5_dir, n10_dir)
        model_results.append(combined)
        if not combined:
            print(f"  WARNING: no results found")

    # Print table
    header_models = "  ".join(
        f"{'Acc':>6} {'Tok':>5} {'Rec':>5}" for _ in args.model_names
    )
    model_header_row = "  ".join(f"{n:>18}" for n in args.model_names)

    lines = [
        f"Combined Silo-Bench (n=5 + n=10, {sum(len(r.get('single_local',[])) for r in [load_per_instance(d) for d in args.n5_dirs + args.n10_dirs])} total instances)",
        "",
        f"{'Protocol':<30}  " + "  ".join(
            f"{'--- ' + n + ' ---':>18}" for n in args.model_names
        ),
        f"{'':30}  " + header_models,
    ]

    for proto in PROTOCOLS:
        label = PROTOCOL_LABELS.get(proto, proto)
        cells = []
        for mr in model_results:
            s = mr.get(proto)
            if s:
                cells.append(f"{s['acc']:6.1f} {s['tok']:5.0f} {s['rec']:+5.2f}")
            else:
                cells.append(f"{'---':>6} {'---':>5} {'---':>5}")
        lines.append(f"{'  ' + label:<30}  " + "  ".join(cells))

    output = "\n".join(lines)
    print(output)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(output + "\n")
    print(f"\nWritten to {args.output}")


if __name__ == "__main__":
    main()
