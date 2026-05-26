"""Broadcast protocol tool implementations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from src.models import AgentState, ToolCall, ToolResult
from src.utils.persistence import read_json, write_json


def tool_broadcast_message(
    agent_id: int,
    content: str,
    round_dir: Path,
    current_round: int,
    state: AgentState,
) -> dict[str, Any]:
    """Broadcast a message to all other agents."""
    broadcast_id = str(uuid.uuid4())
    msg_data = {
        "sender_id": agent_id,
        "content": content,
        "timestamp": current_round,
        "broadcast_id": broadcast_id,
    }

    bc_dir = round_dir / "env" / "broadcasts"
    bc_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{current_round}_{agent_id}_{broadcast_id}.json"
    write_json(bc_dir / filename, msg_data)

    state.messages_sent += 1
    return {"success": True, "message": "Message broadcast to all agents"}


def tool_receive_messages(
    agent_id: int,
    case_dir: Path,
    current_round: int,
    round_dir: Path,
) -> dict[str, Any]:
    """Receive all new broadcast messages from previous rounds.

    Tracks last received round per agent to avoid duplicates.
    """
    # Load last_received_round tracking
    agent_dir = round_dir / f"agent-{agent_id:03d}"
    agent_dir.mkdir(parents=True, exist_ok=True)
    tracking_file = agent_dir / "last_received_round.json"

    # Try to load from previous round first
    rounds_dir = case_dir / "rounds"
    last_received = -1
    if current_round > 1:
        prev_tracking = (
            rounds_dir
            / f"round-{current_round - 1:06d}"
            / f"agent-{agent_id:03d}"
            / "last_received_round.json"
        )
        if prev_tracking.exists():
            data = read_json(prev_tracking)
            last_received = data.get("last_received_round", -1)

    # Also check if we already updated in this round
    if tracking_file.exists():
        data = read_json(tracking_file)
        last_received = max(last_received, data.get("last_received_round", -1))

    messages = []
    max_round_seen = last_received

    # Scan all previous rounds for broadcasts
    for r in range(1, current_round):
        if r <= last_received:
            continue
        bc_dir = rounds_dir / f"round-{r:06d}" / "env" / "broadcasts"
        if not bc_dir.exists():
            continue
        for bc_file in sorted(bc_dir.glob("*.json")):
            msg = read_json(bc_file)
            if msg["sender_id"] != agent_id:
                messages.append({
                    "from": msg["sender_id"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                })
        if r > max_round_seen:
            max_round_seen = r

    # Update tracking
    write_json(tracking_file, {"last_received_round": max_round_seen})

    return {"messages": messages}


def tool_list_agents(num_agents: int) -> dict[str, Any]:
    """Get list of all agent IDs."""
    return {
        "agent_ids": list(range(num_agents)),
        "total": num_agents,
    }


def tool_wait() -> dict[str, Any]:
    """Wait for other agents to act."""
    return {"status": "waiting"}


def tool_submit_result(
    agent_id: int,
    answer: Any,
    round_dir: Path,
    current_round: int,
    state: AgentState,
) -> dict[str, Any]:
    """Submit the final answer."""
    if state.submitted:
        return {"status": "already_submitted"}

    submission = {
        "agent_id": agent_id,
        "answer": answer,
        "round": current_round,
    }

    agent_dir = round_dir / f"agent-{agent_id:03d}"
    agent_dir.mkdir(parents=True, exist_ok=True)
    write_json(agent_dir / "submission.json", submission)

    state.submitted = True
    state.submission_round = current_round
    return {"status": "submitted"}


def execute_tool(
    tool_call: ToolCall,
    agent_id: int,
    case_dir: Path,
    round_dir: Path,
    current_round: int,
    state: AgentState,
    num_agents: int,
) -> ToolResult:
    """Dispatch and execute a tool call for the broadcast protocol."""
    name = tool_call.tool
    params = tool_call.parameters

    try:
        if name == "broadcast_message":
            result = tool_broadcast_message(
                agent_id=agent_id,
                content=str(params.get("content", "")),
                round_dir=round_dir,
                current_round=current_round,
                state=state,
            )
        elif name == "receive_messages":
            result = tool_receive_messages(
                agent_id=agent_id,
                case_dir=case_dir,
                current_round=current_round,
                round_dir=round_dir,
            )
            state.messages_received += len(result.get("messages", []))
        elif name == "list_agents":
            result = tool_list_agents(num_agents)
        elif name == "wait":
            result = tool_wait()
        elif name == "submit_result":
            result = tool_submit_result(
                agent_id=agent_id,
                answer=params.get("answer"),
                round_dir=round_dir,
                current_round=current_round,
                state=state,
            )
        else:
            return ToolResult(
                tool=name,
                parameters=params,
                result={"error": f"Unknown tool: {name}"},
                success=False,
                error=f"Unknown tool: {name}",
            )

        return ToolResult(tool=name, parameters=params, result=result, success=True)

    except Exception as e:
        return ToolResult(
            tool=name,
            parameters=params,
            result={"error": str(e)},
            success=False,
            error=str(e),
        )
