"""
CrewAI-n8n Bridge — FastAPI async wrapper for CrewAI crews.

Endpoints:
  GET  /                          → API info + available crews
  GET  /health                    → Health check
  GET  /crews                     → List all crews (static + dynamic)
  POST /crews                     → Create a dynamic crew
  DELETE /crews/{crew_name}       → Delete a dynamic crew
  POST /crews/{crew_name}/kickoff → Start crew, returns task_id
  GET  /tasks/{task_id}/status    → Task status + progress
  GET  /tasks/{task_id}/stream    → SSE stream of live agent steps
  GET  /tasks/{task_id}/result    → Task result (when completed)
"""

import asyncio
import json
import queue
import threading
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models import (
    CreateCrewRequest,
    KickoffRequest,
    KickoffResponse,
    TaskStatus,
)
from app.runner import (
    AVAILABLE_CREWS,
    STATIC_CREW_NAMES,
    dynamic_crews,
    event_queues,
    run_crew_in_background,
    tasks,
)


# --- App ---

app = FastAPI(
    title="CrewAI-n8n Bridge",
    description="FastAPI service wrapping CrewAI agent teams. Trigger multi-agent crews via HTTP.",
    version="0.2.0",
)


@app.get("/")
def root():
    return {
        "service": "CrewAI-n8n Bridge",
        "version": "0.2.0",
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


# --- Dynamic Crew Management ---

@app.post("/crews", status_code=201)
def create_crew(request: CreateCrewRequest):
    """Create a dynamic crew from agent/task definitions."""
    name = request.name

    # ISC-12: Cannot overwrite static crews
    if name in STATIC_CREW_NAMES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot overwrite built-in crew '{name}'.",
        )

    # ISC-4: Minimum 1 agent and 1 task
    if len(request.agents) < 1:
        raise HTTPException(status_code=422, detail="At least 1 agent required.")
    if len(request.tasks) < 1:
        raise HTTPException(status_code=422, detail="At least 1 task required.")

    # ISC-5: Validate agent references in tasks
    agent_roles = {a.role for a in request.agents}
    for i, task_def in enumerate(request.tasks):
        if task_def.agent not in agent_roles:
            raise HTTPException(
                status_code=422,
                detail=f"Task {i} references agent '{task_def.agent}' which doesn't exist. "
                       f"Available: {sorted(agent_roles)}",
            )

    # ISC-6: Validate context references
    for i, task_def in enumerate(request.tasks):
        for ctx_ref in task_def.context:
            if not ctx_ref.startswith("task_"):
                raise HTTPException(
                    status_code=422,
                    detail=f"Task {i} context '{ctx_ref}' invalid. Use 'task_0', 'task_1', etc.",
                )
            try:
                ref_idx = int(ctx_ref.split("_")[1])
            except (IndexError, ValueError):
                raise HTTPException(
                    status_code=422,
                    detail=f"Task {i} context '{ctx_ref}' invalid format.",
                )
            if ref_idx >= i:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task {i} context '{ctx_ref}' must reference an earlier task (index < {i}).",
                )

    # Validate process
    if request.process not in ("sequential", "hierarchical"):
        raise HTTPException(
            status_code=422,
            detail=f"Process must be 'sequential' or 'hierarchical', got '{request.process}'.",
        )

    # Register
    crew_info = {
        "name": name,
        "description": f"Dynamic crew: {len(request.agents)} agents, {request.process} process",
        "agents": [a.role for a in request.agents],
        "input_fields": [],
        "process": request.process,
        "dynamic": True,
    }
    AVAILABLE_CREWS[name] = crew_info
    dynamic_crews[name] = {"config": request}

    return {
        "message": f"Crew '{name}' created",
        "crew": crew_info,
        "kickoff_url": f"/crews/{name}/kickoff",
    }


@app.delete("/crews/{crew_name}")
def delete_crew(crew_name: str):
    """Delete a dynamic crew. Static crews cannot be deleted."""
    if crew_name in STATIC_CREW_NAMES:
        raise HTTPException(status_code=403, detail=f"Cannot delete built-in crew '{crew_name}'.")
    if crew_name not in dynamic_crews:
        raise HTTPException(status_code=404, detail=f"Dynamic crew '{crew_name}' not found.")

    del dynamic_crews[crew_name]
    del AVAILABLE_CREWS[crew_name]
    return {"message": f"Crew '{crew_name}' deleted"}


# --- Kickoff ---

@app.post("/crews/{crew_name}/kickoff", response_model=KickoffResponse)
def kickoff_crew(crew_name: str, request: KickoffRequest):
    if crew_name not in AVAILABLE_CREWS:
        raise HTTPException(
            status_code=404,
            detail=f"Crew '{crew_name}' not found. Available: {list(AVAILABLE_CREWS.keys())}",
        )

    task_id = str(uuid.uuid4())[:8]
    inputs = request.model_dump(exclude_none=True)

    from app.models import TaskState

    task_state = TaskState(
        task_id=task_id,
        crew_name=crew_name,
        status=TaskStatus.queued,
        inputs={k: v for k, v in inputs.items() if k != "callback_url"},
        callback_url=request.callback_url,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    tasks[task_id] = task_state
    event_queues[task_id] = queue.Queue()

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


# --- Task Endpoints ---

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


@app.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE stream of live agent steps for a running task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    q = event_queues.get(task_id)
    if not q:
        raise HTTPException(status_code=404, detail=f"No event stream for task '{task_id}'")

    task = tasks[task_id]
    if task.status in (TaskStatus.completed, TaskStatus.failed):
        raise HTTPException(
            status_code=410,
            detail=f"Task already {task.status.value}. Use /tasks/{task_id}/result instead.",
        )

    async def event_generator():
        while True:
            try:
                event = await asyncio.to_thread(q.get, timeout=1.0)
            except Exception:
                if tasks[task_id].status in (TaskStatus.completed, TaskStatus.failed):
                    while not q.empty():
                        try:
                            event = q.get_nowait()
                            yield {
                                "event": event["event"],
                                "data": json.dumps(event["data"]),
                            }
                        except queue.Empty:
                            break
                    return
                continue

            yield {
                "event": event["event"],
                "data": json.dumps(event["data"]),
            }

            if event["event"] in ("task_complete", "error"):
                return

    return EventSourceResponse(event_generator())


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
        "duration_sec": task.duration_sec,
        "usage": {
            "total_tokens": task.total_tokens,
            "prompt_tokens": task.prompt_tokens,
            "completion_tokens": task.completion_tokens,
            "successful_requests": task.successful_requests,
        },
    }
