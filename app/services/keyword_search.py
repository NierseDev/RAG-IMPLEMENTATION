"""
Keyword search service using PostgreSQL full-text search.
Implements BM25-like ranking with PostgreSQL's ts_rank functions.
"""
from typing import List, Optional, Dict, Any
from app.core.database import get_supabase_client
from app.models.entities import RetrievalResult
import logging

logger = logging.getLogger(__name__)


class KeywordSearchService:
    """
    Keyword search using PostgreSQL full-text search.
    Uses ts_vector and ts_query for efficient text search with ranking.
    """
    
    def __init__(self):
        self.client = get_supabase_client()
        logger.info("KeywordSearchService initialized")
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter_source: Optional[str] = None,
        rank_method: str = 'ts_rank_cd'
    ) -> List[RetrievalResult]:
        """
        Perform keyword search using PostgreSQL full-text search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_source: Optional source filter
            rank_method: Ranking method ('ts_rank' or 'ts_rank_cd')
            
        Returns:
            List of RetrievalResult objects with keyword match scores
        """
        try:
            # Prepare the query - use plainto_tsquery for safety
            # It automatically handles special characters and multiple words
            
            # Build SQL query for full-text search
            # Note: We're using the text_tsv column created in Sprint 1
            sql_query = f"""
            SELECT 
                chunk_id,
                source,
                text,
                ai_provider,
                embedding_model,
                created_at,
                {rank_method}(text_tsv, plainto_tsquery('english', %(query)s)) as rank
            FROM rag_chunks
            WHERE text_tsv @@ plainto_tsquery('english', %(query)s)
            """
            
            # Add source filter if provided
            if filter_source:
                sql_query += " AND source = %(source)s"
            
            # Order by rank and limit
            sql_query += f" ORDER BY rank DESC LIMIT {top_k}"
            
            # Execute query
            params = {'query': query}
            if filter_source:
                params['source'] = filter_source
            
            response = self.client.rpc('execute_sql', {'sql': sql_query, 'params': params}).execute()
            
            # Check if we got results
            if not response.data:
                logger.info(f"No keyword matches found for query: {query}")
                return []
            
            # Convert to RetrievalResult objects
            results = []
            for row in response.data:
                result = RetrievalResult(
                    chunk_id=row['chunk_id'],
                    source=row['source'],
                    text=row['text'],
                    ai_provider=row['ai_provider'],
                    embedding_model=row['embedding_model'],
                    created_at=row['created_at'],
                    similarity=float(row['rank'])  # Use FTS rank as similarity score
                )
                results.append(result)
            
            logger.info(f"Keyword search found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Keyword search error: {e}")
            # Fallback to simple ILIKE search
            return await self._fallback_search(query, top_k, filter_source)
    
    async def _fallback_search(
        self,
        query: str,
        top_k: int,
        filter_source: Optional[str]
    ) -> List[RetrievalResult]:
        """
        Fallback to simple ILIKE search if full-text search fails.
        """
        try:
            logger.info("Using fallback ILIKE search")
            
            # Build query
            query_builder = self.client.table('rag_chunks').select('*')
            
            # Add text search
            query_builder = query_builder.ilike('text', f'%{query}%')
            
            # Add source filter
            if filter_source:
                query_builder = query_builder.eq('source', filter_source)
            
            # Limit results
            query_builder = query_builder.limit(top_k)
            
            # Execute
            response = query_builder.execute()
            
            if not response.data:
                return []
            
            # Convert to RetrievalResult
            results = []
            for row in response.data:
                # Simple relevance score based on query term frequency
                score = self._calculate_simple_score(query, row['text'])
                
                result = RetrievalResult(
                    chunk_id=row['chunk_id'],
                    source=row['source'],
                    text=row['text'],
                    ai_provider=row['ai_provider'],
                    embedding_model=row['embedding_model'],
                    created_at=row['created_at'],
                    similarity=score
                )
                results.append(result)
            
            # Sort by score
            results.sort(key=lambda x: x.similarity, reverse=True)
            
            logger.info(f"Fallback search found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return []
    
    def _calculate_simple_score(self, query: str, text: str) -> float:
        """
        Calculate simple relevance score based on term frequency.
        """
        query_terms = query.lower().split()
        text_lower = text.lower()
        
        # Count term occurrences
        score = 0.0
        for term in query_terms:
            count = text_lower.count(term)
            score += count
        
        # Normalize by text length
        if len(text) > 0:
            score = score / (len(text) / 1000)  # Per 1000 chars
        
        return score
    
    async def search_with_phrases(
        self,
        query: str,
        top_k: int = 10,
        filter_source: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        Search with phrase matching support.
        Uses phraseto_tsquery for exact phrase matches.
        """
        try:
            sql_query = f"""
            SELECT 
                chunk_id,
                source,
                text,
                ai_provider,
                embedding_model,
                created_at,
                ts_rank_cd(text_tsv, phraseto_tsquery('english', %(query)s)) as rank
            FROM rag_chunks
            WHERE text_tsv @@ phraseto_tsquery('english', %(query)s)
            """
            
            if filter_source:
                sql_query += " AND source = %(source)s"
            
            sql_query += f" ORDER BY rank DESC LIMIT {top_k}"
            
            params = {'query': query}
            if filter_source:
                params['source'] = filter_source
            
            response = self.client.rpc('execute_sql', {'sql': sql_query, 'params': params}).execute()
            
            if not response.data:
                # Fall back to regular search
                return await self.search(query, top_k, filter_source)
            
            results = []
            for row in response.data:
                result = RetrievalResult(
                    chunk_id=row['chunk_id'],
                    source=row['source'],
                    text=row['text'],
                    ai_provider=row['ai_provider'],
                    embedding_model=row['embedding_model'],
                    created_at=row['created_at'],
                    similarity=float(row['rank'])
                )
                results.append(result)
            
            logger.info(f"Phrase search found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Phrase search error: {e}, falling back to regular search")
            return await self.search(query, top_k, filter_source)
    
    def prepare_query_terms(self, query: str) -> str:
        """
        Prepare query terms for full-text search.
        Handles boolean operators and phrase queries.
        """
        # Remove special characters that might break the query
        cleaned = query.strip()
        
        # TODO: Add support for:
        # - Boolean operators (AND, OR, NOT)
        # - Phrase queries ("exact phrase")
        # - Wildcards (prefix matching)
        
        return cleaned


# Global instance
keyword_search_service = KeywordSearchService()
