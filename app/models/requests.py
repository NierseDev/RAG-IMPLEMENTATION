"""
Request models for API endpoints.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request for querying the agentic RAG system."""
    query: str = Field(..., min_length=1, description="User question")
    session_id: Optional[int] = Field(None, ge=1, description="Optional chat session ID for persistence")
    filter_source: Optional[str] = Field(None, description="Filter by document source")
    filter_provider: Optional[str] = Field(None, description="Filter by AI provider")
    filter_model: Optional[str] = Field(None, description="Filter by embedding model")
    top_k: Optional[int] = Field(None, ge=1, le=50, description="Number of results to retrieve")
    enable_agent: bool = Field(True, description="Enable agentic reasoning loop")
    metadata_filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters (doc_type, date_range, entities, document_ids)")
    filter_logic: Optional[str] = Field("AND", description="Filter combination logic: AND or OR")


class SimpleQueryRequest(BaseModel):
    """Request for simple RAG query without agent."""
    query: str = Field(..., min_length=1, description="User question")
    top_k: Optional[int] = Field(None, ge=1, le=50, description="Number of results")
    metadata_filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters (doc_type, date_range, entities, document_ids)")
    filter_logic: Optional[str] = Field("AND", description="Filter combination logic: AND or OR")


class IngestDocumentRequest(BaseModel):
    """Metadata for document ingestion."""
    source: Optional[str] = Field(None, description="Custom source identifier")
    

class AgentConfigRequest(BaseModel):
    """Runtime configuration for agent behavior."""
    max_iterations: Optional[int] = Field(None, ge=1, le=5, description="Max reasoning iterations")
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Min confidence threshold")
    enable_verification: Optional[bool] = Field(None, description="Enable verification")


class HybridSearchRequest(BaseModel):
    """Request for hybrid search query (Sprint 4)."""
    query: str = Field(..., min_length=1, description="Search query")
    metadata_filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters (source, provider, model, doc_type, entities)")
    top_k: Optional[int] = Field(10, ge=1, le=100, description="Number of results to return")
    use_hybrid: Optional[bool] = Field(None, description="Force hybrid or vector-only search")
    min_similarity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum similarity threshold")


class ChatSessionCreateRequest(BaseModel):
    """Request payload to create a chat session."""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Session title")


class ChatSessionUpdateRequest(BaseModel):
    """Request payload to update an existing chat session."""
    title: str = Field(..., min_length=1, max_length=200, description="Updated session title")
