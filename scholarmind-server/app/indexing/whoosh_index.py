from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from whoosh import index as whoosh_index
from whoosh.fields import ID, Schema, TEXT
from whoosh.writing import AsyncWriter

log = logging.getLogger(__name__)

_schema = Schema(
    chunk_id=ID(stored=True, unique=True),
    kb_id=ID(stored=True),
    user_id=ID(stored=True),
    doc_id=ID(stored=True),
    page=TEXT(stored=True),
    content=TEXT(stored=True),
)


def _dir(root: str | Path) -> str:
    d = Path(root) / "main"
    d.mkdir(parents=True, exist_ok=True)
    return str(d.resolve())


def open_or_create_index(root: str | Path):
    path = _dir(root)
    if whoosh_index.exists_in(path):
        return whoosh_index.open_dir(path)
    return whoosh_index.create_in(path, _schema)


def whoosh_upsert_chunks(root: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ix = open_or_create_index(root)
    writer = AsyncWriter(ix)
    for r in rows:
        writer.update_document(
            chunk_id=r["chunk_id"],
            kb_id=r["kb_id"],
            user_id=r["user_id"],
            doc_id=r["doc_id"],
            page=str(int(r["page"])),
            content=str(r["text"])[:200000],
        )
    writer.commit()
    log.info("whoosh upsert %s chunks", len(rows))
