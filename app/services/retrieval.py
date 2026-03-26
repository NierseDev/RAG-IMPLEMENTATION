"""
RAG retrieval service for vector search and query processing.
"""
from typing import List, Optional
from app.core.database import db
from app.services.embedding import embedding_service
from app.models.entities import RetrievalResult
from app.core.config import settings
from app.core.text_utils import estimate_tokens, safe_truncate_chunks
import logging

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for RAG retrieval operations."""
    
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        filter_source: Optional[str] = None,
        filter_provider: Optional[str] = None,
        filter_model: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for a query.
        """
        try:
            # Generate query embedding
            query_embedding = await embedding_service.embed_text(query)
            
            # Use defaults from config if not provided
            top_k = top_k or settings.top_k_results
            min_similarity = min_similarity or settings.min_similarity
            
            # Search for similar chunks
            results = await db.search_similar(
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=min_similarity,
                filter_source=filter_source,
                filter_provider=filter_provider,
                filter_model=filter_model
            )
            
            logger.info(f"Retrieved {len(results)} chunks for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Error in retrieval: {e}")
            return []
    
    def format_context(
        self, 
        results: List[RetrievalResult], 
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Format retrieval results into context string.
        Ensures the context fits within token limits.
        """
        if not results:
            return "No relevant information found."
        
        # Use configured max or default
        max_tokens = max_tokens or settings.max_context_tokens
        
        # Format each result
        context_parts = []
        for idx, result in enumerate(results, 1):
            part = f"[Source {idx}: {result.source} (similarity: {result.similarity:.3f})]\n{result.text}\n"
            context_parts.append(part)
        
        # Check total token count
        full_context = "\n".join(context_parts)
        total_tokens = estimate_tokens(full_context)
        
        if total_tokens <= max_tokens:
            return full_context
        
        # Need to truncate - keep most relevant chunks
        logger.warning(f"Context ({total_tokens} tokens) exceeds limit ({max_tokens}). Truncating.")
        
        # Truncate to fit
        truncated_parts = safe_truncate_chunks(context_parts, max_tokens)
        truncated_context = "\n".join(truncated_parts)
        
        logger.info(f"Truncated context from {len(context_parts)} to {len(truncated_parts)} chunks")
        return truncated_context
    
    def extract_sources(self, results: List[RetrievalResult]) -> List[str]:
        """Extract unique sources from results."""
        sources = []
        seen = set()
        for result in results:
            source_info = f"{result.source} (similarity: {result.similarity:.3f})"
            if result.source not in seen:
                sources.append(source_info)
                seen.add(result.source)
        return sources
    
    async def refine_query(self, original_query: str, feedback: str) -> str:
        """
        Refine a query based on feedback.
        Strategies: expand, focus, or rephrase.
        """
        # For now, use simple query expansion
        # In production, you might use the LLM to refine the query
        
        if "no results" in feedback.lower():
            # Expand query with synonyms or related terms
            return f"{original_query} OR related concepts"
        elif "too broad" in feedback.lower():
            # Focus the query
            return f"{original_query} specific details"
        else:
            # Rephrase
            return original_query


# Global retrieval service instance
retrieval_service = RetrievalService()
