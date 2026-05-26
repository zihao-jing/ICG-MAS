"""Pydantic v2 data models for SILO-BENCH."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---


class TaskLevel(str, Enum):
    I = "I"
    II = "II"
    III = "III"


class Protocol(str, Enum):
    MSG = "msg"
    BROADCAST = "broadcast"
    SFS = "sfs"


class ExecutionStatus(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Chat messages (OpenAI format) ---


class Message(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str


class Context(BaseModel):
    messages: list[Message] = Field(default_factory=list)


# --- Agent state ---


class AgentState(BaseModel):
    agent_id: int
    submitted: bool = False
    submission_round: int | None = None
    last_active_round: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    files_written: int = 0
    files_read: int = 0


# --- Task info (from benchmark JSON) ---


class TaskInfo(BaseModel):
    case_id: str
    case_name: str
    paradigm: str
    num_agents: int
    task_description: str
    expected_output: dict[str, Any]


# --- Config ---


class ModelConfig(BaseModel):
    model: str
    api_base: str
    api_key: str


class CaseConfig(BaseModel):
    agent_count: int
    protocol: Protocol
    model: str
    api_base: str
    api_key: str
    max_rounds: int = 100


# --- Execution tracking ---


class ExecutionInfo(BaseModel):
    started_at: str | None = None
    finished_at: str | None = None
    status: ExecutionStatus = ExecutionStatus.INITIALIZED
    current_round: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    all_submitted: bool = False


# --- Case metadata (top-level file) ---


class CaseMetadata(BaseModel):
    case_id: str
    task_file: str
    task: TaskInfo
    config: CaseConfig
    execution: ExecutionInfo = Field(default_factory=ExecutionInfo)


# --- Tool call parsing ---


class ToolCall(BaseModel):
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


# --- Submission ---


class Submission(BaseModel):
    agent_id: int
    answer: Any
    round: int


class SubmissionRecord(BaseModel):
    agent_id: int
    answer: Any
    correct: bool
    round: int | None = None


# --- Metrics & Results ---


class Metrics(BaseModel):
    success_rate: float
    token_efficiency: float
    communication_density: float


class Results(BaseModel):
    evaluated_at: str
    ground_truth: Any
    submissions: list[SubmissionRecord]
    metrics: Metrics
    success: bool


# --- Protocol-specific message models ---


class P2PMessage(BaseModel):
    sender_id: int
    recipient_id: int
    content: str
    timestamp: int  # round number
    read: bool = False


class BroadcastMessage(BaseModel):
    sender_id: int
    content: str
    timestamp: int  # round number
    broadcast_id: str


class SharedFileEntry(BaseModel):
    content: Any
    modified_by: int
    modified_at_round: int


# --- Log events ---


class LogEvent(BaseModel):
    round: int
    event: str
    agent_id: int
    timestamp: str | None = None
    # optional fields depending on event type
    input_tokens: int | None = None
    output_tokens: int | None = None
    response: str | None = None
    tool: str | None = None
    parameters: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    answer: Any | None = None
