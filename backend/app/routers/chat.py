"""Conversation management and server-sent chat stream endpoints."""

import json
import logging
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import Conversation, Message, SessionLocal, get_db
from app.schemas import ChatRequest, ConversationOut, MessageOut
from app.services.llm import create_provider
from app.services.rag_pipeline import get_sources, rewrite_query, stream_answer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _message_out(message: Message) -> MessageOut:
    """Convert a stored message and its JSON citations to an API model."""
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        sources=json.loads(message.sources_json),
        created_at=message.created_at,
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)) -> list[ConversationOut]:
    """List conversations from newest to oldest."""
    rows = db.query(Conversation).order_by(Conversation.created_at.desc()).all()
    return [ConversationOut(id=row.id, title=row.title, created_at=row.created_at) for row in rows]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: str, db: Session = Depends(get_db)
) -> list[MessageOut]:
    """Return the chronological messages for one conversation."""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [_message_out(message) for message in conversation.messages]


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a conversation and its messages."""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conversation)
    db.commit()


def _sse(event: str, data: dict) -> str:
    """Encode an SSE event with JSON data."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """Persist a user question and stream citations and a grounded response."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")
    if len(question) > 4000:
        raise HTTPException(status_code=422, detail="Question must be at most 4000 characters")

    conversation = (
        db.get(Conversation, request.conversation_id) if request.conversation_id else None
    )
    if request.conversation_id and conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation is None:
        conversation = Conversation(id=str(uuid.uuid4()), title=question[:80])
        db.add(conversation)
        db.flush()
    history = [(message.role, message.content) for message in conversation.messages[-10:]]
    conversation_id = conversation.id
    user_message = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=question,
        sources_json="[]",
    )
    db.add(user_message)
    db.commit()

    def generate() -> Iterator[str]:
        answer_parts: list[str] = []
        sources: list[dict] = []
        try:
            provider = create_provider()
            standalone_question = rewrite_query(question, history, provider)
            _, ranked, candidates = get_sources(
                standalone_question, document_ids=request.document_ids
            )
            sources = [
                {
                    "id": item["id"],
                    "filename": item["metadata"]["filename"],
                    "page": item["metadata"]["page"],
                    "snippet": item["text"],
                    "vector_score": item.get("vector_score"),
                    "bm25_score": item.get("bm25_score"),
                    "rrf_score": item.get("rrf_score"),
                    "rerank_score": item.get("rerank_score"),
                }
                for item in ranked
            ]
            debug = [
                {
                    "id": item["id"],
                    "filename": item["metadata"]["filename"],
                    "page": item["metadata"]["page"],
                    "snippet": item["text"],
                    "vector_score": item.get("vector_score"),
                    "bm25_score": item.get("bm25_score"),
                    "rrf_score": item.get("rrf_score"),
                    "rerank_score": item.get("rerank_score"),
                }
                for item in candidates
            ]
            yield _sse("sources", {"sources": sources, "debug": debug})
            citation_sources = [
                {
                    **item,
                    "metadata": {
                        "filename": item["filename"],
                        "page": item["page"],
                    },
                }
                for item in sources
            ]
            for token in stream_answer(standalone_question, citation_sources, provider):
                answer_parts.append(token)
                yield _sse("token", {"text": token})
            answer = "".join(answer_parts)
            session = SessionLocal()
            try:
                session.add(
                    Message(
                        id=str(uuid.uuid4()),
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        sources_json=json.dumps(sources, ensure_ascii=False),
                    )
                )
                session.commit()
            finally:
                session.close()
            yield _sse("done", {"conversation_id": conversation_id})
        except Exception:
            logger.exception("Chat stream failed for conversation %s", conversation_id)
            yield _sse("error", {"message": "The answer could not be generated. Please try again."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
