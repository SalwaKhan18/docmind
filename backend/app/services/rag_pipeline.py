"""End-to-end retrieval, reranking, and grounded answer generation."""

from collections.abc import Iterator

from app.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.prompts import REWRITE_PROMPT, SYSTEM_PROMPT, answer_prompt
from app.services.reranker import rerank
from app.services.retriever import retrieve

REFUSAL = "I couldn't find this in your documents."


def rewrite_query(
    question: str, history: list[tuple[str, str]], provider: LLMProvider
) -> str:
    """Resolve follow-up references using recent conversation history."""
    if not history:
        return question
    formatted = "\n".join(f"{role}: {content}" for role, content in history[-6:])
    prompt = REWRITE_PROMPT.format(history=formatted, question=question)
    rewritten = provider.complete(prompt).strip()
    return rewritten or question


def get_sources(
    question: str, document_ids: list[str] | None = None
) -> tuple[str, list[dict], list[dict]]:
    """Retrieve and rerank context, returning rewritten query and debug candidates."""
    candidates = retrieve(question, document_ids=document_ids, limit=20)
    ranked = rerank(question, candidates, limit=len(candidates))
    return question, ranked[: get_settings().top_k], ranked


def stream_answer(
    question: str, sources: list[dict], provider: LLMProvider
) -> Iterator[str]:
    """Yield the grounded response, refusing when retrieval returns no context."""
    if not sources:
        yield REFUSAL
        return
    yield from provider.stream(answer_prompt(question, sources), system=SYSTEM_PROMPT)
