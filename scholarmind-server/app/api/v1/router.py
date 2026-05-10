from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, documents, health, knowledge_bases

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, prefix="/knowledge-bases", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
