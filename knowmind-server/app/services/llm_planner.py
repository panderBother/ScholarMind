"""生产对话 Planner：由 LLM 基于会话上下文选择允许的执行步骤。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from agent.graph import AgentState, run_agent_pipeline

from app.models.schemas import ChatRequest
from app.services.edgefn_client import complete_chat_turn, turn_visible_text

log = logging.getLogger(__name__)

RETRIEVAL_STEPS = (
    "memory_retrieval",
    "rag_retrieval",
    "web_search",
    "arxiv_search",
    "semantic_scholar",
)
TOOL_STEPS = ("file_tools", "external_mcp")
FINAL_STEP = "llm_generate"


@dataclass
class ExecutionPlan:
    goal: str
    steps: list[str] = field(default_factory=list)
    rationale: str = ""
    source: str = "llm"


def available_steps(req: ChatRequest) -> list[str]:
    steps = ["memory_retrieval"]
    if req.knowledge_base_id:
        steps.append("rag_retrieval")
    if req.web_search:
        steps.append("web_search")
    if req.arxiv:
        steps.append("arxiv_search")
    if req.semantic_scholar:
        steps.append("semantic_scholar")
    if req.file_tools:
        steps.append("file_tools")
    if req.external_mcp:
        steps.append("external_mcp")
    steps.append(FINAL_STEP)
    return steps


def fallback_plan(req: ChatRequest, *, reason: str = "") -> ExecutionPlan:
    steps = available_steps(req)
    return ExecutionPlan(
        goal=(req.message or "")[:200],
        steps=steps,
        rationale=reason or "Planner 不可用，按已授权能力执行确定性降级计划。",
        source="fallback",
    )


def _extract_json_object(raw: str) -> dict | None:
    text = (raw or "").strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return value if isinstance(value, dict) else None
    return None


async def build_llm_execution_plan(
    req: ChatRequest,
    *,
    conversation_context: str = "",
) -> ExecutionPlan:
    allowed = available_steps(req)
    system = (
        "你是 KnowMind 的执行规划器。根据用户本轮问题和已有会话上下文，从允许步骤中选择必要步骤。"
        "不要选择未授权步骤；避免无意义检索；涉及最新信息时优先 web_search；涉及私有资料时使用 "
        "rag_retrieval；续问、指代或依赖历史结论时使用 memory_retrieval；文件读写才使用 file_tools；"
        "外部专业工具才使用 external_mcp。最后一步必须是 llm_generate。"
        "仅输出 JSON 对象："
        '{"goal":"目标","steps":["步骤"],"rationale":"简短理由"}。'
    )

    async def model_planner(state: AgentState) -> dict:
        user = (
            f"允许步骤：{json.dumps(state.get('available_steps') or [], ensure_ascii=False)}\n\n"
            f"会话上下文：\n{(state.get('conversation_context') or '无')[:6000]}\n\n"
            f"本轮问题：\n{(state.get('user_query') or '')[:8000]}"
        )
        turn = await complete_chat_turn(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        payload = _extract_json_object(turn_visible_text(turn))
        if payload is None:
            raise ValueError("Planner 未返回合法 JSON")
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("Planner steps 不是数组")
        return {
            "goal": str(payload.get("goal") or req.message)[:200],
            "plan_steps": raw_steps,
            "rationale": str(payload.get("rationale") or "LLM 根据上下文生成执行计划")[:500],
            "plan_source": "llm",
        }

    try:
        state = await run_agent_pipeline(
            user_query=req.message,
            conversation_context=conversation_context,
            available_steps=allowed,
            planner=model_planner,
        )
        return ExecutionPlan(
            goal=str(state.get("goal") or req.message)[:200],
            steps=list(state.get("plan_steps") or [FINAL_STEP]),
            rationale=str(state.get("rationale") or "LLM 根据上下文生成执行计划")[:500],
            source=str(state.get("plan_source") or "llm"),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM planner failed, fallback to deterministic plan: %s", exc)
        return fallback_plan(req, reason=f"Planner 降级：{exc}")


def apply_plan_to_request(req: ChatRequest, plan: ExecutionPlan) -> ChatRequest:
    selected = set(plan.steps)
    return req.model_copy(
        update={
            "web_search": req.web_search and "web_search" in selected,
            "arxiv": req.arxiv and "arxiv_search" in selected,
            "semantic_scholar": req.semantic_scholar and "semantic_scholar" in selected,
            "file_tools": req.file_tools and "file_tools" in selected,
            "external_mcp": req.external_mcp and "external_mcp" in selected,
            # 保留会话的知识库归属；本轮是否真正召回由计划步骤控制。
            "knowledge_base_id": req.knowledge_base_id,
        }
    )


def planner_sse(plan: ExecutionPlan) -> dict:
    return {
        "type": "agent_step",
        "step": "planner",
        "status": "done" if plan.source == "llm" else "degraded",
        "detail": f"生成 {len(plan.steps)} 步执行计划",
        "meta": {
            "goal": plan.goal,
            "steps": plan.steps,
            "rationale": plan.rationale,
            "source": plan.source,
        },
    }
