import os

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool


@CrewBase
class StrategyCrew():
    """Strategy Crew — hierarchical process with manager agent."""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def market_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['market_analyst'],  # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
        )

    @agent
    def tech_scout(self) -> Agent:
        return Agent(
            config=self.agents_config['tech_scout'],  # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()],
        )

    @agent
    def business_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config['business_strategist'],  # type: ignore[index]
            verbose=True,
        )

    @task
    def market_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['market_analysis_task'],  # type: ignore[index]
        )

    @task
    def tech_assessment_task(self) -> Task:
        return Task(
            config=self.tasks_config['tech_assessment_task'],  # type: ignore[index]
        )

    @task
    def strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config['strategy_task'],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the StrategyCrew with hierarchical process."""
        manager = LLM(
            model="openrouter/anthropic/claude-sonnet-4",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            max_tokens=4096,
        )
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical,
            manager_llm=manager,
            verbose=True,
        )
