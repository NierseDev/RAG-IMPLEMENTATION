"""
LLM provider adapters for Ollama (local) and OpenRouter (cloud).
"""
from typing import Optional, Protocol
import logging

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response from the LLM."""
        ...

    async def check_availability(self) -> bool:
        """Check if the provider is available."""
        ...


class OllamaProvider:
    """Ollama (local) LLM provider."""

    def __init__(self, base_url: str, model: str, max_output_tokens: int):
        import ollama
        self.client = ollama.Client(host=base_url)
        self.model = model
        self.max_output_tokens = max_output_tokens
        logger.info(f"Ollama provider initialized: {model}")

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using Ollama."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens or self.max_output_tokens,
                "enable_thinking": False
            }
        )

        content = response['message']['content']
        if not content and response['message'].get('thinking'):
            content = response['message']['thinking']
        return content

    async def check_availability(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"Ollama not available: {e}")
            return False


class OpenRouterProvider:
    """OpenRouter cloud LLM provider via OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str, max_output_tokens: int):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_output_tokens = max_output_tokens
        logger.info(f"OpenRouter provider initialized: {model}")

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using OpenRouter."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or self.max_output_tokens
        )
        return response.choices[0].message.content or ""

    async def check_availability(self) -> bool:
        """Check if OpenRouter API is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"OpenRouter not available: {e}")
            return False


def create_llm_provider(provider: str, **kwargs) -> LLMProvider:
    """Factory function to create LLM provider based on configuration."""
    if provider == "ollama":
        return OllamaProvider(
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    if provider == "openrouter":
        return OpenRouterProvider(
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")
