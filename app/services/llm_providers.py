"""
LLM provider adapters for Ollama (local), OpenRouter (cloud), and OpenAI.
"""
from typing import Optional, Protocol, Any, Dict
import logging
import time
import asyncio

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
        self.rate_limit_state: Dict[str, Any] = {}
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

        try:
            # Capture raw headers when available for rate-limit-aware orchestration.
            raw_api = getattr(self.client.chat.completions, "with_raw_response", None)
            if raw_api:
                raw_response = await raw_api.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or self.max_output_tokens
                )
                self._capture_rate_limit_headers(raw_response.headers)
                parsed = raw_response.parse()
            else:
                parsed = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or self.max_output_tokens
                )

            return parsed.choices[0].message.content or ""
        except Exception as e:
            response = getattr(e, "response", None)
            headers = getattr(response, "headers", None)
            if headers:
                self._capture_rate_limit_headers(headers)
            raise

    async def check_availability(self) -> bool:
        """Check if OpenRouter API is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"OpenRouter not available: {e}")
            return False

    def get_rate_limit_state(self) -> Dict[str, Any]:
        """Return most recent OpenRouter rate-limit header snapshot."""
        return dict(self.rate_limit_state)

    def _capture_rate_limit_headers(self, headers: Any) -> None:
        """Extract OpenRouter rate-limit headers when present."""
        if not headers:
            return

        def _header(name: str) -> Optional[str]:
            if hasattr(headers, "get"):
                value = headers.get(name)
                if value is None:
                    value = headers.get(name.lower())
                return value
            return None

        limit = _header("x-ratelimit-limit")
        remaining = _header("x-ratelimit-remaining")
        reset = _header("x-ratelimit-reset")
        reset_after = _header("x-ratelimit-reset-after")

        if not any([limit, remaining, reset, reset_after]):
            return

        snapshot: Dict[str, Any] = {
            "limit": self._to_number(limit),
            "remaining": self._to_number(remaining),
            "reset": self._to_number(reset),
            "reset_after": self._to_number(reset_after),
            "captured_at": time.time()
        }
        self.rate_limit_state = snapshot

    @staticmethod
    def _to_number(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class OpenAIProvider:
    """OpenAI cloud LLM provider via OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str, max_output_tokens: int):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_output_tokens = max_output_tokens
        logger.info(f"OpenAI provider initialized: {model}")

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using OpenAI."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        completion_tokens = max_tokens or self.max_output_tokens
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=completion_tokens
        )
        return response.choices[0].message.content or ""

    async def check_availability(self) -> bool:
        """Check if OpenAI API is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"OpenAI not available: {e}")
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
    if provider == "openai":
        return OpenAIProvider(
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")
