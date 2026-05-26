"""
run_experiment.py — Protocol experiment runner for evidence-flow audit paper.

Runs all protocols on sharded benchmarks and reports accuracy, token cost,
and evidence coverage metrics.

Protocols:
  no-comm:    single_local, majority_vote, best_local
  baselines:  free_form_debate, summary_exchange, confidence_gated,
              disagreement_gated, random_relay, full_sharing
  relay:      score_ranked_relay, redundancy_aware_relay

Usage:
  python -m src.eval.run_experiment [OPTIONS]

  --data PATH           Path to benchmark JSONL (default: dev split)
  --model MODEL         Model string (default: deepseek/deepseek-v4-flash)
  --n-agents N          Agents per instance (default: 3)
  --max-states N        Max evidence units per agent (default: 3)
  --max-tokens N        Per-call output token budget (default: 1024)
  --max-workers N       API concurrency (default: 128)
  --limit N             Cap on instances (0 = no limit)
  --min-hops N          Minimum supporting paragraphs required (default: 2)
  --seed N              Random seed (default: 42)
  --protocols LIST      Comma-separated protocol names, or "all" (default: all)
  --output DIR          Results directory (default: results/run_<timestamp>/)
  --test                Quick smoke-test: limit=5, verbose output, no file I/O
  --provider {openrouter,claude,openai}
                        API provider to use (default: openrouter)
  --debate-rounds N     Rounds for free-form debate (default: 1)
  --conf-threshold F    Confidence threshold for gated comm (default: 0.6)
  --rho F               Redundancy penalty weight rho (default: 0.5)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

try:
    from tqdm import tqdm as _tqdm
    def _info(msg: str) -> None:
        _tqdm.write(msg)
except ImportError:
    _info = print

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.eval.data_loader import (
    load_musique,
    load_musique_sample,
    shards_from_musique,
)
from src.eval.silo_bench_loader import load_silobench, shards_from_silobench, silobench_exact_match
from src.eval.metrics import (
    build_results_table,
    compute_cscov,
    print_results_table,
)
from src.protocols.base import shard_instance, ProtocolResult
from src.protocols.local import compute_local_answers_batch, run_single_local, run_majority_vote_protocol, run_best_local_oracle
from src.eval.evaluate import answer_f1
from src.protocols.full_sharing import run_full_sharing_batch
from src.protocols.debate import run_debate_batch
from src.protocols.summary_exchange import run_summary_exchange_batch
from src.protocols.gated import run_confidence_gated_batch, run_disagreement_gated_batch
from src.protocols.relay import (
    extract_states_batch,
    score_states_batch,
    run_random_relay_batch,
    run_score_ranked_relay_batch,
    run_redundancy_aware_relay_batch,
)

# ---------------------------------------------------------------------------
# Available protocols
# ---------------------------------------------------------------------------

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openrouter": "qwen/qwen3-235b-a22b-2507",
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
}

ALL_PROTOCOLS = [
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

# Protocols that need local-agent answers
_NEEDS_LOCAL = {"single_local", "majority_vote", "best_local", "disagreement_gated"}
# Protocols that need extracted evidence units
_NEEDS_STATES = {"random_relay", "score_ranked_relay", "redundancy_aware_relay"}
# Protocols that need scored units
_NEEDS_SCORES = {"score_ranked_relay", "redundancy_aware_relay"}


# ---------------------------------------------------------------------------
# API provider selection
# ---------------------------------------------------------------------------

def _get_batch_fn(provider: str):
    """Return a batch_request callable for the given provider."""
    if provider == "claude":
        from utility.apis import claude_api
        return claude_api.batch_request
    elif provider == "openai":
        from utility.apis import openai_api
        return openai_api.batch_request
    else:  # default: openrouter
        from utility.apis import openrouter_api
        return openrouter_api.batch_request


# ---------------------------------------------------------------------------
# Per-instance result packaging
# ---------------------------------------------------------------------------

def _protocol_result_to_dict(
    result: ProtocolResult,
    instance: dict,
    compute_cscov_flag: bool = True,
    eval_fn=None,
) -> dict:
    """Convert a ProtocolResult to a JSON-serialisable dict.

    eval_fn overrides the f1 score stored inside ProtocolResult, which lets
    Silo-Bench (exact match) and MuSiQue (F1) use the same protocol runners.
    """
    f1 = eval_fn(result.pred, instance) if eval_fn is not None else result.f1
    d: dict = {
        "id": result.instance_id,
        "pred": result.pred,
        "gold": str(instance.get("answer", "")),
        "f1": f1,
        "correct": f1 >= 1.0,
        "comm_tokens": result.comm_tokens,
        "total_llm_tokens": result.total_llm_tokens,
    }
    if compute_cscov_flag and result.transmitted_states:
        supporting = [p for p in instance["paragraphs"] if p["is_supporting"]]
        d["cscov"] = compute_cscov(supporting, result.transmitted_states)
    elif compute_cscov_flag:
        d["cscov"] = 0.0
    return d


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_experiment(args: argparse.Namespace) -> dict:
    """Execute the full Table 1 experiment and return results dict."""

    # ------------------------------------------------------------------
    # Load data and create shards
    # ------------------------------------------------------------------
    is_silobench = (args.dataset == "silobench")

    if is_silobench:
        print(f"Loading Silo-Bench from: {args.data or '(default benchmarks dir)'}")
        instances = load_silobench(
            path=args.data,
            n_agents_filter=args.n_agents,
        )
        eval_fn = silobench_exact_match
    else:
        if getattr(args, "musique_sample", 0) > 0:
            print(f"Loading MuSiQue sample (n={args.musique_sample}) from: "
                  f"{args.data or '(default dev split)'}")
            instances = load_musique_sample(
                n=args.musique_sample,
                seed=args.seed,
                path=args.data,
                min_hops=args.min_hops,
            )
        else:
            print(f"Loading MuSiQue from: {args.data or '(default dev split)'}")
            instances = load_musique(args.data, min_hops=args.min_hops)
        eval_fn = answer_f1

    if args.limit > 0:
        instances = instances[: args.limit]
        print(f"Limited to {len(instances)} instances (--limit {args.limit})")
    else:
        print(f"Loaded {len(instances)} instances")

    if not instances:
        raise ValueError("No instances loaded — check --data path and --min-hops.")

    if is_silobench:
        shards_list = [shards_from_silobench(inst) for inst in instances]
    else:
        # Use shards_from_musique (1 supporting para per agent) unless --n-agents
        # is explicitly set, in which case fall back to random shard_instance.
        if args.n_agents is not None:
            shards_list = [
                shard_instance(inst, n_agents=args.n_agents, seed=args.seed + i)
                for i, inst in enumerate(instances)
            ]
        else:
            shards_list = [shards_from_musique(inst) for inst in instances]

    # ------------------------------------------------------------------
    # API setup
    # ------------------------------------------------------------------
    batch_fn = _get_batch_fn(args.provider)

    common_kw = dict(
        batch_fn=batch_fn,
        model=args.model,
        max_tokens=args.max_tokens,
        max_workers=args.max_workers,
    )

    protocols = set(args.protocols)

    # ------------------------------------------------------------------
    # Precompute shared data
    # ------------------------------------------------------------------

    # Local agent answers (reused by single_local, majority_vote, best_local,
    # disagreement_gated, and as round-0 for debate)
    local_answers_list: list[list[str]] | None = None
    local_per_agent_tokens: list[list[int]] | None = None
    if protocols & (_NEEDS_LOCAL | {"free_form_debate"}):
        _info("\n[Precompute] Local agent answers ...")
        local_answers_list, local_per_agent_tokens = compute_local_answers_batch(
            instances, shards_list, **common_kw
        )

    # Evidence unit extraction (reused by random_relay, score_ranked_relay, redundancy_aware_relay)
    all_states: list[list[list[str]]] | None = None
    extract_per_inst_tokens: list[int] | None = None
    if protocols & _NEEDS_STATES:
        _info("[Precompute] Extracting evidence units ...")
        all_states, extract_per_inst_tokens = extract_states_batch(
            instances,
            shards_list,
            batch_fn=batch_fn,
            model=args.model,
            max_tokens=args.max_tokens,
            max_states_per_agent=args.max_states,
            max_workers=args.max_workers,
        )

    # Local importance scores (reused by score_ranked_relay and redundancy_aware_relay)
    all_scores: list[list[list[dict]]] | None = None
    score_per_inst_tokens: list[int] | None = None
    if protocols & _NEEDS_SCORES and all_states is not None:
        _info("[Precompute] Scoring evidence units ...")
        all_scores, score_per_inst_tokens = score_states_batch(
            instances,
            all_states,
            batch_fn=batch_fn,
            model=args.model,
            max_workers=args.max_workers,
        )

    # ------------------------------------------------------------------
    # Run each protocol
    # ------------------------------------------------------------------
    raw_results: dict[str, list[ProtocolResult]] = {}

    def _log_results(name: str, results: list) -> None:
        """Print per-instance pred/gold/correct after a protocol finishes."""
        n_correct = 0
        for i, r in enumerate(results):
            inst = instances[i]
            gold = str(inst.get("answer", ""))
            f1 = eval_fn(r.pred, inst) if eval_fn is not None else r.f1
            correct = f1 >= 1.0
            n_correct += int(correct)
            mark = "✓" if correct else "✗"
            _info(f"  {r.instance_id:<16} pred={str(r.pred):<12} gold={gold:<12} {mark}  comm={r.comm_tokens}")
        acc = 100.0 * n_correct / len(results) if results else 0.0
        _info(f"  → {name}: {n_correct}/{len(results)} correct ({acc:.1f}%)")

    def _run(name: str, fn, *a, **kw):
        if name not in protocols:
            return
        _info(f"[Protocol] {name} ...")
        results = fn(*a, **kw)
        raw_results[name] = results
        _log_results(name, results)

    # --- No-communication baselines ---
    import random as _random

    if "single_local" in protocols and local_answers_list is not None:
        _info("[Protocol] single_local ...")
        rng = _random.Random(args.seed)
        raw_results["single_local"] = [
            run_single_local(
                inst, shards, batch_fn, args.model, args.max_tokens,
                rng, precomputed_answers=local_answers_list[i],
                max_workers=args.max_workers,
            )
            for i, (inst, shards) in enumerate(zip(instances, shards_list))
        ]
        # Attribute only the selected agent's tokens (single_local calls one agent).
        # Replay a fresh RNG with the same seed to recover the selected indices.
        if local_per_agent_tokens is not None:
            idx_rng = _random.Random(args.seed)
            for i, (result, shards) in enumerate(zip(raw_results["single_local"], shards_list)):
                sel = idx_rng.randint(0, max(len(shards) - 1, 0))
                result.total_llm_tokens = local_per_agent_tokens[i][sel]
        _log_results("single_local", raw_results["single_local"])

    if "majority_vote" in protocols and local_answers_list is not None:
        _info("[Protocol] majority_vote ...")
        raw_results["majority_vote"] = [
            run_majority_vote_protocol(
                inst, shards, batch_fn, args.model, args.max_tokens,
                precomputed_answers=local_answers_list[i],
                max_workers=args.max_workers,
            )
            for i, (inst, shards) in enumerate(zip(instances, shards_list))
        ]
        if local_per_agent_tokens is not None:
            for i, result in enumerate(raw_results["majority_vote"]):
                result.total_llm_tokens = sum(local_per_agent_tokens[i])
        _log_results("majority_vote", raw_results["majority_vote"])

    if "best_local" in protocols and local_answers_list is not None:
        _info("[Protocol] best_local ...")
        raw_results["best_local"] = [
            run_best_local_oracle(
                inst, shards, batch_fn, args.model, args.max_tokens,
                precomputed_answers=local_answers_list[i],
                max_workers=args.max_workers,
                eval_fn=eval_fn,
            )
            for i, (inst, shards) in enumerate(zip(instances, shards_list))
        ]
        if local_per_agent_tokens is not None:
            for i, result in enumerate(raw_results["best_local"]):
                result.total_llm_tokens = sum(local_per_agent_tokens[i])
        _log_results("best_local", raw_results["best_local"])

    # --- Communication baselines ---
    _run(
        "free_form_debate",
        run_debate_batch,
        instances,
        shards_list,
        batch_fn,
        args.model,
        args.max_tokens,
        n_rounds=args.debate_rounds,
        precomputed_answers_list=local_answers_list,
        precomputed_tokens_list=local_per_agent_tokens,
        max_workers=args.max_workers,
    )

    _run(
        "summary_exchange",
        run_summary_exchange_batch,
        instances,
        shards_list,
        batch_fn,
        args.model,
        args.max_tokens,
        max_workers=args.max_workers,
    )

    _run(
        "confidence_gated",
        run_confidence_gated_batch,
        instances,
        shards_list,
        batch_fn,
        args.model,
        args.max_tokens,
        confidence_threshold=args.conf_threshold,
        max_workers=args.max_workers,
    )

    _run(
        "disagreement_gated",
        run_disagreement_gated_batch,
        instances,
        shards_list,
        batch_fn,
        args.model,
        args.max_tokens,
        precomputed_answers_list=local_answers_list,
        precomputed_tokens_list=local_per_agent_tokens,
        max_workers=args.max_workers,
    )

    # --- Oracle ---
    _run(
        "full_sharing",
        run_full_sharing_batch,
        instances,
        batch_fn,
        args.model,
        args.max_tokens,
        max_workers=args.max_workers,
    )

    # --- Random relay ---
    if "random_relay" in protocols and all_states is not None:
        _run(
            "random_relay",
            run_random_relay_batch,
            instances,
            shards_list,
            batch_fn,
            args.model,
            args.max_tokens,
            args.max_states,
            precomputed_states=all_states,
            precomputed_extract_tokens=extract_per_inst_tokens,
            seed=args.seed,
            max_workers=args.max_workers,
        )

    # --- Score-ranked evidence relay ---
    if "score_ranked_relay" in protocols and all_states is not None:
        _run(
            "score_ranked_relay",
            run_score_ranked_relay_batch,
            instances,
            shards_list,
            batch_fn,
            args.model,
            args.max_tokens,
            args.max_states,
            precomputed_states=all_states,
            precomputed_scores=all_scores,
            precomputed_extract_tokens=extract_per_inst_tokens,
            precomputed_score_tokens=score_per_inst_tokens,
            max_workers=args.max_workers,
        )

    # --- Redundancy-aware evidence relay ---
    if "redundancy_aware_relay" in protocols and all_states is not None:
        _run(
            "redundancy_aware_relay",
            run_redundancy_aware_relay_batch,
            instances,
            shards_list,
            batch_fn,
            args.model,
            args.max_tokens,
            args.max_states,
            rho=args.rho,
            precomputed_states=all_states,
            precomputed_scores=all_scores,
            precomputed_extract_tokens=extract_per_inst_tokens,
            precomputed_score_tokens=score_per_inst_tokens,
            max_workers=args.max_workers,
        )

    # ------------------------------------------------------------------
    # Package per-instance results and compute aggregate metrics
    # ------------------------------------------------------------------
    # CSCOV only applies to protocols with transmitted states and only when
    # gold paragraph annotations are available (MuSiQue, not Silo-Bench).
    _CSCOV_PROTOCOLS = _NEEDS_STATES | {"summary_exchange"}  # protocols with transmitted units
    has_gold_paragraphs = not is_silobench
    protocol_dicts: dict[str, list[dict]] = {}

    for name, results in raw_results.items():
        cscov_for_protocol = has_gold_paragraphs and name in _CSCOV_PROTOCOLS
        protocol_dicts[name] = [
            _protocol_result_to_dict(r, instances[i], cscov_for_protocol, eval_fn=eval_fn)
            for i, r in enumerate(results)
        ]

    table = build_results_table(protocol_dicts)

    return {
        "args": vars(args),
        "n_instances": len(instances),
        "table": table,
        "instance_results": protocol_dicts,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run evidence-flow audit experiment (all protocols on sharded benchmark)."
    )
    parser.add_argument("--data", default=None)
    parser.add_argument(
        "--dataset", default="silobench", choices=["silobench", "musique"],
        help="Primary dataset for Table 1 (default: silobench). Use 'musique' for ablation.",
    )
    parser.add_argument("--model", default=None,
                        help="Model string (default: provider-specific)")
    parser.add_argument("--provider", default="openrouter",
                        choices=["openrouter", "claude", "openai"])
    parser.add_argument("--n-agents", type=int, default=None,
                        help="Agents per instance (silobench: filter by count, default None=all; "
                             "musique: shard count, default 5)")
    parser.add_argument("--max-states", type=int, default=3,
                        help="Max atomic states per agent (default: 3)")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-workers", type=int, default=128)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-hops", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--protocols", default="all",
        help="Comma-separated list of protocols, or 'all'",
    )
    parser.add_argument("--output", default=None,
                        help="Results directory (default: results/run_<timestamp>/)")
    parser.add_argument("--test", action="store_true",
                        help="Quick smoke-test: 5 instances, verbose, no file save")
    parser.add_argument("--musique-sample", type=int, default=0,
                        help="Stratified sample size for MuSiQue (0 = load all, default: 0). "
                             "Default allocation: 50 2-hop + 35 3-hop + 15 4-hop for n=100.")
    parser.add_argument("--debate-rounds", type=int, default=1)
    parser.add_argument("--conf-threshold", type=float, default=0.6)
    parser.add_argument("--rho", type=float, default=0.5)

    args = parser.parse_args(argv)

    # Resolve model default per provider
    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODELS[args.provider]

    # Resolve --test overrides
    if args.test:
        if args.limit == 0:
            args.limit = 5
        print("=== TEST MODE: limit=5, verbose ===")

    # Resolve --protocols
    if args.protocols.lower() == "all":
        args.protocols = set(ALL_PROTOCOLS)
    else:
        requested = {p.strip() for p in args.protocols.split(",")}
        unknown = requested - set(ALL_PROTOCOLS)
        if unknown:
            parser.error(f"Unknown protocol(s): {unknown}. Valid: {ALL_PROTOCOLS}")
        args.protocols = requested

    # Default output directory
    if args.output is None and not args.test:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        args.output = os.path.join(repo_root, "results", f"run_{timestamp}")

    return args


def main(argv: list[str] | None = None) -> None:
    import time
    args = _parse_args(argv)

    # Set up intermediate API response log before any requests fire
    if args.output and not args.test:
        os.makedirs(args.output, exist_ok=True)
        if args.provider == "openrouter":
            from utility.apis.openrouter_api import setup_response_log
            log_path = os.path.join(args.output, "api_responses.jsonl")
            setup_response_log(log_path)
            _info(f"API response log: {log_path}")

    t_start = time.time()
    output = run_experiment(args)
    elapsed = time.time() - t_start

    output["elapsed_seconds"] = round(elapsed, 2)
    print(f"\nTotal running time: {elapsed:.1f}s")
    print("\n=== Table 1 Results ===")
    print_results_table(output["table"])

    if args.output and not args.test:
        os.makedirs(args.output, exist_ok=True)

        json_path = os.path.join(args.output, "results.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        print(f"Results written to: {json_path}")

        # Flat per-instance JSONL: one line per (protocol, instance)
        flat_path = os.path.join(args.output, "per_instance_results.jsonl")
        with open(flat_path, "w", encoding="utf-8") as fh:
            for protocol, rows in output["instance_results"].items():
                for row in rows:
                    fh.write(json.dumps({"protocol": protocol, **row}) + "\n")
        print(f"Per-instance results written to: {flat_path}")

        summary_path = os.path.join(args.output, "summary.txt")
        with open(summary_path, "w", encoding="utf-8") as fh:
            fh.write(f"Model:      {args.model}\n")
            fh.write(f"Instances:  {output['n_instances']}\n")
            fh.write(f"n_agents:   {args.n_agents}\n")
            fh.write(f"max_states: {args.max_states}\n\n")

            col_w = [34, 10, 13, 13, 10, 10, 8]
            header = (
                f"{'Method':<{col_w[0]}} "
                f"{'Acc (%)':{col_w[1]}} "
                f"{'Comm.Tokens':{col_w[2]}} "
                f"{'Token Cost':{col_w[3]}} "
                f"{'Utility':{col_w[4]}} "
                f"{'Recovery':{col_w[5]}} "
                f"{'CSCOV':{col_w[6]}}"
            )
            fh.write(header + "\n")
            fh.write("-" * len(header) + "\n")
            from src.eval.metrics import _DISPLAY_ORDER, _PROTOCOL_LABELS
            table = output["table"]
            order = [k for k in _DISPLAY_ORDER if k in table]
            order += [k for k in table if k not in _DISPLAY_ORDER]
            for name in order:
                row = table[name]
                label = _PROTOCOL_LABELS.get(name, name)
                cscov_str = f"{row['cscov']:>{col_w[6]}.3f}" if "cscov" in row else f"{'N/A':>{col_w[6]}}"
                fh.write(
                    f"{label:<{col_w[0]}} "
                    f"{row['acc']*100:>{col_w[1]}.2f} "
                    f"{row['mean_comm_tokens']:>{col_w[2]}.1f} "
                    f"{row.get('mean_total_llm_tokens', 0.0):>{col_w[3]}.1f} "
                    f"{row['utility']:>{col_w[4]}.4f} "
                    f"{row['recovery']:>{col_w[5]}.3f} "
                    f"{cscov_str}\n"
                )
        print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()
