"""Offline workflow for validating critical-fact tracking.

This module deliberately does not call an LLM.  It turns saved experiment
traces into annotation material, merges two independent annotations, and
recomputes semantic coverage / diagnostic summaries from adjudicated labels.

The existing audit's lexical matcher is retained only as a comparator.  The
validated metrics count a fact as present only when an adjudicator labels the
fact ``faithful`` at the relevant checkpoint.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from src.eval.data_loader import load_musique, shards_from_musique
from src.eval.silo_bench_loader import load_silobench
from src.protocols.base import format_shard_context
from src.protocols.relay import _parse_units, _redundancy_select, _topk_select
from src.protocols.base import parse_score_json


SCHEMA_VERSION = "critical-fact-validation-v1"
LABELS = ("faithful", "partial", "distorted", "absent", "uncertain")
RELAY_PROTOCOLS = {
    "random_relay", "score_ranked_relay", "redundancy_aware_relay",
}
MAX_STATES = 3
SEED = 42
RHO = 0.5


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load non-empty JSONL records with a useful error for malformed rows."""
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {number} of {path}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object on line {number} of {path}")
            records.append(value)
    return records


def write_jsonl(path: str | Path, records: Iterable[dict[str, Any]], *, force: bool = False) -> None:
    """Write JSONL without accidentally replacing an annotation file."""
    destination = Path(path)
    if destination.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {destination}; pass --force to replace it.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_run(run_dir: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_path = Path(run_dir)
    with (run_path / "results.json").open(encoding="utf-8") as handle:
        results = json.load(handle)
    return results, load_jsonl(run_path / "api_responses.jsonl")


def reconstruct_states_and_scores(responses: list[dict[str, Any]]) -> tuple[dict[str, dict[int, list[str]]], dict[str, dict[int, list[dict[str, float]]]]]:
    """Reconstruct extraction/scoring state using the original audit settings."""
    states: dict[str, dict[int, list[str]]] = defaultdict(dict)
    scores: dict[str, dict[int, list[dict[str, float]]]] = defaultdict(lambda: defaultdict(list))
    for response in responses:
        if response.get("phase") == "extraction" and response.get("success"):
            states[response["instance_id"]][int(response["agent"])] = _parse_units(
                response.get("content", ""), MAX_STATES
            )
        if response.get("phase") == "scoring" and response.get("success"):
            score = parse_score_json(response.get("content", ""))
            if not score:
                score = {
                    "relevance": 0.5,
                    "uniqueness": 0.5,
                    "local_importance": 0.5,
                    "overall": 0.5,
                }
            scores[response["instance_id"]][int(response["agent"])].append(score)
    return dict(states), {key: dict(value) for key, value in scores.items()}


def extract_summaries(responses: list[dict[str, Any]]) -> dict[str, dict[int, str]]:
    summaries: dict[str, dict[int, str]] = defaultdict(dict)
    for response in responses:
        if response.get("phase") == "summary" and response.get("success"):
            summaries[response["instance_id"]][int(response["agent"])] = response.get("content", "")
    return dict(summaries)


def get_transmitted_units(
    instance_id: str,
    protocol: str,
    states: dict[str, dict[int, list[str]]],
    scores: dict[str, dict[int, list[dict[str, float]]]],
    n_agents: int,
    k: int = MAX_STATES,
) -> dict[int, list[str]]:
    """Reapply the exact deterministic relay selection used by the old audit."""
    if protocol not in RELAY_PROTOCOLS:
        raise ValueError(f"Unsupported relay protocol: {protocol}")
    if not 1 <= k <= MAX_STATES:
        raise ValueError(f"k must be between 1 and {MAX_STATES}")
    result: dict[int, list[str]] = {}
    for agent in range(n_agents):
        units = states.get(instance_id, {}).get(agent, [])
        agent_scores = scores.get(instance_id, {}).get(agent, [])
        if protocol == "random_relay":
            rng = random.Random(f"{SEED}:{instance_id}")
            selected = rng.sample(units, min(k, len(units))) if units else []
        elif len(agent_scores) >= len(units) and units:
            if protocol == "score_ranked_relay":
                selected = _topk_select(units, agent_scores, k)
            else:
                selected = _redundancy_select(units, agent_scores, k, RHO)
        elif units:
            rng = random.Random(f"{SEED}:{instance_id}:fallback")
            selected = rng.sample(units, min(k, len(units)))
        else:
            selected = []
        result[agent] = selected
    return result


def _units_by_agent(units: dict[int, list[str]], prefix: str) -> list[dict[str, Any]]:
    return [
        {"unit_id": f"{prefix}:a{agent}:u{index}", "agent_id": agent, "text": text}
        for agent in sorted(units)
        for index, text in enumerate(units[agent])
    ]


def _source_supports(instance: dict[str, Any]) -> list[dict[str, Any]]:
    if "agent_configs" in instance:
        return [
            {
                "support_id": f"agent-{item['agent_id']}",
                "agent_id": item["agent_id"],
                "text": str(item["input_shard"]),
            }
            for item in instance["agent_configs"]
        ]
    supporting = [paragraph for paragraph in instance["paragraphs"] if paragraph.get("is_supporting")]
    return [
        {
            "support_id": f"agent-{index}",
            "agent_id": index,
            "title": paragraph.get("title", ""),
            "text": paragraph["paragraph_text"],
        }
        for index, paragraph in enumerate(supporting)
    ]


def _source_contexts(instance: dict[str, Any]) -> list[dict[str, Any]]:
    """Return full private agent contexts for practical repair and controls.

    These are separate from ``source_supports``: on MuSiQue, source supports
    intentionally contain only annotated paragraphs, whereas a valid volume
    control may need a non-supporting paragraph from the original shard.
    """
    if "agent_configs" in instance:
        return [
            {
                "context_id": f"agent-{item['agent_id']}",
                "agent_id": item["agent_id"],
                "text": str(item["input_shard"]),
            }
            for item in instance["agent_configs"]
        ]
    return [
        {
            "context_id": f"agent-{shard.agent_idx}",
            "agent_id": shard.agent_idx,
            "text": format_shard_context(shard),
        }
        for shard in shards_from_musique(instance)
    ]


def _load_instances(dataset: str, *, n_agents: int | None, run_ids: set[str]) -> dict[str, dict[str, Any]]:
    if dataset == "musique":
        instances = load_musique()
    elif dataset == "silobench":
        if n_agents is None:
            raise ValueError("--n-agents is required for Silo-Bench validation exports")
        instances = load_silobench(n_agents_filter=n_agents)
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    return {instance["id"]: instance for instance in instances if instance["id"] in run_ids}


def _result_by_id(results: dict[str, Any], protocol: str) -> dict[str, dict[str, Any]]:
    try:
        rows = results["instance_results"][protocol]
    except KeyError as exc:
        raise ValueError(f"Protocol {protocol!r} is not present in results.json") from exc
    return {row["id"]: row for row in rows}


def _sample_ids(rows: dict[str, dict[str, Any]], sample_size: int, seed: int) -> list[str]:
    """Balanced correct/error sampling; reportable as a stratified sample."""
    if sample_size <= 0 or sample_size >= len(rows):
        return sorted(rows)
    groups = {
        "correct": sorted(key for key, row in rows.items() if float(row.get("f1", 0.0)) >= 1.0),
        "error": sorted(key for key, row in rows.items() if float(row.get("f1", 0.0)) < 1.0),
    }
    rng = random.Random(seed)
    desired = {"correct": sample_size // 2, "error": sample_size - sample_size // 2}
    selected: list[str] = []
    leftovers: list[str] = []
    for name in ("correct", "error"):
        count = min(desired[name], len(groups[name]))
        selected.extend(rng.sample(groups[name], count))
        leftovers.extend(item for item in groups[name] if item not in selected)
    if len(selected) < sample_size:
        selected.extend(rng.sample(leftovers, min(sample_size - len(selected), len(leftovers))))
    return sorted(selected)


def build_trace_packages(
    *,
    dataset: str,
    run_dir: str | Path,
    protocol: str,
    source_id: str,
    n_agents: int | None = None,
    sample_size: int = 0,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Create one immutable, no-API trace package per sampled instance."""
    results, responses = load_run(run_dir)
    run_args = results.get("args", {})
    if n_agents is None:
        n_agents = run_args.get("n_agents")
    protocol_results = _result_by_id(results, protocol)
    selected_ids = _sample_ids(protocol_results, sample_size, seed)
    instances = _load_instances(dataset, n_agents=n_agents, run_ids=set(selected_ids))
    states, scores = reconstruct_states_and_scores(responses)
    summaries = extract_summaries(responses)

    packages: list[dict[str, Any]] = []
    for instance_id in selected_ids:
        if instance_id not in instances:
            continue
        instance = instances[instance_id]
        answer = protocol_results[instance_id]
        checkpoints: dict[str, list[dict[str, Any]]] = {}
        source_supports = _source_supports(instance)
        checkpoints["source"] = [
            {"unit_id": support["support_id"], "agent_id": support["agent_id"], "text": support["text"]}
            for support in source_supports
        ]
        if protocol in RELAY_PROTOCOLS:
            # MuSiQue has a variable number of agents (one per hop), so this
            # must be derived per instance rather than retained from the first
            # sampled trace.
            instance_n_agents = int(n_agents) if n_agents is not None else len(source_supports)
            checkpoints["extraction"] = _units_by_agent(states.get(instance_id, {}), "extraction")
            transmitted = get_transmitted_units(instance_id, protocol, states, scores, instance_n_agents)
            checkpoints["transmission"] = _units_by_agent(transmitted, "transmission")
            # Relay does not transform messages during consolidation, but retain
            # the explicit board checkpoint for annotation/reporting consistency.
            checkpoints["board"] = [dict(unit, unit_id=unit["unit_id"].replace("transmission", "board", 1))
                                    for unit in checkpoints["transmission"]]
        elif protocol == "summary_exchange":
            # _units_by_agent expects one list per agent. A summary is one
            # message, not an iterable of character-level "units".
            transmitted = {
                agent: [text] for agent, text in summaries.get(instance_id, {}).items()
            }
            checkpoints["transmission"] = _units_by_agent(transmitted, "summary")
            checkpoints["board"] = [dict(unit, unit_id=unit["unit_id"].replace("summary", "board", 1))
                                    for unit in checkpoints["transmission"]]
        else:
            raise ValueError(f"Unsupported validation protocol: {protocol}")

        packages.append({
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "dataset": dataset,
            "protocol": protocol,
            "run_dir": str(run_dir),
            "instance_id": instance_id,
            "question": instance["question"],
            "gold_answer": instance["answer"],
            "baseline_prediction": str(answer.get("pred", "")),
            "answer_f1": float(answer.get("f1", 0.0)),
            "answer_correct": float(answer.get("f1", 0.0)) >= 1.0,
            "baseline_comm_tokens": int(answer.get("comm_tokens", 0)),
            "baseline_total_llm_tokens": int(answer.get("total_llm_tokens", 0)),
            "sample_stratum": "correct" if float(answer.get("f1", 0.0)) >= 1.0 else "error",
            "source_supports": source_supports,
            "source_contexts": _source_contexts(instance),
            "checkpoints": checkpoints,
        })
    return packages


def build_fact_templates(trace_packages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make the manual atomic-fact specification sheet from packaged traces."""
    templates = []
    for package in trace_packages:
        templates.append({
            "schema_version": SCHEMA_VERSION,
            "source_id": package["source_id"],
            "instance_id": package["instance_id"],
            "question": package["question"],
            "source_supports": package["source_supports"],
            "source_contexts": package["source_contexts"],
            "critical_facts": [],
            "complete_support_sets": [],
            "instructions": (
                "Replace critical_facts with query-relevant atomic facts. Each fact needs "
                "fact_id, text, source_support_ids, entities, relation, values, and qualifiers. "
                "complete_support_sets is a list of fact-id lists; an instance has complete "
                "support when at least one listed set is faithfully present. Leave it empty to "
                "require every listed fact."
            ),
        })
    return templates


def _validate_fact_spec(spec: dict[str, Any], package: dict[str, Any]) -> list[dict[str, Any]]:
    facts = spec.get("critical_facts")
    if not isinstance(facts, list) or not facts:
        raise ValueError(f"{spec.get('source_id')}:{spec.get('instance_id')} has no critical_facts")
    support_ids = {support["support_id"] for support in package["source_supports"]}
    fact_ids: set[str] = set()
    for fact in facts:
        required = {"fact_id", "text", "source_support_ids", "entities", "relation", "values", "qualifiers"}
        missing = required - set(fact)
        if missing:
            raise ValueError(f"Fact spec {spec.get('instance_id')} is missing {sorted(missing)}")
        if fact["fact_id"] in fact_ids:
            raise ValueError(f"Duplicate fact ID {fact['fact_id']} in {spec.get('instance_id')}")
        fact_ids.add(fact["fact_id"])
        unknown = set(fact["source_support_ids"]) - support_ids
        if unknown:
            raise ValueError(f"Fact {fact['fact_id']} references unknown supports {sorted(unknown)}")
    for support_set in spec.get("complete_support_sets", []):
        unknown = set(support_set) - fact_ids
        if unknown:
            raise ValueError(f"Unknown fact IDs in complete_support_sets: {sorted(unknown)}")
    return facts


def build_label_tasks(
    trace_packages: Iterable[dict[str, Any]], fact_specs: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Produce blinded, checkpoint-level tasks for each fact and annotator."""
    packages = {(p["source_id"], p["instance_id"]): p for p in trace_packages}
    specs = {(s["source_id"], s["instance_id"]): s for s in fact_specs}
    if set(packages) != set(specs):
        missing = set(packages) - set(specs)
        extra = set(specs) - set(packages)
        raise ValueError(f"Fact-spec/package mismatch; missing={sorted(missing)}, extra={sorted(extra)}")

    tasks: list[dict[str, Any]] = []
    for key in sorted(packages):
        package = packages[key]
        spec = specs[key]
        facts = _validate_fact_spec(spec, package)
        for fact in facts:
            source_ids = set(fact["source_support_ids"])
            for checkpoint, units in package["checkpoints"].items():
                visible_units = units
                if checkpoint == "source":
                    visible_units = [unit for unit in units if unit["unit_id"] in source_ids]
                task_id = f"{package['source_id']}::{package['instance_id']}::{fact['fact_id']}::{checkpoint}"
                tasks.append({
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "source_id": package["source_id"],
                    "instance_id": package["instance_id"],
                    "fact_id": fact["fact_id"],
                    "question": package["question"],
                    "fact": fact,
                    "checkpoint": checkpoint,
                    "evidence_units": visible_units,
                    "label": None,
                    "annotator_id": "",
                    "rationale": "",
                    "instructions": (
                        "Label whether the atomic fact is expressed in the evidence at this checkpoint: "
                        "faithful (all entities, relation, values, and qualifiers preserved), partial "
                        "(related but a required element omitted), distorted (a required element changed "
                        "or contradicted), absent, or uncertain. Do not infer facts not stated in the evidence."
                    ),
                })
    return tasks


def _require_annotation_labels(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = record.get("task_id")
        label = record.get("label")
        if not task_id:
            raise ValueError("Every annotation record needs task_id")
        if label not in LABELS:
            raise ValueError(f"{task_id} has invalid label {label!r}; expected one of {LABELS}")
        if task_id in output:
            raise ValueError(f"Duplicate annotation task_id {task_id}")
        output[task_id] = record
    return output


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float | None:
    """Unweighted Cohen's kappa without a third-party statistics dependency."""
    if not labels_a or len(labels_a) != len(labels_b):
        return None
    observed = sum(a == b for a, b in zip(labels_a, labels_b)) / len(labels_a)
    a_counts, b_counts = Counter(labels_a), Counter(labels_b)
    expected = sum((a_counts[label] / len(labels_a)) * (b_counts[label] / len(labels_a)) for label in LABELS)
    if expected == 1.0:
        return 1.0 if observed == 1.0 else None
    return (observed - expected) / (1.0 - expected)


def build_adjudication_tasks(
    annotations_a: Iterable[dict[str, Any]], annotations_b: Iterable[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge independent labels, auto-resolving exact agreements only."""
    first, second = _require_annotation_labels(annotations_a), _require_annotation_labels(annotations_b)
    if set(first) != set(second):
        raise ValueError("Annotator files do not contain the same task IDs")
    task_ids = sorted(first)
    labels_a, labels_b = [first[key]["label"] for key in task_ids], [second[key]["label"] for key in task_ids]
    output: list[dict[str, Any]] = []
    for task_id in task_ids:
        a, b = first[task_id], second[task_id]
        agreed = a["label"] == b["label"]
        output.append({
            **{key: value for key, value in a.items() if key not in {"label", "annotator_id", "rationale"}},
            "annotator_a": {"id": a.get("annotator_id", ""), "label": a["label"], "rationale": a.get("rationale", "")},
            "annotator_b": {"id": b.get("annotator_id", ""), "label": b["label"], "rationale": b.get("rationale", "")},
            "agreement": agreed,
            "final_label": a["label"] if agreed else None,
            "adjudication_reason": "agreed independently" if agreed else "",
        })
    agreement = {
        "schema_version": SCHEMA_VERSION,
        "n_tasks": len(task_ids),
        "n_agreed": sum(a == b for a, b in zip(labels_a, labels_b)),
        "percent_agreement": sum(a == b for a, b in zip(labels_a, labels_b)) / len(task_ids) if task_ids else None,
        "cohen_kappa": cohen_kappa(labels_a, labels_b),
        "label_counts_annotator_a": dict(Counter(labels_a)),
        "label_counts_annotator_b": dict(Counter(labels_b)),
    }
    return output, agreement


def _legacy_match(fact_text: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    """The deployed numerical/lexical coverage rule, applied to an atomic fact."""
    fact_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", fact_text))
    fact_tokens = set(fact_text.lower().split())
    best_score, best_id = 0.0, None
    for unit in units:
        text = unit["text"]
        numbers = set(re.findall(r"-?\d+(?:\.\d+)?", text))
        tokens = set(text.lower().split())
        numeric = len(fact_numbers & numbers) / len(fact_numbers) if fact_numbers and numbers else 0.0
        denom = len(fact_tokens | tokens)
        jaccard = len(fact_tokens & tokens) / denom if denom else 0.0
        score = max(numeric, jaccard)
        if score > best_score:
            best_score, best_id = score, unit["unit_id"]
    return {"covered": best_score > 0.0, "score": best_score, "best_unit_id": best_id}


def _complete_status(fact_labels: dict[str, str], support_sets: list[list[str]]) -> bool | None:
    """Return complete/incomplete/unknown, respecting alternative support sets."""
    sets = support_sets or [sorted(fact_labels)]
    has_unknown = False
    for support_set in sets:
        labels = [fact_labels.get(fact_id) for fact_id in support_set]
        if all(label == "faithful" for label in labels):
            return True
        if any(label in {None, "uncertain"} for label in labels):
            has_unknown = True
    return None if has_unknown else False


def _binary_metrics(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    tp = sum(predicted and actual for predicted, actual in pairs)
    fp = sum(predicted and not actual for predicted, actual in pairs)
    tn = sum(not predicted and not actual for predicted, actual in pairs)
    fn = sum(not predicted and actual for predicted, actual in pairs)
    n = len(pairs)
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": (tp + tn) / n if n else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def analyze_adjudicated_labels(
    trace_packages: Iterable[dict[str, Any]],
    fact_specs: Iterable[dict[str, Any]],
    adjudicated: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Compute semantic coverage, matcher error, and non-exclusive diagnoses."""
    packages = {(p["source_id"], p["instance_id"]): p for p in trace_packages}
    specs = {(s["source_id"], s["instance_id"]): s for s in fact_specs}
    labels: dict[tuple[str, str, str, str], str] = {}
    unresolved: list[str] = []
    for record in adjudicated:
        final = record.get("final_label")
        if final not in LABELS:
            unresolved.append(record.get("task_id", "unknown"))
            continue
        labels[(record["source_id"], record["instance_id"], record["fact_id"], record["checkpoint"])] = final
    if unresolved:
        raise ValueError(f"{len(unresolved)} labels remain unadjudicated (e.g. {unresolved[0]})")

    report_sources: dict[str, Any] = {}
    for source_id in sorted({source for source, _ in packages}):
        source_packages = [package for (source, _), package in packages.items() if source == source_id]
        semantic_by_checkpoint: dict[str, list[bool]] = defaultdict(list)
        complete_by_checkpoint: dict[str, list[bool]] = defaultdict(list)
        matcher_pairs_by_checkpoint: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
        semantic_stages: Counter[str] = Counter()
        proxy_stages: Counter[str] = Counter()
        evaluable_stage_instances = 0
        proxy_stage_instances = 0

        for package in source_packages:
            spec = specs.get((source_id, package["instance_id"]))
            if spec is None:
                raise ValueError(f"Missing fact spec for {source_id}:{package['instance_id']}")
            facts = _validate_fact_spec(spec, package)
            fact_ids = [fact["fact_id"] for fact in facts]
            checkpoint_labels: dict[str, dict[str, str]] = defaultdict(dict)
            checkpoint_proxy: dict[str, dict[str, bool]] = defaultdict(dict)
            for fact in facts:
                for checkpoint, units in package["checkpoints"].items():
                    label = labels.get((source_id, package["instance_id"], fact["fact_id"], checkpoint))
                    if label is None:
                        raise ValueError(f"Missing adjudicated label for {source_id}:{package['instance_id']}:{fact['fact_id']}:{checkpoint}")
                    checkpoint_labels[checkpoint][fact["fact_id"]] = label
                    checkpoint_proxy[checkpoint][fact["fact_id"]] = _legacy_match(fact["text"], units)["covered"]
                    if label != "uncertain":
                        semantic_by_checkpoint[checkpoint].append(label == "faithful")
                        matcher_pairs_by_checkpoint[checkpoint].append(
                            (checkpoint_proxy[checkpoint][fact["fact_id"]], label == "faithful")
                        )

            for checkpoint, fact_labels in checkpoint_labels.items():
                semantic_complete = _complete_status(fact_labels, spec.get("complete_support_sets", []))
                if semantic_complete is not None:
                    complete_by_checkpoint[checkpoint].append(semantic_complete)

            required = {checkpoint for checkpoint in ("source", "extraction", "transmission", "board") if checkpoint in checkpoint_labels}
            if all(checkpoint_labels[checkpoint][fact_id] != "uncertain" for checkpoint in required for fact_id in fact_ids):
                evaluable_stage_instances += 1
                instance_semantic_stages: set[str] = set()
                for fact_id in fact_ids:
                    source_label = checkpoint_labels.get("source", {}).get(fact_id, "faithful")
                    extraction = checkpoint_labels.get("extraction", {}).get(fact_id)
                    transmission = checkpoint_labels.get("transmission", {}).get(fact_id)
                    if source_label == "faithful" and extraction == "absent":
                        instance_semantic_stages.add("extraction_omission")
                    if extraction == "faithful" and transmission == "absent":
                        instance_semantic_stages.add("selection_omission")
                    if extraction == "faithful" and transmission in {"partial", "distorted"}:
                        instance_semantic_stages.add("transmission_nonfaithful")
                board_complete = _complete_status(checkpoint_labels["board"], spec.get("complete_support_sets", []))
                if board_complete and not package["answer_correct"]:
                    instance_semantic_stages.add("candidate_aggregation_failure")
                semantic_stages.update(instance_semantic_stages)

            if all(checkpoint in checkpoint_proxy for checkpoint in required):
                proxy_stage_instances += 1
                instance_proxy_stages: set[str] = set()
                for fact_id in fact_ids:
                    extraction = checkpoint_proxy.get("extraction", {}).get(fact_id)
                    transmission = checkpoint_proxy.get("transmission", {}).get(fact_id)
                    if extraction is False:
                        instance_proxy_stages.add("extraction_omission")
                    if extraction and not transmission:
                        instance_proxy_stages.add("selection_omission")
                proxy_labels = {
                    fact_id: "faithful" if covered else "absent"
                    for fact_id, covered in checkpoint_proxy["board"].items()
                }
                proxy_complete = _complete_status(proxy_labels, spec.get("complete_support_sets", [])) is True
                if proxy_complete and not package["answer_correct"]:
                    instance_proxy_stages.add("candidate_aggregation_failure")
                proxy_stages.update(instance_proxy_stages)

        report_sources[source_id] = {
            "n_instances": len(source_packages),
            "sample_strata": dict(Counter(package["sample_stratum"] for package in source_packages)),
            "semantic_fact_recall": {
                checkpoint: sum(values) / len(values) if values else None
                for checkpoint, values in sorted(semantic_by_checkpoint.items())
            },
            "complete_support_coverage": {
                checkpoint: {
                    "n_evaluable": len(values),
                    "n_complete": sum(values),
                    "rate": sum(values) / len(values) if values else None,
                }
                for checkpoint, values in sorted(complete_by_checkpoint.items())
            },
            "lexical_matcher_vs_semantic": {
                checkpoint: _binary_metrics(pairs)
                for checkpoint, pairs in sorted(matcher_pairs_by_checkpoint.items())
            },
            # Kept as a convenient stable field for downstream table code.
            "lexical_matcher_vs_semantic_board": _binary_metrics(matcher_pairs_by_checkpoint["board"]),
            "semantic_stage_breakdown": {
                "n_evaluable_instances": evaluable_stage_instances,
                "counts": dict(semantic_stages),
                "note": "Counts are non-exclusive instance diagnoses; do not treat them as a partition.",
            },
            "lexical_proxy_stage_breakdown": {
                "n_instances": proxy_stage_instances,
                "counts": dict(proxy_stages),
                "note": "Proxy uses the original positive-overlap matcher on atomic facts; it cannot assess distortion.",
            },
        }
    return {"schema_version": SCHEMA_VERSION, "sources": report_sources}


def build_repair_manifest(
    trace_packages: Iterable[dict[str, Any]],
    fact_specs: Iterable[dict[str, Any]],
    adjudicated: Iterable[dict[str, Any]],
    *,
    development_size: int = 0,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Freeze Extension-B inputs from adjudicated semantic labels.

    The returned records deliberately contain no model-generated repair.  A
    researcher must fill ``volume_control_text`` with a source-grounded,
    non-critical, length-matched control before an execution runner will send
    any requests.  This makes the oracle/practical distinction auditable.
    """
    packages = {(p["source_id"], p["instance_id"]): p for p in trace_packages}
    specs = {(s["source_id"], s["instance_id"]): s for s in fact_specs}
    final_labels: dict[tuple[str, str, str, str], str] = {}
    for record in adjudicated:
        label = record.get("final_label")
        if label not in LABELS:
            raise ValueError(f"Unadjudicated or invalid label in {record.get('task_id', 'unknown')}")
        final_labels[(
            record["source_id"], record["instance_id"], record["fact_id"], record["checkpoint"],
        )] = label

    manifests: list[dict[str, Any]] = []
    for key in sorted(packages):
        package = packages[key]
        spec = specs.get(key)
        if spec is None:
            raise ValueError(f"Missing fact spec for {key[0]}:{key[1]}")
        facts = _validate_fact_spec(spec, package)
        missing: list[dict[str, Any]] = []
        target_support_ids: set[str] = set()
        for fact in facts:
            label = final_labels.get((key[0], key[1], fact["fact_id"], "board"))
            if label is None:
                raise ValueError(f"Missing board label for {key[0]}:{key[1]}:{fact['fact_id']}")
            if label == "uncertain":
                raise ValueError(f"Cannot freeze repair diagnosis with uncertain board label: {key[1]}:{fact['fact_id']}")
            if label != "faithful":
                missing.append({
                    "fact_id": fact["fact_id"],
                    "text": fact["text"],
                    "board_label": label,
                    "source_support_ids": list(fact["source_support_ids"]),
                    # Optional human-specified IDs for removing a distorted unit
                    # before restoring the faithful fact.
                    "remove_board_unit_ids": [],
                })
                target_support_ids.update(fact["source_support_ids"])

        if missing:
            diagnosis = "evidence_deficient"
        elif package["answer_correct"]:
            diagnosis = "baseline_correct"
        else:
            diagnosis = "semantically_complete"

        manifests.append({
            "schema_version": "repair-study-v1",
            "source_id": package["source_id"],
            "dataset": package["dataset"],
            "protocol": package["protocol"],
            "instance_id": package["instance_id"],
            "question": package["question"],
            "gold_answer": package["gold_answer"],
            "diagnosis": diagnosis,
            "baseline": {
                "pred": package.get("baseline_prediction", ""),
                "f1": package["answer_f1"],
                "correct": package["answer_correct"],
                "comm_tokens": package.get("baseline_comm_tokens", 0),
                "total_llm_tokens": package.get("baseline_total_llm_tokens", 0),
            },
            "board_units": package["checkpoints"]["board"],
            "source_supports": package["source_supports"],
            "oracle_facts": missing,
            "target_support_ids": sorted(target_support_ids),
            "volume_control_text": "",
            "volume_control_source_support_ids": [],
            "freeze_note": (
                "Generated from adjudicated labels. Fill volume_control_text and, when needed, "
                "remove_board_unit_ids before evaluation; do not alter diagnosis, target supports, or oracle facts."
            ),
        })
    # The development split is selected only after labels establish the frozen
    # diagnosis.  It is stratified by diagnosis so prompt/rule design sees each
    # observed failure type, while all remaining records remain held out.
    if development_size < 0 or development_size >= len(manifests):
        if development_size:
            raise ValueError("development_size must be smaller than the number of repair records")
    for record in manifests:
        record["evaluation_split"] = "held_out"
    if development_size:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in manifests:
            groups[record["diagnosis"]].append(record)
        rng = random.Random(seed)
        selected: list[dict[str, Any]] = []
        total = len(manifests)
        for diagnosis in sorted(groups):
            group = sorted(groups[diagnosis], key=lambda item: item["instance_id"])
            quota = min(len(group), round(development_size * len(group) / total))
            selected.extend(rng.sample(group, quota))
        remaining = [record for record in manifests if record not in selected]
        if len(selected) < development_size:
            selected.extend(rng.sample(remaining, development_size - len(selected)))
        elif len(selected) > development_size:
            selected = sorted(selected, key=lambda item: item["instance_id"])[:development_size]
        for record in selected:
            record["evaluation_split"] = "development"
    return manifests
