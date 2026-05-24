from pathlib import Path

from app.core.config import settings
from app.storage.base import BlobStorage
from app.storage.local import LocalBlobStorage


def get_blob_storage() -> BlobStorage:
    """工厂：后续可按配置返回 OSS 适配器。"""
    return LocalBlobStorage(Path(settings.storage_local_root))
