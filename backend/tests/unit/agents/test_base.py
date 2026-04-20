from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel as FakeListChatModel,
)
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from src.agents.base import (
    AgentState,
    WorldStateSlice,
    _make_act_node_for_graph,
    _make_perceive_node,
    build_agent_graph,
    extract_json_from_last_message,
    fast_path_node,
    has_tool_calls,
)
from src.agents.master_agent import MasterAgentState, _make_dispatch_agents_node

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_world_state_slice(entity: dict | None = None) -> WorldStateSlice:
    return {
        "entity": entity or {"id": "factory-001", "stock": {"tijolos": 50.0}},
        "related_entities": [],
        "active_events": [],
        "pending_orders": [],
    }


def make_agent_state(
    entity_id: str = "factory-001",
    entity_type: str = "factory",
    world_state: WorldStateSlice | None = None,
    messages: list | None = None,
    decision: dict | None = None,
    fast_path_taken: bool = False,
    decision_history: list | None = None,
    error: str | None = None,
    trigger_event: str = "stock_low",
    current_tick: int = 1,
) -> AgentState:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "trigger_event": trigger_event,
        "current_tick": current_tick,
        "world_state": world_state or make_world_state_slice(),
        "messages": messages or [],
        "decision": decision,
        "fast_path_taken": fast_path_taken,
        "decision_history": decision_history or [],
        "error": error,
    }


# ---------------------------------------------------------------------------
# perceive_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perceive_node_adds_system_message_with_entity_id():
    stub_decision = MagicMock()
    stub_decision.action = "hold"
    stub_decision.created_at = "2024-01-01T00:00:00"

    world_slice = make_world_state_slice(
        entity={"id": "factory-001", "stock": {"tijolos": 50.0}}
    )
    state = make_agent_state(
        entity_id="factory-001",
        entity_type="factory",
        world_state=world_slice,
    )

    with patch("src.agents.base.AgentDecisionRepository") as MockRepo:
        mock_repo_instance = AsyncMock()
        MockRepo.return_value = mock_repo_instance
        mock_repo_instance.get_recent_by_entity.return_value = [stub_decision]

        with patch("pathlib.Path.read_text", return_value="You manage factory-001"):
            perceive_node = _make_perceive_node(MagicMock())
            result = await perceive_node(state)

    messages = result["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], SystemMessage)
    assert "factory-001" in messages[0].content


# ---------------------------------------------------------------------------
# fast_path_node — Case A: hold rule (stock above HIGH_THRESHOLD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_path_hold_when_stock_above_high_threshold():
    entity = {"stock": {"tijolos": 90.0}, "stock_max": {"tijolos": 100.0}}
    state = make_agent_state(
        entity_type="factory",
        world_state=make_world_state_slice(entity=entity),
    )

    result = await fast_path_node(state)

    assert result["fast_path_taken"] is True
    assert result["decision"]["action"] == "hold"


# ---------------------------------------------------------------------------
# fast_path_node — Case B: emergency rule (stock below CRITICAL_THRESHOLD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_path_emergency_when_stock_below_critical_threshold():
    entity = {"stock": {"tijolos": 5.0}, "stock_max": {"tijolos": 100.0}}
    state = make_agent_state(
        entity_type="warehouse",
        world_state=make_world_state_slice(entity=entity),
    )

    result = await fast_path_node(state)

    assert result["fast_path_taken"] is True
    assert result["decision"]["action"] == "request_resupply"


# ---------------------------------------------------------------------------
# fast_path_node — Case C: truck degradation >= 0.95
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_path_request_maintenance_when_truck_degradation_at_limit():
    entity = {"degradation": 0.95}
    state = make_agent_state(
        entity_type="truck",
        world_state=make_world_state_slice(entity=entity),
    )

    result = await fast_path_node(state)

    assert result["fast_path_taken"] is True
    assert result["decision"]["action"] == "request_maintenance"


# ---------------------------------------------------------------------------
# fast_path_node — Case D: truck degradation below threshold (no rule fires)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_path_skipped_when_truck_degradation_below_limit():
    entity = {"degradation": 0.94}
    state = make_agent_state(
        entity_type="truck",
        world_state=make_world_state_slice(entity=entity),
    )

    result = await fast_path_node(state)

    assert result["fast_path_taken"] is False


# ---------------------------------------------------------------------------
# fast_path_node — Case E: ambiguity zone (stock between thresholds)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_path_skipped_in_ambiguity_zone():
    entity = {"stock": {"tijolos": 50.0}, "stock_max": {"tijolos": 100.0}}
    state = make_agent_state(
        entity_type="factory",
        world_state=make_world_state_slice(entity=entity),
    )

    result = await fast_path_node(state)

    assert result["fast_path_taken"] is False


# ---------------------------------------------------------------------------
# build_agent_graph — Case A: fast path route (LLM never called)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_fast_path_does_not_invoke_llm():
    entity = {"stock": {"tijolos": 90.0}, "stock_max": {"tijolos": 100.0}}
    state = make_agent_state(
        entity_type="factory",
        world_state=make_world_state_slice(entity=entity),
    )

    fake_llm = FakeListChatModel(responses=[])
    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []

    with patch("src.agents.base.ChatOpenAI", return_value=fake_llm):
        with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
            with patch("pathlib.Path.read_text", return_value="System prompt"):
                graph = build_agent_graph(
                    agent_type="factory",
                    tools=[],
                    decision_schema_map={
                        "factory": MagicMock(return_value=MagicMock())
                    },
                    db_session=MagicMock(),
                    publisher_instance=AsyncMock(),
                )
                final_state = await graph.ainvoke(state)

    assert final_state["fast_path_taken"] is True
    assert final_state["decision"]["action"] == "hold"


# ---------------------------------------------------------------------------
# build_agent_graph — Case B: full path through LLM (ambiguity zone)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_full_path_calls_decision_schema_and_persists():
    entity = {"stock": {"tijolos": 50.0}, "stock_max": {"tijolos": 100.0}}
    state = make_agent_state(
        entity_type="factory",
        world_state=make_world_state_slice(entity=entity),
    )

    llm_response = AIMessage(content='{"action":"start_production","payload":{}}')
    fake_llm = FakeListChatModel(responses=[llm_response])

    mock_schema_instance = MagicMock()
    mock_schema_class = MagicMock(return_value=mock_schema_instance)
    decision_schema_map = {"factory": mock_schema_class}

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    mock_publisher = AsyncMock()

    with patch("src.agents.base.ChatOpenAI", return_value=fake_llm):
        with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
            with patch("pathlib.Path.read_text", return_value="System prompt"):
                graph = build_agent_graph(
                    agent_type="factory",
                    tools=[],
                    decision_schema_map=decision_schema_map,
                    db_session=MagicMock(),
                    publisher_instance=mock_publisher,
                )
                final_state = await graph.ainvoke(state)

    assert final_state["error"] is None
    mock_schema_class.assert_called_once()


# ---------------------------------------------------------------------------
# build_agent_graph — Case C: tool loop (LLM calls tool then returns JSON)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_tool_loop_visits_tool_node_and_produces_tool_message():
    entity = {"stock": {"tijolos": 50.0}, "stock_max": {"tijolos": 100.0}}
    state = make_agent_state(
        entity_type="factory",
        world_state=make_world_state_slice(entity=entity),
    )

    tool_call_message = AIMessage(
        content="",
        tool_calls=[{"name": "dummy_tool", "id": "call_1", "args": {}}],
    )
    final_message = AIMessage(content='{"action":"start_production","payload":{}}')
    fake_llm = FakeListChatModel(responses=[tool_call_message, final_message])

    @tool
    def dummy_tool() -> str:
        """Dummy tool for testing."""
        return "tool_result"

    mock_schema_instance = MagicMock()
    mock_schema_class = MagicMock(return_value=mock_schema_instance)

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    mock_publisher = AsyncMock()

    with patch("src.agents.base.ChatOpenAI", return_value=fake_llm):
        with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
            with patch("pathlib.Path.read_text", return_value="System prompt"):
                graph = build_agent_graph(
                    agent_type="factory",
                    tools=[dummy_tool],
                    decision_schema_map={"factory": mock_schema_class},
                    db_session=MagicMock(),
                    publisher_instance=mock_publisher,
                )
                final_state = await graph.ainvoke(state)

    tool_messages = [m for m in final_state["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) >= 1


# ---------------------------------------------------------------------------
# act_node — Case A: guardrail passes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_act_node_persists_and_publishes_when_guardrail_passes():
    messages = [AIMessage(content='{"action":"start_production","payload":{}}')]
    state = make_agent_state(entity_type="factory", messages=messages)

    mock_decision_instance = MagicMock()
    mock_schema_class = MagicMock(return_value=mock_decision_instance)
    decision_schema_map = {"factory": mock_schema_class}

    mock_repo = AsyncMock()
    mock_publisher = AsyncMock()

    act_node_fn = _make_act_node_for_graph(decision_schema_map, MagicMock(), mock_publisher)

    with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
        result = await act_node_fn(state)

    assert result["error"] is None
    mock_repo.create.assert_called_once()


# ---------------------------------------------------------------------------
# act_node — Case B: guardrail fails (ValidationError-like)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_act_node_records_error_and_skips_persist_when_guardrail_fails():
    messages = [AIMessage(content='{"action":"start_production","payload":{}}')]
    state = make_agent_state(entity_type="factory", messages=messages)

    mock_schema_class = MagicMock(side_effect=ValueError("guardrail error"))
    decision_schema_map = {"factory": mock_schema_class}

    mock_repo = AsyncMock()
    mock_publisher = AsyncMock()

    act_node_fn = _make_act_node_for_graph(decision_schema_map, MagicMock(), mock_publisher)

    with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
        result = await act_node_fn(state)

    assert result["error"] is not None
    assert result["decision"] is None
    mock_repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# has_tool_calls
# ---------------------------------------------------------------------------


def test_has_tool_calls_returns_true_when_tool_calls_present():
    message = AIMessage(
        content="",
        tool_calls=[{"name": "foo", "id": "1", "args": {}}],
    )
    assert has_tool_calls(message) is True


def test_has_tool_calls_returns_false_when_tool_calls_empty():
    message = AIMessage(content="", tool_calls=[])
    assert has_tool_calls(message) is False


def test_has_tool_calls_returns_false_when_no_tool_calls_attr():
    message = AIMessage(content="plain text")
    assert has_tool_calls(message) is False


# ---------------------------------------------------------------------------
# extract_json_from_last_message
# ---------------------------------------------------------------------------


def test_extract_json_from_last_message_with_string_content():
    messages = [AIMessage(content='{"action": "hold", "payload": {}}')]
    result = extract_json_from_last_message(messages)
    assert result == {"action": "hold", "payload": {}}


def test_extract_json_from_last_message_with_list_content():
    messages = [
        AIMessage(
            content=[{"type": "text", "text": '{"action": "hold", "payload": {}}'}]
        )
    ]
    result = extract_json_from_last_message(messages)
    assert result == {"action": "hold", "payload": {}}


def test_extract_json_from_last_message_raises_on_invalid_json():
    messages = [AIMessage(content="this is not json")]
    with pytest.raises(ValueError):
        extract_json_from_last_message(messages)


# ---------------------------------------------------------------------------
# MasterAgent — dispatch_agents with 3 triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_master_agent_dispatch_creates_task_per_trigger():
    import asyncio

    def make_trigger(entity_id: str, entity_type: str = "store") -> MagicMock:
        t = MagicMock()
        t.entity_id = entity_id
        t.entity_type = entity_type
        t.trigger_event = "stock_low"
        t.current_tick = 1
        return t

    triggers = [
        make_trigger("store-001"),
        make_trigger("store-002"),
        make_trigger("warehouse-001", "warehouse"),
    ]

    mock_agent = MagicMock()
    mock_agent_factory = MagicMock(return_value=mock_agent)

    semaphore = asyncio.Semaphore(4)
    dispatch_node = _make_dispatch_agents_node(semaphore)

    master_state: MasterAgentState = {
        "triggers": triggers,
        "world_state": make_world_state_slice(),
        "current_tick": 1,
        "agent_factory": mock_agent_factory,
    }

    created_tasks = []

    def fake_create_task(coro):
        task = MagicMock()
        created_tasks.append(task)
        coro.close()
        return task

    with patch("asyncio.create_task", side_effect=fake_create_task):
        await dispatch_node(master_state)

    assert len(created_tasks) == 3


# ---------------------------------------------------------------------------
# MasterAgent — dispatch_agents with empty triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_master_agent_dispatch_skips_create_task_when_no_triggers():
    import asyncio

    semaphore = asyncio.Semaphore(4)
    dispatch_node = _make_dispatch_agents_node(semaphore)

    master_state: MasterAgentState = {
        "triggers": [],
        "world_state": make_world_state_slice(),
        "current_tick": 1,
        "agent_factory": MagicMock(),
    }

    with patch("asyncio.create_task") as mock_create_task:
        await dispatch_node(master_state)

    mock_create_task.assert_not_called()
