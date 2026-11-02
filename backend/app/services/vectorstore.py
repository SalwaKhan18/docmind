"""Persistent Chroma vector-store operations."""

from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import get_settings


@lru_cache
def get_collection() -> Collection:
    """Return the persistent document-chunk collection."""
    path = get_settings().data_dir / "chroma"
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    return client.get_or_create_collection(
        name="docmind_chunks", metadata={"hnsw:space": "cosine"}
    )


def add_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Add document chunks and metadata to Chroma."""
    if chunks:
        collection = get_collection()
        collection.add(
            ids=[str(chunk["id"]) for chunk in chunks],
            documents=[str(chunk["text"]) for chunk in chunks],
            embeddings=embeddings,
            metadatas=[chunk["metadata"] for chunk in chunks],
        )


def delete_document(doc_id: str) -> None:
    """Remove every vector associated with a document."""
    get_collection().delete(where={"doc_id": doc_id})


def search(
    query_embedding: list[float], limit: int, document_ids: list[str] | None
) -> dict:
    """Search vectors, optionally restricted to selected documents."""
    collection = get_collection()
    filters = {"doc_id": {"$in": document_ids}} if document_ids else None
    available = collection.count(where=filters) if filters else collection.count()
    if available == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit, available),
        where=filters,
        include=["documents", "metadatas", "distances"],
    )
