"""
CrewAI-n8n Bridge — FastAPI async wrapper for CrewAI crews.

Endpoints:
  GET  /                          → API info + available crews
  POST /crews/{crew_name}/kickoff → Start crew, returns task_id
  GET  /tasks/{task_id}/status    → Task status + progress
  GET  /tasks/{task_id}/result    → Task result (when completed)
  GET  /health                    → Health check
"""

import os
import sys
import uuid
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add crew packages to path
_base = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_base, "research_crew", "src"))
sys.path.insert(0, os.path.join(_base, "sales_crew", "src"))
sys.path.insert(0, os.path.join(_base, "content_crew", "src"))

from research_crew.crew import ResearchCrew
from sales_crew.crew import SalesCrew
from content_crew.crew import ContentCrew


# --- Models ---

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


class KickoffRequest(BaseModel):
    topic: str | None = None
    company: str | None = None


class KickoffResponse(BaseModel):
    task_id: str
    status: TaskStatus
    crew_name: str


# --- State ---

tasks: dict[str, TaskState] = {}

AVAILABLE_CREWS = {
    "research": {
        "name": "research",
        "description": "Research Team — 3 agents analyze a topic and produce an executive brief",
        "agents": ["Research Lead", "Data Analyst", "Report Writer"],
        "input_fields": ["topic"],
    },
    "sales": {
        "name": "sales",
        "description": "Sales Outreach Team — researches a company and creates personalized outreach",
        "agents": ["Company Researcher", "Pitch Writer", "Offer Creator"],
        "input_fields": ["company"],
    },
    "content": {
        "name": "content",
        "description": "Content Team — researches a topic and writes a LinkedIn post",
        "agents": ["Topic Researcher", "Writer", "Editor"],
        "input_fields": ["topic"],
    },
}


# --- Crew Runner ---

def run_crew_in_background(task_id: str, crew_name: str, inputs: dict):
    """Run a CrewAI crew in a background thread."""
    task = tasks[task_id]
    task.status = TaskStatus.running
    task.current_step = "1/3 — Research"

    try:
        if crew_name == "research":
            crew_inputs = {
                "topic": inputs.get("topic", "AI Agents"),
                "current_year": str(datetime.now().year),
            }
            task.current_step = "1/3 — Research Lead analyzing"
            result = ResearchCrew().crew().kickoff(inputs=crew_inputs)
        elif crew_name == "sales":
            crew_inputs = {
                "company": inputs.get("company", "Unknown Company"),
            }
            task.current_step = "1/3 — Company Researcher analyzing"
            result = SalesCrew().crew().kickoff(inputs=crew_inputs)
        elif crew_name == "content":
            crew_inputs = {
                "topic": inputs.get("topic", "AI Trends"),
            }
            task.current_step = "1/3 — Topic Researcher analyzing"
            result = ContentCrew().crew().kickoff(inputs=crew_inputs)
        else:
            raise ValueError(f"Unknown crew: {crew_name}")

        task.result = str(result)
        task.status = TaskStatus.completed

    except Exception as e:
        task.status = TaskStatus.failed
        task.error = str(e)

    task.completed_at = datetime.now(timezone.utc).isoformat()


# --- App ---

app = FastAPI(
    title="CrewAI-n8n Bridge",
    description="FastAPI service wrapping CrewAI agent teams. Trigger multi-agent crews via HTTP.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "service": "CrewAI-n8n Bridge",
        "version": "0.1.0",
        "available_crews": list(AVAILABLE_CREWS.keys()),
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "crews": list(AVAILABLE_CREWS.keys()),
        "active_tasks": sum(1 for t in tasks.values() if t.status == TaskStatus.running),
    }


@app.get("/crews")
def list_crews():
    return {"crews": list(AVAILABLE_CREWS.values())}


@app.post("/crews/{crew_name}/kickoff", response_model=KickoffResponse)
def kickoff_crew(crew_name: str, request: KickoffRequest):
    if crew_name not in AVAILABLE_CREWS:
        raise HTTPException(
            status_code=404,
            detail=f"Crew '{crew_name}' not found. Available: {list(AVAILABLE_CREWS.keys())}",
        )

    task_id = str(uuid.uuid4())[:8]
    inputs = request.model_dump(exclude_none=True)

    task_state = TaskState(
        task_id=task_id,
        crew_name=crew_name,
        status=TaskStatus.queued,
        inputs=inputs,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    tasks[task_id] = task_state

    thread = threading.Thread(
        target=run_crew_in_background,
        args=(task_id, crew_name, inputs),
        daemon=True,
    )
    thread.start()

    return KickoffResponse(
        task_id=task_id,
        status=TaskStatus.queued,
        crew_name=crew_name,
    )


@app.get("/tasks/{task_id}/status")
def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    task = tasks[task_id]
    return {
        "task_id": task.task_id,
        "crew_name": task.crew_name,
        "status": task.status,
        "current_step": task.current_step,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@app.get("/tasks/{task_id}/result")
def get_task_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    task = tasks[task_id]

    if task.status == TaskStatus.running:
        raise HTTPException(status_code=202, detail="Task still running")
    if task.status == TaskStatus.queued:
        raise HTTPException(status_code=202, detail="Task queued")
    if task.status == TaskStatus.failed:
        return {
            "task_id": task.task_id,
            "status": "failed",
            "error": task.error,
        }

    return {
        "task_id": task.task_id,
        "status": "completed",
        "crew_name": task.crew_name,
        "result": task.result,
        "inputs": task.inputs,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }
