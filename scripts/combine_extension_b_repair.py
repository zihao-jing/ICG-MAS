#!/usr/bin/env python3
"""Merge resumable Extension-B repair batches into one result directory."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audit.critical_fact_validation import load_jsonl, write_jsonl
from src.audit.repair_study import summarize_audit_repair_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge completed Extension-B repair batches.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Batch directories containing per_instance_results.jsonl")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = []
    seen = set()
    batch_reports = []
    for directory in args.inputs:
        path = os.path.join(directory, "per_instance_results.jsonl")
        for row in load_jsonl(path):
            identity = (row["source_id"], row["instance_id"], row["condition"])
            if identity in seen:
                raise ValueError(f"Duplicate condition result: {identity}")
            seen.add(identity)
            rows.append(row)
        report_path = os.path.join(directory, "results.json")
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as handle:
                batch_reports.append(json.load(handle))
    report = summarize_audit_repair_results(rows)
    models = {batch.get("model") for batch in batch_reports if batch.get("model")}
    providers = {batch.get("provider") for batch in batch_reports if batch.get("provider")}
    if len(models) > 1 or len(providers) > 1:
        raise ValueError("Cannot merge Extension-B batches from different models or providers")
    if models:
        report["model"] = models.pop()
    if providers:
        report["provider"] = providers.pop()
    report["n_targeted_instances"] = len({(row["source_id"], row["instance_id"]) for row in rows})
    report["n_rows"] = len(rows)
    report["source_batches"] = args.inputs
    os.makedirs(args.output, exist_ok=True)
    write_jsonl(os.path.join(args.output, "per_instance_results.jsonl"), rows, force=True)
    with open(os.path.join(args.output, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"Merged {len(rows)} rows from {len(args.inputs)} batches into {args.output}")


if __name__ == "__main__":
    main()
