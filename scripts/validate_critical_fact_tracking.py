#!/usr/bin/env python3
"""Run the no-API critical-fact validation workflow from revision_plan.md.

Typical workflow:
  1. export cached trace packages for each benchmark/protocol condition;
  2. fill the generated fact template with atomic, query-relevant facts;
  3. create two copies of the label template for independent annotators;
  4. adjudicate disagreements and analyse the final labels.

The script never changes existing results/ directories and never makes API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audit.critical_fact_validation import (
    analyze_adjudicated_labels,
    build_adjudication_tasks,
    build_fact_templates,
    build_label_tasks,
    build_repair_manifest,
    build_trace_packages,
    load_jsonl,
    write_jsonl,
)


def _write_json(path: str, value: dict, force: bool) -> None:
    if os.path.exists(path) and not force:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --force to replace it.")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Offline semantic validation of critical-fact tracking.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export", help="Export cached checkpoint traces and an empty fact sheet.")
    export.add_argument("--dataset", choices=["musique", "silobench"], required=True)
    export.add_argument("--run-dir", required=True)
    export.add_argument("--protocol", choices=["score_ranked_relay", "random_relay", "redundancy_aware_relay", "summary_exchange"], required=True)
    export.add_argument("--source-id", required=True, help="Stable condition ID, e.g. mq_score_relay.")
    export.add_argument("--n-agents", type=int, default=None, help="Required for Silo-Bench if not recorded in results.json.")
    export.add_argument("--sample-size", type=int, default=0, help="0 means all; otherwise balanced correct/error sampling.")
    export.add_argument("--seed", type=int, default=42)
    export.add_argument("--traces-out", required=True)
    export.add_argument("--facts-out", required=True)
    export.add_argument("--force", action="store_true")

    labels = subparsers.add_parser("label-template", help="Join completed fact specs to traces for blinded annotation.")
    labels.add_argument("--traces", required=True)
    labels.add_argument("--facts", required=True)
    labels.add_argument("--output", required=True)
    labels.add_argument("--force", action="store_true")

    adjudicate = subparsers.add_parser("adjudicate", help="Merge two completed annotation files and report agreement.")
    adjudicate.add_argument("--annotator-a", required=True)
    adjudicate.add_argument("--annotator-b", required=True)
    adjudicate.add_argument("--output", required=True)
    adjudicate.add_argument("--agreement-out", required=True)
    adjudicate.add_argument("--force", action="store_true")

    analyse = subparsers.add_parser("analyse", aliases=["analyze"], help="Recompute validated coverage and diagnosis summaries.")
    analyse.add_argument("--traces", required=True)
    analyse.add_argument("--facts", required=True)
    analyse.add_argument("--adjudicated", required=True)
    analyse.add_argument("--output", required=True)
    analyse.add_argument("--force", action="store_true")

    manifest = subparsers.add_parser(
        "repair-manifest",
        help="Freeze Extension-B repair inputs from adjudicated semantic labels.",
    )
    manifest.add_argument("--traces", required=True)
    manifest.add_argument("--facts", required=True)
    manifest.add_argument("--adjudicated", required=True)
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--development-size", type=int, default=0,
                          help="Reserve this many stratified records for rule/prompt development.")
    manifest.add_argument("--seed", type=int, default=42)
    manifest.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "export":
        traces = build_trace_packages(
            dataset=args.dataset,
            run_dir=args.run_dir,
            protocol=args.protocol,
            source_id=args.source_id,
            n_agents=args.n_agents,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        write_jsonl(args.traces_out, traces, force=args.force)
        write_jsonl(args.facts_out, build_fact_templates(traces), force=args.force)
        print(f"Exported {len(traces)} trace packages to {args.traces_out}")
        print(f"Fill atomic facts in {args.facts_out}, then run label-template.")
    elif args.command == "label-template":
        tasks = build_label_tasks(load_jsonl(args.traces), load_jsonl(args.facts))
        write_jsonl(args.output, tasks, force=args.force)
        print(f"Wrote {len(tasks)} blinded annotation tasks to {args.output}")
    elif args.command == "adjudicate":
        tasks, agreement = build_adjudication_tasks(
            load_jsonl(args.annotator_a), load_jsonl(args.annotator_b)
        )
        write_jsonl(args.output, tasks, force=args.force)
        _write_json(args.agreement_out, agreement, args.force)
        print(f"Wrote {len(tasks)} adjudication tasks to {args.output}")
        print(f"Agreement: {agreement['percent_agreement']:.3f}; kappa={agreement['cohen_kappa']}")
    elif args.command == "repair-manifest":
        records = build_repair_manifest(
            load_jsonl(args.traces), load_jsonl(args.facts), load_jsonl(args.adjudicated),
            development_size=args.development_size, seed=args.seed,
        )
        write_jsonl(args.output, records, force=args.force)
        print(f"Wrote {len(records)} frozen Extension-B repair records to {args.output}")
    else:
        report = analyze_adjudicated_labels(
            load_jsonl(args.traces), load_jsonl(args.facts), load_jsonl(args.adjudicated)
        )
        _write_json(args.output, report, args.force)
        print(f"Wrote validated tracking report to {args.output}")


if __name__ == "__main__":
    main()
