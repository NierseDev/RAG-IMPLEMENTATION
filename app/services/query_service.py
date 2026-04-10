"""
Query Service for hybrid search integration (Sprint 4).
Combines vector and keyword search with RRF fusion and metadata filtering.
"""
import asyncio
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import db
from app.core.config import settings
from app.models.entities import RetrievalResult
from app.services.embedding import embedding_service
from app.services.keyword_search import keyword_search_service
from app.services.rrf_fusion import hybrid_fusion

logger = logging.getLogger(__name__)


class QueryService:
    """Service for executing hybrid search queries with metadata filtering."""
    
    def __init__(self):
        """Initialize query service with configuration."""
        self.vector_weight = settings.hybrid_vector_weight
        self.keyword_weight = settings.hybrid_keyword_weight
        self.hybrid_enabled = settings.use_hybrid_search
        self.vector_top_k = 20
        self.keyword_top_k = 20
        self.final_top_k = 10
        
        logger.info(
            f"QueryService initialized: hybrid={self.hybrid_enabled}, "
            f"vector_weight={self.vector_weight}, keyword_weight={self.keyword_weight}"
        )
    
    async def search(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        use_hybrid: Optional[bool] = None,
        min_similarity: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute hybrid search query with metadata filtering.
        
        Args:
            query: User question
            metadata_filters: Optional filters (source, provider, model)
            top_k: Number of final results (default: 10)
            use_hybrid: Override hybrid search enabled (default: config)
            min_similarity: Minimum similarity threshold
            
        Returns:
            Dictionary with results and search breakdown
        """
        start_time = time.time()
        
        try:
            # Configuration
            top_k = top_k or self.final_top_k
            use_hybrid = use_hybrid if use_hybrid is not None else self.hybrid_enabled
            min_similarity = min_similarity or settings.min_similarity
            
            # Initialize tracking
            search_breakdown = {
                'vector_results': 0,
                'keyword_results': 0,
                'vector_score': 0.0,
                'keyword_score': 0.0,
                'fused_results': 0,
                'after_filter': 0,
                'method': 'vector-only'
            }
            retrieval_method = 'vector-only'
            filters_applied = bool(metadata_filters)
            
            # Execute search
            if use_hybrid and self.hybrid_enabled:
                results, breakdown, method = await self._hybrid_search(
                    query=query,
                    metadata_filters=metadata_filters,
                    min_similarity=min_similarity,
                    top_k=top_k
                )
                search_breakdown.update(breakdown)
                retrieval_method = method
            else:
                results, breakdown = await self._vector_search(
                    query=query,
                    metadata_filters=metadata_filters,
                    min_similarity=min_similarity,
                    top_k=top_k
                )
                search_breakdown.update(breakdown)
            
            # Final reranking by score
            results = sorted(results, key=lambda x: x.similarity, reverse=True)[:top_k]
            
            processing_time = time.time() - start_time
            
            # Log performance metrics
            logger.info(
                f"Query processed in {processing_time:.2f}s | "
                f"Method: {retrieval_method} | "
                f"Results: {len(results)}/{top_k} | "
                f"Filters: {filters_applied}"
            )
            
            return {
                'results': results,
                'search_breakdown': search_breakdown,
                'retrieval_method': retrieval_method,
                'filter_applied': filters_applied,
                'processing_time': processing_time,
                'query': query,
                'metadata_filters': metadata_filters
            }
        
        except Exception as e:
            logger.error(f"Query service error: {e}", exc_info=True)
            return {
                'results': [],
                'search_breakdown': {},
                'retrieval_method': 'error',
                'filter_applied': False,
                'processing_time': time.time() - start_time,
                'query': query,
                'error': str(e)
            }
    
    async def _hybrid_search(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        min_similarity: float,
        top_k: int
    ) -> tuple[List[RetrievalResult], Dict[str, Any], str]:
        """
        Execute hybrid search: vector + keyword with RRF fusion.
        
        Returns:
            Tuple of (results, breakdown, retrieval_method)
        """
        logger.info(f"Starting hybrid search for: {query}")
        
        # Step 1 & 2: Execute vector and keyword search in parallel
        vector_task = self._vector_search_internal(
            query=query,
            metadata_filters=metadata_filters,
            min_similarity=min_similarity,
            top_k=self.vector_top_k
        )
        
        keyword_task = self._keyword_search_internal(
            query=query,
            metadata_filters=metadata_filters,
            top_k=self.keyword_top_k
        )
        
        # Execute both searches concurrently
        try:
            vector_results, vector_score = await vector_task
            keyword_results = await keyword_task
        except Exception as e:
            logger.warning(f"Keyword search failed during hybrid search, falling back to vector-only: {e}")
            results, breakdown = await self._vector_search(
                query=query,
                metadata_filters=metadata_filters,
                min_similarity=min_similarity,
                top_k=top_k
            )
            breakdown['method'] = 'vector-only (keyword fallback)'
            return results, breakdown, 'vector-only'
        
        # Step 3: RRF Fusion
        vector_dicts = [self._result_to_dict(r) for r in vector_results]
        keyword_dicts = [self._result_to_dict(r) for r in keyword_results]
        
        fused_dicts = hybrid_fusion.combine(
            vector_results=vector_dicts,
            keyword_results=keyword_dicts,
            use_weights=True
        )
        
        # Step 4: Convert back to RetrievalResult objects
        fused_results = []
        for item in fused_dicts:
            result = RetrievalResult(
                chunk_id=item['chunk_id'],
                source=item['source'],
                text=item['text'],
                ai_provider=item.get('ai_provider'),
                embedding_model=item.get('embedding_model'),
                created_at=item.get('created_at'),
                similarity=item.get('weighted_rrf_score', item.get('rrf_score', 0.0))
            )
            fused_results.append(result)
        
        # Build breakdown
        breakdown = {
            'vector_results': len(vector_results),
            'keyword_results': len(keyword_results),
            'fused_results': len(fused_results),
            'after_filter': len(fused_results),
            'method': 'hybrid'
        }
        
        logger.info(
            f"Hybrid search complete: {len(vector_results)} vector + "
            f"{len(keyword_results)} keyword -> {len(fused_results)} fused"
        )
        
        return fused_results[:top_k], breakdown, 'hybrid'
    
    async def _vector_search(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        min_similarity: float,
        top_k: int
    ) -> tuple[List[RetrievalResult], Dict[str, Any]]:
        """
        Execute vector-only search with metadata filtering.
        
        Returns:
            Tuple of (results, breakdown)
        """
        logger.info(f"Starting vector search for: {query}")
        
        results, _ = await self._vector_search_internal(
            query=query,
            metadata_filters=metadata_filters,
            min_similarity=min_similarity,
            top_k=top_k
        )
        
        breakdown = {
            'vector_results': len(results),
            'after_filter': len(results),
            'method': 'vector-only'
        }
        
        logger.info(f"Vector search returned {len(results)} results")
        return results, breakdown
    
    async def _vector_search_internal(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        min_similarity: float,
        top_k: int
    ) -> tuple[List[RetrievalResult], float]:
        """
        Internal vector search implementation.
        
        Returns:
            Tuple of (results, avg_score)
        """
        query_embedding = await embedding_service.embed_text(query)
        
        # Extract metadata filters
        filter_source = metadata_filters.get('source') if metadata_filters else None
        filter_provider = metadata_filters.get('provider') if metadata_filters else None
        filter_model = metadata_filters.get('model') if metadata_filters else None
        
        results = await db.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            filter_source=filter_source,
            filter_provider=filter_provider,
            filter_model=filter_model
        )
        
        avg_score = sum(r.similarity for r in results) / len(results) if results else 0.0
        logger.debug(f"Vector search: {len(results)} results, avg_score={avg_score:.3f}")
        
        return results, avg_score
    
    async def _keyword_search_internal(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Internal keyword search implementation.
        
        Returns:
            List of results
        """
        filter_source = metadata_filters.get('source') if metadata_filters else None
        
        results = await keyword_search_service.search(
            query=query,
            top_k=top_k,
            filter_source=filter_source
        )
        
        logger.debug(f"Keyword search: {len(results)} results")
        return results
    
    def _result_to_dict(self, result: RetrievalResult) -> dict:
        """Convert RetrievalResult to dictionary for RRF fusion."""
        return {
            'chunk_id': result.chunk_id,
            'source': result.source,
            'text': result.text,
            'ai_provider': result.ai_provider,
            'embedding_model': result.embedding_model,
            'created_at': result.created_at,
            'similarity': result.similarity
        }
    
    def format_results(
        self,
        search_response: Dict[str, Any],
        include_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Format search response for API response.
        
        Args:
            search_response: Response from search()
            include_breakdown: Whether to include search_breakdown
            
        Returns:
            Formatted response dictionary
        """
        results = search_response.get('results', [])
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                'chunk_id': result.chunk_id,
                'source': result.source,
                'text': result.text[:500] + "..." if len(result.text) > 500 else result.text,
                'similarity': round(result.similarity, 3),
                'provider': result.ai_provider,
                'model': result.embedding_model
            })
        
        response = {
            'query': search_response.get('query'),
            'results': formatted_results,
            'retrieved_chunks': len(results),
            'retrieval_method': search_response.get('retrieval_method'),
            'filter_applied': search_response.get('filter_applied', False),
            'processing_time_ms': round(search_response.get('processing_time', 0) * 1000, 1)
        }
        
        if include_breakdown:
            response['search_breakdown'] = search_response.get('search_breakdown', {})
        
        return response


# Global instance
query_service = QueryService()
