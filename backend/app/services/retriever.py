"""Hybrid retrieval and reciprocal-rank fusion."""

from app.services import bm25_index
from app.services.embeddings import embed_texts
from app.services.vectorstore import search as vector_search


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]], k: int = 60
) -> list[dict]:
    """Merge ranked result lists using reciprocal rank fusion."""
    fused: dict[str, dict] = {}
    for results in ranked_lists:
        for rank, result in enumerate(results, start=1):
            item_id = str(result["id"])
            if item_id not in fused:
                fused[item_id] = {**result, "rrf_score": 0.0}
            else:
                fused[item_id] = {**fused[item_id], **result}
            fused[item_id]["rrf_score"] += 1.0 / (k + rank)
    return sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)


def retrieve(
    query: str, document_ids: list[str] | None = None, limit: int = 20, mode: str = "hybrid"
) -> list[dict]:
    """Retrieve chunks using vector, BM25, or reciprocal-rank-fused search."""
    vector_results: list[dict] = []
    bm25_results: list[dict] = []
    if mode in {"vector", "hybrid"}:
        vector = vector_search(embed_texts([query])[0], limit, document_ids)
        ids = vector.get("ids", [[]])[0]
        texts = vector.get("documents", [[]])[0]
        metadata = vector.get("metadatas", [[]])[0]
        distances = vector.get("distances", [[]])[0]
        vector_results = [
            {
                "id": chunk_id,
                "text": text,
                "metadata": meta,
                "vector_score": max(0.0, 1.0 - float(distance)),
            }
            for chunk_id, text, meta, distance in zip(ids, texts, metadata, distances, strict=False)
        ]
    if mode in {"bm25", "hybrid"}:
        bm25_results = bm25_index.search(query, limit, document_ids)
    if mode == "vector":
        return vector_results
    if mode == "bm25":
        return bm25_results
    return reciprocal_rank_fusion([vector_results, bm25_results])
