"""
Multi-provider LLM service supporting Ollama, OpenAI, Anthropic, Google, and Groq.
"""
from typing import Optional, Protocol
from abc import ABC, abstractmethod
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
        # Fallback to thinking if content is empty
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


class OpenAIProvider:
    """OpenAI LLM provider."""
    
    def __init__(self, api_key: str, model: str, max_output_tokens: int):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
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
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or self.max_output_tokens
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


class AnthropicProvider:
    """Anthropic (Claude) LLM provider."""
    
    def __init__(self, api_key: str, model: str, max_output_tokens: int):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_output_tokens = max_output_tokens
        logger.info(f"Anthropic provider initialized: {model}")
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using Anthropic Claude."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_output_tokens,
            temperature=temperature,
            system=system or "You are a helpful AI assistant.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    async def check_availability(self) -> bool:
        """Check if Anthropic API is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"Anthropic not available: {e}")
            return False


class GoogleProvider:
    """Google (Gemini) LLM provider."""
    
    def __init__(self, api_key: str, model: str, max_output_tokens: int):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model
        self.max_output_tokens = max_output_tokens
        logger.info(f"Google provider initialized: {model}")
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using Google Gemini."""
        # Combine system and user prompt for Gemini
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens or self.max_output_tokens,
        }
        
        response = await self.model.generate_content_async(
            full_prompt,
            generation_config=generation_config
        )
        
        return response.text
    
    async def check_availability(self) -> bool:
        """Check if Google API is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"Google not available: {e}")
            return False


class GroqProvider:
    """Groq LLM provider (OpenAI-compatible API)."""
    
    def __init__(self, api_key: str, model: str, max_output_tokens: int):
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=api_key)
        self.model = model
        self.max_output_tokens = max_output_tokens
        logger.info(f"Groq provider initialized: {model}")
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using Groq."""
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
        """Check if Groq API is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"Groq not available: {e}")
            return False


def create_llm_provider(
    provider: str,
    **kwargs
) -> LLMProvider:
    """Factory function to create LLM provider based on configuration."""
    if provider == "ollama":
        return OllamaProvider(
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    elif provider == "openai":
        return OpenAIProvider(
            api_key=kwargs.get("api_key"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    elif provider == "anthropic":
        return AnthropicProvider(
            api_key=kwargs.get("api_key"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    elif provider == "google":
        return GoogleProvider(
            api_key=kwargs.get("api_key"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    elif provider == "groq":
        return GroqProvider(
            api_key=kwargs.get("api_key"),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_output_tokens")
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
