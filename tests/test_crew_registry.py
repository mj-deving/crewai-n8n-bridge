"""Tests for crew registry — validates all 5 built-in crews have correct schemas."""

import pytest

from app.runner import AVAILABLE_CREWS, STATIC_CREW_NAMES


REQUIRED_FIELDS = {"name", "description", "agents", "input_fields"}


class TestStaticCrewRegistry:
    def test_five_static_crews_registered(self):
        assert len(STATIC_CREW_NAMES) == 5

    def test_static_names_match_available_crews(self):
        assert STATIC_CREW_NAMES == {"research", "sales", "content", "strategy", "research-flow"}

    @pytest.mark.parametrize("crew_name", ["research", "sales", "content", "strategy", "research-flow"])
    def test_crew_has_required_fields(self, crew_name):
        crew = AVAILABLE_CREWS[crew_name]
        assert REQUIRED_FIELDS.issubset(crew.keys()), f"{crew_name} missing fields: {REQUIRED_FIELDS - crew.keys()}"

    @pytest.mark.parametrize("crew_name", ["research", "sales", "content", "strategy", "research-flow"])
    def test_crew_name_matches_key(self, crew_name):
        assert AVAILABLE_CREWS[crew_name]["name"] == crew_name

    def test_research_crew_has_three_agents(self):
        assert len(AVAILABLE_CREWS["research"]["agents"]) == 3

    def test_sales_crew_input_is_company(self):
        assert AVAILABLE_CREWS["sales"]["input_fields"] == ["company"]

    def test_strategy_crew_is_hierarchical(self):
        assert AVAILABLE_CREWS["strategy"]["process"] == "hierarchical"

    def test_research_flow_is_flow_process(self):
        assert AVAILABLE_CREWS["research-flow"]["process"] == "flow"

    def test_strategy_crew_has_manager_agent(self):
        agents = AVAILABLE_CREWS["strategy"]["agents"]
        assert "(Manager)" in agents
