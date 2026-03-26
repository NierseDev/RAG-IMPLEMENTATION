"""
Request models for API endpoints.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request for querying the agentic RAG system."""
    query: str = Field(..., min_length=1, description="User question")
    filter_source: Optional[str] = Field(None, description="Filter by document source")
    filter_provider: Optional[str] = Field(None, description="Filter by AI provider")
    filter_model: Optional[str] = Field(None, description="Filter by embedding model")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Number of results to retrieve")
    enable_agent: bool = Field(True, description="Enable agentic reasoning loop")


class SimpleQueryRequest(BaseModel):
    """Request for simple RAG query without agent."""
    query: str = Field(..., min_length=1, description="User question")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Number of results")


class IngestDocumentRequest(BaseModel):
    """Metadata for document ingestion."""
    source: Optional[str] = Field(None, description="Custom source identifier")
    

class AgentConfigRequest(BaseModel):
    """Runtime configuration for agent behavior."""
    max_iterations: Optional[int] = Field(None, ge=1, le=5, description="Max reasoning iterations")
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Min confidence threshold")
    enable_verification: Optional[bool] = Field(None, description="Enable verification")
