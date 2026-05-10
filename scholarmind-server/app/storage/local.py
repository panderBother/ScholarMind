from __future__ import annotations

import asyncio
from pathlib import Path

from app.storage.base import BlobStorage


def _normalize_key(key: str) -> str:
    k = key.replace("\\", "/").strip("/")
    if not k or ".." in k.split("/"):
        raise ValueError("非法存储 key")
    return k


class LocalBlobStorage:
    """开发期本地磁盘实现；根目录由配置指定。"""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def filesystem_path(self, key: str) -> str:
        rel = _normalize_key(key)
        path = (self._root / rel).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as e:
            raise ValueError("路径越界") from e
        return str(path)

    async def put_bytes(self, key: str, data: bytes) -> None:
        path = Path(self.filesystem_path(key))
        path.parent.mkdir(parents=True, exist_ok=True)

        def _write() -> None:
            path.write_bytes(data)

        await asyncio.to_thread(_write)

    async def read_bytes(self, key: str) -> bytes:
        path = Path(self.filesystem_path(key))

        def _read() -> bytes:
            return path.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete(self, key: str) -> None:
        path = Path(self.filesystem_path(key))

        def _unlink() -> None:
            if path.is_file():
                path.unlink()

        await asyncio.to_thread(_unlink)


def assert_blob_storage(x: object) -> BlobStorage:
    """供类型检查：`LocalBlobStorage` 满足 `BlobStorage` 协议。"""
    if not isinstance(x, LocalBlobStorage):
        msg = "当前仅支持 LocalBlobStorage"
        raise TypeError(msg)
    return x
