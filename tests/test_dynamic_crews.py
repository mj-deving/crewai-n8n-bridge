"""Tests for dynamic crew creation, validation, and lifecycle."""

import pytest

from tests.conftest import _dynamic_crew_payload


class TestCreateDynamicCrew:
    def test_create_crew_returns_201(self, client):
        r = client.post("/crews", json=_dynamic_crew_payload("my-crew"))
        assert r.status_code == 201
        data = r.json()
        assert data["message"] == "Crew 'my-crew' created"
        assert data["crew"]["name"] == "my-crew"
        assert data["kickoff_url"] == "/crews/my-crew/kickoff"

    def test_created_crew_appears_in_list(self, client):
        client.post("/crews", json=_dynamic_crew_payload("visible-crew"))
        r = client.get("/crews")
        names = [c["name"] for c in r.json()["crews"]]
        assert "visible-crew" in names

    def test_created_crew_marked_dynamic(self, client):
        client.post("/crews", json=_dynamic_crew_payload("dyn-crew"))
        r = client.get("/crews")
        crew = next(c for c in r.json()["crews"] if c["name"] == "dyn-crew")
        assert crew["dynamic"] is True


class TestDynamicCrewValidation:
    def test_reject_overwrite_static_crew(self, client):
        r = client.post("/crews", json=_dynamic_crew_payload("research"))
        assert r.status_code == 409
        assert "built-in" in r.json()["detail"]

    def test_reject_empty_agents(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["agents"] = []
        r = client.post("/crews", json=payload)
        assert r.status_code == 422

    def test_reject_empty_tasks(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["tasks"] = []
        r = client.post("/crews", json=payload)
        assert r.status_code == 422

    def test_reject_invalid_agent_reference(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["tasks"][0]["agent"] = "NonExistent"
        r = client.post("/crews", json=payload)
        assert r.status_code == 422
        assert "NonExistent" in r.json()["detail"]

    def test_reject_forward_context_reference(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["tasks"][0]["context"] = ["task_1"]
        r = client.post("/crews", json=payload)
        assert r.status_code == 422
        assert "earlier task" in r.json()["detail"]

    def test_reject_invalid_context_format(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["tasks"][1]["context"] = ["bad_ref"]
        r = client.post("/crews", json=payload)
        assert r.status_code == 422

    def test_reject_invalid_tool_name(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["agents"][0]["tools"] = ["exec_code"]
        r = client.post("/crews", json=payload)
        assert r.status_code == 422

    def test_accept_valid_tool_names(self, client):
        payload = _dynamic_crew_payload("tools-crew")
        payload["agents"][0]["tools"] = ["web_search", "scrape_website"]
        r = client.post("/crews", json=payload)
        assert r.status_code == 201

    def test_reject_invalid_process(self, client):
        payload = _dynamic_crew_payload("bad")
        payload["process"] = "random"
        r = client.post("/crews", json=payload)
        assert r.status_code == 422

    def test_reject_invalid_crew_name(self, client):
        payload = _dynamic_crew_payload("bad name!")
        r = client.post("/crews", json=payload)
        assert r.status_code == 422


class TestDeleteDynamicCrew:
    def test_delete_dynamic_crew(self, client):
        client.post("/crews", json=_dynamic_crew_payload("to-delete"))
        r = client.delete("/crews/to-delete")
        assert r.status_code == 200

        # Verify gone from list
        names = [c["name"] for c in client.get("/crews").json()["crews"]]
        assert "to-delete" not in names

    def test_cannot_delete_static_crew(self, client):
        r = client.delete("/crews/research")
        assert r.status_code == 403
        assert "built-in" in r.json()["detail"]

    def test_delete_nonexistent_returns_404(self, client):
        r = client.delete("/crews/ghost")
        assert r.status_code == 404
