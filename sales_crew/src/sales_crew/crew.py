from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent


@CrewBase
class SalesCrew():
    """Sales Outreach Crew — company research, pitch writing, offer creation."""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def company_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['company_researcher'],  # type: ignore[index]
            verbose=True
        )

    @agent
    def pitch_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['pitch_writer'],  # type: ignore[index]
            verbose=True
        )

    @agent
    def offer_creator(self) -> Agent:
        return Agent(
            config=self.agents_config['offer_creator'],  # type: ignore[index]
            verbose=True
        )

    @task
    def company_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['company_research_task'],  # type: ignore[index]
        )

    @task
    def pitch_task(self) -> Task:
        return Task(
            config=self.tasks_config['pitch_task'],  # type: ignore[index]
        )

    @task
    def offer_task(self) -> Task:
        return Task(
            config=self.tasks_config['offer_task'],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the SalesCrew crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
