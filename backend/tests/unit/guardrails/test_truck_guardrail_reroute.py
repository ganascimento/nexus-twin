import pytest

from src.guardrails.truck import TruckDecision


def test_reroute_action_accepted():
    decision = TruckDecision(
        action="reroute",
        reasoning_summary="Route blocked, recalculating",
        payload={"order_id": "order_01", "reason": "route_blocked"},
    )
    assert decision.action == "reroute"


def test_reroute_requires_payload():
    with pytest.raises(Exception):
        TruckDecision(
            action="reroute",
            reasoning_summary="Route blocked",
            payload=None,
        )
