"""Ollama chat-completion provider."""

from collections.abc import Iterator

import httpx

from app.config import get_settings


class OllamaProvider:
    """LLM provider using Ollama's local HTTP API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.llm_model

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Return one response from the Ollama generate API."""
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        response = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["response"]

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        """Yield generated response fragments from Ollama."""
        payload = {"model": self.model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system
        with httpx.stream(
            "POST", f"{self.base_url}/api/generate", json=payload, timeout=120
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    import json

                    event = json.loads(line)
                    if event.get("response"):
                        yield event["response"]
