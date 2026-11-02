"""Lazy local sentence-transformer embedding model."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the configured embedding model."""
    from sentence_transformers import SentenceTransformer

    model_name = get_settings().embedding_model
    logger.info(
        "Loading local embedding model %s; first startup may download model files",
        model_name,
    )
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encode text batches as normalized vectors."""
    if not texts:
        return []
    vectors = get_embedding_model().encode(
        texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32
    )
    return vectors.tolist()
