from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.core.config import settings
from app.http_client import async_request_with_retry, friendly_connect_error

log = logging.getLogger(__name__)

_SILICONFLOW_OCR_PROMPT = "Free OCR"
_EDGEFN_VISION_PROMPT = (
    "请描述这张图片的内容。若包含文字、流程图、表格或界面截图，"
    "请提取关键文字并说明结构与含义。用中文 Markdown 输出，分「文字内容」与「图像描述」两节。"
)
_CHAT_IMAGE_PROMPT = (
    "用户在上传图片附件，请详细分析：\n"
    "1. 提取图中所有可见文字（OCR）\n"
    "2. 描述画面内容、布局、颜色、对象与场景\n"
    "3. 若是 UI/流程图/表格/商品/证件等，说明结构与关键信息\n"
    "用中文 Markdown，分「文字内容」与「图像描述」两节。"
)


def _guess_mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "image/png")


async def _vision_chat_async(
    path: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    image_before_text: bool = True,
) -> str:
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return ""
    if not raw:
        return ""
    mime = _guess_mime(path)
    b64 = base64.standard_b64encode(raw).decode("ascii")
    image_part = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
    text_part = {"type": "text", "text": prompt}
    content = [image_part, text_part] if image_before_text else [text_part, image_part]
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0.0,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def _do_post(client: httpx.AsyncClient) -> httpx.Response:
        return await client.post(url, headers=headers, json=payload)

    try:
        resp = await async_request_with_retry(_do_post, timeout=httpx.Timeout(120.0))
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        content_out = msg.get("content")
        return (content_out or "").strip() if isinstance(content_out, str) else ""
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            body = (e.response.text or "")[:240]
            log.info(
                "视觉 API 400（模型可能不支持 image_url 多模态）model=%s detail=%s",
                model,
                body or e.response.reason_phrase,
            )
        else:
            log.warning("视觉 API 请求失败: %s", friendly_connect_error(e))
        return ""
    except Exception:
        log.warning("视觉 API 调用失败", exc_info=True)
        return ""


async def _siliconflow_vision(path: str, prompt: str, *, image_before_text: bool = True) -> str:
    sf_key = (settings.siliconflow_api_key or "").strip()
    if not sf_key:
        return ""
    return await _vision_chat_async(
        path,
        api_key=sf_key,
        base_url=settings.siliconflow_api_base_url,
        model=settings.siliconflow_vision_model,
        prompt=prompt,
        image_before_text=image_before_text,
    )


async def _edgefn_vision(path: str, prompt: str, *, image_before_text: bool = False) -> str:
    edge_key = (settings.edgefn_api_key or "").strip()
    vision_model = (settings.edgefn_vision_model or "").strip()
    if not edge_key or not vision_model:
        return ""
    return await _vision_chat_async(
        path,
        api_key=edge_key,
        base_url=settings.edgefn_api_base_url,
        model=vision_model,
        prompt=prompt,
        image_before_text=image_before_text,
    )


async def analyze_image_for_chat_async(path: str) -> str:
    """
    对话附件专用：OCR + 视觉描述。
    默认走硅基 DeepSeek-OCR；仅当配置 EDGEFN_VISION_MODEL 时才额外/回退 EdgeFN。
    """
    sections: list[str] = []
    sf_key = (settings.siliconflow_api_key or "").strip()

    if sf_key:
        ocr = await _siliconflow_vision(path, _SILICONFLOW_OCR_PROMPT, image_before_text=True)
        if ocr.strip():
            sections.append("## 文字内容（OCR）\n\n" + ocr.strip())
        describe = await _siliconflow_vision(path, _CHAT_IMAGE_PROMPT, image_before_text=False)
        if describe.strip():
            if "文字内容" in describe or "图像描述" in describe:
                sections.append(describe.strip())
            else:
                sections.append("## 图像描述\n\n" + describe.strip())

    if not sections:
        edge_desc = await _edgefn_vision(path, _EDGEFN_VISION_PROMPT, image_before_text=False)
        if edge_desc.strip():
            sections.append(edge_desc.strip())

    if sections:
        return "\n\n".join(sections)

    return ""


async def ocr_image_cloud_async(path: str) -> str:
    """优先硅基流动 DeepSeek-OCR；未配置时尝试 EdgeFN 视觉模型（非对话模型）。"""
    text = await _siliconflow_vision(path, _SILICONFLOW_OCR_PROMPT, image_before_text=True)
    if text.strip():
        return text
    return await _edgefn_vision(path, _EDGEFN_VISION_PROMPT, image_before_text=False)


async def describe_image_async(path: str) -> str:
    """兼容旧名：返回云端 OCR/视觉结果。"""
    return await ocr_image_cloud_async(path)


def ocr_image_cloud_sync(path: str) -> str:
    """同步包装，供 Celery / 后台线程调用。"""
    import asyncio  # noqa: PLC0415

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(ocr_image_cloud_async(path))).result()
        return loop.run_until_complete(ocr_image_cloud_async(path))
    except RuntimeError:
        return asyncio.run(ocr_image_cloud_async(path))


def describe_image_sync(path: str) -> str:
    return ocr_image_cloud_sync(path)


def analyze_image_for_chat_sync(path: str) -> str:
    import asyncio  # noqa: PLC0415

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(analyze_image_for_chat_async(path))).result()
        return loop.run_until_complete(analyze_image_for_chat_async(path))
    except RuntimeError:
        return asyncio.run(analyze_image_for_chat_async(path))
