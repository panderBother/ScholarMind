from typing import Protocol, runtime_checkable


@runtime_checkable
class BlobStorage(Protocol):
    """对象存储抽象：本地目录与后续 OSS 共用接口。"""

    async def put_bytes(self, key: str, data: bytes) -> None:
        """写入二进制内容，`key` 为逻辑路径（不含盘符）。"""
        ...

    async def read_bytes(self, key: str) -> bytes:
        ...

    async def delete(self, key: str) -> None:
        ...

    def filesystem_path(self, key: str) -> str:
        """供同机 Worker 直接读文件时返回绝对路径。"""
        ...
