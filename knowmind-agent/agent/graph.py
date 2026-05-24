from typing import TypedDict

# LangGraph 状态机占位：后续将节点函数注册到 StateGraph


class AgentState(TypedDict, total=False):
    """跨节点共享的状态字典（最小字段）。"""

    messages: list[str]
    kb_id: str | None
    tool_trace: list[str]


def build_graph_stub():
    """
    返回编译后的图（占位）。

    典型节点：plan -> retrieve -> rerank -> answer -> (optional) report
    """
    return None
