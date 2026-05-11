"""
ablation_study.py -- Main ablation study runner for Table 2.

This runner is separate from run_experiment.py (Table 1).  It defaults to the
same Silo-Bench slice used in the current main runs: n_agents=5, non-segmented
tasks, OpenRouter deepseek/deepseek-v4-flash.

Usage:
  python -m src.eval.ablation_study [OPTIONS]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime
from typing import Callable

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.eval.evaluate import majority_vote
from src.eval.metrics import compute_recovery
from src.eval.silo_bench_loader import load_silobench, shards_from_silobench, silobench_exact_match
from src.protocols.base import ProtocolResult
from src.protocols.full_sharing import run_full_sharing_batch
from src.protocols.local import compute_local_answers_batch
from src.protocols.relay import (
    _aggregate_evidence_board_batch,
    _redundancy_select,
    _topk_select,
    extract_states_batch,
    score_states_batch,
)
from src.protocols.summary_exchange import run_summary_exchange_batch


_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openrouter": "deepseek/deepseek-v4-flash",
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
}

ABLATION_ROWS: dict[str, str] = {
    "csc_redundancy": "CSC + redundancy penalty (full)",
    "csc_topk": "CSC top-k only",
    "summary_exchange": "No atomic extraction (send summary)",
    "random_relay": "No necessity scoring (random states)",
    "relevance_only": "Relevance only (s_rel only)",
    "criticality_only": "Criticality only (s_crit only)",
    "no_uniqueness": "No uniqueness score",
    "no_evidence_board": "No evidence board (agents answer directly)",
    "local_scoring_fails": "Failure analysis: local scoring fails",
}

_DISPLAY_ORDER = [
    "csc_redundancy",
    "csc_topk",
    "summary_exchange",
    "random_relay",
    "relevance_only",
    "criticality_only",
    "no_uniqueness",
    "no_evidence_board",
    "local_scoring_fails",
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


def _agent_coverage(selected: list[list[str]]) -> float:
    """Silo-Bench CSCOV proxy: fraction of agent shards represented."""
    if not selected:
        return 1.0
    covered = sum(1 for agent_states in selected if any(s.strip() for s in agent_states))
    return covered / len(selected)


def _component_scores(
    scores_list: list[list[list[dict]]],
    variant: str,
) -> list[list[list[dict]]]:
    """Return scores with composite replaced by the requested ablation score."""
    out: list[list[list[dict]]] = []
    for inst_scores in scores_list:
        inst_out: list[list[dict]] = []
        for agent_scores in inst_scores:
            agent_out: list[dict] = []
            for score in agent_scores:
                rel = float(score.get("relevance", 0.0))
                uniq = float(score.get("uniqueness", 0.0))
                crit = float(score.get("criticality", 0.0))
                new_score = dict(score)
                if variant == "relevance_only":
                    new_score["composite"] = rel
                elif variant == "criticality_only":
                    new_score["composite"] = crit
                elif variant == "no_uniqueness":
                    new_score["composite"] = (rel + crit) / 2.0
                else:
                    raise ValueError(f"Unknown score ablation: {variant}")
                agent_out.append(new_score)
            inst_out.append(agent_out)
        out.append(inst_out)
    return out


def _select_states(
    all_states: list[list[list[str]]],
    all_scores: list[list[list[dict]]],
    variant: str,
    max_states_per_agent: int,
    seed: int,
    rho: float,
) -> list[list[list[str]]]:
    selected_list: list[list[list[str]]] = []
    rng = random.Random(seed)

    for inst_states, inst_scores in zip(all_states, all_scores):
        selected_inst: list[list[str]] = []
        for agent_states, agent_scores in zip(inst_states, inst_scores):
            if variant == "random_relay":
                selected = (
                    rng.sample(agent_states, min(max_states_per_agent, len(agent_states)))
                    if agent_states
                    else []
                )
            elif variant == "csc_redundancy":
                selected = _redundancy_select(agent_states, agent_scores, max_states_per_agent, rho)
            else:
                selected = _topk_select(agent_states, agent_scores, max_states_per_agent)
            selected_inst.append(selected)
        selected_list.append(selected_inst)

    return selected_list


def _run_selected_variant(
    instances: list[dict],
    selected_list: list[list[list[str]]],
    batch_fn: Callable,
    model: str,
    max_tokens: int,
    max_workers: int,
    precompute_tokens: list[int],
) -> list[dict]:
    """Aggregate selected evidence boards and return per-instance dicts."""
    agg_out = _aggregate_evidence_board_batch(
        instances,
        selected_list,
        batch_fn=batch_fn,
        model=model,
        max_tokens=max_tokens,
        max_workers=max_workers,
    )

    rows: list[dict] = []
    for instance, selected, pre_tok, (pred, _f1, comm_tokens, agg_tok) in zip(
        instances, selected_list, precompute_tokens, agg_out
    ):
        transmitted = [state for agent_states in selected for state in agent_states]
        rows.append(
            {
                "id": instance["id"],
                "pred": pred,
                "f1": silobench_exact_match(pred, instance),
                "comm_tokens": comm_tokens,
                "total_llm_tokens": pre_tok + agg_tok,
                "cscov": _agent_coverage(selected),
                "transmitted_states": transmitted,
            }
        )
    return rows


def _protocol_results_to_rows(
    results: list[ProtocolResult],
    instances: list[dict],
    cscov_mode: str,
) -> list[dict]:
    rows: list[dict] = []
    for result, instance in zip(results, instances):
        if cscov_mode == "summary":
            cscov = sum(1 for s in result.transmitted_states if s.strip()) / max(
                int(instance.get("n_agents", 0)) or len(instance.get("agent_configs", [])),
                1,
            )
        elif cscov_mode == "none":
            cscov = 0.0
        else:
            cscov = 1.0
        rows.append(
            {
                "id": result.instance_id,
                "pred": result.pred,
                "f1": silobench_exact_match(result.pred, instance),
                "comm_tokens": result.comm_tokens,
                "total_llm_tokens": result.total_llm_tokens,
                "cscov": cscov,
                "transmitted_states": result.transmitted_states,
            }
        )
    return rows


def _local_direct_rows(
    instances: list[dict],
    local_answers_list: list[list[str]],
    local_tokens_list: list[list[int]],
) -> list[dict]:
    rows: list[dict] = []
    for instance, answers, tokens in zip(instances, local_answers_list, local_tokens_list):
        nonempty = [a for a in answers if a.strip()]
        pred = majority_vote(nonempty) if nonempty else ""
        rows.append(
            {
                "id": instance["id"],
                "pred": pred,
                "f1": silobench_exact_match(pred, instance),
                "comm_tokens": 0,
                "total_llm_tokens": sum(tokens),
                "cscov": 0.0,
                "transmitted_states": [],
            }
        )
    return rows


def _aggregate_rows(
    rows: list[dict],
    acc_local: float,
    acc_full: float,
) -> dict:
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "acc": 0.0,
            "mean_comm_tokens": 0.0,
            "cscov": 0.0,
            "recovery": 0.0,
        }
    acc = sum(r["f1"] for r in rows) / n
    return {
        "n": n,
        "acc": acc,
        "mean_comm_tokens": sum(r["comm_tokens"] for r in rows) / n,
        "mean_total_llm_tokens": sum(r.get("total_llm_tokens", 0) for r in rows) / n,
        "cscov": sum(r.get("cscov", 0.0) for r in rows) / n,
        "recovery": compute_recovery(acc, acc_local, acc_full),
    }


def run_ablation_study(args: argparse.Namespace) -> dict:
    """Execute Table 2 ablation study and return serialisable results."""
    print(f"Loading Silo-Bench from: {args.data or '(default benchmarks dir)'}")
    instances = load_silobench(args.data, n_agents_filter=args.n_agents)
    if args.limit > 0:
        instances = instances[: args.limit]
        print(f"Limited to {len(instances)} instances (--limit {args.limit})")
    else:
        print(f"Loaded {len(instances)} instances")
    if not instances:
        raise ValueError("No Silo-Bench instances loaded -- check --data and --n-agents.")

    shards_list = [shards_from_silobench(instance) for instance in instances]
    batch_fn = _get_batch_fn(args.provider)

    print("\n[Precompute] Local direct answers for recovery and no-board ablation ...")
    local_answers_list, local_tokens_list = compute_local_answers_batch(
        instances,
        shards_list,
        batch_fn=batch_fn,
        model=args.model,
        max_tokens=args.max_tokens,
        max_workers=args.max_workers,
    )

    rng = random.Random(args.seed)
    single_local_rows = []
    for instance, answers, tokens in zip(instances, local_answers_list, local_tokens_list):
        idx = rng.randint(0, max(len(answers) - 1, 0))
        pred = answers[idx] if answers else ""
        single_local_rows.append(
            {
                "id": instance["id"],
                "pred": pred,
                "f1": silobench_exact_match(pred, instance),
                "comm_tokens": 0,
                "total_llm_tokens": tokens[idx] if idx < len(tokens) else 0,
            }
        )
    acc_local = sum(r["f1"] for r in single_local_rows) / len(single_local_rows)

    print("[Precompute] Full evidence sharing anchor for recovery ...")
    full_results = run_full_sharing_batch(
        instances,
        batch_fn=batch_fn,
        model=args.model,
        max_tokens=args.max_tokens,
        max_workers=args.max_workers,
    )
    full_rows = _protocol_results_to_rows(full_results, instances, cscov_mode="full")
    acc_full = sum(r["f1"] for r in full_rows) / len(full_rows)

    print("[Precompute] Extracting atomic states ...")
    all_states, extract_tokens = extract_states_batch(
        instances,
        shards_list,
        batch_fn=batch_fn,
        model=args.model,
        max_tokens=args.max_tokens,
        max_states_per_agent=args.max_states,
        max_workers=args.max_workers,
    )

    print("[Precompute] Scoring atomic states ...")
    all_scores, score_tokens = score_states_batch(
        instances,
        all_states,
        batch_fn=batch_fn,
        model=args.model,
        max_workers=args.max_workers,
    )
    relay_precompute_tokens = [
        extract_tokens[i] + score_tokens[i] for i in range(len(instances))
    ]
    random_precompute_tokens = extract_tokens

    instance_results: dict[str, list[dict]] = {}

    for variant in (
        "csc_redundancy",
        "csc_topk",
        "random_relay",
        "relevance_only",
        "criticality_only",
        "no_uniqueness",
    ):
        print(f"[Ablation] {ABLATION_ROWS[variant]} ...")
        scores_for_variant = (
            _component_scores(all_scores, variant)
            if variant in {"relevance_only", "criticality_only", "no_uniqueness"}
            else all_scores
        )
        selected = _select_states(
            all_states=all_states,
            all_scores=scores_for_variant,
            variant=variant,
            max_states_per_agent=args.max_states,
            seed=args.seed,
            rho=args.rho,
        )
        pre_tokens = random_precompute_tokens if variant == "random_relay" else relay_precompute_tokens
        instance_results[variant] = _run_selected_variant(
            instances,
            selected,
            batch_fn=batch_fn,
            model=args.model,
            max_tokens=args.max_tokens,
            max_workers=args.max_workers,
            precompute_tokens=pre_tokens,
        )

    print("[Ablation] No atomic extraction (send summary) ...")
    summary_results = run_summary_exchange_batch(
        instances,
        shards_list,
        batch_fn=batch_fn,
        model=args.model,
        max_tokens=args.max_tokens,
        max_workers=args.max_workers,
    )
    instance_results["summary_exchange"] = _protocol_results_to_rows(
        summary_results,
        instances,
        cscov_mode="summary",
    )

    print("[Ablation] No evidence board (agents answer directly) ...")
    instance_results["no_evidence_board"] = _local_direct_rows(
        instances,
        local_answers_list,
        local_tokens_list,
    )

    failure_rows = [
        row
        for row, full_row in zip(instance_results["csc_redundancy"], full_rows)
        if full_row["f1"] > 0 and row["f1"] <= 0
    ]
    instance_results["local_scoring_fails"] = failure_rows

    table = {
        name: _aggregate_rows(rows, acc_local=acc_local, acc_full=acc_full)
        for name, rows in instance_results.items()
    }

    return {
        "args": vars(args),
        "n_instances": len(instances),
        "anchors": {
            "single_local_acc": acc_local,
            "full_sharing_acc": acc_full,
        },
        "table": table,
        "instance_results": instance_results,
    }


def print_ablation_table(table: dict[str, dict]) -> None:
    """Print Table 2-style rows to stdout."""
    col_w = [42, 12, 12, 8, 10]
    header = (
        f"{'Variant':<{col_w[0]}} "
        f"{'Acc (%)':>{col_w[1]}} "
        f"{'Tokens':>{col_w[2]}} "
        f"{'CSCOV':>{col_w[3]}} "
        f"{'Recovery':>{col_w[4]}}"
    )
    print(header)
    print("-" * len(header))
    for name in _DISPLAY_ORDER:
        if name not in table:
            continue
        row = table[name]
        print(
            f"{ABLATION_ROWS[name]:<{col_w[0]}} "
            f"{row['acc'] * 100:>{col_w[1]}.2f} "
            f"{row['mean_comm_tokens']:>{col_w[2]}.1f} "
            f"{row['cscov']:>{col_w[3]}.3f} "
            f"{row['recovery']:>{col_w[4]}.3f}"
        )
    print()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ICG MAS Table 2 ablation study on Silo-Bench."
    )
    parser.add_argument("--data", default=None)
    parser.add_argument("--model", default=None, help="Model string (default: provider-specific)")
    parser.add_argument(
        "--provider",
        default="openrouter",
        choices=["openrouter", "claude", "openai"],
    )
    parser.add_argument(
        "--n-agents",
        type=int,
        default=5,
        help="Silo-Bench agent-count filter (default: 5).",
    )
    parser.add_argument("--max-states", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-workers", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rho", type=float, default=0.5)
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
        args.output = os.path.join(repo_root, "results", f"ablation_{timestamp}")
    return args


def main(argv: list[str] | None = None) -> None:
    import time

    args = _parse_args(argv)
    t_start = time.time()
    output = run_ablation_study(args)
    elapsed = time.time() - t_start
    output["elapsed_seconds"] = round(elapsed, 2)

    print(f"\nTotal running time: {elapsed:.1f}s")
    print("\n=== Table 2 Ablation Study ===")
    print_ablation_table(output["table"])

    if args.output:
        os.makedirs(args.output, exist_ok=True)
        json_path = os.path.join(args.output, "ablation_results.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2)
        print(f"Results written to: {json_path}")


if __name__ == "__main__":
    main()
