"""KnowMind 生产 Planner 的 LangGraph 状态图。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict, total=False):
    user_query: str
    conversation_context: str
    available_steps: list[str]
    plan_steps: list[str]
    goal: str
    rationale: str
    plan_source: str


PlannerCallable = Callable[[AgentState], Awaitable[dict]]


def build_planner_graph(planner: PlannerCallable):
    """构建 LLM Plan → 校验 的真实 LangGraph。"""

    async def plan_node(state: AgentState) -> AgentState:
        result = await planner(state)
        return {**state, **result}

    async def validate_node(state: AgentState) -> AgentState:
        allowed = set(state.get("available_steps") or [])
        selected: list[str] = []
        for raw in state.get("plan_steps") or []:
            step = str(raw).strip()
            if step in allowed and step != "llm_generate" and step not in selected:
                selected.append(step)
        selected.append("llm_generate")
        return {**state, "plan_steps": selected}

    graph = StateGraph(AgentState)
    graph.add_node("llm_plan", plan_node)
    graph.add_node("validate_plan", validate_node)
    graph.add_edge(START, "llm_plan")
    graph.add_edge("llm_plan", "validate_plan")
    graph.add_edge("validate_plan", END)
    return graph.compile()


async def run_agent_pipeline(
    *,
    user_query: str,
    conversation_context: str,
    available_steps: list[str],
    planner: PlannerCallable,
) -> AgentState:
    graph = build_planner_graph(planner)
    return await graph.ainvoke(
        {
            "user_query": user_query,
            "conversation_context": conversation_context,
            "available_steps": available_steps,
            "plan_steps": [],
            "plan_source": "llm",
        }
    )

