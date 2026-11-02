"""Focused API behavior tests with isolated SQLite storage."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.routers import chat as chat_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(chat_router, "SessionLocal", session_factory)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_health_endpoint(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_rejects_unsupported_files(client) -> None:
    response = client.post(
        "/api/documents",
        files=[("files", ("payload.exe", b"no", "application/octet-stream"))],
    )
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_chat_stream_persists_answer_and_sources(client, monkeypatch) -> None:
    source = {
        "id": "chunk-1",
        "text": "The project began in 2024.",
        "metadata": {"filename": "history.txt", "page": 1},
        "vector_score": 0.9,
        "bm25_score": 0.8,
        "rrf_score": 0.03,
        "rerank_score": 0.95,
    }
    monkeypatch.setattr(chat_router, "create_provider", lambda: object())
    monkeypatch.setattr(chat_router, "rewrite_query", lambda question, history, provider: question)
    monkeypatch.setattr(
        chat_router,
        "get_sources",
        lambda question, document_ids=None: (question, [source], [source]),
    )
    def fake_stream_answer(question, sources, provider):
        assert sources[0]["text"] == source["text"]
        yield "It began in 2024 [1]."

    monkeypatch.setattr(chat_router, "stream_answer", fake_stream_answer)

    response = client.post("/api/chat", json={"question": "When did it begin?"})

    assert response.status_code == 200
    assert "event: sources" in response.text
    assert "event: token" in response.text
    assert "event: done" in response.text
    assert "history.txt" in response.text
    data = client.get("/api/conversations")
    conversation_id = data.json()[0]["id"]
    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert json.loads(json.dumps(messages[1]["sources"]))[0]["page"] == 1


def test_empty_question_is_rejected(client) -> None:
    response = client.post("/api/chat", json={"question": "  "})
    assert response.status_code == 422
