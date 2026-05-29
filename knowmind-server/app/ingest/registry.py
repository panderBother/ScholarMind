from __future__ import annotations

import logging
from pathlib import Path

from app.ingest.docx_parser import parse_doc, parse_docx
from app.ingest.excel_parser import parse_csv, parse_excel, parse_xls
from app.ingest.image_parser import parse_image
from app.ingest.pdf import parse_pdf
from app.ingest.text_parser import parse_text_file
from app.ingest.types import EXTENSION_MAP, PREVIEW_FILE_TYPES, FileType, ParseResult

log = logging.getLogger(__name__)


def detect_file_type(filename: str) -> FileType:
    ext = Path(filename).suffix.lower()
    return EXTENSION_MAP.get(ext, FileType.UNKNOWN)


def requires_preview(file_type: FileType) -> bool:
    return file_type in PREVIEW_FILE_TYPES


def parse_file(path: str, filename: str | None = None, file_type: FileType | None = None) -> ParseResult:
    name = filename or Path(path).name
    ft = file_type or detect_file_type(name)
    log.info("parse_file type=%s name=%s", ft, name)

    if ft == FileType.PDF:
        return parse_pdf(path, name)
    if ft == FileType.DOCX:
        return parse_docx(path, name)
    if ft == FileType.DOC:
        return parse_doc(path, name)
    if ft == FileType.XLSX:
        return parse_excel(path, name)
    if ft == FileType.XLS:
        return parse_xls(path, name)
    if ft == FileType.CSV:
        return parse_csv(path, name)
    if ft == FileType.MARKDOWN:
        return parse_text_file(path, name, is_markdown=True)
    if ft == FileType.TEXT:
        return parse_text_file(path, name, is_markdown=False)
    if ft == FileType.IMAGE:
        return parse_image(path, name)
    raise ValueError(f"不支持的文件格式：{Path(name).suffix or name}")
