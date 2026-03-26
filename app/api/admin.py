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
