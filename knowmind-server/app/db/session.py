from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base

__all__ = ["Base", "async_session_maker", "init_db", "close_db", "get_session_factory"]

async_engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str) -> None:
    """创建全局异步引擎与会话工厂（在应用 lifespan 中调用一次）。"""
    global async_engine, async_session_maker
    if async_engine is not None:
        await close_db()
    async_engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def close_db() -> None:
    global async_engine, async_session_maker
    if async_engine is not None:
        await async_engine.dispose()
    async_engine = None
    async_session_maker = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if async_session_maker is None:
        msg = "数据库未初始化：请配置 DATABASE_URL 并确保应用 lifespan 已执行 init_db"
        raise RuntimeError(msg)
    return async_session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    """由路由注入；写操作请在业务层 `await session.commit()`。"""
    try:
        factory = get_session_factory()
    except RuntimeError as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "数据库未配置或尚未初始化",
        ) from e
    async with factory() as session:
        yield session
