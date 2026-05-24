import json

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id
from app.models.mcp_schemas import (
    ImportMcpRequest,
    ImportMcpResponse,
    McpToolsResponse,
    UpdateBuiltinMcpRequest,
)
from app.services import mcp_registry

router = APIRouter()


@router.get("", response_model=McpToolsResponse)
async def get_mcp_tools(user_id: str = Depends(get_current_user_id)) -> McpToolsResponse:
    return mcp_registry.list_tools(user_id)


@router.patch("/builtin", response_model=McpToolsResponse)
async def patch_builtin_tool(
    body: UpdateBuiltinMcpRequest,
    user_id: str = Depends(get_current_user_id),
) -> McpToolsResponse:
    try:
        return mcp_registry.update_builtin(user_id, body.id, body.enabled)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/custom/{custom_id}", response_model=McpToolsResponse)
async def patch_custom_tool(
    custom_id: str,
    body: UpdateBuiltinMcpRequest,
    user_id: str = Depends(get_current_user_id),
) -> McpToolsResponse:
    try:
        return mcp_registry.update_custom_enabled(user_id, custom_id, body.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/import", response_model=ImportMcpResponse)
async def import_mcp_tools(
    body: ImportMcpRequest,
    user_id: str = Depends(get_current_user_id),
) -> ImportMcpResponse:
    try:
        return mcp_registry.import_mcp_json(user_id, body.raw_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 无效: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/custom/{custom_id}", response_model=McpToolsResponse)
async def delete_custom_tool(
    custom_id: str,
    user_id: str = Depends(get_current_user_id),
) -> McpToolsResponse:
    try:
        return mcp_registry.delete_custom(user_id, custom_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
