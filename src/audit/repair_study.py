"""Paired Extension-B repair study with frozen, auditable diagnoses.

The module accepts manifests emitted by ``build_repair_manifest``.  It never
chooses a diagnosis after seeing an intervention outcome.  The command-line
runner defaults to dry-run; API calls require an explicit ``--execute``.
"""

from __future__ import annotations

import ast
import math
import random
import re
from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from utility.apis.base import APIRequest, APIResponse
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import count_tokens_approx, extract_answer
from src.protocols.relay import _EXTRACTION_SYSTEM, _build_extraction_prompt, _parse_units


SCHEMA_VERSION = "repair-study-v1"
CONDITIONS = (
    "baseline",
    "oracle_evidence_repair",
    "practical_evidence_repair",
    "volume_control",
    "aggregation_repair",
    "generic_retry",
)

AUDIT_SCHEMA_VERSION = "audit-repair-study-v1"
AUDIT_CONDITIONS = ("baseline", "audited_evidence_repair", "audited_aggregation_repair", "generic_retry")

_AGGREGATION_SYSTEM = (
    "You are a question-answering assistant. Use only the supplied evidence. "
    "Reason through the evidence privately, then finish your response with the exact line "
    "ANSWER: <concise answer>. Do not omit that line, even if you are uncertain."
)
_REPAIR_AGGREGATION_SYSTEM = (
    "You are a careful evidence-integration assistant. Use only the supplied evidence. "
    "Before answering, silently verify entities, relations, numbers, and dependencies across the evidence. "
    "Reason privately, then finish your response with the exact line "
    "ANSWER: <concise answer>. Do not omit that line, even if you are uncertain."
)

# Strong-repair condition.  The verifier has an intentionally concrete output
# contract so the intervention is more than an instruction to "be careful".
_AUDITED_VERIFIER_SYSTEM = (
    "You are an evidence verifier. Use only the supplied evidence board. "
    "Build a compact verification ledger before answering: identify the relevant entities, "
    "relations, numerical values, and cross-unit dependencies; reconcile any conflict; and state "
    "the answer entailed by the board. Do not use outside knowledge."
)
_NEUTRAL_CONSOLIDATOR_SYSTEM = (
    "You are an evidence consolidation assistant. Use only the supplied evidence board. "
    "Produce a compact ledger of the board facts that are relevant to the question, retaining "
    "their unit numbers and wording. Do not add outside knowledge or perform a special audit."
)
_FINAL_ANSWER_SYSTEM = (
    "You are a question-answering assistant. Use only the evidence board and the supplied working ledger. "
    "Return exactly one line and nothing else: ANSWER: <concise answer>. "
    "Do not omit that line, even if the evidence is insufficient."
)
_AUDITED_FINAL_ANSWER_SYSTEM = (
    "You are a careful question-answering assistant. Use only the evidence board and the supplied verification ledger. "
    "Treat the ledger as an untrusted draft: independently cross-check every answer-critical entity, relation, number, "
    "and dependency against the original evidence board before answering. Correct any ledger error rather than copying it. "
    "Return exactly one line and nothing else: ANSWER: <concise answer>. "
    "Do not omit that line, even if the evidence is insufficient."
)
_MUSIQUE_PATH_SYSTEM = (
    "You are a support-path extractor for a multi-hop QA benchmark. Treat every proposition in the evidence board "
    "as an axiom of the benchmark world, even if it conflicts with your world knowledge or another source. "
    "Do not correct, reject, or fact-check a board statement using outside knowledge. Starting from the entities in "
    "the question, construct the shortest answer-bearing chain of relations. Every hop must cite one or more board "
    "unit numbers. Return these fields exactly: ANSWER_PATH, with one cited hop per line; ANSWER_CANDIDATE; and "
    "MISSING_HOP only when no cited board unit supplies a required hop."
)
_MUSIQUE_PATH_FINAL_SYSTEM = (
    "You are a multi-hop QA answerer. The evidence board is the complete benchmark world. Use only its cited "
    "support path, never world knowledge, to answer. Do not reject a cited path because it seems implausible. "
    "Return exactly one line and nothing else: ANSWER: <concise answer>."
)
_MUSIQUE_GRAPH_SYSTEM = (
    "You are a structured support-path extractor for a multi-hop QA benchmark. Treat every proposition in the "
    "evidence board as an axiom of the benchmark world; never correct it using outside knowledge. Derive the "
    "answer only by binding the entities and relation requested in the question. Return exactly these fields. "
    "QUESTION_ENTITIES: the question entities and any requested answer variable. TARGET_RELATION: the relation "
    "that must connect them. Then write one EDGE_i per required hop in the exact form `EDGE_i: [unit numbers] "
    "subject | relation | object`; each cited unit number must be from the board. The object of each edge must "
    "supply the subject of the next edge, and the last object must answer the requested variable. PATH_STATUS: "
    "COMPLETE only if every required relation is covered; otherwise INCOMPLETE. ANSWER_CANDIDATE: the last object "
    "only for a COMPLETE path, otherwise UNKNOWN."
)
_MUSIQUE_GRAPH_FINAL_SYSTEM = (
    "You are a constrained multi-hop QA answerer. Treat the evidence board as the benchmark world. Use only the "
    "structured ledger's cited EDGE_i lines, not world knowledge and not uncited board text. Answer only when "
    "PATH_STATUS is COMPLETE and the final edge object answers the question's requested variable; otherwise return "
    "ANSWER: UNKNOWN. Return exactly one line and nothing else: ANSWER: <concise answer>."
)
_VISIBLE_EXTRACTION_SYSTEM = (
    "You are an evidence extraction assistant. Return one to three nonempty, numbered, atomic facts directly "
    "supported by the shard and useful for the question. Do not reason privately, do not use outside knowledge, "
    "and do not output anything except the numbered facts."
)


def _silo_task_id(record: dict[str, Any]) -> str:
    """Return a stable Silo-Bench task id, e.g. ``II-15``."""
    return str(record["instance_id"]).rsplit("_n", 1)[0]


# v2 deliberately covered only the small reductions confirmed before the
# first bottleneck-aware execution.  v3 broadens that declared executor
# family; keeping the sets separate makes historical v2 runs reproducible.
_SILO_V2_EXECUTABLE_TASKS = frozenset({"I-01", "I-02", "I-05", "I-06", "I-08", "II-15", "II-16", "III-26"})
_SILO_V3_EXECUTABLE_TASKS = _SILO_V2_EXECUTABLE_TASKS | frozenset({
    "I-07", "I-10", "II-12", "II-17", "II-18", "III-22", "III-23", "III-24", "III-25", "III-27", "III-28", "III-29", "III-30",
})


def _literal_shards(record: dict[str, Any]) -> list[Any] | None:
    """Parse Silo's local JSON/Python-literal shards without executing data."""
    try:
        parsed = []
        for context in sorted(record["source_contexts"], key=lambda context: int(context["agent_id"])):
            raw = str(context["text"])
            try:
                parsed.append(ast.literal_eval(raw))
            except (SyntaxError, ValueError):
                # Character-sequence tasks store their shard as bare text,
                # rather than a quoted Python literal.
                parsed.append(raw)
        return parsed
    except (TypeError, KeyError):
        return None


def _deterministic_silo_repair(
    record: dict[str, Any], *, supported_task_ids: frozenset[str] = _SILO_V2_EXECUTABLE_TASKS,
) -> str | None:
    """Execute small, unambiguous distributed reductions on the original shards.

    This is deliberately limited to task templates whose semantics are fully
    specified by the benchmark prompt.  Unknown templates fall back to the LLM
    path rather than silently guessing a benchmark-specific program.
    """
    if record["dataset"] != "silobench":
        return None
    task_id = _silo_task_id(record)
    if task_id not in supported_task_ids:
        return None
    shards = _literal_shards(record)
    if shards is None:
        return None
    flat = [item for shard in shards for item in shard]
    question = str(record["question"])
    if task_id == "I-01":
        return str(max(flat))
    if task_id == "I-02":
        target = re.search(r'word\s+"([^"\\]+)"', question, flags=re.IGNORECASE)
        return str(sum(str(item) == target.group(1) for item in flat)) if target else None
    if task_id == "I-05":
        bounds = re.search(r"\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]", question)
        if bounds:
            lower, upper = map(int, bounds.groups())
            return str(sum(lower <= int(value) <= upper for value in flat))
    if task_id == "I-06":
        value = 0
        for item in flat:
            value ^= int(item)
        return str(value)
    if task_id in {"I-08", "III-26"}:
        return str(len(set(flat)))
    if task_id == "II-15":
        state = count = 0
        for char in "".join(str(shard) for shard in shards):
            if state == 0 and char == "A":
                state = 1
            elif state == 1 and char == "B":
                state = 2
            elif state == 2 and char == "C":
                count += 1
                state = 0
        return str(count)
    if task_id == "II-16":
        heights = [int(value) for value in flat]
        if not heights:
            return "0"
        left = [0] * len(heights)
        right = [0] * len(heights)
        left[0] = heights[0]
        for index in range(1, len(heights)):
            left[index] = max(left[index - 1], heights[index])
        right[-1] = heights[-1]
        for index in range(len(heights) - 2, -1, -1):
            right[index] = max(right[index + 1], heights[index])
        return str(sum(min(left[index], right[index]) - height for index, height in enumerate(heights)))
    if task_id == "II-17":
        values = [int(value) for value in flat]
        return str([values[index] - values[index - 1] for index in range(1, len(values))])
    if task_id == "I-07":
        return str(round(sum(float(value) for value in flat) / len(flat), 2)) if flat else None
    if task_id == "I-10":
        if not flat:
            return None
        values = [float(value) for value in flat]
        mean = sum(values) / len(values)
        return str(round(math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)), 2))
    if task_id == "II-12":
        values = [float(value) for value in flat]
        return str([round((values[index - 1] + values[index] + values[index + 1]) / 3, 2)
                    for index in range(1, len(values) - 1)])
    if task_id == "II-18":
        pointers: dict[int, int] = {}
        for shard in shards:
            if not isinstance(shard, list):
                return None
            for node in shard:
                if not isinstance(node, dict) or set(("id", "next")) - set(node):
                    return None
                node_id, next_id = int(node["id"]), int(node["next"])
                if node_id in pointers:
                    return None
                pointers[node_id] = next_id
        heads = set(pointers) - {next_id for next_id in pointers.values() if next_id != -1}
        expected = re.search(r"Total nodes:\s*(\d+)", question)
        if len(heads) != 1 or (expected and len(pointers) != int(expected.group(1))):
            return None
        ranks: dict[str, int] = {}
        node = next(iter(heads))
        while node != -1 and node not in ranks:
            if node not in pointers:
                return None
            ranks[str(node)] = len(ranks)
            node = pointers[node]
        return str(ranks) if node == -1 and len(ranks) == len(pointers) else None
    if task_id == "III-22":
        values = sorted(int(value) for value in flat)
        return str(values[len(values) // 2]) if values and len(values) % 2 else None
    if task_id == "III-23":
        total = re.search(r"Total nodes:\s*(\d+)", question)
        if not total:
            return None
        parent = list(range(int(total.group(1))))

        def find(node: int) -> int:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        for shard in shards:
            if not isinstance(shard, list):
                return None
            for edge in shard:
                if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                    return None
                left, right = map(int, edge)
                root_left, root_right = find(left), find(right)
                if root_left != root_right:
                    parent[root_right] = root_left
        return str(len({find(node) for node in range(len(parent))}))
    if task_id == "III-24":
        total = re.search(r"Total nodes:\s*(\d+)", question)
        if not total:
            return None
        node_count = int(total.group(1))
        graph: dict[int, list[int]] = defaultdict(list)
        for shard in shards:
            if not isinstance(shard, list):
                return None
            for edge in shard:
                if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                    return None
                left, right = map(int, edge)
                graph[left].append(right)
                graph[right].append(left)
        distances = {0: 0}
        queue: deque[int] = deque([0])
        while queue:
            node = queue.popleft()
            for neighbor in graph[node]:
                if neighbor not in distances:
                    distances[neighbor] = distances[node] + 1
                    queue.append(neighbor)
        return str({str(node): distances.get(node, -1) for node in range(node_count)})
    if task_id == "III-25":
        match = re.search(r"Initial centroids:\s*(\[[^\n]+?\])\s+\*\*", question)
        if not match:
            return None
        try:
            centroids = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            return None
        points = [tuple(map(float, point)) for shard in shards for point in shard]
        if len(centroids) != 3 or any(len(point) != 2 for point in points):
            return None
        groups: list[list[tuple[float, float]]] = [[] for _ in centroids]
        for point in points:
            cluster = min(range(len(centroids)), key=lambda index: sum((point[axis] - centroids[index][axis]) ** 2 for axis in range(2)))
            groups[cluster].append(point)
        if any(not group for group in groups):
            return None
        return str([[round(sum(point[axis] for point in group) / len(group), 2) for axis in range(2)] for group in groups])
    if task_id == "III-27":
        users: dict[str, list[float]] = {}
        items: dict[str, list[float]] = {}
        for shard in shards:
            if not isinstance(shard, dict) or set(("users", "items")) - set(shard):
                return None
            users.update(shard["users"])
            items.update(shard["items"])
        scores = []
        for user_id, user_vector in users.items():
            for item_id, item_vector in items.items():
                if len(user_vector) != len(item_vector):
                    return None
                scores.append((int(user_id), int(item_id), sum(float(left) * float(right) for left, right in zip(user_vector, item_vector))))
        return str([[user_id, item_id, round(score, 4)] for user_id, item_id, score in sorted(scores, key=lambda item: (-item[2], item[0], item[1]))[:3]])
    if task_id == "III-28":
        total = re.search(r"Total nodes:\s*(\d+)", question)
        if not total:
            return None
        node_count = int(total.group(1))
        edges = [tuple(map(int, edge)) for shard in shards for edge in shard]
        if any(len(edge) != 2 for edge in edges):
            return None
        out_degree: dict[int, int] = defaultdict(int)
        for source, _ in edges:
            out_degree[source] += 1
        rank = {node: (1 - 0.85) / node_count for node in range(node_count)}
        for source, target in edges:
            rank[target] += 0.85 * (1 / node_count) / out_degree[source]
        return str({str(node): round(rank[node], 6) for node in range(node_count)})
    if task_id == "III-29":
        tasks = [task for shard in shards for task in shard]
        if any(not isinstance(task, dict) or set(("id", "duration")) - set(task) for task in tasks):
            return None
        loads = [0] * len(shards)
        for task in sorted(tasks, key=lambda task: (-int(task["duration"]), int(task["id"]))):
            agent = min(range(len(loads)), key=lambda index: (loads[index], index))
            loads[agent] += int(task["duration"])
        mean = sum(loads) / len(loads)
        return str({"variance": round(sum((load - mean) ** 2 for load in loads) / len(loads), 2),
                    "max_load": max(loads), "min_load": min(loads)})
    if task_id == "III-30":
        rows: dict[int, list[int]] = {}
        matrix_b: list[list[int]] | None = None
        for shard in shards:
            if not isinstance(shard, dict) or set(("A_rows", "A_row_indices", "B_matrix")) - set(shard):
                return None
            if len(shard["A_rows"]) != len(shard["A_row_indices"]):
                return None
            if matrix_b is None:
                matrix_b = shard["B_matrix"]
            elif matrix_b != shard["B_matrix"]:
                return None
            for index, row in zip(shard["A_row_indices"], shard["A_rows"]):
                index = int(index)
                if index in rows:
                    return None
                rows[index] = [int(value) for value in row]
        if matrix_b is None or set(rows) != set(range(len(matrix_b))) or any(len(row) != len(matrix_b) for row in rows.values()):
            return None
        return str([[sum(rows[row][column] * matrix_b[column][target] for column in range(len(matrix_b)))
                     for target in range(len(matrix_b[0]))] for row in range(len(matrix_b))])
    return None


_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def _canonical_small_number(text: str) -> int | None:
    """Map a standalone digit or English number phrase to an integer."""
    cleaned = re.sub(r"[^a-z0-9 -]", "", text.lower()).strip()
    if re.fullmatch(r"-?\d+", cleaned):
        return int(cleaned)
    tokens = [token for token in cleaned.replace("-", " ").split() if token]
    if not tokens or any(token not in _NUMBER_WORDS and token != "hundred" for token in tokens):
        return None
    total = current = 0
    for token in tokens:
        if token == "hundred":
            if current == 0:
                return None
            current *= 100
        else:
            current += _NUMBER_WORDS[token]
    return total + current


def _repair_answer_f1(pred: str, gold: str) -> float:
    """Use standard MuSiQue F1, with a narrow numeric surface-form alias."""
    pred_number = _canonical_small_number(pred)
    gold_number = _canonical_small_number(gold)
    if pred_number is not None and pred_number == gold_number:
        return 1.0
    return answer_f1(pred, {"answer": gold, "answer_aliases": []})


def validate_manifest(records: Iterable[dict[str, Any]], *, require_volume_controls: bool = False) -> list[dict[str, Any]]:
    """Validate frozen inputs before planning or executing a study."""
    checked = list(records)
    seen: set[tuple[str, str]] = set()
    required = {
        "schema_version", "source_id", "dataset", "protocol", "instance_id", "question", "gold_answer",
        "diagnosis", "baseline", "board_units", "source_supports", "source_contexts", "oracle_facts", "target_support_ids",
        "volume_control_text", "evaluation_split",
    }
    for record in checked:
        missing = required - set(record)
        if missing:
            raise ValueError(f"Repair manifest missing {sorted(missing)}")
        if record["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"Unsupported repair manifest schema: {record['schema_version']}")
        if record["dataset"] not in {"musique", "silobench"}:
            raise ValueError(f"Unknown dataset: {record['dataset']}")
        if record["protocol"] != "score_ranked_relay":
            raise ValueError("Extension B is defined only for score_ranked_relay")
        if record["diagnosis"] not in {"evidence_deficient", "semantically_complete", "baseline_correct"}:
            raise ValueError(f"Unknown diagnosis: {record['diagnosis']}")
        if record["evaluation_split"] not in {"development", "held_out"}:
            raise ValueError(f"Unknown evaluation split: {record['evaluation_split']}")
        identity = (record["source_id"], record["instance_id"])
        if identity in seen:
            raise ValueError(f"Duplicate repair manifest record: {identity}")
        seen.add(identity)
        if require_volume_controls and not str(record["volume_control_text"]).strip():
            raise ValueError(f"volume_control_text must be filled before execution: {identity}")
        if require_volume_controls and not record.get("volume_control_source_support_ids"):
            raise ValueError(f"volume_control_source_support_ids must document the control source: {identity}")
        if record["diagnosis"] == "evidence_deficient" and not record["oracle_facts"]:
            raise ValueError(f"Evidence-deficient record has no oracle facts: {identity}")
        if require_volume_controls and record["diagnosis"] == "evidence_deficient":
            oracle_length = sum(len(str(fact["text"])) for fact in record["oracle_facts"])
            control_length = len(str(record["volume_control_text"]))
            # The control need not be word-identical (and usually cannot be),
            # but should be close enough in size not to confound information
            # quantity with criticality.
            if oracle_length and not 0.5 <= control_length / oracle_length <= 1.5:
                raise ValueError(f"volume_control_text must be length-matched (0.5–1.5× oracle text): {identity}")
    return checked


def planned_call_count(record: dict[str, Any]) -> int:
    """Upper bound on new calls, excluding cached baseline."""
    # Four direct aggregation conditions plus one practical aggregation.  A
    # practical re-extraction is needed only when a frozen diagnosis identifies
    # source supports to revisit.
    return 5 + int(bool(record["target_support_ids"]))


def select_evaluation_records(records: Iterable[dict[str, Any]], *, include_development: bool = False) -> list[dict[str, Any]]:
    """Return held-out records unless an explicit development sanity run is requested."""
    records = validate_manifest(records)
    return records if include_development else [record for record in records if record["evaluation_split"] == "held_out"]


def study_plan(records: Iterable[dict[str, Any]], *, include_development: bool = False) -> dict[str, Any]:
    records = select_evaluation_records(records, include_development=include_development)
    by_dataset: dict[str, int] = defaultdict(int)
    by_diagnosis: dict[str, int] = defaultdict(int)
    for record in records:
        by_dataset[record["dataset"]] += 1
        by_diagnosis[record["diagnosis"]] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "dry-run",
        "n_instances": len(records),
        "instances_by_dataset": dict(sorted(by_dataset.items())),
        "instances_by_diagnosis": dict(sorted(by_diagnosis.items())),
        "conditions": list(CONDITIONS),
        "new_api_calls": sum(planned_call_count(record) for record in records),
        "note": "Baseline is read from cached traces; no request is sent for it.",
    }


def _board_text(units: list[dict[str, Any]]) -> str:
    if not units:
        return "(no evidence available)"
    return "\n".join(f"[{i + 1}] {unit['text']}" for i, unit in enumerate(units))


def _aggregation_request(record: dict[str, Any], board: list[dict[str, Any]], *, repaired: bool, max_tokens: int, condition: str) -> APIRequest:
    return APIRequest(
        system_query=_REPAIR_AGGREGATION_SYSTEM if repaired else _AGGREGATION_SYSTEM,
        user_query=(
            f"Evidence board:\n{_board_text(board)}\n\n"
            f"Question: {record['question']}\n\n"
            "Use the evidence board only. End with exactly: ANSWER: <concise answer>"
        ),
        model="",  # Filled by the caller to make the helper testable.
        max_tokens=max_tokens,
        temperature=0.0,
        metadata={"phase": "repair_aggregation", "condition": condition, "instance_id": record["instance_id"]},
    )


def _with_oracle_facts(record: dict[str, Any]) -> list[dict[str, Any]]:
    remove_ids = {
        unit_id for fact in record["oracle_facts"] for unit_id in fact.get("remove_board_unit_ids", [])
    }
    board = [dict(unit) for unit in record["board_units"] if unit["unit_id"] not in remove_ids]
    existing = {unit["text"].strip() for unit in board}
    for fact in record["oracle_facts"]:
        if fact["text"].strip() not in existing:
            board.append({"unit_id": f"oracle:{fact['fact_id']}", "agent_id": None, "text": fact["text"]})
    return board


def _with_volume_control(record: dict[str, Any]) -> list[dict[str, Any]]:
    board = [dict(unit) for unit in record["board_units"]]
    board.append({"unit_id": "volume-control", "agent_id": None, "text": record["volume_control_text"]})
    return board


def _practical_extraction_request(record: dict[str, Any], model: str, max_tokens: int) -> APIRequest | None:
    support_ids = set(record["target_support_ids"])
    sources = [
        context for context in record["source_contexts"]
        if context["context_id"] in support_ids
    ]
    if not sources:
        return None
    context = "\n\n".join(str(source["text"]) for source in sources)
    return APIRequest(
        system_query=_EXTRACTION_SYSTEM,
        user_query=_build_extraction_prompt(context, record["question"], max_units=3),
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        metadata={"phase": "repair_reextraction", "condition": "practical_evidence_repair", "instance_id": record["instance_id"]},
    )


def _score(record: dict[str, Any], pred: str) -> float:
    instance = {"answer": record["gold_answer"], "answer_aliases": []}
    return silobench_exact_match(pred, instance) if record["dataset"] == "silobench" else _repair_answer_f1(pred, record["gold_answer"])


def _response_result(record: dict[str, Any], condition: str, response: APIResponse, board: list[dict[str, Any]], *, calls: int, extra_tokens: int = 0) -> dict[str, Any]:
    raw = response.content.strip() if response.success else ""
    pred = extract_answer(raw) if raw else ""
    f1 = _score(record, pred)
    baseline_f1 = float(record["baseline"]["f1"])
    baseline_correct = bool(record["baseline"]["correct"])
    correct = f1 >= 1.0
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": record["source_id"], "dataset": record["dataset"], "instance_id": record["instance_id"],
        "diagnosis": record["diagnosis"], "condition": condition,
        "pred": pred, "f1": f1, "correct": correct,
        "baseline_f1": baseline_f1, "baseline_correct": baseline_correct,
        "delta_f1": f1 - baseline_f1,
        "recovered": (not baseline_correct) and correct,
        "damaged": baseline_correct and not correct,
        "comm_tokens": count_tokens_approx(_board_text(board)),
        "total_llm_tokens": response.usage.get("total_tokens", 0) + extra_tokens,
        "api_calls": calls,
        "success": response.success,
        "error": response.error,
    }


def _cached_baseline(record: dict[str, Any]) -> dict[str, Any]:
    baseline = record["baseline"]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": record["source_id"], "dataset": record["dataset"], "instance_id": record["instance_id"],
        "diagnosis": record["diagnosis"], "condition": "baseline",
        "pred": baseline.get("pred", ""), "f1": float(baseline["f1"]), "correct": bool(baseline["correct"]),
        "baseline_f1": float(baseline["f1"]), "baseline_correct": bool(baseline["correct"]),
        "delta_f1": 0.0, "recovered": False, "damaged": False,
        "comm_tokens": int(baseline.get("comm_tokens", 0)),
        "total_llm_tokens": int(baseline.get("total_llm_tokens", 0)), "api_calls": 0,
        "success": True, "error": None,
    }


def run_repair_study(
    records: Iterable[dict[str, Any]],
    *,
    batch_fn: Callable[[list[APIRequest]], list[APIResponse]],
    model: str,
    aggregation_tokens: int = 256,
    repair_tokens: int = 512,
    extraction_tokens: int = 512,
    include_development: bool = False,
) -> list[dict[str, Any]]:
    """Execute all non-baseline repair conditions for frozen records."""
    records = select_evaluation_records(records, include_development=include_development)
    validate_manifest(records, require_volume_controls=True)
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(_cached_baseline(record))

        def aggregate(condition: str, board: list[dict[str, Any]], *, repaired: bool, max_tokens: int, calls: int = 1, extra_tokens: int = 0) -> dict[str, Any]:
            request = _aggregation_request(record, board, repaired=repaired, max_tokens=max_tokens, condition=condition)
            request.model = model
            response = batch_fn([request])[0]
            return _response_result(record, condition, response, board, calls=calls, extra_tokens=extra_tokens)

        base_board = [dict(unit) for unit in record["board_units"]]
        rows.append(aggregate("oracle_evidence_repair", _with_oracle_facts(record), repaired=False, max_tokens=aggregation_tokens))
        rows.append(aggregate("volume_control", _with_volume_control(record), repaired=False, max_tokens=aggregation_tokens))
        rows.append(aggregate("aggregation_repair", base_board, repaired=True, max_tokens=repair_tokens))
        rows.append(aggregate("generic_retry", base_board, repaired=False, max_tokens=repair_tokens))

        extraction_request = _practical_extraction_request(record, model, extraction_tokens)
        practical_board = list(base_board)
        extraction_tokens_used = 0
        practical_calls = 1
        if extraction_request is not None:
            extraction_response = batch_fn([extraction_request])[0]
            extraction_tokens_used = extraction_response.usage.get("total_tokens", 0)
            if extraction_response.success:
                practical_board.extend({
                    "unit_id": f"practical:{index}", "agent_id": None, "text": text,
                } for index, text in enumerate(_parse_units(extraction_response.content, 3)))
            practical_calls = 2
        rows.append(aggregate(
            "practical_evidence_repair", practical_board, repaired=False,
            max_tokens=aggregation_tokens, calls=practical_calls, extra_tokens=extraction_tokens_used,
        ))
    return rows


def _bootstrap_mean_ci(values: list[float], *, seed: int, draws: int = 2_000) -> list[float | None]:
    if not values:
        return [None, None]
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(draws))
    return [means[int(0.025 * (draws - 1))], means[int(0.975 * (draws - 1))]]


def summarize_repair_results(rows: Iterable[dict[str, Any]], *, seed: int = 42) -> dict[str, Any]:
    """Produce Table-4/5-ready paired metrics with instance bootstrap CIs."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["diagnosis"], row["condition"])].append(row)
    summaries = []
    for (dataset, diagnosis, condition), group in sorted(grouped.items()):
        deltas = [float(row["delta_f1"]) for row in group]
        baseline_errors = [row for row in group if not row["baseline_correct"]]
        baseline_correct = [row for row in group if row["baseline_correct"]]
        summaries.append({
            "dataset": dataset, "diagnosis": diagnosis, "condition": condition, "n": len(group),
            "mean_f1": sum(float(row["f1"]) for row in group) / len(group),
            "mean_delta_f1": sum(deltas) / len(deltas),
            "delta_f1_95ci": _bootstrap_mean_ci(deltas, seed=seed),
            "recovery_rate": sum(bool(row["recovered"]) for row in baseline_errors) / len(baseline_errors) if baseline_errors else None,
            "damage_rate": sum(bool(row["damaged"]) for row in baseline_correct) / len(baseline_correct) if baseline_correct else None,
            "mean_comm_tokens": sum(int(row["comm_tokens"]) for row in group) / len(group),
            "mean_total_llm_tokens": sum(int(row["total_llm_tokens"]) for row in group) / len(group),
            "mean_api_calls": sum(int(row["api_calls"]) for row in group) / len(group),
        })
    return {"schema_version": SCHEMA_VERSION, "summaries": summaries}


# Simplified Extension B: cached-audit-guided repair, with no human labels or oracle facts.
def build_audit_repair_manifest(*, dataset: str, run_dir: str | Path, source_id: str,
                                n_agents: int | None = None, sample_size: int = 0,
                                seed: int = 42) -> list[dict[str, Any]]:
    """Freeze automatic audit signals from a cached score-ranked-relay run."""
    from src.audit.critical_fact_validation import build_trace_packages

    run_path = Path(run_dir)
    with (run_path / "audit_metrics.json").open(encoding="utf-8") as handle:
        audit = json.load(handle)
    metric_by_id = {r["inst_id"]: r for r in audit.get("audit_records", {}).get("score_ranked_relay", [])}
    traces = build_trace_packages(dataset=dataset, run_dir=run_path, protocol="score_ranked_relay",
                                  source_id=source_id, n_agents=n_agents,
                                  sample_size=sample_size, seed=seed)
    records: list[dict[str, Any]] = []
    for trace in traces:
        metric = metric_by_id.get(trace["instance_id"])
        if metric is None:
            raise ValueError(f"Missing score_ranked_relay audit record: {trace['instance_id']}")
        correct = bool(trace["answer_correct"])
        signal = (
            "evidence_gap" if not correct and float(metric["crit_recall"]) < 1.0 else
            "aggregation_gap" if not correct and bool(metric["agg_fail"]) else
            "baseline_correct" if correct else "unclassified_error"
        )
        records.append({
            "schema_version": AUDIT_SCHEMA_VERSION, "source_id": source_id, "dataset": dataset,
            "protocol": "score_ranked_relay", "instance_id": trace["instance_id"],
            "question": trace["question"], "gold_answer": trace["gold_answer"], "audit_signal": signal,
            "audit_metrics": {k: metric.get(k) for k in ("crit_recall", "omission", "redundancy", "useful_budget", "agg_fail")},
            "baseline": {"pred": trace.get("baseline_prediction", ""), "f1": trace["answer_f1"],
                         "correct": correct, "comm_tokens": trace.get("baseline_comm_tokens", 0),
                         "total_llm_tokens": trace.get("baseline_total_llm_tokens", 0)},
            "board_units": trace["checkpoints"]["board"], "source_contexts": trace["source_contexts"],
            "freeze_note": "Cached audit signal was created before repair execution.",
        })
    return records


def validate_audit_manifest(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    records = list(records)
    required = {"schema_version", "source_id", "dataset", "protocol", "instance_id", "question", "gold_answer", "audit_signal", "audit_metrics", "baseline", "board_units", "source_contexts"}
    seen: set[tuple[str, str]] = set()
    for record in records:
        if required - set(record):
            raise ValueError(f"Audit repair manifest missing {sorted(required - set(record))}")
        if record["schema_version"] != AUDIT_SCHEMA_VERSION or record["protocol"] != "score_ranked_relay":
            raise ValueError("Unsupported audit repair manifest")
        if record["audit_signal"] not in {"evidence_gap", "aggregation_gap", "baseline_correct", "unclassified_error"}:
            raise ValueError(f"Unknown audit signal: {record['audit_signal']}")
        identity = (record["source_id"], record["instance_id"])
        if identity in seen:
            raise ValueError(f"Duplicate audit repair record: {identity}")
        seen.add(identity)
    return records


def audit_study_plan(records: Iterable[dict[str, Any]], *, repair_strategy: str = "single_pass") -> dict[str, Any]:
    records = validate_audit_manifest(records)
    if repair_strategy not in {"single_pass", "strong_two_stage", "bottleneck_aware_v2", "bottleneck_aware_v3"}:
        raise ValueError(f"Unknown repair strategy: {repair_strategy}")
    signals: dict[str, int] = defaultdict(int)
    calls = 0
    for record in records:
        signal = record["audit_signal"]
        signals[signal] += 1
        executable_tasks = _SILO_V3_EXECUTABLE_TASKS if repair_strategy == "bottleneck_aware_v3" else _SILO_V2_EXECUTABLE_TASKS
        if (repair_strategy in {"bottleneck_aware_v2", "bottleneck_aware_v3"} and signal in {"evidence_gap", "aggregation_gap"}
                and record["dataset"] == "silobench"
                and _deterministic_silo_repair(record, supported_task_ids=executable_tasks) is not None):
            # The audit repair runs locally; only the two-call generic control
            # is sent to the model.  This is reported as a distinct repair
            # engine, rather than being presented as an LLM-only gain.
            calls += 2
        elif repair_strategy in {"strong_two_stage", "bottleneck_aware_v2", "bottleneck_aware_v3"}:
            calls += len(record["source_contexts"]) + 4 if signal == "evidence_gap" else 4 if signal == "aggregation_gap" else 0
        else:
            calls += len(record["source_contexts"]) + 2 if signal == "evidence_gap" else 2 if signal == "aggregation_gap" else 0
    return {"schema_version": AUDIT_SCHEMA_VERSION, "mode": "dry-run", "n_instances": len(records),
            "instances_by_audit_signal": dict(sorted(signals.items())), "conditions": list(AUDIT_CONDITIONS),
            "repair_strategy": repair_strategy, "new_api_calls": calls,
            "note": "Cached baselines are not re-run; only audit-identified error groups receive interventions. Re-extraction retries after an empty response are reported separately."}


def _audit_baseline(record: dict[str, Any]) -> dict[str, Any]:
    baseline = record["baseline"]
    pred = baseline.get("pred", "")
    f1 = _score(record, pred)
    correct = f1 >= 1.0
    return {"schema_version": AUDIT_SCHEMA_VERSION, "source_id": record["source_id"], "dataset": record["dataset"],
            "instance_id": record["instance_id"], "audit_signal": record["audit_signal"], "condition": "baseline",
            "pred": pred, "f1": f1, "correct": correct,
            "baseline_f1": f1, "baseline_correct": correct, "delta_f1": 0.0,
            "recovered": False, "damaged": False, "comm_tokens": int(baseline.get("comm_tokens", 0)),
            "total_llm_tokens": int(baseline.get("total_llm_tokens", 0)), "api_calls": 0, "success": True, "error": None}


def _audit_response(record: dict[str, Any], condition: str, response: APIResponse, board: list[dict[str, Any]], calls: int, extra_tokens: int = 0) -> dict[str, Any]:
    pred = extract_answer(response.content.strip()) if response.success and response.content.strip() else ""
    f1 = _score(record, pred)
    baseline = record["baseline"]
    baseline_f1 = _score(record, baseline.get("pred", ""))
    baseline_correct = baseline_f1 >= 1.0
    correct = f1 >= 1.0
    return {"schema_version": AUDIT_SCHEMA_VERSION, "source_id": record["source_id"], "dataset": record["dataset"],
            "instance_id": record["instance_id"], "audit_signal": record["audit_signal"], "condition": condition,
            "pred": pred, "f1": f1, "correct": correct, "baseline_f1": baseline_f1,
            "baseline_correct": baseline_correct, "delta_f1": f1 - baseline_f1,
            "recovered": not baseline_correct and correct, "damaged": baseline_correct and not correct,
            "comm_tokens": count_tokens_approx(_board_text(board)),
            "total_llm_tokens": response.usage.get("total_tokens", 0) + extra_tokens,
            "api_calls": calls, "success": response.success, "error": response.error}


def _audit_prediction_result(record: dict[str, Any], condition: str, pred: str, board: list[dict[str, Any]], *,
                             calls: int = 0, total_llm_tokens: int = 0, repair_engine: str = "deterministic") -> dict[str, Any]:
    """Record a local deterministic repair without manufacturing an API response."""
    f1 = _score(record, pred)
    baseline = record["baseline"]
    baseline_f1 = _score(record, baseline.get("pred", ""))
    baseline_correct = baseline_f1 >= 1.0
    correct = f1 >= 1.0
    return {"schema_version": AUDIT_SCHEMA_VERSION, "source_id": record["source_id"], "dataset": record["dataset"],
            "instance_id": record["instance_id"], "audit_signal": record["audit_signal"], "condition": condition,
            "pred": pred, "f1": f1, "correct": correct, "baseline_f1": baseline_f1,
            "baseline_correct": baseline_correct, "delta_f1": f1 - baseline_f1,
            "recovered": not baseline_correct and correct,
            "damaged": baseline_correct and not correct,
            "comm_tokens": count_tokens_approx("\n".join(str(context["text"]) for context in record["source_contexts"])),
            "total_llm_tokens": total_llm_tokens, "api_calls": calls, "success": True, "error": None,
            "repair_engine": repair_engine}


def _strong_repair_analysis_request(record: dict[str, Any], board: list[dict[str, Any]], *, audited: bool,
                                    model: str, max_tokens: int, condition: str,
                                    evidence_as_given_path: bool = False, structured_path: bool = False) -> APIRequest:
    """Create the first, auditable stage of the strong-repair experiment."""
    return APIRequest(
        system_query=(
            _MUSIQUE_GRAPH_SYSTEM if structured_path and audited else
            _MUSIQUE_PATH_SYSTEM if evidence_as_given_path and audited else
            _AUDITED_VERIFIER_SYSTEM if audited else _NEUTRAL_CONSOLIDATOR_SYSTEM
        ),
        user_query=(
            f"Evidence board:\n{_board_text(board)}\n\nQuestion: {record['question']}\n\n"
            "Return the requested compact working ledger."
        ),
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        metadata={"phase": "audit_verification" if audited else "generic_consolidation",
                  "condition": condition, "instance_id": record["instance_id"],
                  # The verifier must return its ledger as visible text for the
                  # answer stage.  DeepSeek's hidden reasoning can otherwise
                  # exhaust this cap without emitting that artifact.
                  "openrouter_reasoning": False},
    )


def _strong_repair_final_request(record: dict[str, Any], board: list[dict[str, Any]], ledger: str, *,
                                 model: str, max_tokens: int, condition: str, audited: bool,
                                 evidence_as_given_path: bool = False, structured_path: bool = False) -> APIRequest:
    return APIRequest(
        system_query=(
            _MUSIQUE_GRAPH_FINAL_SYSTEM if structured_path and audited else
            _MUSIQUE_PATH_FINAL_SYSTEM if evidence_as_given_path and audited else
            _AUDITED_FINAL_ANSWER_SYSTEM if audited else _FINAL_ANSWER_SYSTEM
        ),
        user_query=(
            f"Evidence board:\n{_board_text(board)}\n\nWorking ledger:\n{ledger}\n\n"
            f"Question: {record['question']}\n\n"
            "End with exactly: ANSWER: <concise answer>"
        ),
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        metadata={"phase": "strong_repair_answer", "condition": condition,
                  # Reasoning is carried out in the visible ledger stage.  A
                  # deterministic one-line answer avoids hidden-reasoning-only
                  # responses that cannot be evaluated.
                  "instance_id": record["instance_id"], "openrouter_reasoning": False},
    )


def _musique_required_hops(record: dict[str, Any]) -> int:
    """Infer the benchmark hop count from MuSiQue's stable instance id."""
    match = re.match(r"(\d+)hop", str(record["instance_id"]))
    return int(match.group(1)) if match else 1


def _validate_musique_v3_ledger(record: dict[str, Any], board: list[dict[str, Any]], ledger: str) -> dict[str, Any]:
    """Check the visible path contract before it reaches the answer stage.

    This is intentionally syntactic rather than an oracle: it verifies that
    every claimed hop is cited, citations refer to the supplied board, and the
    model declared a complete path only when it emitted enough edges.  The
    per-instance metadata makes later audits distinguish a bad path from a bad
    final answer without human fact labels.
    """
    board_ids = set(range(1, len(board) + 1))
    edge_pattern = re.compile(r"^EDGE_(\d+):\s*\[([0-9, ]+)\]\s+([^|\n]+)\|([^|\n]+)\|(.+)$", re.MULTILINE)
    edges = edge_pattern.findall(ledger)
    cited_ids = {
        int(unit_id) for _, citations, _, _, _ in edges
        for unit_id in re.findall(r"\d+", citations)
    }
    status_match = re.search(r"^PATH_STATUS:\s*(COMPLETE|INCOMPLETE)\s*$", ledger, re.MULTILINE | re.IGNORECASE)
    candidate_match = re.search(r"^ANSWER_CANDIDATE:\s*(.+?)\s*$", ledger, re.MULTILINE)
    declared_complete = bool(status_match and status_match.group(1).upper() == "COMPLETE")
    candidate = candidate_match.group(1).strip() if candidate_match else ""
    edge_numbers = [int(number) for number, *_ in edges]
    sequential_edges = edge_numbers == list(range(1, len(edge_numbers) + 1))
    valid = bool(
        declared_complete and candidate and candidate.upper() != "UNKNOWN"
        and len(edges) >= _musique_required_hops(record)
        and cited_ids and cited_ids <= board_ids and sequential_edges
    )
    return {
        "audit_path_required_hops": _musique_required_hops(record),
        "audit_path_hops": len(edges),
        "audit_path_cited_units": sorted(cited_ids),
        "audit_path_declared_complete": declared_complete,
        "audit_path_valid": valid,
    }


def run_audit_repair_study(records: Iterable[dict[str, Any]], *, batch_fn: Callable[[list[APIRequest]], list[APIResponse]],
                           model: str, aggregation_tokens: int = 4096, repair_tokens: int = 4096,
                           extraction_tokens: int = 2048, repair_strategy: str = "single_pass",
                           analysis_tokens: int = 2048) -> list[dict[str, Any]]:
    """Run repair stages in batches so a study does not serialize API latency."""
    if repair_strategy not in {"single_pass", "strong_two_stage", "bottleneck_aware_v2", "bottleneck_aware_v3"}:
        raise ValueError(f"Unknown repair strategy: {repair_strategy}")
    records = validate_audit_manifest(records)
    rows = [_audit_baseline(record) for record in records]

    # Silo's algorithmic templates expose unambiguous local state.  When the
    # frozen audit routes such an error here, execute the declared reduction on
    # the original private shards locally instead of asking an LLM to recount a
    # prose summary.  The model-only generic control remains in the experiment.
    deterministic_predictions: dict[int, str] = {}
    if repair_strategy in {"bottleneck_aware_v2", "bottleneck_aware_v3"}:
        executable_tasks = _SILO_V3_EXECUTABLE_TASKS if repair_strategy == "bottleneck_aware_v3" else _SILO_V2_EXECUTABLE_TASKS
        for record_index, record in enumerate(records):
            if record["audit_signal"] not in {"evidence_gap", "aggregation_gap"}:
                continue
            pred = _deterministic_silo_repair(record, supported_task_ids=executable_tasks)
            if pred is None:
                continue
            deterministic_predictions[record_index] = pred
            condition = "audited_evidence_repair" if record["audit_signal"] == "evidence_gap" else "audited_aggregation_repair"
            rows.append(_audit_prediction_result(record, condition, pred, [dict(unit) for unit in record["board_units"]]))

    # Stage 1: all original-shard re-extractions for audit-detected evidence gaps.
    extraction_requests: list[APIRequest] = []
    extraction_index: list[tuple[int, dict[str, Any]]] = []
    for record_index, record in enumerate(records):
        if record["audit_signal"] != "evidence_gap" or record_index in deterministic_predictions:
            continue
        for context in record["source_contexts"]:
            extraction_requests.append(APIRequest(
                system_query=_VISIBLE_EXTRACTION_SYSTEM if repair_strategy == "bottleneck_aware_v2" else _EXTRACTION_SYSTEM,
                user_query=_build_extraction_prompt(str(context["text"]), record["question"], 3),
                model=model, max_tokens=extraction_tokens, temperature=0.0,
                metadata={"phase": "audit_reextraction", "condition": "audited_evidence_repair",
                          "instance_id": record["instance_id"], "agent": context["agent_id"],
                          "openrouter_reasoning": False},
            ))
            extraction_index.append((record_index, context))
    extracted: dict[int, list[dict[str, Any]]] = defaultdict(list)
    extraction_cost: dict[int, int] = defaultdict(int)
    extraction_calls: dict[int, int] = defaultdict(int)
    retry_requests: list[APIRequest] = []
    retry_index: list[tuple[int, dict[str, Any]]] = []
    if extraction_requests:
        for response, (record_index, context) in zip(batch_fn(extraction_requests), extraction_index):
            extraction_calls[record_index] += 1
            extraction_cost[record_index] += response.usage.get("total_tokens", 0)
            units = _parse_units(response.content, 3) if response.success else []
            if units:
                extracted[record_index].extend(
                    {"unit_id": f"audit-reextract:a{context['agent_id']}:u{i}",
                     "agent_id": context["agent_id"], "text": text}
                    for i, text in enumerate(units)
                )
            elif repair_strategy == "bottleneck_aware_v2":
                retry_requests.append(APIRequest(
                    system_query=_VISIBLE_EXTRACTION_SYSTEM,
                    user_query=_build_extraction_prompt(str(context["text"]), records[record_index]["question"], 3),
                    model=model, max_tokens=extraction_tokens, temperature=0.0,
                    metadata={"phase": "audit_reextraction_retry", "condition": "audited_evidence_repair",
                              "instance_id": records[record_index]["instance_id"], "agent": context["agent_id"],
                              "openrouter_reasoning": False},
                ))
                retry_index.append((record_index, context))
    if retry_requests:
        for response, (record_index, context) in zip(batch_fn(retry_requests), retry_index):
            extraction_calls[record_index] += 1
            extraction_cost[record_index] += response.usage.get("total_tokens", 0)
            if response.success:
                extracted[record_index].extend(
                    {"unit_id": f"audit-reextract-retry:a{context['agent_id']}:u{i}",
                     "agent_id": context["agent_id"], "text": text}
                    for i, text in enumerate(_parse_units(response.content, 3))
                )

    if repair_strategy in {"strong_two_stage", "bottleneck_aware_v2", "bottleneck_aware_v3"}:
        # Stage 2: both conditions receive the same strong-model, two-stage
        # inference budget.  Only the first-stage instruction is audit-specific.
        analysis_requests: list[APIRequest] = []
        analysis_index: list[tuple[dict[str, Any], str, list[dict[str, Any]], int, int, bool]] = []
        for record_index, record in enumerate(records):
            board = [dict(unit) for unit in record["board_units"]]
            signal = record["audit_signal"]
            if signal == "evidence_gap":
                if record_index not in deterministic_predictions:
                    repaired_board = board + extracted[record_index]
                    analysis_requests.append(_strong_repair_analysis_request(
                        record, repaired_board, audited=True, model=model, max_tokens=analysis_tokens,
                        condition="audited_evidence_repair",
                        evidence_as_given_path=repair_strategy == "bottleneck_aware_v2" and record["dataset"] == "musique",
                        structured_path=repair_strategy == "bottleneck_aware_v3" and record["dataset"] == "musique"))
                    analysis_index.append((record, "audited_evidence_repair", repaired_board,
                                           extraction_calls[record_index] + 1, extraction_cost[record_index],
                                           repair_strategy == "bottleneck_aware_v3" and record["dataset"] == "musique"))
            elif signal == "aggregation_gap":
                if record_index not in deterministic_predictions:
                    analysis_requests.append(_strong_repair_analysis_request(
                        record, board, audited=True, model=model, max_tokens=analysis_tokens,
                        condition="audited_aggregation_repair",
                        evidence_as_given_path=repair_strategy == "bottleneck_aware_v2" and record["dataset"] == "musique",
                        structured_path=repair_strategy == "bottleneck_aware_v3" and record["dataset"] == "musique"))
                    analysis_index.append((record, "audited_aggregation_repair", board, 1, 0,
                                           repair_strategy == "bottleneck_aware_v3" and record["dataset"] == "musique"))
            else:
                continue
            analysis_requests.append(_strong_repair_analysis_request(
                record, board, audited=False, model=model, max_tokens=analysis_tokens,
                condition="generic_retry"))
            analysis_index.append((record, "generic_retry", board, 1, 0, False))

        final_requests: list[APIRequest] = []
        final_index: list[tuple[dict[str, Any], str, list[dict[str, Any]], int, int, APIResponse, bool, dict[str, Any]]] = []
        for analysis, (record, condition, board, calls, extra_tokens, structured_path) in zip(batch_fn(analysis_requests), analysis_index):
            ledger = analysis.content.strip() if analysis.success and analysis.content.strip() else "(No working ledger was produced.)"
            path_metadata = _validate_musique_v3_ledger(record, board, ledger) if structured_path else {}
            final_requests.append(_strong_repair_final_request(
                record, board, ledger, model=model, max_tokens=repair_tokens, condition=condition,
                audited=condition != "generic_retry",
                evidence_as_given_path=(repair_strategy == "bottleneck_aware_v2" and record["dataset"] == "musique" and condition != "generic_retry"),
                structured_path=structured_path))
            final_index.append((record, condition, board, calls + 1,
                                extra_tokens + analysis.usage.get("total_tokens", 0), analysis,
                                structured_path, path_metadata))
        for final, (record, condition, board, calls, extra_tokens, analysis, _path_mode, path_metadata) in zip(batch_fn(final_requests), final_index):
            if not analysis.success and final.success:
                final.error = f"verification stage failed: {analysis.error}"
            row = _audit_response(record, condition, final, board, calls, extra_tokens)
            row.update(path_metadata)
            rows.append(row)
        return rows

    # Stage 2: original single-pass repaired aggregations and matched retries.
    requests: list[APIRequest] = []
    request_index: list[tuple[dict[str, Any], str, list[dict[str, Any]], int, int]] = []
    for record_index, record in enumerate(records):
        board = [dict(unit) for unit in record["board_units"]]
        signal = record["audit_signal"]
        if signal == "evidence_gap":
            repaired_board = board + extracted[record_index]
            request = _aggregation_request(record, repaired_board, repaired=False,
                                           max_tokens=aggregation_tokens, condition="audited_evidence_repair")
            request.model = model
            requests.append(request)
            request_index.append((record, "audited_evidence_repair", repaired_board,
                                  len(record["source_contexts"]) + 1, extraction_cost[record_index]))
        elif signal == "aggregation_gap":
            request = _aggregation_request(record, board, repaired=True,
                                           max_tokens=repair_tokens, condition="audited_aggregation_repair")
            request.model = model
            requests.append(request)
            request_index.append((record, "audited_aggregation_repair", board, 1, 0))
        else:
            continue
        request = _aggregation_request(record, board, repaired=False,
                                       max_tokens=repair_tokens, condition="generic_retry")
        request.model = model
        requests.append(request)
        request_index.append((record, "generic_retry", board, 1, 0))
    if requests:
        for response, (record, condition, board, calls, extra_tokens) in zip(batch_fn(requests), request_index):
            rows.append(_audit_response(record, condition, response, board, calls, extra_tokens))
    return rows


def summarize_audit_repair_results(rows: Iterable[dict[str, Any]], *, seed: int = 42) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["audit_signal"], row["condition"])].append(row)
    summaries = []
    for (dataset, signal, condition), group in sorted(grouped.items()):
        deltas = [float(row["delta_f1"]) for row in group]
        summaries.append({"dataset": dataset, "audit_signal": signal, "condition": condition, "n": len(group),
                          "mean_f1": sum(float(row["f1"]) for row in group) / len(group),
                          "mean_delta_f1": sum(deltas) / len(deltas), "delta_f1_95ci": _bootstrap_mean_ci(deltas, seed=seed),
                          "recovery_rate": sum(bool(row["recovered"]) for row in group) / len(group),
                          "mean_comm_tokens": sum(int(row["comm_tokens"]) for row in group) / len(group),
                          "mean_total_llm_tokens": sum(int(row["total_llm_tokens"]) for row in group) / len(group),
                          "mean_api_calls": sum(int(row["api_calls"]) for row in group) / len(group)})
    return {"schema_version": AUDIT_SCHEMA_VERSION, "summaries": summaries}
