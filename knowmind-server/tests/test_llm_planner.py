import pytest

from app.models.schemas import ChatRequest
from app.services.edgefn_client import ChatTurnResult
from app.services.llm_planner import apply_plan_to_request, build_llm_execution_plan


@pytest.mark.asyncio
async def test_llm_planner_selects_contextual_steps(monkeypatch) -> None:
    async def fake_complete(_messages):
        return ChatTurnResult(
            content=(
                '{"goal":"核对最新资料","steps":["memory_retrieval","web_search",'
                '"llm_generate"],"rationale":"问题依赖上一轮且需要最新信息"}'
            )
        )

    monkeypatch.setattr("app.services.llm_planner.complete_chat_turn", fake_complete)
    req = ChatRequest(message="继续核对最新版本", web_search=True, arxiv=True)
    plan = await build_llm_execution_plan(req, conversation_context="上一轮讨论了版本差异")
    effective = apply_plan_to_request(req, plan)

    assert plan.source == "llm"
    assert plan.steps == ["memory_retrieval", "web_search", "llm_generate"]
    assert effective.web_search is True
    assert effective.arxiv is False


@pytest.mark.asyncio
async def test_llm_planner_invalid_output_falls_back(monkeypatch) -> None:
    async def fake_complete(_messages):
        return ChatTurnResult(content="not json")

    monkeypatch.setattr("app.services.llm_planner.complete_chat_turn", fake_complete)
    req = ChatRequest(message="查询资料", knowledge_base_id="kb1", web_search=True)
    plan = await build_llm_execution_plan(req)

    assert plan.source == "fallback"
    assert "rag_retrieval" in plan.steps
    assert "web_search" in plan.steps
    assert plan.steps[-1] == "llm_generate"
