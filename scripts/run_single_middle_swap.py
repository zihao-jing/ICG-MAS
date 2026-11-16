#!/usr/bin/env python3
"""Replace one agent's extracted evidence with Gemini, then aggregate with the original model."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.prepare_exact_span_review import ROOT, SETTINGS
from scripts.run_frozen_repair import merge_decisions, original_prompt, prompt_hash, validate_manifest
from src.audit.critical_fact_validation import load_jsonl, write_jsonl
from src.eval.data_loader import load_musique, shards_from_musique
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import load_silobench, shards_from_silobench, silobench_exact_match
from src.protocols.base import extract_answer, format_shard_context
from src.protocols.relay import _EXTRACTION_SYSTEM, _build_extraction_prompt, _parse_units
from utility.apis.base import APIRequest


PLAN_ROOT = ROOT / "results/aggregation_stage_swap_20260926"
MAX_UNITS = 3


def read_inputs(setting: str) -> list[dict]:
    with (PLAN_ROOT / "cohort.csv").open(encoding="utf-8") as handle:
        cohort = [row for row in csv.DictReader(handle) if row["setting"] == setting]
    manifest = load_jsonl(ROOT / f"{setting}_review.jsonl")
    decisions = load_jsonl(ROOT / "exact_span_decisions" / f"{setting}_decisions.jsonl")
    records = [r for r in merge_decisions(manifest, decisions) if r["diagnosis"] == "aggregation_gap"]
    validate_manifest(records)
    by_id = {r["instance_id"]: r for r in records}
    if set(by_id) != {row["instance_id"] for row in cohort}:
        raise ValueError("Frozen cohort and reviewed decisions disagree")
    for row in cohort:
        record = by_id[row["instance_id"]]
        if row["frozen_board_sha256"] != record["original_prompt_sha256"]:
            raise ValueError(f"Frozen board changed for {row['instance_id']}")
    return cohort


def source_shards(setting: str, cohort: list[dict]) -> dict[str, tuple[dict, list]]:
    ids = {row["instance_id"] for row in cohort}
    if "silobench" in setting:
        n_agents = int(setting.rsplit("_n", 1)[1])
        instances = [inst for inst in load_silobench(n_agents_filter=n_agents) if inst["id"] in ids]
        build_shards = shards_from_silobench
    else:
        instances = [inst for inst in load_musique() if inst["id"] in ids]
        build_shards = shards_from_musique
    if {inst["id"] for inst in instances} != ids:
        raise ValueError("Current benchmark is missing frozen case IDs")
    output = {}
    for instance in instances:
        shards = build_shards(instance)
        output[instance["id"]] = instance, shards
    return output


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _response_data(response) -> dict:
    return {"success": response.success, "error": response.error,
            "content": response.content, "usage": response.usage}


def replacement_board(record: dict, agent: int, units: list[str]) -> list[dict]:
    if not units or len(units) > MAX_UNITS:
        raise ValueError("Replacement requires one to three extracted units")
    if not any(int(unit["agent_id"]) == agent for unit in record["board_units"]):
        raise ValueError("Selected agent has no original board units")
    board = [dict(unit) for unit in record["board_units"] if int(unit["agent_id"]) != agent]
    board.extend({"unit_id": f"single-middle:a{agent}:u{index}", "agent_id": agent, "text": text}
                 for index, text in enumerate(units))
    return board


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setting", choices=SETTINGS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()
    cohort = read_inputs(args.setting)
    records = {r["instance_id"]: r for r in merge_decisions(
        load_jsonl(ROOT / f"{args.setting}_review.jsonl"),
        load_jsonl(ROOT / "exact_span_decisions" / f"{args.setting}_decisions.jsonl"))
        if r["diagnosis"] == "aggregation_gap"}
    instances = source_shards(args.setting, cohort)
    plan = {"setting": args.setting, "n_cases": len(cohort),
            "gemini_extraction_calls": len(cohort), "original_aggregation_calls": len(cohort),
            "max_new_calls": 2 * len(cohort), "selected_agents":
            {row["instance_id"]: int(row["selected_middle_agent"]) for row in cohort}}
    if not args.execute:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.mkdir(parents=True)
        _save(args.output / "plan.json", plan)
        print(json.dumps({k: plan[k] for k in ("setting", "n_cases", "max_new_calls")}, indent=2))
        return
    if args.max_calls is None or args.max_calls < plan["max_new_calls"]:
        raise ValueError(f"Execution requires --max-calls at least {plan['max_new_calls']}")
    args.output.mkdir(parents=True, exist_ok=True)
    saved_plan = args.output / "plan.json"
    if saved_plan.exists() and json.loads(saved_plan.read_text()) != plan:
        raise ValueError("Output directory belongs to a different frozen plan")
    _save(saved_plan, plan)
    from src.eval.run_experiment import _get_batch_fn
    from utility.apis.openrouter_api import setup_response_log
    setup_response_log(str(args.output / "api_responses.jsonl"))
    batch = _get_batch_fn("openrouter")
    calls = 0
    extract_requests = []
    extract_rows = []
    for row in cohort:
        case = row["instance_id"]
        path = args.output / "extraction" / f"{case}.json"
        if path.exists() and json.loads(path.read_text()).get("success"):
            continue
        record = records[case]
        instance, shards = instances[case]
        agent = int(row["selected_middle_agent"])
        shard = next(shard for shard in shards if shard.agent_idx == agent)
        source = next(context["text"] for context in record["source_contexts"]
                      if int(context["agent_id"]) == agent)
        if record["dataset"] == "musique":
            if format_shard_context(shard) != source:
                raise ValueError(f"MuSiQue source shard changed for {case}/{agent}")
        elif str(next(config["input_shard"] for config in instance["agent_configs"]
                      if int(config["agent_id"]) == agent)) != source:
            raise ValueError(f"Silo source shard changed for {case}/{agent}")
        extract_requests.append(APIRequest(
            system_query=_EXTRACTION_SYSTEM,
            user_query=_build_extraction_prompt(format_shard_context(shard), record["question"], MAX_UNITS),
            model=record["stronger_model"], max_tokens=record["max_tokens"] // 2,
            metadata={"phase": "single_middle_extraction", "source_id": row["source_id"],
                      "instance_id": case, "agent": agent},
        ))
        extract_rows.append(row)
    if calls + len(extract_requests) > args.max_calls:
        raise ValueError("API call cap exceeded before extraction")
    if extract_requests:
        responses = batch(extract_requests, max_workers=args.max_workers)
        if len(responses) != len(extract_requests):
            raise ValueError("Wrong extraction response count")
        calls += len(responses)
        for row, response in zip(extract_rows, responses):
            states = _parse_units(response.content, MAX_UNITS) if response.success else []
            payload = {**_response_data(response), "units": states,
                       "selected_agent": int(row["selected_middle_agent"])}
            _save(args.output / "extraction" / f"{row['instance_id']}.json", payload)
    agg_requests = []
    agg_rows = []
    for row in cohort:
        case = row["instance_id"]
        path = args.output / "aggregation" / f"{case}.json"
        if path.exists() and json.loads(path.read_text()).get("success"):
            continue
        extraction_path = args.output / "extraction" / f"{case}.json"
        if not extraction_path.exists():
            continue
        extracted = json.loads(extraction_path.read_text())
        if not extracted.get("success") or not extracted.get("units"):
            continue
        record = records[case]
        agent = int(row["selected_middle_agent"])
        board = replacement_board(record, agent, extracted["units"])
        system, user = original_prompt(record, board)
        agg_requests.append(APIRequest(
            system_query=system, user_query=user, model=record["original_model"],
            max_tokens=record["max_tokens"], temperature=record["temperature"],
            metadata={"phase": "single_middle_aggregation", "source_id": row["source_id"],
                      "instance_id": case, "agent": agent, "prompt_sha256": prompt_hash(record, board)},
        ))
        agg_rows.append((row, board))
    if calls + len(agg_requests) > args.max_calls:
        raise ValueError("API call cap exceeded before aggregation")
    if agg_requests:
        responses = batch(agg_requests, max_workers=args.max_workers)
        if len(responses) != len(agg_requests):
            raise ValueError("Wrong aggregation response count")
        calls += len(responses)
        for (row, board), request, response in zip(agg_rows, agg_requests, responses):
            case = row["instance_id"]
            record = records[case]
            prediction = extract_answer(response.content.strip()) if response.success else ""
            instance = instances[case][0]
            score = (silobench_exact_match(prediction, instance) if record["dataset"] == "silobench"
                     else answer_f1(prediction, instance)) if response.success else None
            payload = {**_response_data(response), "prediction": prediction, "score": score,
                       "selected_agent": int(row["selected_middle_agent"]),
                       "prompt_sha256": request.metadata["prompt_sha256"],
                       "board_units": board}
            _save(args.output / "aggregation" / f"{case}.json", payload)
    results = []
    for row in cohort:
        case = row["instance_id"]
        path = args.output / "aggregation" / f"{case}.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text())
        results.append({"setting": args.setting, "source_id": row["source_id"], "instance_id": case,
                        "selected_middle_agent": int(row["selected_middle_agent"]),
                        "original_score": float(row["original_score"]),
                        "terminal_gemini_score": float(row["terminal_gemini_score"]),
                        "middle_gemini_score": result["score"], "middle_success": result["success"],
                        "middle_prediction": result["prediction"],
                        "middle_prompt_sha256": result["prompt_sha256"]})
    write_jsonl(args.output / "per_instance_results.jsonl", results, force=True)
    print(json.dumps({"setting": args.setting, "api_calls_this_run": calls,
                      "completed_cases": sum(row["middle_success"] for row in results),
                      "planned_cases": len(cohort)}, indent=2))


if __name__ == "__main__":
    main()
