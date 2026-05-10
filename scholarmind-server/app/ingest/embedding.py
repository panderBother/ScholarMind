"""向量嵌入：本地 bge（sentence-transformers）、云端 http（OpenAI 兼容 /v1/embeddings）、hash（测试）。"""

from __future__ import annotations

import os

# Windows 上 HF XET 下载大模型易中断/卡在 0%，且 Ctrl+C 后会留下不完整缓存；默认走经典下载（可用环境变量改为 0 启用 XET）
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import hashlib
import logging
import math
import threading
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

_model_lock = threading.Lock()
_st_model: Any = None


def hash_embedding(text: str, dim: int = 384) -> list[float]:
    """确定性伪向量（用于 pytest / 无模型环境）；维数应与 `embedding_vector_dim` 一致。"""
    h = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    vec: list[float] = []
    for i in range(dim):
        b = h[i % len(h)]
        vec.append((b / 255.0) * 2.0 - 1.0)
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def _load_sentence_transformer() -> Any:
    global _st_model  # noqa: PLW0603 — 进程内单例
    with _model_lock:
        if _st_model is None:
            from sentence_transformers import SentenceTransformer

            mid = get_settings().embedding_model_id
            log.info(
                "加载嵌入模型 %s（首次需下载约 2GB+，请耐心等待；勿中断；HF_HUB_DISABLE_XET=%s）…",
                mid,
                os.environ.get("HF_HUB_DISABLE_XET", ""),
            )
            _st_model = SentenceTransformer(mid, trust_remote_code=True)
            log.info("嵌入模型就绪")
        return _st_model


def _parse_embeddings_json(data: dict[str, Any]) -> list[list[float]]:
    """兼容 OpenAI 批量 data[] 与白山文档里的单条 embedding 字段。"""
    raw_data = data.get("data")
    if isinstance(raw_data, list) and raw_data:
        items = sorted(raw_data, key=lambda x: int(x.get("index", 0)))
        out: list[list[float]] = []
        for it in items:
            emb = it.get("embedding")
            if not isinstance(emb, list):
                raise RuntimeError("embedding 响应缺少 data[].embedding")
            out.append([float(x) for x in emb])
        return out

    single = data.get("embedding")
    if isinstance(single, list):
        return [[float(x) for x in single]]

    raise RuntimeError(f"无法解析 embedding 响应字段: {list(data.keys())}")


def _embed_http_batch(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    base_src = s.embedding_http_base_url or s.edgefn_api_base_url
    base = (base_src or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("云端嵌入未配置地址：请设置 EMBEDDING_HTTP_BASE_URL 或 EDGEFN_API_BASE_URL")

    key = (s.embedding_http_api_key or s.edgefn_api_key or "").strip()
    if not key:
        raise RuntimeError("云端嵌入未配置密钥：请设置 EMBEDDING_HTTP_API_KEY 或 EDGEFN_API_KEY")

    url = f"{base}/embeddings"
    model = s.embedding_http_model
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(120.0, connect=30.0)

    # 截断过长片段，避免网关拒收（粗略按字符上限）
    max_chars = 12000
    clipped = [t[:max_chars] if len(t) > max_chars else t for t in texts]

    with httpx.Client(timeout=timeout) as client:
        # 先尝试 OpenAI 风格批量 input: string[]
        try:
            r = client.post(url, headers=headers, json={"model": model, "input": clipped})
            r.raise_for_status()
            vecs = _parse_embeddings_json(r.json())
            if len(vecs) == len(clipped):
                return vecs
            log.warning(
                "http embedding 批量返回条数与请求不一致 (%s vs %s)，改为逐条请求",
                len(vecs),
                len(clipped),
            )
        except (httpx.HTTPStatusError, RuntimeError, KeyError, TypeError, ValueError) as e:
            log.warning("http embedding 批量失败，改为逐条: %s", e)

        out: list[list[float]] = []
        for i, one in enumerate(clipped):
            r = client.post(url, headers=headers, json={"model": model, "input": one})
            r.raise_for_status()
            rows = _parse_embeddings_json(r.json())
            if len(rows) != 1:
                raise RuntimeError(f"单条 embedding 期望 1 条向量，得到 {len(rows)}（index={i}）")
            out.append(rows[0])
        return out


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量嵌入；空列表返回空。"""
    if not texts:
        return []
    settings = get_settings()
    mode = (settings.embedding_mode or "bge").strip().lower()
    dim = int(settings.embedding_vector_dim)

    if mode == "hash":
        return [hash_embedding(t, dim=dim) for t in texts]

    if mode == "http":
        vecs = _embed_http_batch(texts)
        for i, v in enumerate(vecs):
            if len(v) != dim:
                log.warning(
                    "云端返回向量维数 %s 与 EMBEDDING_VECTOR_DIM=%s 不一致（条 %s），仍以返回值为准入库",
                    len(v),
                    dim,
                    i,
                )
        return vecs

    model = _load_sentence_transformer()
    emb = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=max(1, settings.embedding_batch_size),
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return emb.tolist()
