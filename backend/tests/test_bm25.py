"""Tests for persisted BM25 search and document filters."""

from app.services import bm25_index


def test_bm25_search_returns_match_for_single_selected_document(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        bm25_index, "_index_path", lambda: tmp_path / "bm25_index.json"
    )
    bm25_index.rebuild(
        [
            {
                "id": "chunk-1",
                "text": "Adult admission costs fourteen dollars.",
                "metadata": {"doc_id": "museum", "filename": "museum.md", "page": 1},
            },
            {
                "id": "chunk-2",
                "text": "A library loan lasts twenty-one days.",
                "metadata": {"doc_id": "library", "filename": "library.md", "page": 1},
            },
        ]
    )

    matches = bm25_index.search("adult admission", 20, ["museum"])

    assert len(matches) == 1
    assert matches[0]["id"] == "chunk-1"
    assert matches[0]["bm25_score"] == 1.0


def test_bm25_search_ignores_queries_without_tokens() -> None:
    assert bm25_index._tokens("!?.,") == []
