"""Shared fixtures for CrewAI-n8n Bridge tests."""

import queue
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models import TaskState, TaskStatus


@pytest.fixture()
def client():
    """Fresh TestClient with clean state for each test."""
    from app.runner import tasks, event_queues, dynamic_crews, AVAILABLE_CREWS, STATIC_CREW_NAMES

    # Snapshot original state
    original_crews = dict(AVAILABLE_CREWS)
    original_dynamic = dict(dynamic_crews)

    # Clear mutable state
    tasks.clear()
    event_queues.clear()
    dynamic_crews.clear()

    # Reset AVAILABLE_CREWS to static only
    AVAILABLE_CREWS.clear()
    AVAILABLE_CREWS.update(original_crews)
    for name in list(AVAILABLE_CREWS):
        if name not in STATIC_CREW_NAMES:
            del AVAILABLE_CREWS[name]

    from app.main import app
    with TestClient(app) as c:
        yield c

    # Restore
    tasks.clear()
    event_queues.clear()
    dynamic_crews.clear()
    AVAILABLE_CREWS.clear()
    AVAILABLE_CREWS.update(original_crews)


@pytest.fixture()
def completed_task():
    """Insert a completed task directly into task store."""
    from app.runner import tasks, event_queues

    task = TaskState(
        task_id="test-done",
        crew_name="research",
        status=TaskStatus.completed,
        inputs={"topic": "AI Testing"},
        result="Mock research result about AI Testing.",
        started_at="2026-04-14T10:00:00+00:00",
        completed_at="2026-04-14T10:01:25+00:00",
        current_step="3/3 — Report Writer writing",
        duration_sec=85.0,
        total_tokens=6800,
        prompt_tokens=5000,
        completion_tokens=1800,
        successful_requests=6,
    )
    tasks[task.task_id] = task
    event_queues[task.task_id] = queue.Queue()
    yield task
    tasks.pop(task.task_id, None)
    event_queues.pop(task.task_id, None)


@pytest.fixture()
def running_task():
    """Insert a running task directly into task store."""
    from app.runner import tasks, event_queues

    task = TaskState(
        task_id="test-run",
        crew_name="research",
        status=TaskStatus.running,
        inputs={"topic": "AI Testing"},
        started_at="2026-04-14T10:00:00+00:00",
        current_step="1/3 — Research Lead analyzing",
    )
    tasks[task.task_id] = task
    event_queues[task.task_id] = queue.Queue()
    yield task
    tasks.pop(task.task_id, None)
    event_queues.pop(task.task_id, None)


@pytest.fixture()
def failed_task():
    """Insert a failed task directly into task store."""
    from app.runner import tasks, event_queues

    task = TaskState(
        task_id="test-fail",
        crew_name="research",
        status=TaskStatus.failed,
        inputs={"topic": "AI Testing"},
        error="API key required for openrouter",
        started_at="2026-04-14T10:00:00+00:00",
        completed_at="2026-04-14T10:00:02+00:00",
        duration_sec=2.0,
    )
    tasks[task.task_id] = task
    event_queues[task.task_id] = queue.Queue()
    yield task
    tasks.pop(task.task_id, None)
    event_queues.pop(task.task_id, None)


@pytest.fixture()
def mock_kickoff():
    """Mock run_crew_in_background to complete instantly without LLM calls."""
    def fake_runner(task_id, crew_name, inputs):
        from app.runner import tasks
        task = tasks[task_id]
        task.status = TaskStatus.completed
        task.result = f"Mock result for {crew_name}"
        task.duration_sec = 0.1
        task.completed_at = datetime.now(timezone.utc).isoformat()
        task.total_tokens = 100
        task.prompt_tokens = 80
        task.completion_tokens = 20
        task.successful_requests = 2

    with patch("app.main.run_crew_in_background", side_effect=fake_runner) as mock:
        yield mock


def _dynamic_crew_payload(name="test-crew", process="sequential"):
    """Helper to build a valid dynamic crew creation payload."""
    return {
        "name": name,
        "agents": [
            {"role": "Analyst", "goal": "Analyze data", "backstory": "Expert analyst"},
            {"role": "Writer", "goal": "Write reports", "backstory": "Expert writer"},
        ],
        "tasks": [
            {"description": "Analyze the topic", "expected_output": "Analysis report", "agent": "Analyst"},
            {"description": "Write summary", "expected_output": "Summary", "agent": "Writer", "context": ["task_0"]},
        ],
        "process": process,
    }
