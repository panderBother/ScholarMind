from __future__ import annotations

import io
import logging

log = logging.getLogger(__name__)

_tesseract_available: bool | None = None


def is_tesseract_available() -> bool:
    global _tesseract_available  # noqa: PLW0603
    if _tesseract_available is not None:
        return _tesseract_available
    try:
        import pytesseract  # noqa: PLC0415

        pytesseract.get_tesseract_version()
        _tesseract_available = True
    except Exception:
        _tesseract_available = False
    return _tesseract_available


def ocr_image_bytes(data: bytes, *, lang: str = "chi_sim+eng") -> str:
    """对图片字节做 OCR；未安装 Tesseract 时返回空字符串。"""
    if not data:
        return ""
    if not is_tesseract_available():
        log.debug("Tesseract 不可用，跳过 OCR")
        return ""
    try:
        from PIL import Image  # noqa: PLC0415
        import pytesseract  # noqa: PLC0415

        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img, lang=lang)
        return (text or "").strip()
    except Exception:
        log.warning("OCR 失败", exc_info=True)
        return ""


def ocr_pil_image(img, *, lang: str = "chi_sim+eng") -> str:
    if not is_tesseract_available():
        return ""
    try:
        import pytesseract  # noqa: PLC0415

        return (pytesseract.image_to_string(img, lang=lang) or "").strip()
    except Exception:
        log.warning("OCR PIL 失败", exc_info=True)
        return ""
