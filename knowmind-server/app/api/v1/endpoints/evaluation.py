from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.evaluation import EvalDashboardOut
from app.services import evaluation_service as eval_svc

router = APIRouter()


@router.get("/dashboard", response_model=EvalDashboardOut)
async def evaluation_dashboard(
    _user_id: str = Depends(get_current_user_id),
):
    return eval_svc.get_dashboard()


@router.post("/run", response_model=EvalDashboardOut)
async def run_evaluation(
    _user_id: str = Depends(get_current_user_id),
):
    """触发 sample 数据集评估并刷新看板数据。"""
    return eval_svc.run_sample_eval()
