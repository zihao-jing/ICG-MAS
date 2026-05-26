"""Shared engine: init_case, run_round, evaluate — parameterized by protocol."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import srsly

from src.models import (
    AgentState,
    CaseConfig,
    CaseMetadata,
    Context,
    ExecutionInfo,
    ExecutionStatus,
    Message,
    Protocol,
    TaskInfo,
)
from src.utils.config import load_config
from src.utils.llm import call_llm
from src.utils.metrics import (
    compute_communication_density,
    compute_partial_correctness,
    compute_success_rate,
    compute_token_consumption,
)
from src.utils.parsing import parse_tool_calls
from src.utils.persistence import append_jsonl, read_json, write_json
from src.utils.prompts import generate_system_prompt

# Load defaults from configs/config.yaml (falls back to env vars)
_cfg = load_config()
DEFAULT_MODEL_URL = _cfg["api_base"]
DEFAULT_API_KEY = _cfg["api_key"]
DEFAULT_MODEL = _cfg["model"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _get_protocol_tools(protocol: str):
    """Dynamically import the tools module for a given protocol."""
    mod = importlib.import_module(f"src.{protocol}.tools")
    return mod


def _log(case_dir: Path, agent_id: int, event: dict[str, Any]) -> None:
    """Append a log event to the agent's JSONL log."""
    event["timestamp"] = _now_iso()
    append_jsonl(case_dir / "logs" / f"agent-{agent_id:03d}.jsonl", event)


# ---------------------------------------------------------------------------
# init_case
# ---------------------------------------------------------------------------


def init_case(
    task_file: str,
    protocol: str,
    model: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    max_rounds: int = 100,
    workspace: str = "workspace",
) -> str:
    """Initialize a new case workspace.

    Returns the created case directory path.
    """
    model = model or DEFAULT_MODEL
    api_base = api_base or DEFAULT_MODEL_URL
    api_key = api_key or DEFAULT_API_KEY

    # Load benchmark JSON
    task_data = read_json(task_file)
    case_id_base = task_data["case_id"]

    # Determine num_agents from data: prefer agent_configs list length,
    # fall back to metadata, then default to 1 for single-agent baselines.
    if "agent_configs" in task_data:
        num_agents = len(task_data["agent_configs"])
    elif "metadata" in task_data and "num_agents" in task_data["metadata"]:
        num_agents = task_data["metadata"]["num_agents"]
    else:
        num_agents = 1

    # Sanitize model name for directory (replace / with -)
    model_safe = model.replace("/", "-")
    # Map protocol to short label for directory naming
    protocol_label = {"msg": "p2p", "broadcast": "bp", "sfs": "sfs"}[protocol]
    timestamp = _timestamp_compact()
    case_id = f"{case_id_base}_{protocol_label}_{model_safe}_{timestamp}"

    case_dir = Path(workspace) / case_id
    rounds_dir = case_dir / "rounds"
    logs_dir = case_dir / "logs"

    # Create directory structure
    round0_dir = rounds_dir / "round-000000"
    round0_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Normalize expected_output to always be {"per_agent_values": [...]}
    raw_expected = task_data["expected_output"]
    if isinstance(raw_expected, dict) and "per_agent_values" in raw_expected:
        expected_output = raw_expected
    else:
        # Baseline format: raw value is the answer for the single agent
        expected_output = {"type": "single", "per_agent_values": [raw_expected]}

    # Build metadata
    task_info = TaskInfo(
        case_id=case_id_base,
        case_name=task_data["case_name"],
        paradigm=task_data["paradigm"],
        num_agents=num_agents,
        task_description=task_data.get("task_description", task_data["case_name"]),
        expected_output=expected_output,
    )

    config = CaseConfig(
        agent_count=num_agents,
        protocol=Protocol(protocol),
        model=model,
        api_base=api_base,
        api_key=api_key,
        max_rounds=max_rounds,
    )

    execution = ExecutionInfo(
        started_at=_now_iso(),
        status=ExecutionStatus.INITIALIZED,
        current_round=0,
    )

    metadata = CaseMetadata(
        case_id=case_id,
        task_file=str(task_file),
        task=task_info,
        config=config,
        execution=execution,
    )

    write_json(case_dir / "metadata.json", metadata.model_dump())

    # Normalize agent configs to a list
    if "agent_configs" in task_data:
        agent_configs = task_data["agent_configs"]
    else:
        # Baseline single-agent format
        agent_configs = [task_data["agent_config"]]

    # Initialize round-000000 for each agent
    for i in range(num_agents):
        agent_conf = agent_configs[i]

        # Generate protocol-specific system prompt
        system_prompt = generate_system_prompt(protocol, i, num_agents)
        user_prompt = agent_conf["user_prompt"]

        context = Context(messages=[
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ])

        state = AgentState(agent_id=i, last_active_round=0)

        agent_dir = round0_dir / f"agent-{i:03d}"
        agent_dir.mkdir(parents=True, exist_ok=True)
        write_json(agent_dir / "context.json", context.model_dump())
        write_json(agent_dir / "state.json", state.model_dump())

        _log(case_dir, i, {"round": 0, "event": "initialized", "agent_id": i})

    # Initialize protocol-specific env for round 0
    env_dir = round0_dir / "env"
    env_dir.mkdir(parents=True, exist_ok=True)
    if protocol == "msg":
        (env_dir / "messages").mkdir(exist_ok=True)
    elif protocol == "broadcast":
        (env_dir / "broadcasts").mkdir(exist_ok=True)
    elif protocol == "sfs":
        write_json(env_dir / "shared_kv.json", {})

    return str(case_dir)


# ---------------------------------------------------------------------------
# run_round
# ---------------------------------------------------------------------------


def run_round(case_dir: str) -> bool:
    """Execute one round of the case.

    Returns True if the case is now done (all submitted or max rounds reached).
    """
    case_dir = Path(case_dir)
    meta_dict = read_json(case_dir / "metadata.json")
    metadata = CaseMetadata(**meta_dict)

    # Check if already done
    if metadata.execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
        return True

    protocol = metadata.config.protocol.value
    num_agents = metadata.config.agent_count
    current_round = metadata.execution.current_round + 1
    max_rounds = metadata.config.max_rounds

    rounds_dir = case_dir / "rounds"
    prev_round_dir = rounds_dir / f"round-{current_round - 1:06d}"
    round_dir = rounds_dir / f"round-{current_round:06d}"
    round_dir.mkdir(parents=True, exist_ok=True)

    # Setup env for new round
    env_dir = round_dir / "env"
    env_dir.mkdir(parents=True, exist_ok=True)

    if protocol == "msg":
        (env_dir / "messages").mkdir(exist_ok=True)
    elif protocol == "broadcast":
        (env_dir / "broadcasts").mkdir(exist_ok=True)
    elif protocol == "sfs":
        # Copy shared_kv.json from previous round
        prev_kv = prev_round_dir / "env" / "shared_kv.json"
        if prev_kv.exists():
            kv_data = read_json(prev_kv)
            write_json(env_dir / "shared_kv.json", kv_data)
        else:
            write_json(env_dir / "shared_kv.json", {})

    # Get protocol tools module
    tools_mod = _get_protocol_tools(protocol)

    # Update status to RUNNING
    metadata.execution.status = ExecutionStatus.RUNNING
    write_json(case_dir / "metadata.json", metadata.model_dump())

    all_submitted = True

    for i in range(num_agents):
        # Load previous state
        prev_state_file = prev_round_dir / f"agent-{i:03d}" / "state.json"
        state = AgentState(**read_json(prev_state_file))

        # Create agent dir for this round
        agent_round_dir = round_dir / f"agent-{i:03d}"
        agent_round_dir.mkdir(parents=True, exist_ok=True)

        if state.submitted:
            # Copy state forward, no action needed
            write_json(agent_round_dir / "state.json", state.model_dump())
            # Copy context forward
            prev_ctx_file = prev_round_dir / f"agent-{i:03d}" / "context.json"
            ctx_data = read_json(prev_ctx_file)
            write_json(agent_round_dir / "context.json", ctx_data)
            # Copy submission forward
            prev_sub = prev_round_dir / f"agent-{i:03d}" / "submission.json"
            if prev_sub.exists():
                write_json(agent_round_dir / "submission.json", read_json(prev_sub))
            continue

        all_submitted = False

        # Load context
        prev_ctx_file = prev_round_dir / f"agent-{i:03d}" / "context.json"
        ctx = Context(**read_json(prev_ctx_file))

        # Call LLM
        messages_for_api = [m.model_dump() for m in ctx.messages]
        _log(case_dir, i, {
            "round": current_round,
            "event": "llm_request",
            "agent_id": i,
            "input_tokens": 0,
        })

        llm_result = call_llm(
            api_base=metadata.config.api_base,
            api_key=metadata.config.api_key,
            model=metadata.config.model,
            messages=messages_for_api,
        )

        content = llm_result["content"]
        input_tokens = llm_result["input_tokens"]
        output_tokens = llm_result["output_tokens"]

        metadata.execution.total_input_tokens += input_tokens
        metadata.execution.total_output_tokens += output_tokens

        _log(case_dir, i, {
            "round": current_round,
            "event": "llm_response",
            "agent_id": i,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "response": content,
        })

        # Add assistant message to context
        ctx.messages.append(Message(role="assistant", content=content))

        # Parse tool calls
        tool_calls = parse_tool_calls(content)

        # Execute tool calls — stop at round-ending tools (wait, submit_result)
        ROUND_ENDING_TOOLS = {"wait", "submit_result"}
        tool_results_text_parts = []
        for tc in tool_calls:
            _log(case_dir, i, {
                "round": current_round,
                "event": "tool_call",
                "agent_id": i,
                "tool": tc.tool,
                "parameters": tc.parameters,
            })

            tr = tools_mod.execute_tool(
                tool_call=tc,
                agent_id=i,
                case_dir=case_dir,
                round_dir=round_dir,
                current_round=current_round,
                state=state,
                num_agents=num_agents,
            )

            _log(case_dir, i, {
                "round": current_round,
                "event": "tool_result",
                "agent_id": i,
                "tool": tc.tool,
                "result": tr.result,
            })

            tool_results_text_parts.append(
                f"<tool_result>\n"
                f"  <tool>{tc.tool}</tool>\n"
                f"  <result>{srsly.json_dumps(tr.result)}</result>\n"
                f"</tool_result>"
            )

            # If agent submitted, log it
            if tc.tool == "submit_result" and state.submitted:
                _log(case_dir, i, {
                    "round": current_round,
                    "event": "submitted",
                    "agent_id": i,
                    "answer": tc.parameters.get("answer"),
                })

            # Round-ending: stop executing further tool calls
            if tc.tool in ROUND_ENDING_TOOLS:
                break

        # Add tool results as user message
        if tool_results_text_parts:
            tool_msg = "\n\n".join(tool_results_text_parts)
            ctx.messages.append(Message(role="user", content=tool_msg))
        else:
            # No tool calls parsed - give feedback
            ctx.messages.append(Message(
                role="user",
                content=(
                    "<tool_result>\n"
                    "  <tool>system</tool>\n"
                    "  <result>No valid tool calls detected in your response. "
                    "Please use the XML format: "
                    "<tool_call><tool>tool_name</tool><parameters>...</parameters></tool_call>"
                    "</result>\n"
                    "</tool_result>"
                ),
            ))

        # Update state
        state.last_active_round = current_round

        # Save context and state
        write_json(agent_round_dir / "context.json", ctx.model_dump())
        write_json(agent_round_dir / "state.json", state.model_dump())

        # Check if submitted this round
        if state.submitted:
            # Also check if now all are submitted
            pass

    # Update metadata
    metadata.execution.current_round = current_round
    metadata.execution.all_submitted = all_submitted or _check_all_submitted(
        round_dir, num_agents
    )

    # Check termination
    done = False
    if metadata.execution.all_submitted:
        done = True
    elif current_round >= max_rounds:
        done = True

    if done:
        metadata.execution.finished_at = _now_iso()
        metadata.execution.status = ExecutionStatus.COMPLETED
        write_json(case_dir / "metadata.json", metadata.model_dump())
        evaluate(str(case_dir))
    else:
        write_json(case_dir / "metadata.json", metadata.model_dump())

    return done


def _check_all_submitted(round_dir: Path, num_agents: int) -> bool:
    """Check if all agents have submitted in the given round."""
    for i in range(num_agents):
        state_file = round_dir / f"agent-{i:03d}" / "state.json"
        if not state_file.exists():
            return False
        state = AgentState(**read_json(state_file))
        if not state.submitted:
            return False
    return True


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def evaluate(case_dir: str) -> dict[str, Any]:
    """Evaluate the case and write results.json.

    Returns the results dict.
    """
    case_dir = Path(case_dir)
    meta_dict = read_json(case_dir / "metadata.json")
    metadata = CaseMetadata(**meta_dict)

    num_agents = metadata.config.agent_count
    current_round = metadata.execution.current_round
    rounds_dir = case_dir / "rounds"

    # Load expected output from the original task file
    expected_output = metadata.task.expected_output
    per_agent_expected = expected_output["per_agent_values"]

    # Collect submissions from the final round
    final_round_dir = rounds_dir / f"round-{current_round:06d}"
    submissions = []
    for i in range(num_agents):
        sub_file = final_round_dir / f"agent-{i:03d}" / "submission.json"
        if sub_file.exists():
            sub = read_json(sub_file)
            submissions.append(sub)
        else:
            # Agent didn't submit - count as wrong
            submissions.append({"agent_id": i, "answer": None, "round": None})

    # Compute metrics
    success_rate = compute_success_rate(submissions, expected_output)

    # Determine task level from case_id for partial correctness calculation
    case_id = metadata.task.case_id
    if case_id.startswith("I-"):
        level = "I"
    elif case_id.startswith("II-"):
        level = "II"
    else:
        level = "III"
    partial_correctness = compute_partial_correctness(submissions, expected_output, level)

    total_tokens = (
        metadata.execution.total_input_tokens + metadata.execution.total_output_tokens
    )
    token_consumption = compute_token_consumption(total_tokens, current_round)

    # Count total messages for communication density
    total_messages = _count_messages(case_dir, metadata.config.protocol.value, current_round)
    comm_density = compute_communication_density(total_messages, num_agents)

    # Build submission records
    submission_records = []
    for sub in submissions:
        aid = sub["agent_id"]
        answer = sub["answer"]
        expected = per_agent_expected[aid] if aid < len(per_agent_expected) else None
        from src.utils.metrics import _normalize_value

        correct = _normalize_value(answer) == _normalize_value(expected)
        submission_records.append({
            "agent_id": aid,
            "answer": answer,
            "correct": correct,
            "round": sub.get("round"),
        })

    results = {
        "evaluated_at": _now_iso(),
        "ground_truth": per_agent_expected,
        "submissions": submission_records,
        "metrics": {
            # Paper notation: S, P, C, D (Section 3.3)
            "S_success_rate": success_rate,
            "P_partial_correctness": partial_correctness,
            "C_token_consumption": token_consumption,
            "D_communication_density": comm_density,
            # Legacy names for backward compatibility
            "success_rate": success_rate,
            "partial_correctness": partial_correctness,
            "token_consumption": token_consumption,
            "communication_density": comm_density,
        },
        "success": success_rate == 1.0,
    }

    write_json(case_dir / "results.json", results)

    # Update metadata
    metadata.execution.status = ExecutionStatus.COMPLETED
    metadata.execution.finished_at = _now_iso()
    write_json(case_dir / "metadata.json", metadata.model_dump())

    return results


def _count_messages(case_dir: Path, protocol: str, max_round: int) -> int:
    """Count total messages across all rounds."""
    rounds_dir = case_dir / "rounds"
    count = 0

    for r in range(1, max_round + 1):
        round_dir = rounds_dir / f"round-{r:06d}"
        if protocol == "msg":
            msg_dir = round_dir / "env" / "messages"
            if msg_dir.exists():
                count += len(list(msg_dir.glob("*.json")))
        elif protocol == "broadcast":
            bc_dir = round_dir / "env" / "broadcasts"
            if bc_dir.exists():
                count += len(list(bc_dir.glob("*.json")))
        elif protocol == "sfs":
            # For SFS, count file writes as communication operations
            # Each write_file represents a communication action
            kv_file = round_dir / "env" / "shared_kv.json"
            if kv_file.exists():
                kv = read_json(kv_file)
                # Count files modified in this specific round
                for path, entry in kv.items():
                    if isinstance(entry, dict) and entry.get("modified_at_round") == r:
                        count += 1

    return count
