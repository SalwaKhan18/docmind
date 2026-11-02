"""Pydantic response and request schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    """Public document metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: str
    chunk_count: int
    error: str | None
    created_at: datetime


class UploadOut(BaseModel):
    """Documents accepted for background ingestion."""

    documents: list[DocumentOut]


class ConversationOut(BaseModel):
    """Conversation summary."""

    id: str
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    """Persisted message representation."""

    id: str
    conversation_id: str
    role: str
    content: str
    sources: list[dict]
    created_at: datetime


class ChatRequest(BaseModel):
    """Question submitted to the RAG pipeline."""

    question: str
    conversation_id: str | None = None
    document_ids: list[str] | None = None


class HealthOut(BaseModel):
    """Health-check response."""

    status: str
    provider: str
    model: str
