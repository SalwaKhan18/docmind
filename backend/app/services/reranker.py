"""Lazy cross-encoder reranking."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


@lru_cache
def get_reranker() -> CrossEncoder:
    """Load and cache the configured cross-encoder."""
    from sentence_transformers import CrossEncoder

    model_name = get_settings().reranker_model
    logger.info("Loading reranker %s; first startup may download model files", model_name)
    return CrossEncoder(model_name)


def rerank(query: str, candidates: list[dict], limit: int = 5) -> list[dict]:
    """Score candidates against a query and return the strongest matches."""
    if not candidates:
        return []
    scores = get_reranker().predict([(query, item["text"]) for item in candidates])
    ranked = []
    for item, score in zip(candidates, scores, strict=False):
        ranked.append({**item, "rerank_score": float(score)})
    return sorted(ranked, key=lambda item: item["rerank_score"], reverse=True)[:limit]
