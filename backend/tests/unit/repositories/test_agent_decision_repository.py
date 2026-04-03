import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import AgentDecision
from src.repositories.agent_decision import AgentDecisionRepository


def _make_decision(entity_id="f1"):
    return AgentDecision(
        id=uuid.uuid4(),
        agent_type="factory",
        entity_id=entity_id,
        tick=1,
        event_type="trigger_resupply",
        action="start_production",
        payload={},
    )


@pytest.mark.asyncio
async def test_get_recent_by_entity_orders_by_created_at_desc():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_decision(),
        _make_decision(),
        _make_decision(),
    ]
    session.execute.return_value = result

    repo = AgentDecisionRepository(session)
    decisions = await repo.get_recent_by_entity(entity_id="f1", limit=10)

    assert len(decisions) == 3
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_filters_by_entity_id_when_provided():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_decision(entity_id="f1"),
        _make_decision(entity_id="f1"),
    ]
    session.execute.return_value = result

    repo = AgentDecisionRepository(session)
    decisions = await repo.get_all(entity_id="f1")

    assert len(decisions) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_returns_all_when_entity_id_is_none():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_decision(entity_id="f1"),
        _make_decision(entity_id="f2"),
        _make_decision(entity_id="w1"),
        _make_decision(entity_id="s1"),
        _make_decision(entity_id="t1"),
    ]
    session.execute.return_value = result

    repo = AgentDecisionRepository(session)
    decisions = await repo.get_all(entity_id=None)

    assert len(decisions) == 5
    session.execute.assert_called_once()
