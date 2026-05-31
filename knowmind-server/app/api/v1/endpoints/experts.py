import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db, get_session_factory
from app.models.schemas import ChatRequest
from app.schemas.expert import ExpertChatRequest, ExpertCreateIn, ExpertOut
from app.services import expert_service as expert_svc
from app.services.chat_service import iter_chat_stream
from app.services.expert_service import ExpertError

router = APIRouter()


def _out(row) -> ExpertOut:
    return ExpertOut(**expert_svc.expert_to_schema(row))


@router.post("", response_model=ExpertOut, status_code=201)
async def create_expert(
    body: ExpertCreateIn,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        row = await expert_svc.create_expert(
            session,
            user_id,
            kb_id=body.kb_id,
            name=body.name,
            description=body.description,
        )
        await session.commit()
        await session.refresh(row)
    except ExpertError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return _out(row)


@router.get("", response_model=list[ExpertOut])
async def list_experts(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    rows = await expert_svc.list_experts(session, user_id, kb_id=kb_id, limit=limit)
    return [_out(r) for r in rows]


@router.get("/{expert_id}", response_model=ExpertOut)
async def get_expert(
    expert_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        row = await expert_svc.get_expert(session, user_id, expert_id)
    except ExpertError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return _out(row)


@router.post("/{expert_id}/refresh", response_model=ExpertOut)
async def refresh_expert(
    expert_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        row = await expert_svc.refresh_expert_prompt(session, user_id, expert_id)
        await session.commit()
        await session.refresh(row)
    except ExpertError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return _out(row)


@router.delete("/{expert_id}", status_code=204)
async def delete_expert(
    expert_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        await expert_svc.delete_expert(session, user_id, expert_id)
        await session.commit()
    except ExpertError as e:
        raise HTTPException(e.status_code, detail=e.message) from e


@router.post("/{expert_id}/chat/stream")
async def expert_chat_stream(
    expert_id: str,
    req: ExpertChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    factory = get_session_factory()

    async def gen():
        async with factory() as session:
            try:
                expert = await expert_svc.get_expert(session, user_id, expert_id)
            except ExpertError as e:
                err = json.dumps({"type": "error", "message": e.message}, ensure_ascii=False)
                yield f"data: {err}\n\n"
                yield "data: {\"type\":\"done\"}\n\n"
                return

            chat_req = ChatRequest(
                message=req.message,
                knowledge_base_id=expert.kb_id,
                deep_research=req.deep_research,
                web_search=req.web_search,
                arxiv=req.arxiv or req.deep_research,
                semantic_scholar=req.semantic_scholar or req.deep_research,
                file_tools=False,
                external_mcp=False,
                conversation_id=req.conversation_id,
            )
            async for line in iter_chat_stream(
                chat_req,
                session=session,
                user_id=user_id,
                expert_prompt=expert.system_prompt,
                expert_id=expert.id,
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
