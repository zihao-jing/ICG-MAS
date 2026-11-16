#!/usr/bin/env python3
"""Component-targeted repairs under the original relay aggregation prompt.

``prepare`` exports a review sheet from a cached score-ranked-relay run.
Researchers must review diagnoses and cite source contexts for manually
restored facts. ``run`` is a zero-API dry run unless --execute is specified.
No repair arm changes the aggregation instructions, decoding settings, or
board formatting; the stronger-model arm changes only the model identifier.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable

from src.audit.critical_fact_validation import (
    _load_instances,
    build_trace_packages,
    load_jsonl,
    write_jsonl,
)
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest, APIResponse


SCHEMA_VERSION = "frozen-repair-v1"
DIAGNOSES = {"evidence_gap", "aggregation_gap", "baseline_correct"}
REVIEW_FIELDS = {"diagnosis", "reviewed_by", "review_note", "missing_facts", "volume_control", "stronger_model"}
OPTIONAL_REVIEW_FIELDS = {"board_corrections"}


def prepare_manifest(
    *, dataset: str, run_dir: str | Path, source_id: str,
    n_agents: int | None = None, sample_size: int = 0, seed: int = 42,
) -> list[dict[str, Any]]:
    """Export saved boards and baseline metadata without inferring a repair."""
    run_dir = Path(run_dir)
    with (run_dir / "results.json").open(encoding="utf-8") as handle:
        run = json.load(handle)
    args = run.get("args", {})
    original_model = args.get("model")
    if not original_model:
        raise ValueError("Original model is missing from results.json args")
    traces = build_trace_packages(
        dataset=dataset, run_dir=run_dir, protocol="score_ranked_relay",
        source_id=source_id, n_agents=n_agents, sample_size=sample_size, seed=seed,
    )
    instances = _load_instances(
        dataset, n_agents=n_agents or args.get("n_agents"),
        run_ids={trace["instance_id"] for trace in traces},
    )
    audit_path = run_dir / "audit_metrics.json"
    audit_by_id: dict[str, dict[str, Any]] = {}
    if audit_path.exists():
        with audit_path.open(encoding="utf-8") as handle:
            audit = json.load(handle)
        audit_by_id = {
            row["inst_id"]: row
            for row in audit.get("audit_records", {}).get("score_ranked_relay", [])
        }
    records = []
    for trace in traces:
        instance_id = trace["instance_id"]
        contexts = trace["source_contexts"]
        agents = sorted({int(context["agent_id"]) for context in contexts})
        if agents != list(range(len(agents))):
            raise ValueError(f"Non-contiguous agent IDs for {instance_id}")
        record = {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "dataset": dataset,
            "instance_id": instance_id,
            "question": trace["question"],
            "gold_answer": trace["gold_answer"],
            "answer_aliases": instances[instance_id].get("answer_aliases", []),
            "original_model": original_model,
            "original_provider": args.get("provider", "openrouter"),
            "stronger_model": "",
            "max_tokens": int(args.get("max_tokens", 4096)),
            # Original relay APIRequest omitted temperature; its default is 0.7.
            "temperature": 0.7,
            "n_agents": len(agents),
            "board_units": trace["checkpoints"]["board"],
            "source_contexts": contexts,
            "source_supports": trace["source_supports"],
            "baseline": {
                "pred": trace["baseline_prediction"],
                "f1": trace["answer_f1"],
                "correct": trace["answer_correct"],
            },
            "audit_hint": {
                key: audit_by_id.get(instance_id, {}).get(key)
                for key in ("crit_recall", "agg_fail")
            },
            "diagnosis": "needs_review",
            "reviewed_by": "",
            "review_note": "",
            "missing_facts": [],
            "board_corrections": [],
            "volume_control": None,
            "prompt_provenance": "Reconstructed from the saved relay implementation; original API request text was not logged.",
        }
        record["original_prompt_sha256"] = prompt_hash(record, record["board_units"])
        records.append(record)
    return records


def _group_board(record: dict[str, Any], board: list[dict[str, Any]]) -> list[list[str]]:
    grouped: list[list[str]] = [[] for _ in range(int(record["n_agents"]))]
    for unit in board:
        agent = int(unit["agent_id"])
        if not 0 <= agent < len(grouped):
            raise ValueError(f"Board unit has invalid agent ID: {agent}")
        grouped[agent].append(str(unit["text"]))
    return grouped


def original_prompt(record: dict[str, Any], board: list[dict[str, Any]]) -> tuple[str, str]:
    return _AGGREGATION_SYSTEM, _build_evidence_board_prompt(
        _group_board(record, board), str(record["question"])
    )


def prompt_hash(record: dict[str, Any], board: list[dict[str, Any]]) -> str:
    system, user = original_prompt(record, board)
    return hashlib.sha256(json.dumps([system, user], ensure_ascii=False).encode("utf-8")).hexdigest()


def decision_templates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep long, immutable task traces separate from short review decisions."""
    return [
        {"source_id": record["source_id"], "instance_id": record["instance_id"],
         **{field: record[field] for field in REVIEW_FIELDS},
         "board_corrections": record.get("board_corrections", [])}
        for record in records
    ]


def merge_decisions(records: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for decision in decisions:
        key = (decision.get("source_id", ""), decision.get("instance_id", ""))
        required = REVIEW_FIELDS | {"source_id", "instance_id"}
        if key in by_key or not required <= set(decision) or set(decision) - required - OPTIONAL_REVIEW_FIELDS:
            raise ValueError(f"Duplicate or malformed review decision: {key}")
        by_key[key] = decision
    expected = {(record["source_id"], record["instance_id"]) for record in records}
    if set(by_key) != expected:
        raise ValueError("Review decisions must cover exactly the manifest instances")
    return [
        {**record, **{field: by_key[(record["source_id"], record["instance_id"])][field]
                     for field in REVIEW_FIELDS},
         "board_corrections": by_key[(record["source_id"], record["instance_id"])].get("board_corrections", [])}
        for record in records
    ]


def _correction_value(record: dict[str, Any], correction: dict[str, Any]) -> str:
    source = next(context for context in record["source_contexts"]
                  if context["context_id"] == correction["source_context_id"])
    values = ast.literal_eval(source["text"])
    if not isinstance(values, list):
        raise ValueError("Board correction requires a source list")
    kind = correction["kind"]
    if kind == "word_count" and str(record["instance_id"]).startswith("I-02"):
        match = re.search(r'word "([^"]+)"', record["question"])
        if not match:
            raise ValueError("Cannot identify target word for board correction")
        return str(values.count(match.group(1)))
    if kind == "item_count" and str(record["instance_id"]).startswith("I-02"):
        return str(len(values))
    if kind == "local_sum" and str(record["instance_id"]).startswith("I-07"):
        total = sum((Decimal(str(value)) for value in values), Decimal(0))
        return str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    raise ValueError(f"Unsupported board correction kind: {kind}")


def correction_text(record: dict[str, Any], correction: dict[str, Any]) -> str:
    agent = _agent_for_context(record, correction["source_context_id"])
    old, new = correction["incorrect_value"], correction["correct_value"]
    if correction["kind"] == "word_count":
        label = "local word count"
    elif correction["kind"] == "item_count":
        label = "local list length"
    else:
        label = "local sum (rounded to two decimal places)"
    return f"Correction to Agent {agent}'s earlier {label}: {new}, not {old}."


def validate_manifest(records: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    stronger_models: set[str] = set()
    for record in records:
        key = (record.get("source_id", ""), record.get("instance_id", ""))
        if record.get("schema_version") != SCHEMA_VERSION or key in seen:
            raise ValueError(f"Invalid or duplicate repair record: {key}")
        seen.add(key)
        if (record.get("diagnosis") not in DIAGNOSES
                or not record.get("reviewed_by", "").strip()
                or not record.get("review_note", "").strip()):
            raise ValueError(f"Human-reviewed diagnosis required for {key}")
        if record.get("dataset") not in {"silobench", "musique"}:
            raise ValueError(f"Unknown dataset for {key}")
        if not record.get("original_model") or int(record.get("max_tokens", 0)) <= 0:
            raise ValueError(f"Missing original generation settings for {key}")
        if not 0 <= float(record.get("temperature", -1)) <= 2:
            raise ValueError(f"Invalid temperature for {key}")
        if "board_units" not in record or not record.get("source_contexts"):
            raise ValueError(f"Original board and source contexts required for {key}")
        if prompt_hash(record, record["board_units"]) != record.get("original_prompt_sha256"):
            raise ValueError(f"Original prompt changed after manifest preparation: {key}")
        context_ids = {str(context["context_id"]) for context in record["source_contexts"]}
        corrections = record.get("board_corrections", [])
        if not isinstance(corrections, list):
            raise ValueError(f"Board corrections must be a list: {key}")
        if record["diagnosis"] == "evidence_gap":
            facts = record.get("missing_facts")
            if not isinstance(facts, list) or not facts:
                raise ValueError(f"Exact missing source spans required for evidence-gap record: {key}")
            existing_texts = {str(unit["text"]).strip().casefold() for unit in record["board_units"]}
            for fact in facts:
                if not str(fact.get("text", "")).strip() or fact.get("source_context_id") not in context_ids:
                    raise ValueError(f"Every restored fact needs text and a valid source context: {key}")
                if not fact.get("verified_by", "").strip():
                    raise ValueError(f"Every restored fact needs manual verification: {key}")
                source = next(context for context in record["source_contexts"]
                              if context["context_id"] == fact["source_context_id"])
                if fact["text"] not in source["text"]:
                    raise ValueError(f"Restored text must be an exact source span: {key}")
                if record["dataset"] == "musique" and not any(
                    int(support["agent_id"]) == int(source["agent_id"])
                    and fact["text"] in support["text"]
                    for support in record["source_supports"]
                ):
                    raise ValueError(f"MuSiQue restored span must be in gold supporting evidence: {key}")
                if fact["text"].strip().casefold() in existing_texts:
                    raise ValueError(f"Restored fact already appears on the board: {key}")
            units_by_id = {unit["unit_id"]: unit for unit in record["board_units"]}
            if len(units_by_id) != len(record["board_units"]):
                raise ValueError(f"Duplicate original board unit IDs: {key}")
            for correction in corrections:
                if (not isinstance(correction, dict)
                        or correction.get("source_context_id") not in context_ids
                        or not str(correction.get("verified_by", "")).strip()):
                    raise ValueError(f"Board correction requires cited source and reviewer: {key}")
                unit = units_by_id.get(correction.get("corrects_unit_id"))
                if unit is None or int(unit["agent_id"]) != _agent_for_context(record, correction["source_context_id"]):
                    raise ValueError(f"Board correction must cite a unit from the same agent: {key}")
                old = str(correction.get("incorrect_value", ""))
                new = str(correction.get("correct_value", ""))
                if not old or old not in str(unit["text"]) or old == new:
                    raise ValueError(f"Board correction must cite the incorrect original value: {key}")
                if new != _correction_value(record, correction):
                    raise ValueError(f"Board correction does not match the source calculation: {key}")
            control = record.get("volume_control")
            if control is not None:
                if not isinstance(control, dict) or not str(control.get("text", "")).strip():
                    raise ValueError(f"Non-critical control must contain text for {key}")
                if control.get("source_context_id") not in context_ids or not control.get("verified_by", "").strip():
                    raise ValueError(f"Control needs source context and manual verification: {key}")
                control_source = next(context for context in record["source_contexts"]
                                      if context["context_id"] == control["source_context_id"])
                if control["text"] not in control_source["text"]:
                    raise ValueError(f"Control text must be an exact source span: {key}")
                if control["text"].strip().casefold() in {fact["text"].strip().casefold() for fact in facts}:
                    raise ValueError(f"Control cannot duplicate the restored fact: {key}")
                fact_length = sum(len(fact["text"]) for fact in facts)
                if not 0.5 <= len(control["text"]) / fact_length <= 1.5:
                    raise ValueError(f"Control must be 0.5--1.5 times the restored text length: {key}")
        elif record["diagnosis"] == "aggregation_gap":
            if corrections:
                raise ValueError(f"Aggregation-gap record cannot contain board corrections: {key}")
            if record.get("missing_facts"):
                raise ValueError(f"Aggregation-gap record cannot contain missing facts: {key}")
            if not record.get("stronger_model", "").strip():
                raise ValueError(f"Stronger model required for aggregation-gap record: {key}")
            if record["stronger_model"] == record["original_model"]:
                raise ValueError(f"Stronger model must differ from the original model: {key}")
            stronger_models.add(record["stronger_model"])
        elif corrections:
            raise ValueError(f"Only evidence-gap records can contain board corrections: {key}")
        _group_board(record, record["board_units"])
    if len(stronger_models) > 1:
        raise ValueError("Preselect one stronger model for the evaluation batch")


def _agent_for_context(record: dict[str, Any], context_id: str) -> int:
    return next(int(context["agent_id"]) for context in record["source_contexts"]
                if context["context_id"] == context_id)


def conditions(record: dict[str, Any], *, cross_interventions: bool = False) -> dict[str, tuple[str, list[dict[str, Any]]]]:
    """Return model and board for each pre-declared intervention arm."""
    board = [dict(unit) for unit in record["board_units"]]
    arms = {"exact_replay": (record["original_model"], board)}
    if record["diagnosis"] == "evidence_gap":
        restored = [dict(unit) for unit in board]
        for index, fact in enumerate(record["missing_facts"]):
            restored.append({
                "unit_id": f"exact-span:{index}",
                "agent_id": _agent_for_context(record, fact["source_context_id"]),
                "text": fact["text"],
            })
        for index, correction in enumerate(record.get("board_corrections", [])):
            restored.append({
                "unit_id": f"board-correction:{index}",
                "agent_id": _agent_for_context(record, correction["source_context_id"]),
                "text": correction_text(record, correction),
            })
        arms["restored_fact"] = (record["original_model"], restored)
        control = record.get("volume_control")
        if control is not None:
            control_board = [dict(unit) for unit in board] + [{
                "unit_id": "volume-control",
                "agent_id": _agent_for_context(record, control["source_context_id"]),
                "text": control["text"],
            }]
            arms["noncritical_control"] = (record["original_model"], control_board)
        if cross_interventions:
            stronger_model = record.get("stronger_model", "").strip()
            if not stronger_model or stronger_model == record["original_model"]:
                raise ValueError("Cross intervention requires a distinct stronger model")
            arms["stronger_model"] = (stronger_model, [dict(unit) for unit in board])
    elif record["diagnosis"] == "aggregation_gap":
        arms["stronger_model"] = (record["stronger_model"], [dict(unit) for unit in board])
    return arms


def plan(records: list[dict[str, Any]]) -> dict[str, Any]:
    validate_manifest(records)
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        for condition in conditions(record):
            counts[condition] += 1
    return {"schema_version": SCHEMA_VERSION, "n_instances": len(records),
            "new_api_calls": sum(counts.values()), "calls_by_condition": dict(sorted(counts.items())),
            "note": "No API calls occur without --execute. Cached original answers are retained for comparison; exact_replay is a diagnostic arm."}


def _score(record: dict[str, Any], pred: str) -> float:
    instance = {"answer": record["gold_answer"], "answer_aliases": record.get("answer_aliases", [])}
    return (silobench_exact_match(pred, instance) if record["dataset"] == "silobench"
            else answer_f1(pred, instance))


def run(
    records: list[dict[str, Any]], *, batch_fn: Callable[[list[APIRequest]], list[APIResponse]],
    only_conditions: set[tuple[str, str, str]] | None = None,
    upstream_ignore: str | None = None,
    cross_interventions: bool = False,
) -> list[dict[str, Any]]:
    validate_manifest(records)
    requests: list[APIRequest] = []
    index: list[tuple[dict[str, Any], str, list[dict[str, Any]]]] = []
    for record in records:
        for condition, (model, board) in conditions(record, cross_interventions=cross_interventions).items():
            if (only_conditions is not None
                    and (record["source_id"], record["instance_id"], condition) not in only_conditions):
                continue
            system, user = original_prompt(record, board)
            metadata = {"phase": "frozen_repair", "condition": condition,
                        "source_id": record["source_id"], "instance_id": record["instance_id"],
                        "prompt_sha256": prompt_hash(record, board)}
            if upstream_ignore and model.startswith("mistralai/"):
                metadata["openrouter_provider_ignore"] = [upstream_ignore]
            requests.append(APIRequest(
                system_query=system, user_query=user, model=model,
                max_tokens=int(record["max_tokens"]), temperature=float(record["temperature"]),
                metadata=metadata,
            ))
            index.append((record, condition, board))
    responses = batch_fn(requests)
    if len(responses) != len(requests):
        raise ValueError("Provider returned a different number of responses than requests")
    rows: list[dict[str, Any]] = []
    for request, response, (record, condition, board) in zip(requests, responses, index):
        pred = extract_answer(response.content.strip()) if response.success and response.content.strip() else ""
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "source_id": record["source_id"], "dataset": record["dataset"],
            "original_model": record["original_model"], "n_agents": record["n_agents"],
            "instance_id": record["instance_id"], "diagnosis": record["diagnosis"],
            "condition": condition, "model": request.model,
            "pred": pred, "f1": _score(record, pred),
            "baseline_pred": record["baseline"]["pred"],
            "baseline_f1": _score(record, record["baseline"]["pred"]),
            "success": response.success, "error": response.error,
            "api_calls": 1, "total_llm_tokens": response.usage.get("total_tokens", 0),
            "n_board_units": len(board), "prompt_sha256": request.metadata["prompt_sha256"],
        })
    return rows


def _bootstrap_ci(values: list[float], *, seed: int = 42, draws: int = 2000) -> list[float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(draws))
    return [means[int(0.025 * (draws - 1))], means[int(0.975 * (draws - 1))]]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_case: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (row["source_id"], row["instance_id"])
        if row["condition"] in by_case[key]:
            raise ValueError(f"Duplicate condition for {key}")
        by_case[key][row["condition"]] = row
    paired: dict[tuple[str, str, str, int | None, str, str, str], list[float]] = defaultdict(list)
    win_counts: dict[tuple[str, str, str, int | None, str, str, str], list[int]] = defaultdict(list)
    arm_scores: dict[tuple[str, str, str, int | None, str, str, str], list[float]] = defaultdict(list)
    control_scores: dict[tuple[str, str, str, int | None, str, str, str], list[float]] = defaultdict(list)
    original_scores: dict[tuple[str, str, str, int | None, str, str, str], list[float]] = defaultdict(list)
    original_deltas: dict[tuple[str, str, str, int | None, str, str, str], list[float]] = defaultdict(list)
    original_win_counts: dict[tuple[str, str, str, int | None, str, str, str], list[int]] = defaultdict(list)
    contrasts = (
        ("restored_fact", "noncritical_control"),
        ("restored_fact", "exact_replay"),
        ("noncritical_control", "exact_replay"),
        ("gold_support_repair", "exact_replay"),
        ("source_shard_repair", "exact_replay"),
        ("stronger_model", "exact_replay"),
    )
    for case in by_case.values():
        for condition, control in contrasts:
            row, comparator = case.get(condition), case.get(control)
            if row is None or comparator is None or not row["success"] or not comparator["success"]:
                continue
            # MuSiQue is one mixed-hop setting; n_agents varies with hop count.
            # Preserve Silo-Bench's fixed agent-count settings as separate rows.
            setting_agents = row.get("n_agents") if row["dataset"] == "silobench" else None
            key = (row["source_id"], row["dataset"], row.get("original_model", ""),
                   setting_agents, row["diagnosis"], condition, control)
            paired[key].append(float(row["f1"]) - float(comparator["f1"]))
            win_counts[key].append(int(row["f1"] > comparator["f1"]) - int(row["f1"] < comparator["f1"]))
            arm_scores[key].append(float(row["f1"]))
            control_scores[key].append(float(comparator["f1"]))
            original_scores[key].append(float(comparator["baseline_f1"]))
            original_deltas[key].append(float(row["f1"]) - float(comparator["baseline_f1"]))
            original_win_counts[key].append(
                int(row["f1"] > comparator["baseline_f1"])
                - int(row["f1"] < comparator["baseline_f1"])
            )
    summaries = []
    for (source_id, dataset, original_model, n_agents, diagnosis, condition, control), deltas in sorted(paired.items()):
        comparisons = win_counts[(source_id, dataset, original_model, n_agents, diagnosis, condition, control)]
        original_comparisons = original_win_counts[(source_id, dataset, original_model, n_agents, diagnosis, condition, control)]
        baseline_deltas = original_deltas[(source_id, dataset, original_model, n_agents, diagnosis, condition, control)]
        summaries.append({
            "source_id": source_id, "dataset": dataset, "original_model": original_model,
            "n_agents": n_agents, "diagnosis": diagnosis, "condition": condition, "control": control,
            "n_paired": len(deltas), "mean_f1_delta": sum(deltas) / len(deltas),
            "mean_arm_score": sum(arm_scores[(source_id, dataset, original_model, n_agents, diagnosis, condition, control)]) / len(deltas),
            "mean_control_score": sum(control_scores[(source_id, dataset, original_model, n_agents, diagnosis, condition, control)]) / len(deltas),
            "mean_original_score": sum(original_scores[(source_id, dataset, original_model, n_agents, diagnosis, condition, control)]) / len(deltas),
            "mean_original_delta": sum(baseline_deltas) / len(baseline_deltas),
            "original_delta_95ci": _bootstrap_ci(baseline_deltas),
            "original_improved": sum(value > 0 for value in original_comparisons),
            "original_worsened": sum(value < 0 for value in original_comparisons),
            "original_tied": sum(value == 0 for value in original_comparisons),
            "delta_95ci": _bootstrap_ci(deltas),
            "improved": sum(value > 0 for value in comparisons),
            "worsened": sum(value < 0 for value in comparisons),
            "tied": sum(value == 0 for value in comparisons),
        })
    return {"schema_version": SCHEMA_VERSION, "n_instances": len(by_case),
            "comparison": "Original-run versus intervention on the same selected cases is the paper-facing contrast. Exact replay is diagnostic. Failed responses are excluded.",
            "summaries": summaries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Export a no-API review sheet")
    prepare.add_argument("--dataset", choices=["silobench", "musique"], required=True)
    prepare.add_argument("--run-dir", required=True)
    prepare.add_argument("--source-id", required=True)
    prepare.add_argument("--n-agents", type=int)
    prepare.add_argument("--limit", type=int, default=0)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--output", required=True)
    execute = sub.add_parser("run", help="Validate a reviewed manifest; --execute sends paid API calls")
    execute.add_argument("--manifest", required=True)
    execute.add_argument("--decisions", help="Short reviewed decision JSONL; leaves the prepared manifest untouched")
    execute.add_argument("--output", required=True, help="New output directory")
    execute.add_argument("--provider", choices=["openrouter", "claude", "openai"], default="openrouter")
    execute.add_argument("--max-workers", type=int, default=8)
    execute.add_argument("--max-calls", type=int, help="Required with --execute; hard cap on planned paid calls")
    execute.add_argument("--execute", action="store_true")
    execute.add_argument("--retry-from", help="Prior run directory; retry only its failed API arms")
    execute.add_argument("--ignore-upstream", help="OpenRouter provider slug to avoid for Mistral replay calls")
    execute.add_argument("--cross-arms-only", action="store_true", help="Run Gemini on annotated evidence-gap cases only")
    report = sub.add_parser("summarize", help="Summarize paired executed results")
    report.add_argument("--results", required=True)
    report.add_argument("--output", required=True)
    review = sub.add_parser("decisions", help="Export a compact annotation sheet from a prepared manifest")
    review.add_argument("--manifest", required=True)
    review.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        records = prepare_manifest(
            dataset=args.dataset, run_dir=args.run_dir, source_id=args.source_id,
            n_agents=args.n_agents, sample_size=args.limit, seed=args.seed,
        )
        write_jsonl(args.output, records)
        print(f"Prepared {len(records)} records requiring human review: {args.output}")
    elif args.command == "run":
        records = load_jsonl(args.manifest)
        if args.decisions:
            records = merge_decisions(records, load_jsonl(args.decisions))
        excluded = sum(record.get("diagnosis") == "exclude" for record in records)
        records = [record for record in records if record.get("diagnosis") != "exclude"]
        if not records:
            raise ValueError("No reviewed evaluation records remain after exclusions")
        study_plan = plan(records)
        cross_keys: set[tuple[str, str, str]] | None = None
        if args.cross_arms_only:
            cross_keys = set()
            for record in records:
                if record["diagnosis"] != "evidence_gap":
                    continue
                # Exact repair needs an explicit source span; there is no
                # meaningful source-restoration arm on a complete board.
                conditions(record, cross_interventions=True)
                cross_keys.add((record["source_id"], record["instance_id"], "stronger_model"))
            if not cross_keys:
                raise ValueError("No annotated evidence-gap cases for cross-model execution")
            study_plan["new_api_calls"] = len(cross_keys)
            study_plan["calls_by_condition"] = dict(sorted(Counter(key[2] for key in cross_keys).items()))
            study_plan["note"] = "Only Gemini on annotated evidence-gap cases is executed; cached original answers remain the report comparison."
        study_plan["n_excluded_before_execution"] = excluded
        prior_rows: list[dict[str, Any]] = []
        retry_keys: set[tuple[str, str, str]] | None = None
        if args.retry_from:
            prior_rows = load_jsonl(Path(args.retry_from) / "per_instance_results.jsonl")
            expected = cross_keys if cross_keys is not None else {
                (record["source_id"], record["instance_id"], condition)
                for record in records for condition in conditions(record)
            }
            found = [(row["source_id"], row["instance_id"], row["condition"]) for row in prior_rows]
            if len(found) != len(set(found)) or set(found) != expected:
                raise ValueError("Retry source must contain exactly the planned condition rows")
            retry_keys = {
                (row["source_id"], row["instance_id"], row["condition"])
                for row in prior_rows if not row["success"]
            }
            if not retry_keys:
                raise ValueError("Retry source has no failed API arms")
            study_plan["retry_from"] = args.retry_from
            study_plan["new_api_calls"] = len(retry_keys)
            study_plan["calls_by_condition"] = dict(Counter(key[2] for key in retry_keys))
        providers = {record.get("original_provider", "openrouter") for record in records}
        if providers != {args.provider}:
            raise ValueError(f"Original provider {sorted(providers)} does not match --provider {args.provider}")
        if args.execute and (args.max_calls is None or args.max_calls < study_plan["new_api_calls"]):
            raise ValueError("--execute requires --max-calls at least equal to the planned call count")
        destination = Path(args.output)
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "plan.json").write_text(json.dumps(study_plan, indent=2) + "\n", encoding="utf-8")
        if not args.execute:
            print(json.dumps(study_plan, indent=2))
            return
        from src.eval.run_experiment import _get_batch_fn
        if args.provider == "openrouter":
            from utility.apis.openrouter_api import setup_response_log
            setup_response_log(str(destination / "api_responses.jsonl"))
        provider_batch = _get_batch_fn(args.provider)
        rows = run(records, batch_fn=lambda requests: provider_batch(requests, max_workers=args.max_workers),
                   only_conditions=retry_keys if retry_keys is not None else cross_keys,
                   upstream_ignore=args.ignore_upstream, cross_interventions=args.cross_arms_only)
        if retry_keys is not None:
            retried = {(row["source_id"], row["instance_id"], row["condition"]): row for row in rows}
            rows = [retried.get((row["source_id"], row["instance_id"], row["condition"]), row)
                    for row in prior_rows]
        write_jsonl(destination / "per_instance_results.jsonl", rows)
        (destination / "summary.json").write_text(json.dumps(summarize(rows), indent=2) + "\n", encoding="utf-8")
        print(f"Executed {len(rows)} intervention calls; results: {destination}")
    elif args.command == "decisions":
        records = load_jsonl(args.manifest)
        write_jsonl(args.output, decision_templates(records))
        print(f"Prepared {len(records)} compact review decisions: {args.output}")
    else:
        rows = load_jsonl(args.results)
        output = Path(args.output)
        if output.exists():
            raise FileExistsError(output)
        output.write_text(json.dumps(summarize(rows), indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
