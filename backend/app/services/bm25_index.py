"""JSON-persisted BM25 index over ingested chunks."""

import json
import re
import threading
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.config import get_settings

_lock = threading.RLock()
_entries: list[dict] = []


def _index_path() -> Path:
    return get_settings().data_dir / "bm25_index.json"


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def load_index() -> list[dict]:
    """Load the persisted BM25 corpus into memory."""
    global _entries
    path = _index_path()
    with _lock:
        if path.exists():
            _entries = json.loads(path.read_text(encoding="utf-8"))
        else:
            _entries = []
        return list(_entries)


def rebuild(entries: list[dict] | None = None) -> None:
    """Replace and persist the searchable chunk corpus."""
    global _entries
    with _lock:
        if entries is not None:
            _entries = entries
        path = _index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_entries, ensure_ascii=False), encoding="utf-8")


def upsert(entries: list[dict]) -> None:
    """Add or replace chunks belonging to the supplied documents."""
    with _lock:
        current = load_index()
        doc_ids = {entry["metadata"]["doc_id"] for entry in entries}
        preserved = [entry for entry in current if entry["metadata"]["doc_id"] not in doc_ids]
        rebuild(preserved + entries)


def remove_document(doc_id: str) -> None:
    """Remove a document's chunks from the BM25 corpus."""
    with _lock:
        rebuild([entry for entry in load_index() if entry["metadata"]["doc_id"] != doc_id])


def search(query: str, limit: int, document_ids: list[str] | None) -> list[dict]:
    """Return BM25-ranked chunks and normalized display scores."""
    entries = load_index()
    if document_ids:
        entries = [e for e in entries if e["metadata"]["doc_id"] in document_ids]
    if not entries:
        return []
    model = BM25Okapi([_tokens(entry["text"]) for entry in entries])
    scores = model.get_scores(_tokens(query))
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:limit]
    maximum = max((score for _, score in ranked), default=0)
    return [
        {**entries[index], "bm25_score": float(score / maximum) if maximum > 0 else 0.0}
        for index, score in ranked
        if score > 0
    ]
