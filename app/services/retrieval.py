"""
RAG retrieval service for vector search and query processing.
Enhanced with hybrid search (vector + keyword) support (Sprint 3).
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
    """Service for RAG retrieval operations with hybrid search support."""
    
    def __init__(self):
        """Initialize retrieval service with optional hybrid search."""
        self.keyword_search = None
        self.hybrid_fusion = None
        self.context_optimizer = None
        
        # Sprint 3: Load hybrid search components if enabled
        if settings.use_hybrid_search:
            try:
                from app.services.keyword_search import keyword_search_service
                from app.services.rrf_fusion import hybrid_fusion
                self.keyword_search = keyword_search_service
                self.hybrid_fusion = hybrid_fusion
                logger.info("Hybrid search enabled (vector + keyword with RRF)")
            except ImportError as e:
                logger.warning(f"Hybrid search components not available: {e}")
        
        # Sprint 3: Load context optimizer
        try:
            from app.services.context_optimizer import context_optimizer
            self.context_optimizer = context_optimizer
            logger.info("Context optimizer enabled")
        except ImportError:
            logger.warning("Context optimizer not available")
    
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        filter_source: Optional[str] = None,
        filter_provider: Optional[str] = None,
        filter_model: Optional[str] = None,
        use_hybrid: Optional[bool] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for a query.
        Sprint 3: Supports hybrid search (vector + keyword).
        """
        try:
            # Sprint 3: Optimize top_k using context optimizer if available
            if top_k is None:
                if self.context_optimizer:
                    top_k = self.context_optimizer.calculate_optimal_top_k(query)
                    logger.info(f"Context optimizer suggested top_k={top_k}")
                else:
                    top_k = settings.top_k_results
            
            # Use defaults from config if not provided
            min_similarity = min_similarity or settings.min_similarity
            use_hybrid = use_hybrid if use_hybrid is not None else settings.use_hybrid_search
            
            # Sprint 3: Use hybrid search if enabled and available
            if use_hybrid and self.keyword_search and self.hybrid_fusion:
                return await self._hybrid_retrieve(
                    query=query,
                    top_k=top_k,
                    min_similarity=min_similarity,
                    filter_source=filter_source,
                    filter_provider=filter_provider,
                    filter_model=filter_model
                )
            else:
                # Fall back to vector-only search
                return await self._vector_retrieve(
                    query=query,
                    top_k=top_k,
                    min_similarity=min_similarity,
                    filter_source=filter_source,
                    filter_provider=filter_provider,
                    filter_model=filter_model
                )
            
        except Exception as e:
            logger.error(f"Error in retrieval: {e}")
            return []
    
    async def _vector_retrieve(
        self,
        query: str,
        top_k: int,
        min_similarity: float,
        filter_source: Optional[str],
        filter_provider: Optional[str],
        filter_model: Optional[str]
    ) -> List[RetrievalResult]:
        """Vector-only retrieval (original method)."""
        # Generate query embedding
        query_embedding = await embedding_service.embed_text(query)
        
        # Search for similar chunks
        results = await db.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            filter_source=filter_source,
            filter_provider=filter_provider,
            filter_model=filter_model
        )
        
        logger.info(f"Vector search retrieved {len(results)} chunks")
        return results
    
    async def _hybrid_retrieve(
        self,
        query: str,
        top_k: int,
        min_similarity: float,
        filter_source: Optional[str],
        filter_provider: Optional[str],
        filter_model: Optional[str]
    ) -> List[RetrievalResult]:
        """
        Hybrid retrieval combining vector and keyword search.
        Sprint 3: Uses RRF to combine results.
        """
        # Perform vector search
        vector_results = await self._vector_retrieve(
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
            filter_source=filter_source,
            filter_provider=filter_provider,
            filter_model=filter_model
        )
        
        # Perform keyword search
        keyword_results = await self.keyword_search.search(
            query=query,
            top_k=top_k,
            filter_source=filter_source
        )
        
        logger.info(f"Hybrid search: {len(vector_results)} vector + {len(keyword_results)} keyword results")
        
        # Convert to dictionaries for fusion
        vector_dicts = [self._result_to_dict(r) for r in vector_results]
        keyword_dicts = [self._result_to_dict(r) for r in keyword_results]
        
        # Combine using RRF
        fused_results = self.hybrid_fusion.combine(
            vector_results=vector_dicts,
            keyword_results=keyword_dicts,
            use_weights=True
        )
        
        # Convert back to RetrievalResult objects
        final_results = []
        for item in fused_results[:top_k]:
            result = RetrievalResult(
                chunk_id=item['chunk_id'],
                source=item['source'],
                text=item['text'],
                ai_provider=item['ai_provider'],
                embedding_model=item['embedding_model'],
                created_at=item['created_at'],
                similarity=item.get('weighted_rrf_score', item.get('rrf_score', 0.0))
            )
            final_results.append(result)
        
        logger.info(f"Hybrid fusion produced {len(final_results)} results")
        return final_results
    
    def _result_to_dict(self, result: RetrievalResult) -> dict:
        """Convert RetrievalResult to dictionary for fusion."""
        return {
            'chunk_id': result.chunk_id,
            'source': result.source,
            'text': result.text,
            'ai_provider': result.ai_provider,
            'embedding_model': result.embedding_model,
            'created_at': result.created_at,
            'similarity': result.similarity
        }
    
    def format_context(
        self, 
        results: List[RetrievalResult], 
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Format retrieval results into context string with APA-style source information.
        Ensures the context fits within token limits.
        """
        if not results:
            return "No relevant information found."
        
        # Use configured max or default
        max_tokens = max_tokens or settings.max_context_tokens
        
        # Format each result with APA-friendly citations
        context_parts = []
        for idx, result in enumerate(results, 1):
            # Extract potential author/year from source filename
            source_name = result.source.replace('.pdf', '').replace('_', ' ')
            
            # Format: [Source #: Filename] Content
            # The LLM will use this to create proper APA citations
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
