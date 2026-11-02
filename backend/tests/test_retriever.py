"""Tests for hybrid retrieval fusion."""

from app.services import retriever, vectorstore
from app.services.retriever import reciprocal_rank_fusion


def test_rrf_combines_rankings_and_preserves_best_match() -> None:
    vectors = [
        {"id": "shared", "text": "a", "vector_score": 0.9},
        {"id": "vector", "text": "b"},
    ]
    keywords = [
        {"id": "shared", "text": "a", "bm25_score": 1.0},
        {"id": "keyword", "text": "c"},
    ]

    result = reciprocal_rank_fusion([vectors, keywords])

    assert [item["id"] for item in result] == ["shared", "vector", "keyword"]
    assert result[0]["rrf_score"] > result[1]["rrf_score"]
    assert result[0]["vector_score"] == 0.9
    assert result[0]["bm25_score"] == 1.0


def test_hybrid_retriever_queries_both_indexes(monkeypatch) -> None:
    vector_result = {
        "ids": [["vector-id"]],
        "documents": [["semantic match"]],
        "metadatas": [[{"doc_id": "doc", "filename": "guide.md", "page": 1}]],
        "distances": [[0.1]],
    }
    keyword_result = {
        "id": "keyword-id",
        "text": "exact keyword match",
        "metadata": {"doc_id": "doc", "filename": "guide.md", "page": 2},
        "bm25_score": 1.0,
    }
    calls = {"vector": 0, "bm25": 0}
    monkeypatch.setattr(retriever, "embed_texts", lambda _: [[0.0, 1.0]])
    monkeypatch.setattr(
        retriever,
        "vector_search",
        lambda *_: calls.update(vector=calls["vector"] + 1) or vector_result,
    )
    monkeypatch.setattr(
        retriever.bm25_index,
        "search",
        lambda *_: calls.update(bm25=calls["bm25"] + 1) or [keyword_result],
    )

    result = retriever.retrieve("question")

    assert calls == {"vector": 1, "bm25": 1}
    assert {item["id"] for item in result} == {"vector-id", "keyword-id"}


def test_vector_search_caps_results_and_applies_document_filter(monkeypatch) -> None:
    class CollectionStub:
        def count(self):
            return 3

        def query(self, **kwargs):
            return kwargs

    monkeypatch.setattr(vectorstore, "get_collection", CollectionStub)

    result = vectorstore.search([0.0, 1.0], 20, ["doc-id"])

    assert result["n_results"] == 3
    assert result["where"] == {"doc_id": {"$in": ["doc-id"]}}
