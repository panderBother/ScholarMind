from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from app.core.config import get_settings

log = logging.getLogger(__name__)


@runtime_checkable
class VectorIndex(Protocol):
    def upsert_chunks(self, rows: list[dict[str, Any]]) -> None: ...

    def delete_chunks(self, chunk_ids: list[str]) -> None: ...

    def query_similar(
        self,
        *,
        kb_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]: ...


def get_vector_index() -> VectorIndex:
    s = get_settings()
    if s.milvus_uri:
        try:
            from app.indexing.vector_milvus import MilvusRemoteIndex

            idx: VectorIndex = MilvusRemoteIndex(
                s.milvus_uri,
                collection_name=s.milvus_collection_name,
                vector_dim=s.embedding_vector_dim,
            )
            log.info("vector backend: milvus (%s)", s.milvus_uri)
            return idx
        except Exception as e:
            log.warning("Milvus 不可用，回退 Chroma: %s", e)
    from app.indexing.vector_chroma import ChromaVectorIndex

    log.info("vector backend: chroma (%s)", s.chroma_data_path)
    return ChromaVectorIndex(s.chroma_data_path, collection_name=s.chroma_collection_name)
