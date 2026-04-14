# CrewAI-n8n Bridge

FastAPI service exposing CrewAI multi-agent crews as REST endpoints. n8n or any HTTP client can trigger agent crews via API.

## Quick Start

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Swagger UI: http://localhost:8000/docs
```

## Architecture

```
app/
  main.py     — FastAPI endpoints (REST + SSE + dynamic crew CRUD)
  models.py   — Pydantic models (TaskState, KickoffRequest, AgentDefinition, etc.)
  runner.py   — Crew runner, SSE event callbacks, dynamic crew builder, shared state

*_crew/src/   — Built-in crews using @CrewBase + YAML config (agents.yaml, tasks.yaml)
flows/        — CrewAI Flow with quality gate (research_flow.py)
```

## Key Conventions

- **LLM:** All agents use `openrouter/anthropic/claude-sonnet-4` via LiteLLM. No date suffix.
- **Env vars:** `OPENROUTER_API_KEY` (required), `SERPER_API_KEY` (optional, for web search)
- **Hierarchical crews:** Must set `manager_llm` with explicit `max_tokens=4096` to prevent 402 errors
- **Flows:** Use linear while-loop pattern, NOT `@router()` + `@listen()` (causes infinite loops)
- **State:** In-memory dicts in `runner.py` — `tasks`, `event_queues`, `dynamic_crews`, `AVAILABLE_CREWS`
- **SSE:** `queue.Queue` (stdlib, thread-safe) bridges background threads to async SSE generator
- **Dynamic crews:** Tool whitelist in `models.py` (`web_search`, `scrape_website`) — no arbitrary code execution

## API Overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/crews` | Create dynamic crew (JSON agents/tasks/process) |
| DELETE | `/crews/{name}` | Delete dynamic crew (static crews protected) |
| POST | `/crews/{name}/kickoff` | Start crew run, returns task_id |
| GET | `/tasks/{id}/status` | Poll task status |
| GET | `/tasks/{id}/stream` | SSE stream of live agent steps |
| GET | `/tasks/{id}/result` | Get completed result + token usage |

## Testing

```bash
# Run full test suite (54 tests, no API keys needed)
pytest tests/ -v

# Quick smoke test
pytest tests/test_api.py -v
```

Tests use `FastAPI.TestClient` with mocked crew runners — no LLM calls.

| File | Tests | Coverage |
|------|-------|----------|
| `test_api.py` | 15 | All REST endpoints, status codes, error cases |
| `test_crew_registry.py` | 14 | Static crew schemas, fields, process types |
| `test_dynamic_crews.py` | 16 | Create/delete lifecycle, all validation rules |
| `test_task_store.py` | 6 | TaskState model, event queue behavior |

## Built-in Crews

| Name | Process | Agents | Input |
|------|---------|--------|-------|
| research | Sequential | Research Lead, Data Analyst, Report Writer | topic |
| sales | Sequential | Company Researcher, Pitch Writer, Offer Creator | company |
| content | Sequential | Topic Researcher, Writer, Editor | topic |
| strategy | Hierarchical | Market Analyst, Tech Scout, Business Strategist + Manager | topic |
| research-flow | Flow | Research Crew + Quality Judge | topic |
