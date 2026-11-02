"""Tests for safe answer generation and citation normalization."""

from app.services.rag_pipeline import _normalize_citations, stream_answer


def test_normalize_citations_across_stream_fragments() -> None:
    result = "".join(
        _normalize_citations(iter(["Cost is $14【", "1†L1-L2", "】."]), 1)
    )

    assert result == "Cost is $14[1]."


def test_sourced_answer_gets_citation_if_model_omits_one() -> None:
    result = "".join(_normalize_citations(iter(["Admission is $14."]), 1))

    assert result == "Admission is $14. [1]"


def test_missing_context_returns_exact_refusal_without_provider_call() -> None:
    class Provider:
        def stream(self, prompt, system=None):
            raise AssertionError("Provider should not be called without sources")

    assert list(stream_answer("Question", [], Provider())) == [
        "I couldn't find this in your documents."
    ]
