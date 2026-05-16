from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    conversations,
    documents,
    health,
    knowledge_bases,
    mcp_tools,
    workspace_files,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, prefix="/knowledge-bases", tags=["documents"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(
    workspace_files.router,
    prefix="/workspace/files",
    tags=["workspace-files"],
)
api_router.include_router(mcp_tools.router, prefix="/mcp/tools", tags=["mcp-tools"])
