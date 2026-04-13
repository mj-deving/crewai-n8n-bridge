"""
Research Flow with Quality Gate.

Flow: run research crew → score quality (0-10) → if < 7 and iterations left, re-run → deliver.
Uses a simple linear flow without router to avoid infinite loop issues.
"""

import json
import os
import sys
import time
from datetime import datetime

from crewai import LLM
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel

# Add research_crew to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "research_crew", "src"))
from research_crew.crew import ResearchCrew


class ResearchFlowState(BaseModel):
    topic: str = ""
    research_output: str = ""
    quality_score: int = 0
    quality_feedback: str = ""
    iteration: int = 0
    max_iterations: int = 2
    final_output: str = ""


class ResearchFlow(Flow[ResearchFlowState]):
    """Research Flow with quality gate — retries if score < 7."""

    def _run_crew(self):
        """Run the research crew (internal helper)."""
        inputs = {
            "topic": self.state.topic,
            "current_year": str(datetime.now().year),
        }
        if self.state.quality_feedback:
            inputs["topic"] = (
                f"{self.state.topic}\n\n"
                f"IMPORTANT FEEDBACK FROM PREVIOUS ITERATION — address these issues:\n"
                f"{self.state.quality_feedback}"
            )

        result = ResearchCrew().crew().kickoff(inputs=inputs)
        self.state.research_output = str(result)

    def _score_quality(self):
        """Score the research output 0-10 (internal helper)."""
        llm = LLM(
            model="openrouter/anthropic/claude-sonnet-4",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            max_tokens=512,
        )

        prompt = f"""Rate this research report on a scale of 0-10. Consider:
- Completeness (covers key aspects of the topic)
- Data quality (includes specific numbers, statistics)
- Structure (clear sections, logical flow)
- Actionability (provides practical insights)

Report:
{self.state.research_output[:3000]}

Respond with ONLY a JSON object:
{{"score": <0-10>, "feedback": "<specific improvements needed if score < 7>"}}"""

        response = llm.call([{"role": "user", "content": prompt}])
        response_text = str(response) if not isinstance(response, str) else response

        try:
            json_start = response_text.index("{")
            json_end = response_text.rindex("}") + 1
            data = json.loads(response_text[json_start:json_end])
            self.state.quality_score = int(data.get("score", 7))
            self.state.quality_feedback = data.get("feedback", "")
        except (ValueError, json.JSONDecodeError):
            self.state.quality_score = 7
            self.state.quality_feedback = ""

    @start()
    def run_research_with_quality_gate(self):
        """Run research crew, score, retry if needed, deliver."""
        while self.state.iteration < self.state.max_iterations:
            self.state.iteration += 1
            print(f"[Flow] Iteration {self.state.iteration}: Running research on '{self.state.topic}'")

            self._run_crew()
            print(f"[Flow] Research complete ({len(self.state.research_output)} chars)")

            self._score_quality()
            print(f"[Flow] Quality score: {self.state.quality_score}/10")

            if self.state.quality_score >= 7:
                print(f"[Flow] Score >= 7, delivering")
                break

            print(f"[Flow] Score < 7, retrying with feedback: {self.state.quality_feedback[:100]}...")

        self.state.final_output = self.state.research_output
        print(f"[Flow] Done (score: {self.state.quality_score}, iterations: {self.state.iteration})")
