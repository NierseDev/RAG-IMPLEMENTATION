"""
Multi-provider embedding service supporting Ollama and OpenAI.
"""
from typing import List
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
import logging

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider:
    """Ollama embedding provider."""
    
    def __init__(self, base_url: str, model: str, max_tokens: int):
        import ollama
        self.client = ollama.Client(host=base_url)
        self.model = model
        self.max_tokens = max_tokens
        logger.info(f"Ollama embedding provider initialized: {model}")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Check and truncate if needed
        tokens = estimate_tokens(text)
        if tokens > self.max_tokens:
            logger.warning(f"Text ({tokens} tokens) exceeds limit ({self.max_tokens}). Truncating.")
            text = truncate_to_token_limit(text, self.max_tokens, reserve_tokens=10)
        
        response = self.client.embeddings(
            model=self.model,
            prompt=text
        )
        return response['embedding']


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider."""
    
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info(f"OpenAI embedding provider initialized: {model}")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding


class EmbeddingService:
    """Service for generating embeddings with multi-provider support."""
    
    def __init__(self):
        self.max_tokens = settings.embedding_context_window
        
        # Initialize provider based on configuration
        self._init_provider()
        
        logger.info(f"Embedding service initialized")
        logger.info(f"  Provider: {settings.embedding_provider}")
        logger.info(f"  Model: {settings.current_embedding_model}")
        logger.info(f"  Dimensions: {settings.embedding_dimensions}")
        logger.info(f"  Max tokens: {self.max_tokens}")
    
    def _init_provider(self):
        """Initialize the embedding provider based on configuration."""
        provider = settings.embedding_provider
        
        if provider == "ollama":
            self.provider = OllamaEmbeddingProvider(
                base_url=settings.ollama_base_url,
                model=settings.ollama_embed_model,
                max_tokens=self.max_tokens
            )
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
            self.provider = OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_embedding_model
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            return await self.provider.embed_text(text)
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Check if it's a context length error
            if "context" in str(e).lower() or "length" in str(e).lower() or "token" in str(e).lower():
                logger.error("Context length error detected. Retrying with more aggressive truncation.")
                try:
                    truncated = truncate_to_token_limit(text, self.max_tokens // 2)
                    return await self.provider.embed_text(truncated)
                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}")
                    raise
            raise
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = await self.embed_text(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error in batch embedding (chunk {i+1}/{len(texts)}): {e}")
                embeddings.append([])
        
        successful = sum(1 for e in embeddings if e)
        logger.info(f"Generated {successful}/{len(texts)} embeddings successfully")
        return embeddings
    
    async def check_availability(self) -> bool:
        """Check if embedding provider is available."""
        try:
            test_embedding = await self.embed_text("test")
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Embedding provider not available: {e}")
            return False


# Global embedding service instance
embedding_service = EmbeddingService()
