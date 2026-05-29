from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.ingest.ocr import ocr_image_bytes
from app.ingest.types import PageText, ParseResult
from app.ingest.vlm import ocr_image_cloud_sync


def parse_image(path: str, filename: str | None = None) -> ParseResult:
    raw = Path(path).read_bytes()
    cloud_ocr = ocr_image_cloud_sync(path) if (settings.siliconflow_api_key or settings.edgefn_api_key) else ""
    local_ocr = ocr_image_bytes(raw) if not cloud_ocr else ""
    ocr_text = cloud_ocr or local_ocr

    parts: list[str] = []
    if ocr_text:
        parts.append("## 文字内容（OCR）\n\n" + ocr_text)
    else:
        parts.append(
            "## 文字内容（OCR）\n\n"
            "（未识别到文字。可配置 SILICONFLOW_API_KEY（DeepSeek-OCR）、安装 Tesseract，"
            "或配置支持识图的 EdgeFN 模型）"
        )

    content = "\n\n".join(parts)
    base = (filename or Path(path).name).rsplit(".", 1)[0]
    summary = (ocr_text or "图片")[:500]
    pages = [PageText(page_index=0, text=content)]
    return ParseResult(pages=pages, title=base[:200], summary=summary, content=content)
