import json
import os
import pathlib
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.repositories.agent_decision import AgentDecisionRepository
from src.simulation.publisher import publish_agent_decision

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

HIGH_THRESHOLD = 0.85
CRITICAL_THRESHOLD = 0.10

_EMERGENCY_ACTION_MAP = {
    "store": "order_replenishment",
    "warehouse": "request_resupply",
    "factory": "start_production",
}


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


def _format_world_state_summary(world_state: WorldStateSlice) -> str:
    entity = world_state.get("entity", {})
    related = world_state.get("related_entities", [])
    active_events = world_state.get("active_events", [])
    pending_orders = world_state.get("pending_orders", [])

    parts = [f"Entity: {json.dumps(entity, default=str)}"]
    if related:
        parts.append(f"Related entities: {json.dumps(related, default=str)}")
    if active_events:
        parts.append(f"Active events: {json.dumps(active_events, default=str)}")
    if pending_orders:
        parts.append(f"Pending orders: {json.dumps(pending_orders, default=str)}")
    return "\n".join(parts)


def _format_decision_history(history: list) -> str:
    if not history:
        return "No previous decisions."
    entries = []
    for h in history:
        if isinstance(h, dict):
            entries.append(json.dumps(h, default=str))
        else:
            entry = {
                "tick": getattr(h, "tick", None),
                "action": getattr(h, "action", None),
                "event_type": getattr(h, "event_type", None),
                "payload": getattr(h, "payload", {}),
            }
            entries.append(json.dumps(entry, default=str))
    return "\n".join(entries)


def _make_perceive_node(db_session):
    async def perceive_node(state: AgentState) -> dict:
        repo = AgentDecisionRepository(db_session)
        history = await repo.get_recent_by_entity(state["entity_id"], limit=10)

        prompt_path = (
            pathlib.Path(__file__).parent / "prompts" / f"{state['entity_type']}.md"
        )
        prompt = prompt_path.read_text()
        prompt = prompt.replace("{entity_id}", state["entity_id"])
        prompt = prompt.replace("{trigger_event}", state["trigger_event"])
        prompt = prompt.replace(
            "{world_state_summary}",
            _format_world_state_summary(state["world_state"]),
        )
        prompt = prompt.replace(
            "{decision_history}", _format_decision_history(history)
        )

        entity = state["world_state"].get("entity", {})
        if state["entity_type"] == "truck":
            prompt = prompt.replace(
                "{truck_type}", str(entity.get("truck_type", "unknown"))
            )

        return {
            **state,
            "messages": [SystemMessage(content=prompt)],
            "decision_history": history,
        }

    return perceive_node


async def fast_path_node(state: AgentState) -> dict:
    entity = state["world_state"]["entity"]
    entity_type = state["entity_type"]

    if entity_type == "truck":
        if entity.get("degradation", 0.0) >= 0.95:
            return {
                **state,
                "fast_path_taken": True,
                "decision": {
                    "action": "request_maintenance",
                    "reasoning_summary": "fast-path: degradation >= 95%, maintenance required",
                    "payload": {"current_degradation": entity.get("degradation", 1.0)},
                },
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
                "decision": {
                    "action": "hold",
                    "reasoning_summary": f"fast-path: stock ratio {ratio:.0%} above {HIGH_THRESHOLD:.0%} threshold",
                    "payload": None,
                },
            }
        if ratio < CRITICAL_THRESHOLD:
            emergency_action = _EMERGENCY_ACTION_MAP.get(entity_type, "hold")
            return {
                **state,
                "fast_path_taken": True,
                "decision": {
                    "action": emergency_action,
                    "reasoning_summary": f"fast-path: stock ratio {ratio:.0%} below {CRITICAL_THRESHOLD:.0%} critical threshold",
                    "payload": None,
                },
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


def _make_act_node_for_graph(decision_schema_map, db_session, publisher_instance):
    async def _act_node(state: AgentState) -> dict:
        schema_map = decision_schema_map
        session = db_session

        try:
            if state.get("fast_path_taken") and state.get("decision"):
                raw = state["decision"]
            else:
                raw = extract_json_from_last_message(state["messages"])

            entity_type = state["entity_type"]
            if entity_type in schema_map:
                schema_map[entity_type](**raw)

            repo = AgentDecisionRepository(session)
            await repo.create(
                {
                    "entity_id": state["entity_id"],
                    "agent_type": entity_type,
                    "event_type": state.get("trigger_event", "unknown"),
                    "tick": state["current_tick"],
                    "action": raw.get("action"),
                    "payload": raw.get("payload", {}),
                }
            )
            await publish_agent_decision(
                {
                    "entity_id": state["entity_id"],
                    "entity_type": entity_type,
                    **raw,
                },
                state["current_tick"],
                publisher_instance,
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

    perceive_fn = _make_perceive_node(db_session)
    decide_node = _make_decide_node(llm, tools)
    act_node_fn = _make_act_node_for_graph(
        decision_schema_map, db_session, publisher_instance
    )

    graph = StateGraph(AgentState)
    graph.add_node("perceive", perceive_fn)
    graph.add_node("fast_path", fast_path_node)
    graph.add_node("decide", decide_node)
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_node("act", act_node_fn)

    graph.set_entry_point("perceive")
    graph.add_edge("perceive", "fast_path")
    graph.add_conditional_edges(
        "fast_path",
        lambda state: "act" if state["fast_path_taken"] else "decide",
    )
    graph.add_conditional_edges(
        "decide",
        lambda state: "tool_node" if has_tool_calls(state) else "act",
    )
    graph.add_edge("tool_node", "decide")
    graph.add_edge("act", END)

    return graph.compile()
