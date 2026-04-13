"""
Query endpoints for agentic RAG.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
import time
from app.models.requests import (
    QueryRequest,
    SimpleQueryRequest,
    HybridSearchRequest,
    ChatSessionCreateRequest,
    ChatSessionUpdateRequest
)
from app.models.responses import AgentResponse, SimpleRAGResponse, HybridSearchResponse
from app.services.agent import create_agent
from app.services.retrieval import retrieval_service
from app.services.query_service import query_service
from app.services.llm import llm_service
from app.core.database import get_supabase_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


def _normalize_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Add session_id alias for frontend compatibility."""
    normalized = dict(session)
    if 'session_id' not in normalized and 'id' in normalized:
        normalized['session_id'] = normalized['id']
    return normalized


@router.post("/agentic", response_model=AgentResponse)
async def agentic_query(request: QueryRequest):
    """
    Execute agentic RAG query with full reasoning loop.
    The agent will iteratively retrieve, reason, and verify until confident or max iterations reached.
    Sprint 4: Supports metadata filtering with AND/OR logic.
    """
    start_time = time.time()
    
    try:
        # Create agent instance
        agent = create_agent()
        
        # Sprint 4: Store metadata filters in agent state for retrieval
        # We'll need to extend the agent to pass filters to retrieve
        state = await agent.query(
            query=request.query,
            top_k=request.top_k,
            filter_source=request.filter_source,
            metadata_filters=request.metadata_filters,
            filter_logic=request.filter_logic
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
        
        # Sprint 3: Build detailed trace data
        from app.models.responses import RetrievedChunkTrace, VerificationTrace
        
        # Convert retrieved docs to detailed traces
        retrieved_chunks_detail = []
        for doc in state.retrieved_docs:
            retrieved_chunks_detail.append(RetrievedChunkTrace(
                chunk_id=doc.chunk_id,
                source=doc.source,
                text=doc.text[:500],  # Truncate for response size
                similarity=doc.similarity,
                iteration_retrieved=1  # Could track which iteration retrieved this
            ))
        
        # Convert verification results to detailed traces
        verification_detail = []
        for idx, verification in enumerate(state.verification_results, 1):
            verification_detail.append(VerificationTrace(
                verified=verification.get('verified', False),
                confidence=verification.get('confidence', 0.0),
                issues=verification.get('issues', []),
                grounded_claims=verification.get('grounded_claims', 0),
                total_claims=verification.get('total_claims', 0),
                iteration=idx
            ))
        
        # Build agent steps trace
        agent_steps = []
        for reasoning in state.reasoning:
            agent_steps.append({
                'description': reasoning,
                'timestamp': processing_time
            })
        
        response_payload = AgentResponse(
            query=state.original_query,
            answer=answer_text,
            confidence=state.confidence,
            sources=state.sources,
            reasoning_trace=state.reasoning,
            iterations=state.iteration,
            retrieved_chunks=len(state.retrieved_docs),
            verification_passed=all(v.get('verified', False) for v in state.verification_results),
            processing_time=processing_time,
            # Sprint 3 additions
            retrieved_chunks_detail=retrieved_chunks_detail,
            verification_detail=verification_detail,
            agent_steps=agent_steps,
            tool_calls=[]  # TODO: Track tool calls from agent
        )

        # Best-effort message persistence for session-backed chat UIs.
        if request.session_id:
            try:
                client = get_supabase_client()
                client.table('chat_messages').insert([
                    {
                        "session_id": request.session_id,
                        "role": "user",
                        "content": request.query
                    },
                    {
                        "session_id": request.session_id,
                        "role": "assistant",
                        "content": answer_text
                    }
                ]).execute()
            except Exception as persistence_error:
                logger.warning(
                    f"Could not persist chat messages for session {request.session_id}: {persistence_error}"
                )

        # Sprint 3: Enhanced response with detailed trace data
        return response_payload
    
    except Exception as e:
        logger.error(f"Error in agentic query: {e}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@router.post("/simple", response_model=SimpleRAGResponse)
async def simple_query(request: SimpleQueryRequest):
    """
    Simple RAG query without agentic reasoning.
    Single retrieval + answer generation.
    Sprint 4: Supports metadata filtering.
    """
    try:
        # Retrieve relevant chunks
        results = await retrieval_service.retrieve(
            query=request.query,
            top_k=request.top_k,
            metadata_filters=request.metadata_filters,
            filter_logic=request.filter_logic
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


@router.post("/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest):
    """
    Hybrid search query combining vector and keyword search (Sprint 4).
    
    Implements:
    - Vector search (top 20 results)
    - Keyword search with FTS (top 20 results)
    - RRF fusion with configurable weights
    - Optional metadata filtering
    - Returns top 10 reranked results with search breakdown
    """
    start_time = time.time()
    
    try:
        logger.info(f"Hybrid search request: query='{request.query}', filters={request.metadata_filters}")
        
        # Execute hybrid search
        search_result = await query_service.search(
            query=request.query,
            metadata_filters=request.metadata_filters,
            top_k=request.top_k,
            use_hybrid=request.use_hybrid,
            min_similarity=request.min_similarity
        )
        
        # Check for errors
        if 'error' in search_result:
            logger.error(f"Search error: {search_result['error']}")
            raise HTTPException(status_code=500, detail=f"Search failed: {search_result['error']}")
        
        # Format response
        formatted = query_service.format_results(search_result, include_breakdown=True)
        
        logger.info(
            f"Hybrid search completed: {len(formatted['results'])} results in "
            f"{formatted['processing_time_ms']:.1f}ms using {formatted['retrieval_method']}"
        )
        
        return HybridSearchResponse(
            query=formatted['query'],
            results=formatted['results'],
            retrieved_chunks=formatted['retrieved_chunks'],
            retrieval_method=formatted['retrieval_method'],
            filter_applied=formatted['filter_applied'],
            processing_time_ms=formatted['processing_time_ms'],
            search_breakdown=formatted['search_breakdown']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Hybrid search error: {str(e)}")


# ============================================================================
# Chat Session Management Endpoints (Phase 2)
# ============================================================================

@router.post("/sessions")
async def create_chat_session(payload: Optional[ChatSessionCreateRequest] = None):
    """Create a new chat session."""
    try:
        client = get_supabase_client()
        title = payload.title if payload and payload.title else "New Chat"

        session_data = {
            "title": title
        }

        result = client.table('chat_sessions').insert(session_data).execute()

        if result.data:
            session = _normalize_session(result.data[0])
            return {
                "success": True,
                "session_id": session["session_id"],
                "session": session
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")

    except HTTPException:
        raise
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
        
        sessions = [_normalize_session(session) for session in (result.data or [])]
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
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
        
        session = _normalize_session(session_result.data[0])
        return {
            "success": True,
            "session_id": session["session_id"],
            "session": session,
            "messages": messages_result.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}")
async def update_chat_session(session_id: int, payload: ChatSessionUpdateRequest):
    """Update chat session metadata."""
    try:
        client = get_supabase_client()

        result = client.table('chat_sessions') \
            .update({"title": payload.title}) \
            .eq('id', session_id) \
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = _normalize_session(result.data[0])
        return {
            "success": True,
            "session_id": session["session_id"],
            "session": session
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat session: {e}")
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

