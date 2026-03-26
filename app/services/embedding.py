"""
Embedding service using Ollama.
"""
from typing import List
import ollama
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using Ollama."""
    
    def __init__(self):
        self.client = ollama.Client(host=settings.ollama_base_url)
        self.model = settings.ollama_embed_model
        self.max_tokens = settings.embedding_context_window
        logger.info(f"Embedding service initialized with model: {self.model} (max tokens: {self.max_tokens})")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            # Check and truncate if needed
            tokens = estimate_tokens(text)
            if tokens > self.max_tokens:
                logger.warning(f"Text ({tokens} tokens) exceeds embedding limit ({self.max_tokens}). Truncating.")
                text = truncate_to_token_limit(text, self.max_tokens, reserve_tokens=10)
            
            response = self.client.embeddings(
                model=self.model,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Check if it's a context length error
            if "context" in str(e).lower() or "length" in str(e).lower() or "token" in str(e).lower():
                logger.error("Context length error detected. Text may be too long for embedding model.")
                # Try with more aggressive truncation
                try:
                    truncated = truncate_to_token_limit(text, self.max_tokens // 2)
                    logger.info("Retrying with more aggressive truncation")
                    response = self.client.embeddings(
                        model=self.model,
                        prompt=truncated
                    )
                    return response['embedding']
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
        """Check if embedding model is available."""
        try:
            test_embedding = await self.embed_text("test")
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Embedding model not available: {e}")
            return False


# Global embedding service instance
embedding_service = EmbeddingService()
