"""Crew runner — background execution, SSE events, callbacks."""

import os
import queue
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models import TaskState, TaskStatus, TOOL_WHITELIST

# Add crew packages to path
_base = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_base, "research_crew", "src"))
sys.path.insert(0, os.path.join(_base, "sales_crew", "src"))
sys.path.insert(0, os.path.join(_base, "content_crew", "src"))
sys.path.insert(0, os.path.join(_base, "strategy_crew", "src"))
sys.path.insert(0, os.path.join(_base, "flows"))

from research_crew.crew import ResearchCrew
from sales_crew.crew import SalesCrew
from content_crew.crew import ContentCrew
from strategy_crew.crew import StrategyCrew
from research_flow import ResearchFlow


# --- Shared State ---

AVAILABLE_CREWS: dict[str, dict] = {
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
    "strategy": {
        "name": "strategy",
        "description": "Strategy Team — hierarchical process with manager coordinating market, tech, and business analysis",
        "agents": ["Market Analyst", "Tech Scout", "Business Strategist", "(Manager)"],
        "input_fields": ["topic"],
        "process": "hierarchical",
    },
    "research-flow": {
        "name": "research-flow",
        "description": "Research Flow — runs research crew with quality gate (score < 7 triggers retry)",
        "agents": ["Research Lead", "Data Analyst", "Report Writer", "(Quality Judge)"],
        "input_fields": ["topic"],
        "process": "flow",
    },
}

STATIC_CREW_NAMES: set[str] = set(AVAILABLE_CREWS.keys())
dynamic_crews: dict[str, dict] = {}

tasks: dict[str, TaskState] = {}
event_queues: dict[str, queue.Queue] = {}


# --- SSE Helpers ---

def _emit_event(task_id: str, event: str, data: dict):
    """Push an SSE event to the task's queue (thread-safe)."""
    q = event_queues.get(task_id)
    if q:
        q.put({"event": event, "data": data})


def _make_callbacks(task_id: str, crew_name: str):
    """Create step_callback and task_callback that emit SSE events."""
    agents = AVAILABLE_CREWS[crew_name]["agents"]
    total = len([a for a in agents if not a.startswith("(")])
    state = {"task_index": 0, "started": False}

    def step_callback(step_output):
        from crewai.agents.parser import AgentFinish
        idx = state["task_index"]
        agent_name = agents[min(idx, len(agents) - 1)]
        if agent_name.startswith("("):
            agent_name = agent_name.strip("()")

        if not state["started"]:
            state["started"] = True
            _emit_event(task_id, "agent_start", {
                "agent": agent_name,
                "step": f"{idx + 1}/{total}",
            })

        if isinstance(step_output, AgentFinish):
            _emit_event(task_id, "agent_complete", {
                "agent": agent_name,
                "step": f"{idx + 1}/{total}",
                "output_preview": str(step_output.output)[:200],
            })

    def task_callback(task_output):
        state["task_index"] += 1
        state["started"] = False
        idx = state["task_index"]
        if idx < total:
            agent_name = agents[idx]
            if agent_name.startswith("("):
                agent_name = agent_name.strip("()")
            _emit_event(task_id, "agent_start", {
                "agent": agent_name,
                "step": f"{idx + 1}/{total}",
            })

    return step_callback, task_callback


# --- Callback ---

def send_callback(task: TaskState):
    """POST result to callback_url if configured."""
    if not task.callback_url:
        return
    payload = {
        "task_id": task.task_id,
        "crew_name": task.crew_name,
        "status": task.status.value,
        "result": task.result,
        "error": task.error,
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
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(task.callback_url, json=payload)
            print(f"[Callback] POST {task.callback_url} → {resp.status_code}")
    except Exception as e:
        print(f"[Callback] Failed to POST {task.callback_url}: {e}")


# --- Dynamic Crew Builder ---

def _resolve_tools(tool_names: list[str]):
    """Resolve tool name strings to CrewAI tool instances."""
    from crewai_tools import SerperDevTool, ScrapeWebsiteTool
    tool_map = {
        "SerperDevTool": SerperDevTool,
        "ScrapeWebsiteTool": ScrapeWebsiteTool,
    }
    resolved = []
    for name in tool_names:
        cls_name = TOOL_WHITELIST[name]
        resolved.append(tool_map[cls_name]())
    return resolved


def _build_dynamic_crew(crew_name: str, step_cb, task_cb):
    """Build a CrewAI Crew from a dynamic crew config."""
    from crewai import Agent, Crew, LLM, Process, Task

    config = dynamic_crews[crew_name]["config"]

    # Build agents
    agent_map: dict[str, Agent] = {}
    for agent_def in config.agents:
        tools = _resolve_tools(agent_def.tools) if agent_def.tools else []
        agent_map[agent_def.role] = Agent(
            role=agent_def.role,
            goal=agent_def.goal,
            backstory=agent_def.backstory,
            tools=tools,
            llm="openrouter/anthropic/claude-sonnet-4",
            verbose=True,
            max_iter=3,
        )

    # Build tasks with context references
    task_list: list[Task] = []
    task_by_index: dict[str, Task] = {}
    for i, task_def in enumerate(config.tasks):
        ctx = [task_by_index[ref] for ref in task_def.context if ref in task_by_index]
        t = Task(
            description=task_def.description,
            expected_output=task_def.expected_output,
            agent=agent_map[task_def.agent],
            context=ctx if ctx else None,
        )
        task_list.append(t)
        task_by_index[f"task_{i}"] = t

    # Build crew
    process = Process.hierarchical if config.process == "hierarchical" else Process.sequential
    crew_kwargs: dict[str, Any] = {
        "agents": list(agent_map.values()),
        "tasks": task_list,
        "process": process,
        "verbose": True,
        "step_callback": step_cb,
        "task_callback": task_cb,
    }
    if process == Process.hierarchical:
        crew_kwargs["manager_llm"] = LLM(
            model="openrouter/anthropic/claude-sonnet-4",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            max_tokens=4096,
        )

    return Crew(**crew_kwargs)


# --- Crew Runner ---

def run_crew_in_background(task_id: str, crew_name: str, inputs: dict):
    """Run a CrewAI crew in a background thread."""
    task = tasks[task_id]
    task.status = TaskStatus.running
    start_time = time.time()
    step_cb, task_cb = _make_callbacks(task_id, crew_name)

    try:
        if crew_name in dynamic_crews:
            task.current_step = f"1/{len(dynamic_crews[crew_name]['config'].agents)} — starting"
            crew_obj = _build_dynamic_crew(crew_name, step_cb, task_cb)
            result = crew_obj.kickoff(inputs=inputs)
        elif crew_name == "research":
            crew_inputs = {
                "topic": inputs.get("topic", "AI Agents"),
                "current_year": str(datetime.now().year),
            }
            task.current_step = "1/3 — Research Lead analyzing"
            crew_obj = ResearchCrew().crew()
            crew_obj.step_callback = step_cb
            crew_obj.task_callback = task_cb
            result = crew_obj.kickoff(inputs=crew_inputs)
        elif crew_name == "sales":
            crew_inputs = {
                "company": inputs.get("company", "Unknown Company"),
            }
            task.current_step = "1/3 — Company Researcher analyzing"
            crew_obj = SalesCrew().crew()
            crew_obj.step_callback = step_cb
            crew_obj.task_callback = task_cb
            result = crew_obj.kickoff(inputs=crew_inputs)
        elif crew_name == "content":
            crew_inputs = {
                "topic": inputs.get("topic", "AI Trends"),
            }
            task.current_step = "1/3 — Topic Researcher analyzing"
            crew_obj = ContentCrew().crew()
            crew_obj.step_callback = step_cb
            crew_obj.task_callback = task_cb
            result = crew_obj.kickoff(inputs=crew_inputs)
        elif crew_name == "strategy":
            crew_inputs = {
                "topic": inputs.get("topic", "AI Strategy"),
            }
            task.current_step = "1/3 — Manager delegating tasks"
            crew_obj = StrategyCrew().crew()
            crew_obj.step_callback = step_cb
            crew_obj.task_callback = task_cb
            result = crew_obj.kickoff(inputs=crew_inputs)
        elif crew_name == "research-flow":
            task.current_step = "Flow: running research with quality gate"
            _emit_event(task_id, "agent_start", {
                "agent": "Research Flow",
                "step": "1/1",
            })
            flow = ResearchFlow()
            flow_result = flow.kickoff(inputs={"topic": inputs.get("topic", "AI Agents")})
            task.result = flow.state.final_output
            task.status = TaskStatus.completed
            task.duration_sec = round(time.time() - start_time, 1)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            _emit_event(task_id, "task_complete", {
                "crew_name": crew_name,
                "duration_sec": task.duration_sec,
            })
            send_callback(task)
            return
        else:
            raise ValueError(f"Unknown crew: {crew_name}")

        task.result = str(result)
        task.status = TaskStatus.completed

        # Capture token usage from CrewOutput
        if hasattr(result, 'token_usage'):
            usage = result.token_usage
            task.total_tokens = usage.total_tokens
            task.prompt_tokens = usage.prompt_tokens
            task.completion_tokens = usage.completion_tokens
            task.successful_requests = usage.successful_requests

    except Exception as e:
        task.status = TaskStatus.failed
        task.error = str(e)
        _emit_event(task_id, "error", {"error": str(e)})

    task.duration_sec = round(time.time() - start_time, 1)
    task.completed_at = datetime.now(timezone.utc).isoformat()
    _emit_event(task_id, "task_complete", {
        "crew_name": crew_name,
        "duration_sec": task.duration_sec,
        "status": task.status.value,
    })
    send_callback(task)
