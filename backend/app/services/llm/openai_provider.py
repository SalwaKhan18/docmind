"""OpenAI chat-completion provider."""

from collections.abc import Iterator

from openai import OpenAI

from app.config import get_settings


class OpenAIProvider:
    """LLM provider backed by the OpenAI API."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Return one response from OpenAI."""
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        result = self.client.chat.completions.create(model=self.model, messages=messages)
        return result.choices[0].message.content or ""

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        """Yield response chunks from OpenAI."""
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        for event in self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        ):
            content = event.choices[0].delta.content
            if content:
                yield content
