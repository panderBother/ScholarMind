"""BGE-Reranker 精排：对 RRF 融合后的候选片段按 query-passage 相关度重排序。"""

from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

from app.core.config import get_settings
from app.http_client import sync_request_with_retry

log = logging.getLogger(__name__)

_reranker_lock = threading.Lock()
_reranker_model: Any = None


def _load_reranker() -> Any:
    global _reranker_model  # noqa: PLW0603
    with _reranker_lock:
        if _reranker_model is None:
            from sentence_transformers import CrossEncoder

            model_id = get_settings().rerank_model_id
            log.info("加载本地 Rerank 模型 %s …", model_id)
            _reranker_model = CrossEncoder(model_id, trust_remote_code=True)
            log.info("本地 Rerank 模型就绪")
        return _reranker_model


def _rerank_http_scores(query: str, documents: list[str]) -> list[float]:
    """调用白山智算 / EdgeFN OpenAI 兼容 POST /v1/rerank。"""
    s = get_settings()
    base_src = s.rerank_http_base_url or s.embedding_http_base_url or s.edgefn_api_base_url
    base = (base_src or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("云端 Rerank 未配置地址：请设置 RERANK_HTTP_BASE_URL 或 EDGEFN_API_BASE_URL")

    key = (s.rerank_http_api_key or s.embedding_http_api_key or s.edgefn_api_key or "").strip()
    if not key:
        raise RuntimeError("云端 Rerank 未配置密钥：请设置 RERANK_HTTP_API_KEY 或 EDGEFN_API_KEY")

    url = f"{base}/rerank"
    model = s.rerank_http_model
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(120.0, connect=30.0)
    payload = {"model": model, "query": query, "documents": documents}

    def _post(client: httpx.Client) -> httpx.Response:
        return client.post(url, headers=headers, json=payload)

    r = sync_request_with_retry(_post, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("Rerank 响应格式异常")

    results = data.get("results")
    if not isinstance(results, list):
        raise RuntimeError(f"Rerank 响应缺少 results 字段: {list(data.keys())}")

    scores = [0.0] * len(documents)
    for item in results:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(scores):
            continue
        score = item.get("relevance_score")
        if score is None:
            score = item.get("score")
        scores[idx] = float(score or 0.0)
    return scores


def _rerank_local_scores(query: str, documents: list[str]) -> list[float]:
    model = _load_reranker()
    pairs = [(query, doc) for doc in documents]
    raw_scores = model.predict(pairs, show_progress_bar=False)
    return [float(s) for s in raw_scores]


def _apply_rerank_scores(
    candidates: list[dict[str, Any]],
    raw_scores: list[float],
) -> list[dict[str, Any]]:
    settings = get_settings()
    out: list[dict[str, Any]] = []
    for cand, score in zip(candidates, raw_scores):
        row = dict(cand)
        rs = float(score)
        row["rerank_score"] = rs
        row["score"] = rs
        out.append(row)

    out.sort(key=lambda x: float(x.get("rerank_score") or 0.0), reverse=True)

    min_score = settings.rerank_min_score
    if min_score is not None:
        out = [r for r in out if float(r.get("rerank_score") or 0.0) >= min_score]
    return out


def rerank_candidates(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对候选列表精排；hash 模式或关闭 rerank 时保持 RRF 顺序。"""
    if not candidates:
        return []

    settings = get_settings()
    embed_mode = (settings.embedding_mode or "bge").strip().lower()
    if not settings.rerank_enabled or embed_mode == "hash":
        return candidates

    q = (query or "").strip()
    if not q:
        return candidates

    documents = [str(c.get("text") or "")[:8000] for c in candidates]
    rerank_mode = (settings.rerank_mode or "http").strip().lower()

    try:
        if rerank_mode == "local":
            raw_scores = _rerank_local_scores(q, documents)
        else:
            raw_scores = _rerank_http_scores(q, documents)
    except Exception as e:
        log.warning("rerank failed (%s), fallback to RRF order: %s", rerank_mode, e)
        return candidates

    out = _apply_rerank_scores(candidates, raw_scores)
    log.info("rerank (%s): in=%s out=%s", rerank_mode, len(candidates), len(out))
    return out
