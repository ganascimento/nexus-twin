import json
import os
import pathlib
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from loguru import logger

from src.repositories.agent_decision import AgentDecisionRepository
from src.simulation.publisher import publish_agent_decision

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "0"))
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
DECISION_HISTORY_LIMIT = int(os.getenv("DECISION_HISTORY_LIMIT", "3"))

STORE_HOLD_REORDER_MULTIPLIER = 2.0
WAREHOUSE_HOLD_MIN_STOCK_MULTIPLIER = 3.0
FACTORY_HOLD_STOCK_RATIO = 0.85
TRUCK_MAINTENANCE_DEGRADATION = 0.95

_STOCK_POLL_EVENTS = frozenset({
    "low_stock_trigger",
    "stock_trigger_warehouse",
    "stock_trigger_factory",
})


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
    trigger_payload: dict
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


def _strip_markdown_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    newline = stripped.find("\n")
    if newline == -1:
        return stripped
    body = stripped[newline + 1:]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[: -3]
    return body.strip()


def _parse_json_tolerant(text: str) -> dict:
    cleaned = _strip_markdown_json_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first == -1 or last == -1 or last <= first:
            raise ValueError(f"Invalid JSON in last message: {text!r}")
        try:
            return json.loads(cleaned[first : last + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in last message: {e}")


def extract_json_from_last_message(messages: list) -> dict:
    last = messages[-1]
    content = last.content
    if isinstance(content, str):
        return _parse_json_tolerant(content)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return _parse_json_tolerant(item["text"])
    raise ValueError("No valid JSON found in last message")


_COMPACT_JSON_SEPARATORS = (",", ":")


def _dumps_compact(obj) -> str:
    return json.dumps(obj, default=str, separators=_COMPACT_JSON_SEPARATORS)


def _format_world_state_summary(world_state: WorldStateSlice) -> str:
    entity = world_state.get("entity", {})
    related = world_state.get("related_entities", [])
    active_events = world_state.get("active_events", [])
    pending_orders = world_state.get("pending_orders", [])

    parts = [f"Entity: {_dumps_compact(entity)}"]
    if related:
        parts.append(f"Related entities: {_dumps_compact(related)}")
    if active_events:
        parts.append(f"Active events: {_dumps_compact(active_events)}")
    if pending_orders:
        parts.append(f"Pending orders: {_dumps_compact(pending_orders)}")
    return "\n".join(parts)


def _format_decision_history(history: list) -> str:
    if not history:
        return "No previous decisions."
    entries = []
    for h in history:
        if isinstance(h, dict):
            entries.append(_dumps_compact(h))
        else:
            entry = {
                "tick": getattr(h, "tick", None),
                "action": getattr(h, "action", None),
                "event_type": getattr(h, "event_type", None),
                "payload": getattr(h, "payload", {}),
            }
            entries.append(_dumps_compact(entry))
    return "\n".join(entries)


def _make_perceive_node(db_session):
    async def perceive_node(state: AgentState) -> dict:
        repo = AgentDecisionRepository(db_session)
        history = await repo.get_recent_by_entity(
            state["entity_id"], limit=DECISION_HISTORY_LIMIT
        )

        prompt_path = (
            pathlib.Path(__file__).parent / "prompts" / f"{state['entity_type']}.md"
        )
        prompt = prompt_path.read_text()
        prompt = prompt.replace("{entity_id}", state["entity_id"])
        prompt = prompt.replace("{trigger_event}", state["trigger_event"])
        trigger_payload = state.get("trigger_payload") or {}
        prompt = prompt.replace(
            "{trigger_payload}",
            _dumps_compact(trigger_payload) if trigger_payload else "(none)",
        )
        prompt = prompt.replace(
            "{world_state_summary}",
            _format_world_state_summary(state["world_state"]),
        )
        prompt = prompt.replace("{decision_history}", _format_decision_history(history))

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


def _hold_decision(reason: str) -> dict:
    return {
        "fast_path_taken": True,
        "decision": {
            "action": "hold",
            "reasoning_summary": f"fast-path: {reason}",
            "payload": None,
        },
    }


def _store_fast_path_hold(entity: dict) -> dict | None:
    stocks = entity.get("stocks")
    if not stocks:
        return None
    for s in stocks:
        reorder_point = s.get("reorder_point") or 0
        stock = s.get("stock") or 0
        demand_rate = s.get("demand_rate") or 0
        if reorder_point <= 0 or demand_rate <= 0:
            return None
        if stock < reorder_point * STORE_HOLD_REORDER_MULTIPLIER:
            return None
    return _hold_decision(
        f"all materials stock >= {STORE_HOLD_REORDER_MULTIPLIER}x reorder_point"
    )


def _warehouse_fast_path_hold(entity: dict) -> dict | None:
    stocks = entity.get("stocks")
    if not stocks:
        return None
    for s in stocks:
        min_stock = s.get("min_stock") or 0
        stock = s.get("stock") or 0
        reserved = s.get("stock_reserved") or 0
        available = stock - reserved
        if min_stock <= 0:
            return None
        if available < min_stock * WAREHOUSE_HOLD_MIN_STOCK_MULTIPLIER:
            return None
    return _hold_decision(
        f"all materials available >= {WAREHOUSE_HOLD_MIN_STOCK_MULTIPLIER}x min_stock"
    )


def _factory_fast_path_hold(entity: dict) -> dict | None:
    products = entity.get("products")
    if not products:
        return None
    for p in products:
        stock_max = p.get("stock_max") or 0
        stock = p.get("stock") or 0
        if stock_max <= 0:
            return None
        if stock < stock_max * FACTORY_HOLD_STOCK_RATIO:
            return None
    return _hold_decision(
        f"all products stock >= {FACTORY_HOLD_STOCK_RATIO:.0%} of stock_max"
    )


def _truck_fast_path(entity: dict) -> dict | None:
    if entity.get("degradation", 0.0) >= TRUCK_MAINTENANCE_DEGRADATION:
        return {
            "fast_path_taken": True,
            "decision": {
                "action": "request_maintenance",
                "reasoning_summary": (
                    f"fast-path: degradation >= {TRUCK_MAINTENANCE_DEGRADATION:.0%}, "
                    "maintenance required"
                ),
                "payload": {"current_degradation": entity.get("degradation", 1.0)},
            },
        }
    return None


_FAST_PATH_BY_ENTITY_TYPE = {
    "store": _store_fast_path_hold,
    "warehouse": _warehouse_fast_path_hold,
    "factory": _factory_fast_path_hold,
    "truck": _truck_fast_path,
}


async def fast_path_node(state: AgentState) -> dict:
    entity = state["world_state"]["entity"]
    entity_type = state["entity_type"]
    trigger_event = state.get("trigger_event", "")

    if entity_type == "truck":
        result = _truck_fast_path(entity)
    elif trigger_event in _STOCK_POLL_EVENTS:
        resolver = _FAST_PATH_BY_ENTITY_TYPE.get(entity_type)
        result = resolver(entity) if resolver is not None else None
    else:
        result = None

    if result is None:
        return {**state, "fast_path_taken": False}
    return {**state, **result}


def _make_decide_node(llm, tools):
    try:
        bound_llm = llm.bind_tools(tools) if tools else llm
    except NotImplementedError:
        bound_llm = llm

    async def decide_node(state: AgentState) -> dict:
        response = await bound_llm.ainvoke(state["messages"])
        return {"messages": [response]}

    return decide_node


def _make_act_node_for_graph(
    decision_schema_map, db_session, publisher_instance, decision_effect_processor=None
):
    async def _act_node(state: AgentState) -> dict:
        schema_map = decision_schema_map
        session = db_session

        try:
            if state.get("fast_path_taken") and state.get("decision"):
                raw = state["decision"]
            else:
                raw = extract_json_from_last_message(state["messages"])

            if raw.get("action") == "hold" and raw.get("payload") == {}:
                raw["payload"] = None

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
                    "payload": raw.get("payload") or {},
                }
            )

            if decision_effect_processor is not None:
                await decision_effect_processor.process(
                    entity_type,
                    state["entity_id"],
                    raw.get("action"),
                    raw.get("payload", {}),
                    state["current_tick"],
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
            logger.exception(
                "Agent act_node failed | entity_type={} entity_id={} event={} raw={}",
                state.get("entity_type"),
                state.get("entity_id"),
                state.get("trigger_event"),
                locals().get("raw"),
            )
            return {**state, "decision": None, "error": str(e)}

    return _act_node


def build_agent_graph(
    agent_type: str,
    tools: list,
    decision_schema_map: dict,
    db_session,
    publisher_instance,
    decision_effect_processor=None,
):
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        max_retries=OPENAI_MAX_RETRIES,
        timeout=OPENAI_TIMEOUT_SECONDS,
    )

    perceive_fn = _make_perceive_node(db_session)
    decide_node = _make_decide_node(llm, tools)
    act_node_fn = _make_act_node_for_graph(
        decision_schema_map, db_session, publisher_instance, decision_effect_processor
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
