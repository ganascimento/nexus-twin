import pytest
from pydantic import ValidationError

from src.guardrails.base import AgentDecisionBase


class TestAgentDecisionBase:
    def test_valid_decision(self):
        decision = AgentDecisionBase(
            action="hold",
            reasoning_summary="Stock levels are adequate",
        )
        assert decision.action == "hold"
        assert decision.reasoning_summary == "Stock levels are adequate"

    def test_empty_reasoning_summary_rejected(self):
        with pytest.raises(ValidationError):
            AgentDecisionBase(action="hold", reasoning_summary="")

    def test_whitespace_only_reasoning_summary_rejected(self):
        with pytest.raises(ValidationError):
            AgentDecisionBase(action="hold", reasoning_summary="   ")

    def test_missing_reasoning_summary_rejected(self):
        with pytest.raises(ValidationError):
            AgentDecisionBase(action="hold")
