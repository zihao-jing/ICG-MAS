#!/usr/bin/env python3
"""Execute or dry-run automatic cached-audit-guided Extension-B repairs."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audit.critical_fact_validation import write_jsonl
from src.audit.repair_study import (
    audit_study_plan,
    build_audit_repair_manifest,
    run_audit_repair_study,
    summarize_audit_repair_results,
)
from src.eval.run_experiment import _PROVIDER_DEFAULT_MODELS, _get_batch_fn


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatic cached-audit-guided Extension-B repair ablation.")
    parser.add_argument("--dataset", choices=["silobench", "musique"], required=True)
    parser.add_argument("--run-dir", required=True, help="Cached score-ranked-relay run with audit_metrics.json")
    parser.add_argument("--source-id", required=True, help="Stable source identifier recorded in outputs")
    parser.add_argument("--output", required=True, help="Directory for plan or executed results")
    parser.add_argument("--n-agents", type=int, default=None, help="Required for Silo-Bench if absent from results.json")
    parser.add_argument("--limit", type=int, default=0, help="Balanced correct/error sample; 0 uses all cached instances")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--signal", nargs="+", choices=["evidence_gap", "aggregation_gap", "baseline_correct", "unclassified_error"],
                        help="Run only these frozen audit-signal groups; useful for resumable API batches.")
    parser.add_argument("--offset", type=int, default=0, help="Start offset after signal filtering.")
    parser.add_argument("--count", type=int, default=0, help="Maximum instances after offset; 0 means all.")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", choices=["openrouter", "claude", "openai"], default="openrouter")
    # Match the cached Qwen relay run's generation budget.  Lower caps caused
    # Qwen to expose partial reasoning but truncate before its ANSWER line.
    parser.add_argument("--aggregation-tokens", type=int, default=4096)
    parser.add_argument("--repair-tokens", type=int, default=4096)
    parser.add_argument("--extraction-tokens", type=int, default=2048)
    parser.add_argument("--analysis-tokens", type=int, default=2048,
                        help="First-stage verifier/consolidator budget for --repair-strategy strong_two_stage.")
    parser.add_argument("--repair-strategy", choices=["single_pass", "strong_two_stage", "bottleneck_aware_v2", "bottleneck_aware_v3"], default="single_pass",
                        help="single_pass reproduces prompt repair; strong_two_stage uses matched ledgers; v2 uses limited Silo reductions and evidence-as-given paths; v3 expands verified Silo executors and enforces cited MuSiQue relation-path ledgers.")
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--execute", action="store_true", help="Send API requests. Omit for a zero-API dry-run.")
    args = parser.parse_args()

    records = build_audit_repair_manifest(
        dataset=args.dataset, run_dir=args.run_dir, source_id=args.source_id,
        n_agents=args.n_agents, sample_size=args.limit, seed=args.seed,
    )
    if args.signal:
        allowed = set(args.signal)
        records = [record for record in records if record["audit_signal"] in allowed]
    if args.offset < 0 or args.count < 0:
        parser.error("--offset and --count must be non-negative")
    records = records[args.offset:] if args.count == 0 else records[args.offset:args.offset + args.count]
    os.makedirs(args.output, exist_ok=True)
    write_jsonl(os.path.join(args.output, "audit_repair_manifest.jsonl"), records, force=True)
    plan = audit_study_plan(records, repair_strategy=args.repair_strategy)
    with open(os.path.join(args.output, "plan.json"), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, sort_keys=True)
        handle.write("\n")
    if not args.execute:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return

    model = args.model or _PROVIDER_DEFAULT_MODELS[args.provider]
    if args.provider == "openrouter":
        from utility.apis.openrouter_api import setup_response_log
        setup_response_log(os.path.join(args.output, "api_responses.jsonl"))
    provider_batch = _get_batch_fn(args.provider)
    rows = run_audit_repair_study(
        records, batch_fn=lambda requests: provider_batch(requests, max_workers=args.max_workers), model=model,
        aggregation_tokens=args.aggregation_tokens, repair_tokens=args.repair_tokens,
        extraction_tokens=args.extraction_tokens, repair_strategy=args.repair_strategy,
        analysis_tokens=args.analysis_tokens,
    )
    report = summarize_audit_repair_results(rows)
    report.update({"model": model, "provider": args.provider, "n_cached_instances": len(records),
                   "repair_strategy": args.repair_strategy, "plan": plan})
    write_jsonl(os.path.join(args.output, "per_instance_results.jsonl"), rows, force=True)
    with open(os.path.join(args.output, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"Executed {len(records)} paired instances; results written to {args.output}")


if __name__ == "__main__":
    main()
