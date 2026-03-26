"""
Database client for Supabase with vector operations.
"""
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from app.core.config import settings
from app.models.entities import RAGChunk, RetrievalResult
import logging

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client for vector operations."""
    
    _instance: Optional['SupabaseClient'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
            logger.info("Supabase client initialized")
    
    @property
    def client(self) -> Client:
        """Get the Supabase client."""
        if self._client is None:
            raise RuntimeError("Supabase client not initialized")
        return self._client
    
    async def insert_chunk(self, chunk: RAGChunk) -> bool:
        """Insert a single chunk into the database."""
        try:
            data = {
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "text": chunk.text,
                "ai_provider": chunk.ai_provider,
                "embedding_model": chunk.embedding_model,
                "embedding": chunk.embedding
            }
            
            result = self.client.table("rag_chunks").insert(data).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error inserting chunk: {e}")
            return False
    
    async def insert_chunks_batch(self, chunks: List[RAGChunk]) -> int:
        """Insert multiple chunks in batch."""
        try:
            data = [
                {
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "text": chunk.text,
                    "ai_provider": chunk.ai_provider,
                    "embedding_model": chunk.embedding_model,
                    "embedding": chunk.embedding
                }
                for chunk in chunks
            ]
            
            result = self.client.table("rag_chunks").insert(data).execute()
            inserted = len(result.data)
            logger.info(f"Inserted {inserted} chunks in batch")
            return inserted
        except Exception as e:
            logger.error(f"Error in batch insert: {e}")
            return 0
    
    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 6,
        min_similarity: float = 0.0,
        filter_source: Optional[str] = None,
        filter_provider: Optional[str] = None,
        filter_model: Optional[str] = None
    ) -> List[RetrievalResult]:
        """Search for similar chunks using vector similarity."""
        try:
            result = self.client.rpc(
                "match_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": top_k,
                    "min_similarity": min_similarity,
                    "filter_source": filter_source,
                    "filter_provider": filter_provider,
                    "filter_model": filter_model
                }
            ).execute()
            
            return [RetrievalResult(**item) for item in result.data]
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            result = self.client.rpc("get_chunk_stats").execute()
            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    async def delete_by_source(self, source: str) -> int:
        """Delete all chunks from a specific source."""
        try:
            result = self.client.table("rag_chunks").delete().eq("source", source).execute()
            deleted = len(result.data) if result.data else 0
            logger.info(f"Deleted {deleted} chunks from source: {source}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting chunks: {e}")
            return 0
    
    async def list_sources(self) -> List[str]:
        """List all unique sources in the database."""
        try:
            result = self.client.table("rag_chunks").select("source").execute()
            sources = list(set(item["source"] for item in result.data))
            return sorted(sources)
        except Exception as e:
            logger.error(f"Error listing sources: {e}")
            return []
    
    async def source_exists(self, source: str) -> bool:
        """Check if a source already exists in the database."""
        try:
            result = self.client.table("rag_chunks").select("id").eq("source", source).limit(1).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking source existence: {e}")
            return False
    
    async def get_source_chunk_count(self, source: str) -> int:
        """Get the number of chunks for a specific source."""
        try:
            result = self.client.table("rag_chunks").select("id", count="exact").eq("source", source).execute()
            return result.count if result.count else 0
        except Exception as e:
            logger.error(f"Error getting chunk count: {e}")
            return 0
    
    async def clear_all(self) -> int:
        """Clear all chunks (use with caution!)."""
        try:
            result = self.client.table("rag_chunks").delete().neq("id", 0).execute()
            deleted = len(result.data) if result.data else 0
            logger.warning(f"Cleared all chunks: {deleted} deleted")
            return deleted
        except Exception as e:
            logger.error(f"Error clearing chunks: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            self.client.table("rag_chunks").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database client instance
db = SupabaseClient()
