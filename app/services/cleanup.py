"""
Cleanup service for orphaned chunks and document management.
"""
from typing import List, Dict, Any
import logging
from app.core.database import get_supabase_client

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for cleaning up orphaned chunks and managing document lifecycle."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def cleanup_orphaned_chunks(self) -> Dict[str, Any]:
        """
        Remove chunks that reference deleted documents.
        
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info("Starting orphaned chunks cleanup...")
        
        try:
            # Find chunks with document_id that no longer exists in documents_registry
            result = self.client.rpc(
                'cleanup_orphaned_chunks'
            ).execute()
            
            deleted_count = result.data if result.data else 0
            
            logger.info(f"Cleaned up {deleted_count} orphaned chunks")
            
            return {
                "success": True,
                "deleted_chunks": deleted_count,
                "message": f"Removed {deleted_count} orphaned chunks"
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned chunks: {e}")
            return {
                "success": False,
                "deleted_chunks": 0,
                "error": str(e)
            }
    
    async def cleanup_failed_documents(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Remove documents that have been in 'failed' status for too long.
        
        Args:
            max_age_hours: Maximum age in hours for failed documents
            
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info(f"Cleaning up failed documents older than {max_age_hours} hours...")
        
        try:
            # Delete failed documents older than specified hours
            # This will CASCADE delete associated chunks
            result = self.client.rpc(
                'cleanup_failed_documents',
                {'hours': max_age_hours}
            ).execute()
            
            deleted_count = result.data if result.data else 0
            
            logger.info(f"Cleaned up {deleted_count} failed documents")
            
            return {
                "success": True,
                "deleted_documents": deleted_count,
                "message": f"Removed {deleted_count} failed documents"
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup failed documents: {e}")
            return {
                "success": False,
                "deleted_documents": 0,
                "error": str(e)
            }
    
    async def delete_document_and_chunks(self, document_id: int) -> Dict[str, Any]:
        """
        Delete a document and all its associated chunks.
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            Dictionary with deletion results
        """
        logger.info(f"Deleting document {document_id} and its chunks...")
        
        try:
            # Get chunk count before deletion
            chunks_result = self.client.table('rag_chunks') \
                .select('id', count='exact') \
                .eq('document_id', document_id) \
                .execute()
            
            chunk_count = chunks_result.count if chunks_result.count else 0
            
            # Delete document (CASCADE will delete chunks automatically)
            doc_result = self.client.table('documents_registry') \
                .delete() \
                .eq('id', document_id) \
                .execute()
            
            if doc_result.data:
                logger.info(f"Deleted document {document_id} and {chunk_count} chunks")
                return {
                    "success": True,
                    "document_id": document_id,
                    "deleted_chunks": chunk_count,
                    "message": f"Deleted document and {chunk_count} associated chunks"
                }
            else:
                logger.warning(f"Document {document_id} not found")
                return {
                    "success": False,
                    "error": "Document not found"
                }
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_cleanup_stats(self) -> Dict[str, Any]:
        """
        Get statistics about documents and chunks that could be cleaned up.
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Count orphaned chunks
            orphaned_result = self.client.table('rag_chunks') \
                .select('id', count='exact') \
                .is_('document_id', 'null') \
                .execute()
            
            # Count failed documents
            failed_result = self.client.table('documents_registry') \
                .select('id', count='exact') \
                .eq('status', 'failed') \
                .execute()
            
            # Count processing documents (stuck for > 1 hour)
            from datetime import datetime, timedelta
            cutoff_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            stuck_result = self.client.table('documents_registry') \
                .select('id', count='exact') \
                .eq('status', 'processing') \
                .lt('created_at', cutoff_time) \
                .execute()
            
            return {
                "orphaned_chunks": orphaned_result.count if orphaned_result.count else 0,
                "failed_documents": failed_result.count if failed_result.count else 0,
                "stuck_documents": stuck_result.count if stuck_result.count else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get cleanup stats: {e}")
            return {
                "orphaned_chunks": 0,
                "failed_documents": 0,
                "stuck_documents": 0,
                "error": str(e)
            }


# Global instance
cleanup_service = CleanupService()
