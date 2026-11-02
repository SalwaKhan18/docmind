"""Provider interface for chat-completion backends."""

from collections.abc import Iterator
from typing import Protocol


class LLMProvider(Protocol):
    """Minimal interface implemented by supported language-model providers."""

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Return one non-streaming response."""

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        """Yield generated text fragments."""
