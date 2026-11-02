"""Groq chat-completion provider."""

from collections.abc import Iterator

from groq import Groq

from app.config import get_settings


class GroqProvider:
    """LLM provider backed by Groq's OpenAI-compatible chat API."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.llm_model

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Return a single response from Groq."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        result = self.client.chat.completions.create(model=self.model, messages=messages)
        return result.choices[0].message.content or ""

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        """Yield response chunks from Groq."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        stream = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )
        for event in stream:
            content = event.choices[0].delta.content
            if content:
                yield content
