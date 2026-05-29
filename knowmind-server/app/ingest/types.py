from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    MARKDOWN = "markdown"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


# 扩展名 → 类型
EXTENSION_MAP: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".doc": FileType.DOC,
    ".xlsx": FileType.XLSX,
    ".xls": FileType.XLS,
    ".csv": FileType.CSV,
    ".md": FileType.MARKDOWN,
    ".markdown": FileType.MARKDOWN,
    ".txt": FileType.TEXT,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".webp": FileType.IMAGE,
}

# 所有格式上传后先预览确认，再异步入库
PREVIEW_FILE_TYPES: frozenset[FileType] = frozenset(
    {
        FileType.PDF,
        FileType.DOCX,
        FileType.DOC,
        FileType.XLSX,
        FileType.XLS,
        FileType.CSV,
        FileType.MARKDOWN,
        FileType.TEXT,
        FileType.IMAGE,
    }
)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(EXTENSION_MAP.keys())

FILE_MAGIC: dict[FileType, bytes | tuple[bytes, ...]] = {
    FileType.PDF: b"%PDF",
    FileType.DOCX: b"PK\x03\x04",
    FileType.XLSX: b"PK\x03\x04",
}

MIME_BY_TYPE: dict[FileType, str] = {
    FileType.PDF: "application/pdf",
    FileType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileType.DOC: "application/msword",
    FileType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileType.XLS: "application/vnd.ms-excel",
    FileType.CSV: "text/csv",
    FileType.MARKDOWN: "text/markdown",
    FileType.TEXT: "text/plain",
    FileType.IMAGE: "image/png",
}


@dataclass
class PageText:
    page_index: int  # 0-based
    text: str


@dataclass
class ParseResult:
    """解析结果，供预览与入库共用。"""

    pages: list[PageText]
    title: str | None = None
    summary: str | None = None
    content: str | None = None  # 合并后的 Markdown 正文（预览用）

    def merged_content(self) -> str:
        if self.content:
            return self.content
        parts = [(p.text or "").strip() for p in self.pages if (p.text or "").strip()]
        return "\n\n".join(parts)
