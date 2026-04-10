"""
Response models for API endpoints.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    """Response from document ingestion with validation details."""
    success: bool
    message: str
    source: str
    chunks_created: int = 0
    file_size: Optional[int] = None
    processing_time: Optional[float] = None
    
    # Enhanced validation data (Sprint 3)
    file_hash: Optional[str] = None
    duplicate_action: Optional[str] = None  # "skip", "replace", "append"
    validation_warnings: List[str] = Field(default_factory=list)
    metadata_extracted: Dict[str, Any] = Field(default_factory=dict)


class BatchIngestResponse(BaseModel):
    """Response from batch document ingestion."""
    success: bool
    message: str
    total_files: int
    successful: int
    failed: int
    results: List[Dict[str, Any]] = Field(default_factory=list)
    total_chunks_created: int = 0
    total_processing_time: float = 0


class RetrievedChunkTrace(BaseModel):
    """Detailed trace information for a retrieved chunk."""
    chunk_id: str
    source: str
    text: str
    similarity: float
    iteration_retrieved: int


class VerificationTrace(BaseModel):
    """Detailed verification result trace."""
    verified: bool
    confidence: float
    issues: List[str] = Field(default_factory=list)
    grounded_claims: int = 0
    total_claims: int = 0
    iteration: int


class AgentResponse(BaseModel):
    """Response from agentic RAG query with detailed trace data."""
    query: str
    answer: str
    confidence: Optional[float] = None
    sources: List[str] = Field(default_factory=list)
    reasoning_trace: List[str] = Field(default_factory=list)
    iterations: int = 0
    retrieved_chunks: int = 0
    verification_passed: bool = True
    processing_time: Optional[float] = None
    
    # Enhanced trace data (Sprint 3)
    retrieved_chunks_detail: List[RetrievedChunkTrace] = Field(default_factory=list)
    verification_detail: List[VerificationTrace] = Field(default_factory=list)
    agent_steps: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class SimpleRAGResponse(BaseModel):
    """Response from simple RAG query."""
    query: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: int = 0


class HybridSearchBreakdown(BaseModel):
    """Breakdown of hybrid search results."""
    vector_results: int = 0
    keyword_results: int = 0
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    fused_results: int = 0
    after_filter: int = 0
    method: str = "vector-only"


class HybridSearchResponse(BaseModel):
    """Response from hybrid search query."""
    query: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: int = 0
    retrieval_method: str = "vector-only"
    filter_applied: bool = False
    processing_time_ms: float = 0.0
    search_breakdown: HybridSearchBreakdown = Field(default_factory=HybridSearchBreakdown)


class HealthResponse(BaseModel):
    """System health check response."""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    database_connected: bool
    ollama_available: bool
    ollama_models: Optional[Dict[str, bool]] = None


class StatsResponse(BaseModel):
    """Database and usage statistics."""
    total_chunks: int = 0
    unique_sources: int = 0
    unique_models: int = 0
    latest_chunk: Optional[datetime] = None
    database_size: Optional[str] = None


class DocumentListResponse(BaseModel):
    """List of documents in the knowledge base."""
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
