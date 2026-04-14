"""
RAG retrieval service for vector search and query processing.
Enhanced with hybrid search (vector + keyword) support (Sprint 3).
Integrated with metadata filtering (Sprint 4).
"""
from typing import List, Optional, Dict, Any
from pathlib import Path
from app.core.database import db
from app.services.embedding import embedding_service
from app.models.entities import RetrievalResult
from app.core.config import settings
from app.core.text_utils import estimate_tokens, safe_truncate_chunks
import logging
import re

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for RAG retrieval operations with hybrid search support."""
    
    def __init__(self):
        """Initialize retrieval service with optional hybrid search."""
        self.keyword_search = None
        self.hybrid_fusion = None
        self.context_optimizer = None
        self.metadata_filter = None
        
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
        
        # Sprint 4: Load metadata filter
        try:
            from app.services.metadata_filter import metadata_filter
            self.metadata_filter = metadata_filter
            logger.info("Metadata filtering enabled")
        except ImportError:
            logger.warning("Metadata filter not available")
    
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        filter_source: Optional[str] = None,
        filter_provider: Optional[str] = None,
        filter_model: Optional[str] = None,
        use_hybrid: Optional[bool] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        filter_logic: str = "AND"
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for a query.
        Sprint 3: Supports hybrid search (vector + keyword).
        Sprint 4: Integrated metadata filtering with optional reranking.
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
                results = await self._hybrid_retrieve(
                    query=query,
                    top_k=top_k,
                    min_similarity=min_similarity,
                    filter_source=filter_source,
                    filter_provider=filter_provider,
                    filter_model=filter_model
                )
            else:
                # Fall back to vector-only search
                results = await self._vector_retrieve(
                    query=query,
                    top_k=top_k,
                    min_similarity=min_similarity,
                    filter_source=filter_source,
                    filter_provider=filter_provider,
                    filter_model=filter_model
                )
            
            # Sprint 4: Apply metadata filtering if provided
            if metadata_filters and self.metadata_filter:
                results = self.metadata_filter.apply_filters(
                    results,
                    metadata_filters,
                    logic=filter_logic
                )
                # Rerank by filter score combined with vector similarity
                results = self.metadata_filter.rerank_by_filters(
                    results,
                    metadata_filters,
                    filter_weight=0.2
                )
                logger.info(f"Applied metadata filters: {len(results)} results after filtering")
            
            return results
            
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
        max_tokens: Optional[int] = None,
        max_results: Optional[int] = None,
        include_page_hint: bool = True,
        include_created_at: bool = False
    ) -> str:
        """
        Format retrieval results into a compact context string.
        Ensures the context fits within token limits.
        """
        if not results:
            return "No relevant information found."
        
        # Use configured max or default
        max_tokens = max_tokens or settings.max_context_tokens
        selected_results = results[:max_results] if max_results is not None else results
        
        # Group by source so citation numbers map to documents, not chunks.
        grouped_results: Dict[str, List[RetrievalResult]] = {}
        source_order: List[str] = []
        for result in selected_results:
            if result.source not in grouped_results:
                grouped_results[result.source] = []
                source_order.append(result.source)
            grouped_results[result.source].append(result)

        # Format each source with a compact, consistent structure.
        context_parts = []
        for idx, source in enumerate(source_order, 1):
            source_results = grouped_results[source]
            lines = [
                f"=== Source {idx} ===",
                f"source: {source}",
                f"chunk_count: {len(source_results)}"
            ]
            for chunk_idx, result in enumerate(source_results, 1):
                page_hint = self._extract_page_hint(result.chunk_id)
                lines.extend([
                    f"chunk: {result.chunk_id}",
                    f"score: {result.similarity:.3f}"
                ])
                if include_created_at and result.created_at:
                    lines.append(f"created: {result.created_at.isoformat()}")
                if include_page_hint and page_hint:
                    lines.append(f"page: {page_hint}")
                lines.append(f"text: {result.text}")
                if chunk_idx < len(source_results):
                    lines.append("---")
            lines.append(f"=== End Source {idx} ===")
            context_parts.append("\n".join(lines))
        
        # Check total token count
        full_context = "\n".join(context_parts)
        total_tokens = estimate_tokens(full_context)
        
        if total_tokens <= max_tokens:
            return f"{full_context}\nEND OF CONTEXT"
        
        # Need to truncate - keep most relevant chunks
        logger.warning(f"Context ({total_tokens} tokens) exceeds limit ({max_tokens}). Truncating.")
        
        # Truncate to fit
        truncated_parts = safe_truncate_chunks(context_parts, max_tokens)
        truncated_context = "\n".join(truncated_parts)
        truncated_context = f"{truncated_context}\n[Context truncated to fit token limit]\nEND OF CONTEXT"
        
        logger.info(f"Truncated context from {len(context_parts)} to {len(truncated_parts)} chunks")
        return truncated_context

    def _extract_page_hint(self, chunk_id: str) -> Optional[str]:
        """Extract a page hint from chunk_id when present."""
        patterns = [
            r'page[_\- ]?(\d+)',
            r'\bp[_\- ]?(\d+)\b',
            r'chunk[_\- ]?\d+[_\- ]?(\d+)$'
        ]
        for pattern in patterns:
            match = re.search(pattern, chunk_id.lower())
            if match:
                return match.group(1)
        return None
    
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

    def build_source_references(
        self,
        results: List[RetrievalResult],
        document_names: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Build structured source references for answer responses."""
        if not results:
            return []

        document_names = document_names or {}
        references: List[Dict[str, Any]] = []
        seen = set()

        for result in sorted(results, key=lambda item: item.similarity, reverse=True):
            if result.source in seen:
                continue

            seen.add(result.source)
            document_name = document_names.get(result.source) or self._derive_document_name(result.source)
            references.append({
                "document_name": document_name,
                "source": result.source,
                "chunk_id": result.chunk_id,
                "similarity": round(result.similarity, 3),
                "page": self._extract_page_hint(result.chunk_id),
                "created_at": result.created_at.isoformat() if result.created_at else None
            })

        return references

    def _derive_document_name(self, source: str) -> str:
        """Fallback source label when no document title is available."""
        name = Path(source).name or source
        stem = Path(name).stem
        return stem if stem else name
    
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
