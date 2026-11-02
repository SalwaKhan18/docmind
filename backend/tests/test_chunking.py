"""Tests for page-aware recursive text chunking."""

import pytest

from app.services.chunking import chunk_pages, split_text


def test_split_text_respects_size_and_overlap() -> None:
    text = "First sentence. " * 120
    chunks = split_text(text, chunk_size=200, overlap=30)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert chunks[0][-20:] in chunks[1]


def test_chunk_pages_keeps_page_metadata() -> None:
    chunks = chunk_pages([(3, "A useful sentence."), (4, "Another useful sentence.")], 100, 10)

    assert [(chunk["page"], chunk["text"]) for chunk in chunks] == [
        (3, "A useful sentence."),
        (4, "Another useful sentence."),
    ]


def test_split_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        split_text("text", chunk_size=100, overlap=100)


def test_long_sentence_is_not_truncated() -> None:
    text = "x" * 1500
    chunks = split_text(text, chunk_size=200, overlap=30)

    assert all(len(chunk) <= 200 for chunk in chunks)
    assert chunks[0] == "x" * 200
    assert chunks[-1].endswith("x")
    assert len(chunks) == 9
