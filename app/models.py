"""Pydantic models for the CrewAI-n8n Bridge API."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator


# --- Task Models ---

class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskState(BaseModel):
    task_id: str
    crew_name: str
    status: TaskStatus
    inputs: dict[str, Any]
    result: str | None = None
    error: str | None = None
    started_at: str
    completed_at: str | None = None
    current_step: str | None = None
    callback_url: str | None = None
    duration_sec: float | None = None
    total_tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    successful_requests: int | None = None


class KickoffRequest(BaseModel):
    topic: str | None = None
    company: str | None = None
    callback_url: str | None = None


class KickoffResponse(BaseModel):
    task_id: str
    status: TaskStatus
    crew_name: str


# --- Dynamic Crew Models ---

TOOL_WHITELIST = {
    "web_search": "SerperDevTool",
    "scrape_website": "ScrapeWebsiteTool",
}


class AgentDefinition(BaseModel):
    role: str
    goal: str
    backstory: str
    tools: list[str] = []

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: list[str]) -> list[str]:
        for tool_name in v:
            if tool_name not in TOOL_WHITELIST:
                raise ValueError(
                    f"Tool '{tool_name}' not allowed. Available: {list(TOOL_WHITELIST.keys())}"
                )
        return v


class TaskDefinition(BaseModel):
    description: str
    expected_output: str
    agent: str
    context: list[str] = []


class CreateCrewRequest(BaseModel):
    name: str
    agents: list[AgentDefinition]
    tasks: list[TaskDefinition]
    process: str = "sequential"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Crew name must be alphanumeric (hyphens and underscores allowed)")
        return v
