"""
run_evidence_flow_audit.py — Main script for the evidence-flow audit experiment.

Runs multiple communication protocols, logs full audit data (shards, extracted
units, transmitted units, evidence board, alignments, metrics), then exports
JSONL and LaTeX tables.

Usage:
  python scripts/run_evidence_flow_audit.py [OPTIONS]

  --benchmark {silo_bench,musique}
  --num-agents N          Number of agents (default: 5)
  --protocols LIST        Comma-separated protocol names, or "all" (default: all)
  --output-dir DIR        Output directory (default: outputs/evidence_flow_audit/)
  --model MODEL           LLM model string
  --provider {openrouter,claude,openai}
  --max-states N          Max evidence units per agent (default: 3)
  --max-tokens N          Max tokens per LLM call (default: 4096)
  --max-workers N         API concurrency (default: 64)
  --limit N               Max instances (0 = no limit)
  --seed N                Random seed (default: 42)
  --alignment-method {lexical,llm}
  --run-deletions         Run evidence deletion intervention experiments
  --run-local-importance  Run local importance failure analysis
  --test                  Quick smoke-test: 5 instances
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.eval.run_experiment import _get_batch_fn, _PROVIDER_DEFAULT_MODELS
from src.eval.data_loader import load_musique
from src.eval.silo_bench_loader import load_silobench, shards_from_silobench, silobench_exact_match
from src.eval.evaluate import answer_f1
from src.protocols.base import shard_instance, format_shard_context
from src.protocols.relay import (
    extract_states_batch,
    score_states_batch,
    run_random_relay_batch,
    run_score_ranked_relay_batch,
    run_redundancy_aware_relay_batch,
)
from src.protocols.full_sharing import run_full_sharing_batch
from src.protocols.debate import run_debate_batch
from src.protocols.summary_exchange import run_summary_exchange_batch
from src.protocols.gated import run_confidence_gated_batch, run_disagreement_gated_batch
from src.protocols.local import (
    compute_local_answers_batch,
    run_single_local,
    run_majority_vote_protocol,
)

from src.audit.evidence_units import load_gold_support_units, EvidenceUnit
from src.audit.alignment import align_units
from src.audit.metrics import (
    compute_task_audit,
    protocol_audit_summary,
    print_audit_table,
)
from src.audit.reporting import export_all, write_jsonl


# ---------------------------------------------------------------------------
# Available protocols for the audit
# ---------------------------------------------------------------------------

ALL_AUDIT_PROTOCOLS = [
    "single_local",
    "majority_vote",
    "free_form_debate",
    "summary_exchange",
    "confidence_gated",
    "disagreement_gated",
    "random_relay",
    "score_ranked_relay",
    "redundancy_aware_relay",
    "full_sharing",
]

_NEEDS_LOCAL = {"single_local", "majority_vote", "disagreement_gated", "free_form_debate"}
_NEEDS_STATES = {"random_relay", "score_ranked_relay", "redundancy_aware_relay"}
_NEEDS_SCORES = {"score_ranked_relay", "redundancy_aware_relay"}


# ---------------------------------------------------------------------------
# Helpers for converting ProtocolResult transmitted states to EvidenceUnits
# ---------------------------------------------------------------------------

def _states_to_units(
    task_id: str,
    transmitted_states: list[str],
    protocol: str,
) -> list[EvidenceUnit]:
    return [
        EvidenceUnit(
            unit_id=f"{task_id}_{protocol}_tx{i}",
            task_id=task_id,
            agent_id=None,
            text=s,
            source="transmitted_message",
            metadata={"protocol": protocol},
        )
        for i, s in enumerate(transmitted_states)
    ]


# ---------------------------------------------------------------------------
# Build full per-task logging record
# ---------------------------------------------------------------------------

def _build_task_record(
    task: dict,
    protocol: str,
    result,
    gold_units: list[EvidenceUnit],
    alignments: list[dict],
    audit_metrics: dict,
    shards,
    all_unit_texts: list[list[str]] | None = None,
    all_score_dicts: list[list[dict]] | None = None,
) -> dict:
    """Build the full logging schema record for one task/protocol run."""
    task_id = task.get("id", result.instance_id)

    agent_shards_log = []
    for i, shard in enumerate(shards):
        entry: dict = {
            "agent_id": i + 1,
            "raw_context": format_shard_context(shard)[:500],
            "gold_support_units": [
                u.text for u in gold_units
                if u.agent_id == i or u.agent_id is None
            ],
        }
        if all_unit_texts is not None and i < len(all_unit_texts):
            entry["extracted_units"] = all_unit_texts[i]
        agent_shards_log.append(entry)

    local_scores_log = []
    if all_unit_texts is not None and all_score_dicts is not None:
        for agent_i, (units, scores) in enumerate(zip(all_unit_texts, all_score_dicts)):
            for unit_text, score in zip(units, scores):
                local_scores_log.append({
                    "agent_id": agent_i,
                    "unit_text": unit_text,
                    "relevance": score.get("relevance", 0.5),
                    "uniqueness": score.get("uniqueness", 0.5),
                    "local_importance": score.get("local_importance",
                                                  score.get("criticality", 0.5)),
                    "overall": score.get("overall", score.get("composite", 0.5)),
                })

    return {
        "task_id": task_id,
        "question": task.get("question", ""),
        "gold_answer": task.get("answer", ""),
        "protocol": protocol,
        "final_answer": result.pred,
        "answer_correct": audit_metrics.get("accuracy", 0),
        "comm_tokens": result.comm_tokens,
        "total_tokens": result.total_llm_tokens,
        "agent_shards": agent_shards_log,
        "evidence_board": result.transmitted_states,
        "local_scores": local_scores_log,
        "alignments": alignments,
        "audit_metrics": {
            k: v for k, v in audit_metrics.items()
            if k not in ("task_id", "protocol")
        },
    }


# ---------------------------------------------------------------------------
# Main audit runner
# ---------------------------------------------------------------------------

def run_audit(args: argparse.Namespace) -> None:
    is_silobench = (args.benchmark == "silo_bench")
    if is_silobench:
        instances = load_silobench(path=args.data, n_agents_filter=args.num_agents)
        eval_fn = silobench_exact_match
    else:
        instances = load_musique(args.data, min_hops=2)
        eval_fn = answer_f1

    if args.limit > 0:
        instances = instances[: args.limit]
    print(f"Loaded {len(instances)} instances from {args.benchmark}")

    if is_silobench:
        shards_list = [shards_from_silobench(inst) for inst in instances]
    else:
        shards_list = [
            shard_instance(inst, n_agents=args.num_agents, seed=args.seed + i)
            for i, inst in enumerate(instances)
        ]

    batch_fn = _get_batch_fn(args.provider)
    protocols = set(args.protocols)

    # ------------------------------------------------------------------
    # Precompute shared data
    # ------------------------------------------------------------------
    local_answers_list = None
    local_per_agent_tokens = None
    if protocols & _NEEDS_LOCAL:
        print("[Precompute] Local agent answers ...")
        local_answers_list, local_per_agent_tokens = compute_local_answers_batch(
            instances, shards_list,
            batch_fn=batch_fn, model=args.model,
            max_tokens=args.max_tokens, max_workers=args.max_workers,
        )

    all_states = None
    extract_tokens = None
    if protocols & _NEEDS_STATES:
        print("[Precompute] Extracting evidence units ...")
        all_states, extract_tokens = extract_states_batch(
            instances, shards_list,
            batch_fn=batch_fn, model=args.model,
            max_tokens=args.max_tokens,
            max_states_per_agent=args.max_states,
            max_workers=args.max_workers,
        )

    all_scores = None
    score_tokens = None
    if protocols & _NEEDS_SCORES and all_states is not None:
        print("[Precompute] Scoring evidence units ...")
        all_scores, score_tokens = score_states_batch(
            instances, all_states,
            batch_fn=batch_fn, model=args.model,
            max_workers=args.max_workers,
        )

    # ------------------------------------------------------------------
    # Run protocols
    # ------------------------------------------------------------------
    import random as _random
    raw_results: dict[str, list] = {}

    def _run(name, fn, *a, **kw):
        if name not in protocols:
            return
        print(f"[Protocol] Running {name} ...")
        raw_results[name] = fn(*a, **kw)

    if "single_local" in protocols and local_answers_list is not None:
        print("[Protocol] Running single_local ...")
        rng = _random.Random(args.seed)
        raw_results["single_local"] = [
            run_single_local(inst, shards, batch_fn, args.model, args.max_tokens,
                             rng, precomputed_answers=local_answers_list[i],
                             max_workers=args.max_workers)
            for i, (inst, shards) in enumerate(zip(instances, shards_list))
        ]

    if "majority_vote" in protocols and local_answers_list is not None:
        print("[Protocol] Running majority_vote ...")
        raw_results["majority_vote"] = [
            run_majority_vote_protocol(inst, shards, batch_fn, args.model, args.max_tokens,
                                       precomputed_answers=local_answers_list[i],
                                       max_workers=args.max_workers)
            for i, (inst, shards) in enumerate(zip(instances, shards_list))
        ]

    _run("free_form_debate", run_debate_batch, instances, shards_list,
         batch_fn, args.model, args.max_tokens, n_rounds=1,
         precomputed_answers_list=local_answers_list,
         precomputed_tokens_list=local_per_agent_tokens,
         max_workers=args.max_workers)

    _run("summary_exchange", run_summary_exchange_batch, instances, shards_list,
         batch_fn, args.model, args.max_tokens, max_workers=args.max_workers)

    _run("confidence_gated", run_confidence_gated_batch, instances, shards_list,
         batch_fn, args.model, args.max_tokens,
         confidence_threshold=0.6, max_workers=args.max_workers)

    _run("disagreement_gated", run_disagreement_gated_batch, instances, shards_list,
         batch_fn, args.model, args.max_tokens,
         precomputed_answers_list=local_answers_list,
         precomputed_tokens_list=local_per_agent_tokens,
         max_workers=args.max_workers)

    _run("full_sharing", run_full_sharing_batch, instances,
         batch_fn, args.model, args.max_tokens, max_workers=args.max_workers)

    if "random_relay" in protocols and all_states is not None:
        _run("random_relay", run_random_relay_batch, instances, shards_list,
             batch_fn, args.model, args.max_tokens, args.max_states,
             precomputed_states=all_states,
             precomputed_extract_tokens=extract_tokens,
             seed=args.seed, max_workers=args.max_workers)

    if "score_ranked_relay" in protocols and all_states is not None:
        _run("score_ranked_relay", run_score_ranked_relay_batch, instances, shards_list,
             batch_fn, args.model, args.max_tokens, args.max_states,
             precomputed_states=all_states, precomputed_scores=all_scores,
             precomputed_extract_tokens=extract_tokens,
             precomputed_score_tokens=score_tokens,
             max_workers=args.max_workers)

    if "redundancy_aware_relay" in protocols and all_states is not None:
        _run("redundancy_aware_relay", run_redundancy_aware_relay_batch, instances, shards_list,
             batch_fn, args.model, args.max_tokens, args.max_states,
             rho=0.5, precomputed_states=all_states, precomputed_scores=all_scores,
             precomputed_extract_tokens=extract_tokens,
             precomputed_score_tokens=score_tokens,
             max_workers=args.max_workers)

    # ------------------------------------------------------------------
    # Compute audit metrics and build records
    # ------------------------------------------------------------------
    print("\n[Audit] Computing evidence-flow metrics ...")
    all_protocol_records: list[dict] = []
    protocol_summaries: dict[str, dict] = {}

    for protocol, results in raw_results.items():
        protocol_records: list[dict] = []

        for i, (inst, shards, result) in enumerate(
            zip(instances, shards_list, results)
        ):
            task_id = inst.get("id", str(i))
            gold_units = load_gold_support_units(inst, task_id)

            # Wrap transmitted states as EvidenceUnits
            transmitted_units = _states_to_units(
                task_id, result.transmitted_states, protocol
            )

            # Align transmitted units to gold
            alignments = align_units(
                gold_units, transmitted_units,
                method=args.alignment_method,
            )

            # Compute answer correctness
            f1 = eval_fn(result.pred, inst)
            is_correct = f1 >= 0.5

            audit_metrics = compute_task_audit(
                task_id=task_id,
                protocol=protocol,
                answer_correct=is_correct,
                comm_tokens=result.comm_tokens,
                total_tokens=result.total_llm_tokens,
                gold_critical_units=gold_units,
                transmitted_units=transmitted_units,
                alignments=alignments,
            )

            # Per-agent states and scores for relay protocols
            agent_states = (all_states[i] if all_states is not None else None)
            agent_scores = (all_scores[i] if all_scores is not None else None)

            record = _build_task_record(
                task=inst,
                protocol=protocol,
                result=result,
                gold_units=gold_units,
                alignments=alignments,
                audit_metrics=audit_metrics,
                shards=shards,
                all_unit_texts=agent_states,
                all_score_dicts=agent_scores,
            )
            protocol_records.append(audit_metrics)
            all_protocol_records.append(record)

        protocol_summaries[protocol] = protocol_audit_summary(protocol_records)

    # ------------------------------------------------------------------
    # Print and export
    # ------------------------------------------------------------------
    print("\n=== Evidence-Flow Audit Results ===")
    print_audit_table(protocol_summaries)

    os.makedirs(args.output_dir, exist_ok=True)
    export_all(
        output_dir=args.output_dir,
        protocol_records=all_protocol_records,
        deletion_records=[],  # filled in if --run-deletions
        local_importance_records=[],
        summaries=protocol_summaries,
    )

    # Save full per-task records
    write_jsonl(
        os.path.join(args.output_dir, "audit", "full_task_records.jsonl"),
        all_protocol_records,
    )

    # Save protocol summaries
    summary_path = os.path.join(args.output_dir, "audit", "protocol_summaries.json")
    with open(summary_path, "w") as f:
        json.dump(protocol_summaries, f, indent=2)
    print(f"\nAll outputs written to: {args.output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evidence-flow audit experiment.")
    p.add_argument("--benchmark", default="silo_bench",
                   choices=["silo_bench", "musique"])
    p.add_argument("--data", default=None)
    p.add_argument("--num-agents", type=int, default=5)
    p.add_argument("--protocols", default="all")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--provider", default="openrouter",
                   choices=["openrouter", "claude", "openai"])
    p.add_argument("--max-states", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--max-workers", type=int, default=64)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--alignment-method", default="lexical",
                   choices=["lexical", "llm"])
    p.add_argument("--run-deletions", action="store_true")
    p.add_argument("--run-local-importance", action="store_true")
    p.add_argument("--test", action="store_true")

    args = p.parse_args(argv)

    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODELS.get(args.provider, "deepseek/deepseek-v4-flash")

    if args.test and args.limit == 0:
        args.limit = 5

    if args.protocols.lower() == "all":
        args.protocols = set(ALL_AUDIT_PROTOCOLS)
    else:
        args.protocols = {p.strip() for p in args.protocols.split(",")}

    if args.output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = os.path.join(
            os.path.dirname(__file__), "..", "outputs",
            f"evidence_flow_audit_{ts}"
        )

    return args


if __name__ == "__main__":
    run_audit(_parse_args())
