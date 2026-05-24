from __future__ import annotations

import logging

from app.core.config import get_settings
from app.indexing.vector_chroma_chat import ChromaChatMemoryIndex

log = logging.getLogger(__name__)

_chat_index: ChromaChatMemoryIndex | None = None


def get_chat_memory_index() -> ChromaChatMemoryIndex:
    """对话记忆仅使用 Chroma 独立 collection（与 Milvus 文档索引并存时仍以 Chroma 存对话）。"""
    global _chat_index
    if _chat_index is None:
        s = get_settings()
        _chat_index = ChromaChatMemoryIndex(
            s.chroma_data_path,
            collection_name=s.chroma_chat_collection_name,
        )
        log.info("chat memory chroma: %s / %s", s.chroma_data_path, s.chroma_chat_collection_name)
    return _chat_index
