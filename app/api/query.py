"""
Query endpoints for agentic RAG.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
import time
from app.models.requests import QueryRequest, SimpleQueryRequest
from app.models.responses import AgentResponse, SimpleRAGResponse
from app.services.agent import create_agent
from app.services.retrieval import retrieval_service
from app.services.llm import llm_service
from app.core.database import get_supabase_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", response_model=AgentResponse)
async def agentic_query(request: QueryRequest):
    """
    Execute agentic RAG query with full reasoning loop.
    The agent will iteratively retrieve, reason, and verify until confident or max iterations reached.
    """
    start_time = time.time()
    
    try:
        # Create agent instance
        agent = create_agent()
        
        # Execute agentic query
        state = await agent.query(
            query=request.query,
            top_k=request.top_k,
            filter_source=request.filter_source
        )
        
        processing_time = time.time() - start_time
        
        # DEBUG: Log final state
        logger.info("=" * 80)
        logger.info("DEBUG: Final Response State")
        logger.info(f"  final_answer exists: {state.final_answer is not None}")
        logger.info(f"  final_answer length: {len(state.final_answer) if state.final_answer else 0}")
        logger.info(f"  confidence: {state.confidence}")
        logger.info(f"  iterations: {state.iteration}")
        logger.info(f"  verification_results count: {len(state.verification_results)}")
        if state.verification_results:
            logger.info(f"  last verification: {state.verification_results[-1]}")
        logger.info("=" * 80)
        
        # Build response
        answer_text = state.final_answer if state.final_answer else "Unable to generate answer"
        if not state.final_answer:
            logger.error("DEBUG: final_answer is None! This is why 'Unable to generate answer' appears")
        
        return AgentResponse(
            query=state.original_query,
            answer=answer_text,
            confidence=state.confidence,
            sources=state.sources,
            reasoning_trace=state.reasoning,
            iterations=state.iteration,
            retrieved_chunks=len(state.retrieved_docs),
            verification_passed=all(v.get('verified', False) for v in state.verification_results),
            processing_time=processing_time
        )
    
    except Exception as e:
        logger.error(f"Error in agentic query: {e}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@router.post("/simple", response_model=SimpleRAGResponse)
async def simple_query(request: SimpleQueryRequest):
    """
    Simple RAG query without agentic reasoning.
    Single retrieval + answer generation.
    """
    try:
        # Retrieve relevant chunks
        results = await retrieval_service.retrieve(
            query=request.query,
            top_k=request.top_k
        )
        
        if not results:
            return SimpleRAGResponse(
                query=request.query,
                answer="I couldn't find any relevant information to answer your question.",
                sources=[],
                retrieved_chunks=0
            )
        
        # Format context
        context = retrieval_service.format_context(results)
        
        # Generate answer
        prompt = llm_service.create_answer_prompt(request.query, context)
        answer = await llm_service.generate(prompt, temperature=0.7)
        
        # Format sources
        sources = [
            {
                "source": r.source,
                "similarity": r.similarity,
                "text": r.text[:200] + "..." if len(r.text) > 200 else r.text
            }
            for r in results
        ]
        
        return SimpleRAGResponse(
            query=request.query,
            answer=answer.strip(),
            sources=sources,
            retrieved_chunks=len(results)
        )
    
    except Exception as e:
        logger.error(f"Error in simple query: {e}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


# ============================================================================
# Chat Session Management Endpoints (Phase 2)
# ============================================================================

@router.post("/sessions")
async def create_chat_session(title: Optional[str] = None):
    """Create a new chat session."""
    try:
        client = get_supabase_client()
        
        session_data = {
            "title": title or "New Chat",
            "created_at": "now()",
            "updated_at": "now()"
        }
        
        result = client.table('chat_sessions').insert(session_data).execute()
        
        if result.data:
            return {
                "success": True,
                "session": result.data[0]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")
            
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_chat_sessions(limit: int = 50, offset: int = 0):
    """List all chat sessions."""
    try:
        client = get_supabase_client()
        
        result = client.table('chat_sessions') \
            .select('*') \
            .order('updated_at', desc=True) \
            .limit(limit) \
            .offset(offset) \
            .execute()
        
        return {
            "success": True,
            "sessions": result.data,
            "count": len(result.data)
        }
        
    except Exception as e:
        logger.error(f"Error listing chat sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: int):
    """Get a specific chat session with its messages."""
    try:
        client = get_supabase_client()
        
        # Get session
        session_result = client.table('chat_sessions') \
            .select('*') \
            .eq('id', session_id) \
            .execute()
        
        if not session_result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get messages
        messages_result = client.table('chat_messages') \
            .select('*') \
            .eq('session_id', session_id) \
            .order('created_at', desc=False) \
            .execute()
        
        return {
            "success": True,
            "session": session_result.data[0],
            "messages": messages_result.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: int):
    """Delete a chat session and all its messages."""
    try:
        client = get_supabase_client()
        
        result = client.table('chat_sessions') \
            .delete() \
            .eq('id', session_id) \
            .execute()
        
        if result.data:
            return {
                "success": True,
                "message": "Session deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

