# LangGraph 风格状态机（轻量实现，供后续扩展为完整 LangGraph）

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """跨节点共享的状态字典。"""

    messages: list[str]
    kb_id: str | None
    tool_trace: list[str]
    plan_steps: list[str]
    context_parts: list[str]
    user_query: str


def plan_node(state: AgentState) -> AgentState:
    steps: list[str] = []
    if state.get("kb_id"):
        steps.append("rag_retrieval")
    steps.extend(["memory_retrieval", "llm_generate"])
    return {**state, "plan_steps": steps, "tool_trace": [*state.get("tool_trace", []), "plan"]}


def retrieve_node(state: AgentState) -> AgentState:
    return {**state, "tool_trace": [*state.get("tool_trace", []), "retrieve"]}


def answer_node(state: AgentState) -> AgentState:
    return {**state, "tool_trace": [*state.get("tool_trace", []), "answer"]}


def run_agent_pipeline(
    *,
    user_query: str,
    kb_id: str | None = None,
    extra_steps: list[str] | None = None,
) -> AgentState:
    """同步执行 Plan → Retrieve → Answer 最小链路（无 LLM 依赖）。"""
    state: AgentState = {
        "user_query": user_query,
        "kb_id": kb_id,
        "messages": [],
        "tool_trace": [],
        "context_parts": [],
    }
    state = plan_node(state)
    if extra_steps:
        state["plan_steps"] = list(extra_steps) + state.get("plan_steps", [])
    state = retrieve_node(state)
    state = answer_node(state)
    return state


def build_graph_stub():
    """返回可调用流水线（兼容旧接口）。"""
    return run_agent_pipeline
