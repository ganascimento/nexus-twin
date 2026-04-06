import asyncio
import json
import os
import pathlib
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.agent_decision import AgentDecisionRepository

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

HIGH_THRESHOLD = 0.85
CRITICAL_THRESHOLD = 0.10


class WorldStateSlice(TypedDict):
    entity: dict
    related_entities: list[dict]
    active_events: list[dict]
    pending_orders: list[dict]


class DecisionMemory(TypedDict):
    tick: int
    event_type: str
    action: str
    summary: str


class AgentDecision(TypedDict):
    action: str
    payload: dict


class AgentState(TypedDict):
    world_state: WorldStateSlice
    entity_id: str
    entity_type: str
    trigger_event: str
    current_tick: int
    messages: Annotated[list, add_messages]
    decision_history: list
    decision: dict | None
    fast_path_taken: bool
    error: str | None


def has_tool_calls(state_or_message) -> bool:
    if isinstance(state_or_message, dict):
        messages = state_or_message.get("messages", [])
        if not messages:
            return False
        last = messages[-1]
    else:
        last = state_or_message
    return bool(getattr(last, "tool_calls", None))


def extract_json_from_last_message(messages: list) -> dict:
    last = messages[-1]
    content = last.content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in last message: {e}")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in last message: {e}")
    raise ValueError("No valid JSON found in last message")


async def perceive_node(state: AgentState) -> dict:
    session = AsyncSession()
    repo = AgentDecisionRepository(session)
    history_result = repo.get_recent_by_entity(state["entity_id"], limit=10)
    history = (
        await history_result if asyncio.iscoroutine(history_result) else history_result
    )

    prompt_path = (
        pathlib.Path(__file__).parent / "prompts" / f"{state['entity_type']}.md"
    )
    prompt = prompt_path.read_text()
    prompt = prompt.replace("{entity_id}", state["entity_id"])
    prompt = prompt.replace("{trigger_event}", state["trigger_event"])

    return {
        **state,
        "messages": [SystemMessage(content=prompt)],
        "decision_history": history,
    }


async def fast_path_node(state: AgentState) -> dict:
    entity = state["world_state"]["entity"]
    entity_type = state["entity_type"]

    if entity_type == "truck":
        if entity.get("degradation", 0.0) >= 0.95:
            return {
                **state,
                "fast_path_taken": True,
                "decision": {"action": "request_maintenance", "payload": {}},
            }
        return {**state, "fast_path_taken": False}

    stock = entity.get("stock", {})
    stock_max = entity.get("stock_max", {})

    for material_id, qty in stock.items():
        max_qty = stock_max.get(material_id, qty)
        if max_qty == 0:
            continue
        ratio = qty / max_qty
        if ratio > HIGH_THRESHOLD:
            return {
                **state,
                "fast_path_taken": True,
                "decision": {"action": "hold", "payload": {}},
            }
        if ratio < CRITICAL_THRESHOLD:
            return {
                **state,
                "fast_path_taken": True,
                "decision": {"action": "emergency_order", "payload": {}},
            }

    return {**state, "fast_path_taken": False}


def _make_decide_node(llm, tools):
    try:
        bound_llm = llm.bind_tools(tools) if tools else llm
    except NotImplementedError:
        bound_llm = llm

    async def decide_node(state: AgentState) -> dict:
        response = await bound_llm.ainvoke(state["messages"])
        return {"messages": [response]}

    return decide_node


async def act_node(state: AgentState) -> dict:
    schema_map = state.get("_decision_schema_map")
    publisher = state.get("_publisher")
    db_session = state.get("_db_session")

    try:
        raw = extract_json_from_last_message(state["messages"])
        schema_class = schema_map[state["entity_type"]]
        schema_class(**raw)
        repo = AgentDecisionRepository(db_session)
        await repo.create(
            {
                "entity_id": state["entity_id"],
                "entity_type": state["entity_type"],
                "tick": state["current_tick"],
                "action": raw.get("action"),
                "payload": raw.get("payload", {}),
            }
        )
        await publisher.publish_decision(
            state["entity_id"],
            state["entity_type"],
            raw,
        )
        return {**state, "decision": raw, "error": None}
    except Exception as e:
        return {**state, "decision": None, "error": str(e)}


def _make_act_node_for_graph(decision_schema_map, db_session, publisher_instance):
    async def _act_node(state: AgentState) -> dict:
        schema_map = state.get("_decision_schema_map", decision_schema_map)
        publisher = state.get("_publisher", publisher_instance)
        session = state.get("_db_session", db_session)

        try:
            raw = extract_json_from_last_message(state["messages"])
            schema_class = schema_map[state["entity_type"]]
            schema_class(**raw)
            repo = AgentDecisionRepository(session)
            await repo.create(
                {
                    "entity_id": state["entity_id"],
                    "entity_type": state["entity_type"],
                    "tick": state["current_tick"],
                    "action": raw.get("action"),
                    "payload": raw.get("payload", {}),
                }
            )
            await publisher.publish_decision(
                state["entity_id"],
                state["entity_type"],
                raw,
            )
            return {**state, "decision": raw, "error": None}
        except Exception as e:
            return {**state, "decision": None, "error": str(e)}

    return _act_node


def build_agent_graph(
    agent_type: str,
    tools: list,
    decision_schema_map: dict,
    db_session,
    publisher_instance,
):
    llm = ChatOpenAI(model=OPENAI_MODEL)

    decide_node = _make_decide_node(llm, tools)
    act_node_fn = _make_act_node_for_graph(
        decision_schema_map, db_session, publisher_instance
    )

    graph = StateGraph(AgentState)
    graph.add_node("perceive", perceive_node)
    graph.add_node("fast_path", fast_path_node)
    graph.add_node("decide", decide_node)
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_node("act", act_node_fn)

    graph.set_entry_point("perceive")
    graph.add_edge("perceive", "fast_path")
    graph.add_conditional_edges(
        "fast_path",
        lambda state: END if state["fast_path_taken"] else "decide",
    )
    graph.add_conditional_edges(
        "decide",
        lambda state: "tool_node" if has_tool_calls(state) else "act",
    )
    graph.add_edge("tool_node", "decide")
    graph.add_edge("act", END)

    return graph.compile()
