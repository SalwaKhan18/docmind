"""End-to-end retrieval, reranking, and grounded answer generation."""

import re
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


def _normalize_citations(tokens: Iterator[str], source_count: int) -> Iterator[str]:
    """Convert model citation glyphs and ensure a sourced answer cites context."""
    pending = ""
    output: list[str] = []
    for token in tokens:
        pending += token
        while pending:
            opening = pending.find("【")
            if opening < 0:
                safe_length = max(0, len(pending) - 2)
                if safe_length:
                    fragment, pending = pending[:safe_length], pending[safe_length:]
                    output.append(fragment)
                    yield fragment
                break
            if opening:
                fragment, pending = pending[:opening], pending[opening:]
                output.append(fragment)
                yield fragment
            closing = pending.find("】", 1)
            if closing < 0:
                break
            label = pending[1:closing]
            citation = re.fullmatch(r"\s*(\d+)(?:†[^】]*)?\s*", label)
            if citation:
                fragment = f"[{citation.group(1)}]"
            else:
                fragment = pending[: closing + 1]
            output.append(fragment)
            yield fragment
            pending = pending[closing + 1 :]
    if pending:
        output.append(pending)
        yield pending
    answer = "".join(output)
    if source_count and not re.search(r"\[\s*[1-9]\d*\s*\]", answer):
        yield " [1]"


def stream_answer(
    question: str, sources: list[dict], provider: LLMProvider
) -> Iterator[str]:
    """Yield the grounded response, refusing when retrieval returns no context."""
    if not sources:
        yield REFUSAL
        return
    yield from _normalize_citations(
        provider.stream(answer_prompt(question, sources), system=SYSTEM_PROMPT),
        source_count=len(sources),
    )
