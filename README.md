# CrewAI-n8n Bridge

FastAPI-Service der CrewAI Agent-Teams als REST-Endpoints exposed. n8n (oder jeder HTTP-Client) kann Multi-Agent-Reasoning per API-Call triggern.

```
┌─ n8n / curl ──────────┐     ┌─ FastAPI (CrewAI Bridge) ──────────────────┐
│                        │     │                                            │
│  POST /kickoff ────────┼────►│  Spawnt Crew (3+ Agents)                  │
│  + callback_url        │     │  Sequential / Hierarchical / Flow         │
│                        │     │  Returns { task_id: "abc123" }            │
│                        │     │                                            │
│  Option A: Polling     │     │                                            │
│  GET /status ◄─────────┼─────│  { status: "running", step: "2/3" }      │
│  GET /result ◄─────────┼─────│  { result: "...", usage: {...} }          │
│                        │     │                                            │
│  Option B: Callback    │     │                                            │
│  Webhook ◄─────────────┼─────│  POST callback_url mit Result            │
└────────────────────────┘     └────────────────────────────────────────────┘
```

## Tech-Stack

| Komponente | Tool | Version |
|---|---|---|
| Agent Framework | CrewAI | 1.14.1 |
| LLM | Claude Sonnet 4 via OpenRouter | openrouter/anthropic/claude-sonnet-4 |
| API Layer | FastAPI + Uvicorn | 0.135.3 |
| Web Search | SerperDevTool + ScrapeWebsiteTool | via crewai-tools |
| Task State | In-Memory Dict | v1 |
| Container | Docker Compose | bridge + n8n |
| Python | 3.12.3 | |

## 5 Agent-Crews

### Research Crew (Sequential)
**Agents:** Research Lead → Data Analyst → Report Writer
**Input:** `{"topic": "KI im deutschen Maschinenbau 2026"}`
**Output:** Strukturierter Executive Brief (~5KB) mit Summary, Key Findings, Data Table, Implications, Sources

### Sales Crew (Sequential)
**Agents:** Company Researcher → Pitch Writer → Offer Creator
**Input:** `{"company": "Everlast AI"}`
**Output:** KI-Lösungsvorschlag auf Deutsch (~2.3KB) mit Pain Points, Lösung, Timeline, ROI

### Content Crew (Sequential)
**Agents:** Topic Researcher → Writer → Editor
**Input:** `{"topic": "Warum 94% der KMUs noch keine KI haben"}`
**Output:** Fertiger LinkedIn-Post auf Deutsch (~1KB) mit Hashtags, copy-paste-ready

### Strategy Crew (Hierarchical)
**Agents:** Manager (auto) → Market Analyst, Tech Scout, Business Strategist
**Process:** `Process.hierarchical` — Manager-Agent verteilt Tasks dynamisch
**Input:** `{"topic": "Voice AI für DACH Versicherungen"}`
**Output:** Strategieempfehlung mit Marktanalyse, Tech-Assessment, Aktionsplan

### Research Flow (Flow mit Quality Gate)
**Agents:** Research Crew + Quality Judge (LLM-Score)
**Process:** `Flow` — Research → Score (0-10) → Score < 7? Retry mit Feedback → Deliver
**Input:** `{"topic": "Agentic AI Frameworks 2026"}`
**Output:** Qualitätsgeprüfter Research Report (mind. Score 7/10)

## Setup

```bash
# Python 3.10-3.13 erforderlich
python3 --version

# Venv + Dependencies
python3 -m venv venv
source venv/bin/activate
pip install crewai 'crewai[tools]' fastapi uvicorn httpx

# Crew-Packages installieren
cd research_crew && pip install -e . && cd ..

# Environment
export OPENROUTER_API_KEY=<your-key>
export SERPER_API_KEY=<your-serper-key>  # Optional: für echte Websuche (serper.dev)
```

### Docker Compose (Alternative)

```bash
# Env-Vars setzen
export OPENROUTER_API_KEY=<your-key>
export SERPER_API_KEY=<your-serper-key>

# Starten
docker compose up -d

# → CrewAI Bridge: http://localhost:8000
# → n8n:           http://localhost:5678
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
| GET | `/crews` | Details aller Crews (Agents, Input-Felder, Process) |
| POST | `/crews/{name}/kickoff` | Crew starten, returns `task_id` |
| GET | `/tasks/{id}/status` | Status: queued/running/completed/failed |
| GET | `/tasks/{id}/result` | Ergebnis + Token Usage + Duration |

Verfügbare Crews: `research`, `sales`, `content`, `strategy`, `research-flow`

## Beispiel: Polling-Workflow

```bash
# 1. Crew starten
TASK_ID=$(curl -s -X POST http://localhost:8000/crews/research/kickoff \
  -H "Content-Type: application/json" \
  -d '{"topic": "Voice AI im DACH-Mittelstand"}' | jq -r '.task_id')
echo "Task: $TASK_ID"

# 2. Status pollen (~60s)
curl -s http://localhost:8000/tasks/$TASK_ID/status
# → {"status": "running", "current_step": "1/3 — Research Lead analyzing"}

# 3. Ergebnis abholen (inkl. Token Usage)
curl -s http://localhost:8000/tasks/$TASK_ID/result | jq '{status, duration_sec, usage, result_preview: .result[:200]}'
```

## Beispiel: Callback-Workflow (kein Polling nötig)

```bash
curl -s -X POST http://localhost:8000/crews/research/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Voice AI im DACH-Mittelstand",
    "callback_url": "http://your-n8n:5678/webhook/crewai-callback"
  }'
# → Crew läuft → POST an callback_url mit vollem Result + Usage
```

## Beispiel: Hierarchical Strategy Crew

```bash
curl -s -X POST http://localhost:8000/crews/strategy/kickoff \
  -H "Content-Type: application/json" \
  -d '{"topic": "Voice AI für DACH Versicherungen"}'
# Manager-Agent koordiniert Market Analyst, Tech Scout, Business Strategist
```

## Beispiel: Research Flow mit Quality Gate

```bash
curl -s -X POST http://localhost:8000/crews/research-flow/kickoff \
  -H "Content-Type: application/json" \
  -d '{"topic": "Agentic AI Frameworks 2026"}'
# Flow: Research → Score → Score < 7? Retry → Deliver
```

## n8n Integration

Workflow-Templates in `n8n/`:
- `research-crew-workflow.json` — Webhook trigger → CrewAI kickoff → respond
- `callback-receiver-workflow.json` — Empfängt Crew-Results via Callback

**Import:** n8n UI → Workflows → Import from File → JSON auswählen

**n8nac (as-code):**
```bash
npm install --save-dev n8n-as-code
npx n8nac init-auth --host http://<n8n-host>:5678 --api-key "<key>"
npx n8nac init-project --project-index 1 --sync-folder workflows
npx n8nac push    # Workflows zu n8n pushen
npx n8nac list    # Aktive Workflows anzeigen
```

## Was funktioniert hat

- **OpenRouter + LiteLLM:** Model-String `openrouter/anthropic/claude-sonnet-4` in agents.yaml — LiteLLM routet automatisch
- **@CrewBase + YAML:** Saubere Trennung von Agent-Config und Code
- **Background Threads:** Mehrere Crews können parallel laufen
- **Sequential Process:** Vorhersagbare Ergebnisse, Agents bauen aufeinander auf via `context`
- **Hierarchical Process:** Manager-Agent verteilt Tasks dynamisch an Worker-Agents
- **CrewAI Flows:** Flow mit Quality Gate — automatischer Retry bei niedrigem Score
- **SerperDevTool:** Echte Websuche, Agents liefern aktuelle Daten statt LLM-Halluzinationen
- **Token Tracking:** Result-Endpoint liefert `usage` (total_tokens, prompt_tokens, completion_tokens) und `duration_sec`
- **Webhook Callbacks:** Optional `callback_url` — eliminiert Polling

## Was wir gelernt haben

- OpenRouter Model-IDs haben **keinen Datums-Suffix** (`claude-sonnet-4`, nicht `claude-sonnet-4-20250514`)
- `crewai run` erstellt eigene `.venv` mit `uv` — für FastAPI importieren wir die Crew-Klassen direkt
- `OPENROUTER_API_KEY` wird von LiteLLM automatisch erkannt
- `Process.hierarchical` braucht `manager_llm` Parameter — nutzt das gleiche OpenRouter-Modell
- CrewAI Flows verwenden `@start()`, `@listen()`, `@router()` Decorators für deterministische Pipelines
- `CrewOutput.token_usage` enthält Token-Metriken direkt nach kickoff()

## Projektstruktur

```
crewai-n8n-bridge/
├── app/
│   └── main.py                  ← FastAPI mit allen Endpoints
├── research_crew/
│   └── src/research_crew/       ← Sequential: Research → Data → Report
├── sales_crew/
│   └── src/sales_crew/          ← Sequential: Company → Pitch → Offer
├── content_crew/
│   └── src/content_crew/        ← Sequential: Research → Write → Edit
├── strategy_crew/
│   └── src/strategy_crew/       ← Hierarchical: Manager → Workers
├── flows/
│   └── research_flow.py         ← Flow: Research + Quality Gate
├── n8n/
│   ├── research-crew-workflow.json
│   └── callback-receiver-workflow.json
├── Dockerfile
├── docker-compose.yml           ← bridge + n8n
└── README.md
```

## Feature-Status

- [x] CrewAI Crews (Research, Sales, Content)
- [x] FastAPI async wrapper mit Background Threads
- [x] Webhook Callbacks (optional callback_url)
- [x] n8n Workflow Templates
- [x] SerperDevTool + ScrapeWebsiteTool
- [x] Token/Cost Tracking pro Crew-Run
- [x] CrewAI Flows mit Quality Gate
- [x] Hierarchical Process (Strategy Crew)
- [x] Docker Compose (bridge + n8n)
- [x] n8nac Setup-Anleitung
