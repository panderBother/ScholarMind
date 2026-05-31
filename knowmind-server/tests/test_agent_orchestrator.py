import pytest

from app.models.schemas import ChatRequest
from app.services.agent_orchestrator import build_research_plan


def test_build_research_plan_includes_rag() -> None:
    req = ChatRequest(message="test", knowledge_base_id="kb1", deep_research=True, arxiv=True)
    plan = build_research_plan(req, "user1")
    assert "rag_retrieval" in plan.steps
    assert "llm_generate" in plan.steps
