"""Plan-and-Execute 轻量编排：深度研究模式下的步骤规划与 agent_step 推送。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import ChatRequest
from app.services.chat_prefetch import want_arxiv, want_semantic_scholar


@dataclass
class ResearchPlan:
    goal: str
    steps: list[str] = field(default_factory=list)
    notes: str = ""
    context_mode: str = "new_conversation"


def _want_web(req: ChatRequest, user_id: str | None) -> bool:
    from app.core.config import settings

    if not settings.web_search_enabled or not req.web_search:
        return False
    if user_id:
        from app.services import mcp_registry

        return mcp_registry.is_builtin_enabled(user_id, "web_search")
    return True


def build_research_plan(req: ChatRequest, user_id: str | None) -> ResearchPlan:
    """根据会话开关生成可观测的执行计划（非 LangGraph，但对齐 Plan-and-Execute 语义）。"""
    steps: list[str] = []
    context_mode = "continuation" if req.conversation_id else "new_conversation"
    if req.conversation_id:
        steps.append("memory_retrieval")
    if req.knowledge_base_id:
        steps.append("rag_retrieval")
    if want_arxiv(req, user_id):
        steps.append("arxiv_search")
    if want_semantic_scholar(req, user_id):
        steps.append("semantic_scholar")
    if _want_web(req, user_id):
        steps.append("web_search")
    if req.file_tools:
        steps.append("file_tools")
    if req.external_mcp:
        steps.append("external_mcp")
    if "memory_retrieval" not in steps:
        steps.append("memory_retrieval")
    steps.append("llm_generate")

    notes = "续聊时先恢复会话记忆，再并行检索私有库与公开学术/网页资料，最后综合生成可核对回答。"
    if context_mode == "new_conversation":
        notes = "并行检索私有库与公开学术/网页资料，再结合工作记忆生成可核对回答。"
    if not steps or steps == ["memory_retrieval", "llm_generate"]:
        notes = "未开启额外工具，将基于对话记忆与模型知识回答。"

    return ResearchPlan(
        goal=(req.message or "")[:200],
        steps=steps,
        notes=notes,
        context_mode=context_mode,
    )


def plan_step_sse(plan: ResearchPlan) -> dict:
    return {
        "type": "agent_step",
        "step": "planner",
        "status": "done",
        "detail": f"计划 {len(plan.steps)} 步：{' → '.join(_step_labels(plan.steps))}",
        "meta": {
            "goal": plan.goal,
            "steps": plan.steps,
            "notes": plan.notes,
            "context_mode": plan.context_mode,
        },
    }


def _step_labels(steps: list[str]) -> list[str]:
    labels = {
        "rag_retrieval": "知识库检索",
        "arxiv_search": "arXiv",
        "semantic_scholar": "Semantic Scholar",
        "web_search": "联网搜索",
        "file_tools": "文件读写",
        "external_mcp": "外部 MCP",
        "memory_retrieval": "对话记忆",
        "llm_generate": "综合生成",
    }
    return [labels.get(s, s) for s in steps]
