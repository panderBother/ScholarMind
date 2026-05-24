from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_sync_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _sync_database_url() -> str:
    u = get_settings().database_url
    if not u:
        msg = "DATABASE_URL 未配置"
        raise RuntimeError(msg)
    return u.replace("+asyncmy", "+pymysql", 1)


def get_sync_sessionmaker() -> sessionmaker[Session]:
    global _sync_engine, _SessionLocal
    if _SessionLocal is None:
        _sync_engine = create_engine(_sync_database_url(), pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False, autoflush=False)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_sync_sessionmaker()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
