"""深度研究：按 Plan 顺序执行检索步骤，失败自动重试一次。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from app.models.schemas import ChatRequest
from app.services.agent_orchestrator import build_research_plan
from app.services.chat_prefetch import (
    PrefetchResult,
    fetch_arxiv_md,
    fetch_semantic_scholar_md,
    merge_context_parts,
    want_arxiv,
    want_semantic_scholar,
)

MAX_RETRIES = 1


async def _retry_step(
    step: str,
    run: Callable[[], Awaitable[str]],
    *,
    emit: Callable[[dict], None],
    agent_step_sse: Callable[..., dict],
) -> str:
    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        detail = "执行中…" if attempt == 0 else f"重试 ({attempt}/{MAX_RETRIES})…"
        emit(agent_step_sse(step, status="running", detail=detail))
        try:
            return await run()
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.3)
    emit(agent_step_sse(step, status="error", detail=f"失败：{last_err}"))
    return ""


async def execute_deep_research_prefetch(
    *,
    req: ChatRequest,
    user_id: str | None,
    kb_context: str,
    load_rag: Callable[[], Awaitable[tuple[str, list]]],
    rag_hits: list,
    rag_diag: dict,
    agent_step_sse: Callable[..., dict],
    sse_event: Callable[[dict], str],
    rag_step_done: Callable[..., dict],
    want_web_search: Callable[[ChatRequest, str | None], bool],
    fetch_web: Callable[[], Awaitable[str]],
) -> AsyncIterator[str | PrefetchResult]:
    plan = build_research_plan(req, user_id)
    yield sse_event(
        {
            "type": "agent_step",
            "step": "planner",
            "status": "done",
            "detail": f"深度研究 {len(plan.steps)} 步：顺序执行",
            "meta": {"goal": plan.goal, "steps": plan.steps, "notes": plan.notes},
        },
    )

    lines: list[str] = []

    def emit(payload: dict) -> None:
        lines.append(sse_event(payload))

    kb_md = (kb_context or "").strip()
    web_md = ""
    arxiv_md = ""
    s2_md = ""

    for step in plan.steps:
        if step == "rag_retrieval" and req.knowledge_base_id:

            async def _load() -> str:
                nonlocal kb_md
                kb_md, hits = await load_rag()
                rag_hits.clear()
                rag_hits.extend(hits)
                return kb_md

            await _retry_step("rag_retrieval", _load, emit=emit, agent_step_sse=agent_step_sse)
            emit(rag_step_done(rag_hits, kb_markdown=kb_md, diag=rag_diag))
        elif step == "arxiv_search" and want_arxiv(req, user_id):
            arxiv_md = await _retry_step(
                "arxiv_search",
                lambda: fetch_arxiv_md(req, user_id),
                emit=emit,
                agent_step_sse=agent_step_sse,
            )
            emit(
                agent_step_sse(
                    "arxiv_search",
                    status="done",
                    detail="已注入 arXiv 结果" if arxiv_md.strip() else "无 arXiv 结果",
                ),
            )
        elif step == "semantic_scholar" and want_semantic_scholar(req, user_id):
            s2_md = await _retry_step(
                "semantic_scholar",
                lambda: fetch_semantic_scholar_md(req, user_id),
                emit=emit,
                agent_step_sse=agent_step_sse,
            )
            emit(
                agent_step_sse(
                    "semantic_scholar",
                    status="done",
                    detail="已注入 Semantic Scholar 结果" if s2_md.strip() else "无 S2 结果",
                ),
            )
        elif step == "web_search" and want_web_search(req, user_id):
            web_md = await _retry_step("web_search", fetch_web, emit=emit, agent_step_sse=agent_step_sse)
            emit(
                agent_step_sse(
                    "web_search",
                    status="done",
                    detail="已注入联网结果" if web_md.strip() else "无联网结果",
                ),
            )

    for line in lines:
        yield line

    attachment_md = ""
    if user_id and req.attachment_ids:
        from app.services.chat_attachment_service import load_attachment_context_async

        attachment_md = await load_attachment_context_async(user_id, req.attachment_ids)

    merged = merge_context_parts(kb_md, web_md, arxiv_md, s2_md, attachment_md)
    yield PrefetchResult(
        merged_context=merged,
        web_injected=bool(web_md.strip()),
        arxiv_injected=bool(arxiv_md.strip()),
        semantic_scholar_injected=bool(s2_md.strip()),
    )
