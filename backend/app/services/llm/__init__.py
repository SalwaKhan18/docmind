"""Provider selection for the supported LLM backends."""

from app.config import get_settings
from app.services.llm.base import LLMProvider


def create_provider() -> LLMProvider:
    """Instantiate the provider selected by LLM_PROVIDER."""
    provider = get_settings().llm_provider.lower()
    if provider == "groq":
        from app.services.llm.groq_provider import GroqProvider

        return GroqProvider()
    if provider == "openai":
        from app.services.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if provider == "ollama":
        from app.services.llm.ollama_provider import OllamaProvider

        return OllamaProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")