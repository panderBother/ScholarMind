from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    """Kubernetes / 负载均衡健康检查。"""
    return HealthResponse(status="ok")
