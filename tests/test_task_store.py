"""Tests for in-memory task state management."""

import queue

import pytest

from app.models import TaskState, TaskStatus
from app.runner import tasks, event_queues, _emit_event


class TestTaskStateModel:
    def test_create_task_with_required_fields(self):
        task = TaskState(
            task_id="abc",
            crew_name="research",
            status=TaskStatus.queued,
            inputs={"topic": "test"},
            started_at="2026-04-14T10:00:00+00:00",
        )
        assert task.task_id == "abc"
        assert task.status == TaskStatus.queued
        assert task.result is None
        assert task.duration_sec is None

    def test_task_status_transitions(self):
        task = TaskState(
            task_id="t1",
            crew_name="research",
            status=TaskStatus.queued,
            inputs={},
            started_at="2026-04-14T10:00:00+00:00",
        )
        task.status = TaskStatus.running
        assert task.status == TaskStatus.running
        task.status = TaskStatus.completed
        assert task.status == TaskStatus.completed

    def test_task_optional_fields_default_none(self):
        task = TaskState(
            task_id="t2",
            crew_name="sales",
            status=TaskStatus.queued,
            inputs={},
            started_at="2026-04-14T10:00:00+00:00",
        )
        assert task.callback_url is None
        assert task.error is None
        assert task.total_tokens is None
        assert task.completed_at is None


class TestEventQueue:
    def test_emit_event_to_existing_queue(self):
        tid = "eq-test-1"
        event_queues[tid] = queue.Queue()
        _emit_event(tid, "agent_start", {"agent": "Test", "step": "1/1"})

        event = event_queues[tid].get_nowait()
        assert event["event"] == "agent_start"
        assert event["data"]["agent"] == "Test"
        event_queues.pop(tid)

    def test_emit_event_to_missing_queue_is_noop(self):
        # Should not raise
        _emit_event("nonexistent-task", "agent_start", {"agent": "X"})

    def test_multiple_events_preserve_order(self):
        tid = "eq-test-2"
        event_queues[tid] = queue.Queue()
        _emit_event(tid, "agent_start", {"step": "1"})
        _emit_event(tid, "agent_complete", {"step": "1"})
        _emit_event(tid, "task_complete", {"done": True})

        events = []
        while not event_queues[tid].empty():
            events.append(event_queues[tid].get_nowait())

        assert [e["event"] for e in events] == ["agent_start", "agent_complete", "task_complete"]
        event_queues.pop(tid)
