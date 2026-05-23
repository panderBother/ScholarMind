from __future__ import annotations

import logging
import shutil
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
    item_id=ID(stored=True),
    lifecycle_status=ID(stored=True),
    page=TEXT(stored=True),
    content=TEXT(stored=True),
)

_REQUIRED_FIELDS = frozenset(_schema.names())


def _dir(root: str | Path) -> str:
    d = Path(root) / "main"
    d.mkdir(parents=True, exist_ok=True)
    return str(d.resolve())


def _schema_matches(ix: whoosh_index.FileIndex) -> bool:
    return frozenset(ix.schema.names()) == _REQUIRED_FIELDS


def _recreate_index(root: str | Path) -> whoosh_index.FileIndex:
    path = Path(_dir(root))
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    log.warning("whoosh index rebuilt at %s (schema upgrade)", path)
    return whoosh_index.create_in(str(path), _schema)


def open_or_create_index(root: str | Path) -> whoosh_index.FileIndex:
    path = _dir(root)
    if whoosh_index.exists_in(path):
        ix = whoosh_index.open_dir(path)
        if not _schema_matches(ix):
            log.warning(
                "whoosh schema mismatch existing=%s required=%s",
                sorted(ix.schema.names()),
                sorted(_REQUIRED_FIELDS),
            )
            ix.close()
            return _recreate_index(root)
        return ix
    return whoosh_index.create_in(path, _schema)


def whoosh_upsert_chunks(root: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    def _write(ix: whoosh_index.FileIndex) -> None:
        writer = AsyncWriter(ix)
        for r in rows:
            writer.update_document(
                chunk_id=r["chunk_id"],
                kb_id=r["kb_id"],
                user_id=r["user_id"],
                doc_id=str(r.get("doc_id") or ""),
                item_id=str(r.get("item_id") or ""),
                lifecycle_status=str(r.get("lifecycle_status") or "published"),
                page=str(int(r["page"])),
                content=str(r["text"])[:200000],
            )
        writer.commit()

    ix = open_or_create_index(root)
    try:
        _write(ix)
    except Exception as e:
        from whoosh.fields import UnknownFieldError

        if not isinstance(e, UnknownFieldError):
            raise
        log.warning("whoosh upsert hit UnknownFieldError, rebuilding once: %s", e)
        ix.close()
        ix = _recreate_index(root)
        _write(ix)
    log.info("whoosh upsert %s chunks", len(rows))


def whoosh_delete_chunk(root: str | Path, chunk_id: str) -> None:
    if not chunk_id:
        return
    ix = open_or_create_index(root)
    writer = AsyncWriter(ix)
    writer.delete_by_term("chunk_id", chunk_id)
    writer.commit()
