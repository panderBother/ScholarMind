from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class ChromaChatMemoryIndex:
    """对话记忆向量：按 conversation_id + user_id 过滤，与文档 Chroma collection 分离。"""

    def __init__(self, data_path: str | Path, *, collection_name: str) -> None:
        import chromadb
        from chromadb.config import Settings

        root = Path(data_path)
        root.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(root.resolve()),
            settings=Settings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_turn(
        self,
        *,
        chunk_id: str,
        text: str,
        conversation_id: str,
        user_id: str,
        chunk_kind: str,
        assistant_message_id: str,
    ) -> None:
        from app.ingest.embedding import embed_texts

        t = (text or "").strip()[:16000]
        if not t:
            return
        try:
            emb = embed_texts([t])[0]
        except Exception as e:
            log.warning("chat memory embed skip: %s", e)
            return
        self._col.upsert(
            ids=[chunk_id],
            embeddings=[emb],
            documents=[t],
            metadatas=[
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "chunk_kind": chunk_kind,
                    "assistant_message_id": assistant_message_id,
                },
            ],
        )
        log.info("chroma chat upsert chunk_id=%s", chunk_id)

    def query_for_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        k = max(1, min(top_k, 64))
        try:
            raw = self._col.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where={
                    "$and": [
                        {"conversation_id": conversation_id},
                        {"user_id": user_id},
                    ],
                },
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            log.warning("chroma chat query failed: %s", e)
            return []

        ids_list = raw.get("ids") or []
        docs_list = raw.get("documents") or []
        meta_list = raw.get("metadatas") or []
        dist_list = raw.get("distances") or []
        if not ids_list or not ids_list[0]:
            return []

        out: list[dict[str, Any]] = []
        for i, cid in enumerate(ids_list[0]):
            doc_txt = (docs_list[0][i] if docs_list and docs_list[0] else "") or ""
            meta = (meta_list[0][i] if meta_list and meta_list[0] else {}) or {}
            dist = None
            if dist_list and dist_list[0] and i < len(dist_list[0]):
                dist = float(dist_list[0][i])
            out.append(
                {
                    "chunk_id": cid,
                    "text": doc_txt,
                    "chunk_kind": str(meta.get("chunk_kind", "")),
                    "distance": dist,
                },
            )
        return out
