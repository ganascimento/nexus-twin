import asyncio
import os
from typing import Callable, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph


class _MasterAgentStateRequired(TypedDict):
    triggers: list
    world_state: dict
    current_tick: int
    agent_factory: Callable


class MasterAgentState(_MasterAgentStateRequired, total=False):
    chaos_injected: bool


async def evaluate_world_node(state: MasterAgentState) -> dict:
    from src.services.trigger_evaluation import TriggerEvaluationService

    triggers = await TriggerEvaluationService().evaluate_all(state["world_state"])
    return {**state, "triggers": triggers}


def _make_dispatch_agents_node(semaphore: asyncio.Semaphore):
    async def dispatch_agents_node(state: MasterAgentState) -> dict:
        agent_factory = state.get("agent_factory")

        async def semaphore_wrap(sem, coro):
            async with sem:
                await coro

        for trigger in state["triggers"]:
            if agent_factory:
                agent = agent_factory(trigger.entity_type)
                coro = agent.run_cycle(trigger)
            else:
                continue
            asyncio.create_task(semaphore_wrap(semaphore, coro))

        return state

    return dispatch_agents_node


def _make_evaluate_chaos_node(llm):
    async def evaluate_chaos_node(state: MasterAgentState) -> dict:
        from src.services.chaos import ChaosService

        tick = state["current_tick"]
        prompt = (
            f"Tick {tick}. WorldState summary: {str(state['world_state'])[:500]}. "
            "Should an autonomous chaos event be injected? Reply only 'yes' or 'no'."
        )

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            if "yes" in response.content.lower():
                result = await ChaosService().inject_autonomous_event(
                    {
                        "tick": tick,
                        "source": "autonomous",
                    }
                )
                return {**state, "chaos_injected": result is not None}
        except Exception:
            pass

        return {**state, "chaos_injected": False}

    return evaluate_chaos_node


def _build_master_graph(semaphore: asyncio.Semaphore):
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    dispatch_node = _make_dispatch_agents_node(semaphore)
    chaos_node = _make_evaluate_chaos_node(llm)

    graph = StateGraph(MasterAgentState)
    graph.add_node("evaluate_world", evaluate_world_node)
    graph.add_node("dispatch_agents", dispatch_node)
    graph.add_node("evaluate_chaos", chaos_node)

    graph.set_entry_point("evaluate_world")
    graph.add_edge("evaluate_world", "dispatch_agents")
    graph.add_edge("dispatch_agents", "evaluate_chaos")
    graph.add_edge("evaluate_chaos", END)

    return graph.compile()


async def run_master_cycle(state: MasterAgentState) -> dict:
    agent_factory = state.get("agent_factory")

    for trigger in state["triggers"]:
        if agent_factory:
            agent = agent_factory(trigger.entity_type)
            coro = agent.run_cycle(trigger)
        else:

            async def _noop():
                pass

            coro = _noop()
        asyncio.create_task(coro)

    return state


async def run_master_cycle_full(
    world_state: dict,
    current_tick: int,
    agent_factory: Callable,
    semaphore: asyncio.Semaphore,
) -> None:
    initial_state: MasterAgentState = {
        "world_state": world_state,
        "current_tick": current_tick,
        "triggers": [],
        "agent_factory": agent_factory,
    }
    graph = _build_master_graph(semaphore)
    await graph.ainvoke(initial_state)
