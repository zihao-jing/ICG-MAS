"""
bottleneck_analysis.py -- Critical evidence bottleneck analysis for Table 3.

This runner is intentionally separate from run_experiment.py (Table 1).  It
constructs controlled evidence-board ablations and evaluates each ablated board
with the same batched evidence-board aggregation used by the relay protocols.

By default it uses Silo-Bench for consistency with Table 1.  Silo-Bench does not
ship paragraph-level gold support labels, so each agent's private shard is
treated as one critical evidence unit.  MuSiQue remains available when
paragraph-level support/distractor annotations are desired.

Usage:
  python -m src.eval.bottleneck_analysis [OPTIONS]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.eval.data_loader import get_supporting_paragraphs, load_musique
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import (
    load_silobench,
    shards_from_silobench,
    silobench_exact_match,
)
from src.protocols.base import count_tokens_approx, format_shard_context
from src.protocols.relay import _aggregate_evidence_board_batch


_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openrouter": "deepseek/deepseek-v4-flash",
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
}


@dataclass(frozen=True)
class EvidenceUnit:
    """One board unit with enough metadata to remove it by evidence type."""

    text: str
    kind: str
    paragraph_idx: int | None = None


BOTTLENECK_ROWS: dict[str, str] = {
    "none": "None (full board)",
    "remove_1_critical": "1 critical unit removed",
    "remove_2_critical": "2 critical units removed",
    "remove_random_distractor": "Random distractor removed",
    "remove_redundant_support": "Redundant support removed",
}

_DISPLAY_ORDER = [
    "none",
    "remove_1_critical",
    "remove_2_critical",
    "remove_random_distractor",
    "remove_redundant_support",
]


def _get_batch_fn(provider: str):
    """Return a batch_request callable for the given provider."""
    if provider == "claude":
        from utility.apis import claude_api

        return claude_api.batch_request
    if provider == "openai":
        from utility.apis import openai_api

        return openai_api.batch_request
    from utility.apis import openrouter_api

    return openrouter_api.batch_request


def _format_paragraph_unit(paragraph: dict) -> str:
    title = paragraph.get("title", "Untitled")
    text = paragraph.get("paragraph_text", "")
    return f"[{title}] {text}".strip()


def _make_full_board(instance: dict, rng: random.Random) -> list[EvidenceUnit]:
    """Build a typed oracle board for bottleneck ablations.

    The full board contains every gold supporting paragraph, one sampled
    distractor when available, and one redundant copy of a support unit when
    available.  Critical-unit removals drop both the original and redundant
    copies for the removed support index, so CSCOV reflects missing support.
    """
    supporting = sorted(get_supporting_paragraphs(instance), key=lambda p: p.get("idx", 0))
    distractors = sorted(
        [p for p in instance.get("paragraphs", []) if not p.get("is_supporting")],
        key=lambda p: p.get("idx", 0),
    )

    board = [
        EvidenceUnit(
            text=_format_paragraph_unit(paragraph),
            kind="critical",
            paragraph_idx=paragraph.get("idx"),
        )
        for paragraph in supporting
    ]

    if distractors:
        distractor = rng.choice(distractors)
        board.append(
            EvidenceUnit(
                text=_format_paragraph_unit(distractor),
                kind="distractor",
                paragraph_idx=distractor.get("idx"),
            )
        )

    if supporting:
        redundant = supporting[-1]
        board.append(
            EvidenceUnit(
                text=_format_paragraph_unit(redundant),
                kind="redundant_support",
                paragraph_idx=redundant.get("idx"),
            )
        )

    return board


def _make_silobench_full_board(instance: dict) -> list[EvidenceUnit]:
    """Build one typed evidence unit per Silo-Bench agent shard."""
    board = [
        EvidenceUnit(
            text=f"Agent {shard.agent_idx} private shard:\n{format_shard_context(shard)}",
            kind="critical",
            paragraph_idx=shard.agent_idx,
        )
        for shard in shards_from_silobench(instance)
    ]
    if board:
        redundant = board[-1]
        board.append(
            EvidenceUnit(
                text=f"Redundant copy of agent {redundant.paragraph_idx} shard:\n{redundant.text}",
                kind="redundant_support",
                paragraph_idx=redundant.paragraph_idx,
            )
        )
    board.append(
        EvidenceUnit(
            text="Distractor note: This line is unrelated to the task and should not affect the answer.",
            kind="distractor",
            paragraph_idx=None,
        )
    )
    return board


def _build_ablated_units(
    instance: dict,
    variant: str,
    seed: int = 42,
    dataset: str = "silobench",
) -> list[EvidenceUnit]:
    """Return typed transmitted board units for one Table 3 variant."""
    rng = random.Random(f"{seed}:{instance.get('id', '')}")
    if dataset == "silobench":
        board = _make_silobench_full_board(instance)
    elif dataset == "musique":
        board = _make_full_board(instance, rng)
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    critical_indices = [
        unit.paragraph_idx for unit in board if unit.kind == "critical"
    ]
    critical_indices = [idx for idx in critical_indices if idx is not None]

    remove_paragraph_indices: set[int] = set()
    remove_kinds: set[str] = set()

    if variant == "none":
        pass
    elif variant == "remove_1_critical":
        remove_paragraph_indices = set(critical_indices[:1])
    elif variant == "remove_2_critical":
        remove_paragraph_indices = set(critical_indices[:2])
    elif variant == "remove_random_distractor":
        remove_kinds = {"distractor"}
    elif variant == "remove_redundant_support":
        remove_kinds = {"redundant_support"}
    else:
        raise ValueError(f"Unknown bottleneck variant: {variant}")

    ablated: list[EvidenceUnit] = []
    for unit in board:
        if unit.kind in remove_kinds:
            continue
        if unit.kind in {"critical", "redundant_support"}:
            if unit.paragraph_idx in remove_paragraph_indices:
                continue
        ablated.append(unit)
    return ablated


def build_ablated_board(
    instance: dict,
    variant: str,
    seed: int = 42,
    dataset: str = "silobench",
) -> list[str]:
    """Return transmitted board strings for one Table 3 ablation variant."""
    return [unit.text for unit in _build_ablated_units(instance, variant, seed, dataset)]


def _oracle_cscov(
    instance: dict,
    transmitted_units: list[EvidenceUnit],
    dataset: str,
) -> float:
    """Exact support-unit coverage for the controlled bottleneck board."""
    if dataset == "silobench":
        support_indices = {
            agent_config["agent_id"] for agent_config in instance["agent_configs"]
        }
    else:
        support_indices = {
            paragraph.get("idx")
            for paragraph in get_supporting_paragraphs(instance)
            if paragraph.get("idx") is not None
        }
    if not support_indices:
        return 1.0

    covered = {
        unit.paragraph_idx
        for unit in transmitted_units
        if unit.kind in {"critical", "redundant_support"}
        and unit.paragraph_idx in support_indices
    }
    return len(covered) / len(support_indices)


def _run_variant(
    instances: list[dict],
    variant: str,
    dataset: str,
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int,
    seed: int,
) -> tuple[dict, list[dict]]:
    units_list = [
        _build_ablated_units(instance, variant, seed=seed, dataset=dataset)
        for instance in instances
    ]
    selected_list = [[[unit.text for unit in units]] for units in units_list]
    agg_out = _aggregate_evidence_board_batch(
        instances,
        selected_list,
        batch_fn=batch_fn,
        model=model,
        max_tokens=max_tokens,
        max_workers=max_workers,
    )

    per_instance: list[dict] = []
    for instance, units, selected, (pred, f1, _comm_tokens, agg_tokens) in zip(
        instances, units_list, selected_list, agg_out
    ):
        eval_score = (
            silobench_exact_match(pred, instance)
            if dataset == "silobench"
            else answer_f1(pred, instance)
        )
        transmitted = selected[0]
        per_instance.append(
            {
                "id": instance["id"],
                "pred": pred,
                "f1": eval_score,
                "comm_tokens": sum(count_tokens_approx(s) for s in transmitted),
                "total_llm_tokens": agg_tokens,
                "cscov": _oracle_cscov(instance, units, dataset),
                "transmitted_states": transmitted,
            }
        )

    n = len(per_instance)
    if n == 0:
        row = {"n": 0, "acc": 0.0, "cscov": 0.0, "mean_comm_tokens": 0.0}
    else:
        row = {
            "n": n,
            "acc": sum(r["f1"] for r in per_instance) / n,
            "cscov": sum(r["cscov"] for r in per_instance) / n,
            "mean_comm_tokens": sum(r["comm_tokens"] for r in per_instance) / n,
            "mean_total_llm_tokens": sum(r["total_llm_tokens"] for r in per_instance) / n,
        }
    return row, per_instance


def run_bottleneck_analysis(args: argparse.Namespace) -> dict:
    """Execute Table 3 bottleneck analysis and return serialisable results."""
    if args.dataset == "silobench":
        print(f"Loading Silo-Bench from: {args.data or '(default benchmarks dir)'}")
        instances = load_silobench(args.data, n_agents_filter=args.n_agents)
    else:
        print(f"Loading MuSiQue from: {args.data or '(default dev split)'}")
        instances = load_musique(args.data, min_hops=args.min_hops)
    if args.limit > 0:
        instances = instances[: args.limit]
        print(f"Limited to {len(instances)} instances (--limit {args.limit})")
    else:
        print(f"Loaded {len(instances)} instances")

    if not instances:
        raise ValueError("No instances loaded -- check --data path and --min-hops.")

    batch_fn = _get_batch_fn(args.provider)
    table: dict[str, dict] = {}
    instance_results: dict[str, list[dict]] = {}

    for variant in _DISPLAY_ORDER:
        print(f"[Bottleneck] {BOTTLENECK_ROWS[variant]} ...")
        row, per_instance = _run_variant(
            instances=instances,
            variant=variant,
            dataset=args.dataset,
            batch_fn=batch_fn,
            model=args.model,
            max_tokens=args.max_tokens,
            max_workers=args.max_workers,
            seed=args.seed,
        )
        table[variant] = row
        instance_results[variant] = per_instance

    return {
        "args": vars(args),
        "n_instances": len(instances),
        "table": table,
        "instance_results": instance_results,
    }


def print_bottleneck_table(table: dict[str, dict]) -> None:
    """Print Table 3-style rows to stdout."""
    col_w = [30, 14, 8]
    header = (
        f"{'Evidence removed':<{col_w[0]}} "
        f"{'Accuracy (%)':>{col_w[1]}} "
        f"{'CSCOV':>{col_w[2]}}"
    )
    print(header)
    print("-" * len(header))
    for variant in _DISPLAY_ORDER:
        if variant not in table:
            continue
        row = table[variant]
        print(
            f"{BOTTLENECK_ROWS[variant]:<{col_w[0]}} "
            f"{row['acc'] * 100:>{col_w[1]}.2f} "
            f"{row['cscov']:>{col_w[2]}.3f}"
        )
    print()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Table 3 critical evidence bottleneck analysis."
    )
    parser.add_argument("--data", default=None)
    parser.add_argument(
        "--dataset",
        default="silobench",
        choices=["silobench", "musique"],
        help="Dataset for Table 3 (default: silobench, matching Table 1).",
    )
    parser.add_argument("--model", default=None, help="Model string (default: provider-specific)")
    parser.add_argument(
        "--provider",
        default="openrouter",
        choices=["openrouter", "claude", "openai"],
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-workers", type=int, default=128)
    parser.add_argument(
        "--n-agents",
        type=int,
        default=5,
        help="Silo-Bench agent-count filter (default: 5, matching Table 1 runs).",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-hops", type=int, default=2, help="MuSiQue-only hop filter.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--test",
        action="store_true",
        help="Quick smoke-test: limit=5 and skip file output unless --output is set.",
    )

    args = parser.parse_args(argv)
    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODELS[args.provider]
    if args.test and args.limit == 0:
        args.limit = 5
        print("=== TEST MODE: limit=5 ===")
    if args.output is None and not args.test:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        args.output = os.path.join(repo_root, "results", f"bottleneck_{timestamp}")
    return args


def main(argv: list[str] | None = None) -> None:
    import time

    args = _parse_args(argv)
    t_start = time.time()
    output = run_bottleneck_analysis(args)
    elapsed = time.time() - t_start
    output["elapsed_seconds"] = round(elapsed, 2)

    print(f"\nTotal running time: {elapsed:.1f}s")
    print("\n=== Table 3 Bottleneck Analysis ===")
    print_bottleneck_table(output["table"])

    if args.output:
        os.makedirs(args.output, exist_ok=True)
        json_path = os.path.join(args.output, "bottleneck_results.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2)
        print(f"Results written to: {json_path}")


if __name__ == "__main__":
    main()
