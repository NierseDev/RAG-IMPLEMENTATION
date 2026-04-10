"""
Admin and system endpoints.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.models.responses import HealthResponse, StatsResponse
from app.core.database import db
from app.services.embedding import embedding_service
from app.services.llm import llm_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    System health check.
    Checks database connectivity and Ollama availability.
    """
    try:
        # Check database
        db_connected = await db.health_check()
        
        # Check Ollama LLM
        llm_available = await llm_service.check_availability()
        
        # Check Ollama embeddings
        embed_available = await embedding_service.check_availability()
        
        status = "healthy" if (db_connected and llm_available and embed_available) else "degraded"
        
        return HealthResponse(
            status=status,
            timestamp=datetime.utcnow(),
            database_connected=db_connected,
            ollama_available=llm_available and embed_available,
            ollama_models={
                "llm": llm_available,
                "embeddings": embed_available
            }
        )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            database_connected=False,
            ollama_available=False
        )


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get database statistics.
    """
    try:
        stats = await db.get_stats()
        
        return StatsResponse(
            total_chunks=stats.get('total_chunks', 0),
            unique_sources=stats.get('unique_sources', 0),
            unique_models=stats.get('unique_models', 0),
            latest_chunk=stats.get('latest_chunk')
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reset")
async def reset_database():
    """
    Clear all chunks from the database.
    USE WITH CAUTION - This deletes all data!
    """
    try:
        deleted = await db.clear_all()
        
        return {
            "success": True,
            "message": f"Database reset complete",
            "deleted_chunks": deleted
        }
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Status API Endpoints (Phase 2)
# ============================================================================

@router.get("/agent/status")
async def get_agent_status():
    """Get current agent status and configuration."""
    try:
        from app.core.config import settings
        
        # Check agent components
        llm_status = await llm_service.check_availability()
        embed_status = await embedding_service.check_availability()
        
        return {
            "status": "online" if (llm_status and embed_status) else "degraded",
            "llm": {
                "available": llm_status,
                "model": settings.ollama_llm_model,
                "provider": "ollama"
            },
            "embeddings": {
                "available": embed_status,
                "model": settings.ollama_embed_model,
                "provider": "ollama",
                "dimensions": 1024  # mxbai-embed-large
            },
            "configuration": {
                "max_iterations": settings.max_agent_iterations,
                "min_confidence": settings.min_confidence_threshold,
                "chunk_size": settings.max_chunk_tokens,
                "top_k": settings.top_k_results,
                "verification_enabled": settings.enable_verification
            }
        }
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/status")
async def get_database_status():
    """Get database connection and performance stats."""
    try:
        from app.core.database import get_supabase_client
        
        client = get_supabase_client()
        db_connected = await db.health_check()
        
        # Get all documents to count by status
        doc_result = client.table('documents_registry').select('*').execute()
        
        # Count by status
        status_counts = {}
        total_docs = 0
        if doc_result.data:
            total_docs = len(doc_result.data)
            for doc in doc_result.data:
                status = doc.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get chunk stats
        stats = await db.get_stats()
        
        # Get cleanup stats
        from app.services.cleanup import cleanup_service
        cleanup_stats = await cleanup_service.get_cleanup_stats()
        
        return {
            "status": "connected" if db_connected else "disconnected",
            "connection_pool": {
                "healthy": db_connected
            },
            "documents": {
                "total": total_docs,
                "by_status": status_counts
            },
            "chunks": {
                "total": stats.get('total_chunks', 0),
                "unique_sources": stats.get('unique_sources', 0),
                "orphaned": cleanup_stats.get('orphaned_chunks', 0)
            },
            "maintenance": {
                "failed_documents": cleanup_stats.get('failed_documents', 0),
                "stuck_processing": cleanup_stats.get('stuck_documents', 0),
                "orphaned_chunks": cleanup_stats.get('orphaned_chunks', 0)
            }
        }
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def run_cleanup():
    """Run database cleanup tasks."""
    try:
        from app.services.cleanup import cleanup_service
        
        # Run all cleanup tasks
        orphaned_result = await cleanup_service.cleanup_orphaned_chunks()
        failed_result = await cleanup_service.cleanup_failed_documents(max_age_hours=24)
        
        return {
            "success": True,
            "orphaned_chunks": orphaned_result,
            "failed_documents": failed_result
        }
    except Exception as e:
        logger.error(f"Error running cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

