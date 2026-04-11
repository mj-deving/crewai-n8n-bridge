# CrewAI-n8n Bridge

FastAPI-Service der CrewAI Agent-Teams als REST-Endpoints exposed. n8n (oder jeder HTTP-Client) kann Multi-Agent-Reasoning per API-Call triggern.

```
┌─ n8n / curl ──────────┐     ┌─ FastAPI (CrewAI Bridge) ──────────────────┐
│                        │     │                                            │
│  POST /kickoff ────────┼────►│  Spawnt Crew (3 Agents, sequential)       │
│                        │     │  Returns { task_id: "abc123" }            │
│  GET /status ◄─────────┼─────│  { status: "running", step: "2/3" }      │
│                        │     │                                            │
│  GET /result ◄─────────┼─────│  { result: "## Report\n..." }            │
└────────────────────────┘     └────────────────────────────────────────────┘
```

## Tech-Stack

| Komponente | Tool | Version |
|---|---|---|
| Agent Framework | CrewAI | 1.14.1 |
| LLM | Claude Sonnet 4 via OpenRouter | openrouter/anthropic/claude-sonnet-4 |
| API Layer | FastAPI + Uvicorn | 0.135.3 |
| Task State | In-Memory Dict | v1 |
| Python | 3.12.3 | |

## 3 Agent-Crews

### Research Crew
**Agents:** Research Lead → Data Analyst → Report Writer
**Input:** `{"topic": "KI im deutschen Maschinenbau 2026"}`
**Output:** Strukturierter Executive Brief (~5KB) mit Summary, Key Findings, Data Table, Implications, Sources

### Sales Crew
**Agents:** Company Researcher → Pitch Writer → Offer Creator
**Input:** `{"company": "Everlast AI"}`
**Output:** KI-Lösungsvorschlag auf Deutsch (~2.3KB) mit Pain Points, Lösung, Timeline, ROI

### Content Crew
**Agents:** Topic Researcher → Writer → Editor
**Input:** `{"topic": "Warum 94% der KMUs noch keine KI haben"}`
**Output:** Fertiger LinkedIn-Post auf Deutsch (~1KB) mit Hashtags, copy-paste-ready

## Setup

```bash
# Python 3.10-3.13 erforderlich
python3 --version

# Venv + Dependencies
python3 -m venv venv
source venv/bin/activate
pip install crewai 'crewai[tools]' fastapi uvicorn

# Crew-Packages installieren
cd research_crew && pip install -e . && cd ..

# Environment
export OPENROUTER_API_KEY=<your-key>
```

## API starten

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Beschreibung |
|---|---|---|
| GET | `/` | Service info + verfügbare Crews |
| GET | `/health` | Health check + aktive Tasks |
| GET | `/crews` | Details aller Crews (Agents, Input-Felder) |
| POST | `/crews/{name}/kickoff` | Crew starten, returns `task_id` |
| GET | `/tasks/{id}/status` | Status: queued/running/completed/failed |
| GET | `/tasks/{id}/result` | Ergebnis (nur wenn completed) |

## Beispiel: Kompletter Workflow

```bash
# 1. Crew starten
TASK_ID=$(curl -s -X POST http://localhost:8000/crews/research/kickoff \
  -H "Content-Type: application/json" \
  -d '{"topic": "Voice AI im DACH-Mittelstand"}' | jq -r '.task_id')
echo "Task: $TASK_ID"

# 2. Status pollen (~60s)
curl -s http://localhost:8000/tasks/$TASK_ID/status
# → {"status": "running", "current_step": "1/3 — Research Lead analyzing"}

# 3. Ergebnis abholen
curl -s http://localhost:8000/tasks/$TASK_ID/result | jq '.result'
```

## Was funktioniert hat

- **OpenRouter + LiteLLM:** Model-String `openrouter/anthropic/claude-sonnet-4` in agents.yaml — LiteLLM routet automatisch
- **@CrewBase + YAML:** Saubere Trennung von Agent-Config und Code
- **Background Threads:** Mehrere Crews können parallel laufen
- **Sequential Process:** Vorhersagbare Ergebnisse, Agents bauen aufeinander auf via `context`

## Was wir gelernt haben

- OpenRouter Model-IDs haben **keinen Datums-Suffix** (`claude-sonnet-4`, nicht `claude-sonnet-4-20250514`)
- `crewai run` erstellt eigene `.venv` mit `uv` — für FastAPI importieren wir die Crew-Klassen direkt
- `OPENROUTER_API_KEY` wird von LiteLLM automatisch erkannt
- Agents ohne `tools: [web_search]` generieren Content aus Training-Wissen — für echte Recherche braucht man Search-Tools

## Projektstruktur

```
crewai-n8n-bridge/
├── app/
│   └── main.py              ← FastAPI mit allen Endpoints
├── research_crew/
│   └── src/research_crew/
│       ├── config/
│       │   ├── agents.yaml   ← 3 Research Agents
│       │   └── tasks.yaml    ← 3 Sequential Tasks
│       └── crew.py           ← @CrewBase Klasse
├── sales_crew/
│   └── src/sales_crew/
│       ├── config/
│       │   ├── agents.yaml   ← 3 Sales Agents
│       │   └── tasks.yaml    ← 3 Sequential Tasks
│       └── crew.py           ← @CrewBase Klasse
├── content_crew/
│   └── src/content_crew/
│       ├── config/
│       │   ├── agents.yaml   ← 3 Content Agents
│       │   └── tasks.yaml    ← 3 Sequential Tasks
│       └── crew.py           ← @CrewBase Klasse
└── README.md
```

## Nächste Schritte

- [ ] Webhook Callbacks statt Polling (POST an n8n wenn Crew fertig)
- [ ] n8n Workflow: Webhook → CrewAI → Email mit Report
- [ ] Web Search Tools für echte Recherche
- [ ] Token/Cost Tracking pro Crew-Run
- [ ] Docker Compose (crewai-bridge + n8n)
