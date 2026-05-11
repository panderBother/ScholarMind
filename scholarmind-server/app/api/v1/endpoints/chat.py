from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user_id
from app.db.session import get_session_factory
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import iter_chat_stream, run_chat
from app.services.rag_context import build_kb_context_markdown

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """同步对话（含知识库 RAG 上下文）。当前版本未接多轮记忆，与流式接口行为可能不一致。"""
    factory = get_session_factory()
    async with factory() as session:
        kb_ctx = await build_kb_context_markdown(session, user_id, req.knowledge_base_id, req.message)
        return await run_chat(req, kb_context=kb_ctx)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """SSE 流式对话：在单连接内持有 DB 会话，启用多轮记忆（MySQL + Redis + 对话向量）。"""

    factory = get_session_factory()

    async def gen():
        async with factory() as session:
            kb_ctx = await build_kb_context_markdown(session, user_id, req.knowledge_base_id, req.message)
            async for line in iter_chat_stream(
                req,
                kb_context=kb_ctx,
                session=session,
                user_id=user_id,
            ):
                yield line

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
