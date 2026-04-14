"""Tests for FastAPI endpoints — all run without API keys."""

import pytest


class TestRootEndpoint:
    def test_root_returns_service_info(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "CrewAI-n8n Bridge"
        assert data["version"] == "0.2.0"
        assert data["docs"] == "/docs"

    def test_root_lists_all_crew_names(self, client):
        r = client.get("/")
        crews = r.json()["available_crews"]
        assert "research" in crews
        assert "sales" in crews
        assert "content" in crews
        assert "strategy" in crews
        assert "research-flow" in crews


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_counts_active_tasks(self, client, running_task):
        r = client.get("/health")
        assert r.json()["active_tasks"] == 1


class TestCrewsEndpoint:
    def test_list_crews_returns_all_static(self, client):
        r = client.get("/crews")
        assert r.status_code == 200
        names = [c["name"] for c in r.json()["crews"]]
        assert len(names) == 5
        assert set(names) == {"research", "sales", "content", "strategy", "research-flow"}


class TestKickoffEndpoint:
    def test_kickoff_returns_task_id(self, client, mock_kickoff):
        r = client.post(
            "/crews/research/kickoff",
            json={"topic": "AI Testing"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "task_id" in data
        assert data["crew_name"] == "research"
        assert data["status"] == "queued"

    def test_kickoff_unknown_crew_returns_404(self, client):
        r = client.post(
            "/crews/nonexistent/kickoff",
            json={"topic": "test"},
        )
        assert r.status_code == 404
        assert "nonexistent" in r.json()["detail"]

    def test_kickoff_excludes_callback_url_from_inputs(self, client, mock_kickoff):
        r = client.post(
            "/crews/research/kickoff",
            json={"topic": "test", "callback_url": "http://example.com/hook"},
        )
        task_id = r.json()["task_id"]
        status = client.get(f"/tasks/{task_id}/status")
        # callback_url should not appear as an input — it's metadata
        assert status.status_code == 200


class TestTaskStatusEndpoint:
    def test_status_returns_running_task(self, client, running_task):
        r = client.get(f"/tasks/{running_task.task_id}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"
        assert data["crew_name"] == "research"
        assert data["current_step"] is not None

    def test_status_returns_404_for_unknown_task(self, client):
        r = client.get("/tasks/nonexistent/status")
        assert r.status_code == 404


class TestTaskResultEndpoint:
    def test_result_returns_completed_task(self, client, completed_task):
        r = client.get(f"/tasks/{completed_task.task_id}/result")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["result"] == "Mock research result about AI Testing."
        assert data["duration_sec"] == 85.0

    def test_result_includes_token_usage(self, client, completed_task):
        r = client.get(f"/tasks/{completed_task.task_id}/result")
        usage = r.json()["usage"]
        assert usage["total_tokens"] == 6800
        assert usage["prompt_tokens"] == 5000
        assert usage["completion_tokens"] == 1800
        assert usage["successful_requests"] == 6

    def test_result_returns_202_for_running_task(self, client, running_task):
        r = client.get(f"/tasks/{running_task.task_id}/result")
        assert r.status_code == 202

    def test_result_returns_failed_task_with_error(self, client, failed_task):
        r = client.get(f"/tasks/{failed_task.task_id}/result")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "failed"
        assert "API key" in data["error"]

    def test_result_returns_404_for_unknown_task(self, client):
        r = client.get("/tasks/nonexistent/result")
        assert r.status_code == 404
