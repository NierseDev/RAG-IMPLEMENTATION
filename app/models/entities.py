"""
Entity models for the RAG system.
These represent core domain objects and database entities.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RAGChunk(BaseModel):
    """Database entity representing a stored chunk with embedding."""
    id: Optional[int] = None
    chunk_id: str
    source: str
    text: str
    ai_provider: str = "ollama"
    embedding_model: str
    embedding: List[float]
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RetrievalResult(BaseModel):
    """Result from vector similarity search."""
    chunk_id: str
    source: str
    ai_provider: str
    embedding_model: str
    text: str
    similarity: float
    created_at: datetime
    rerank_score: Optional[float] = None
    diversity_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class AgentState(BaseModel):
    """Tracks the state of the agentic reasoning loop."""
    iteration: int = 0
    original_query: str
    current_query: str
    plan: Optional[str] = None
    retrieved_docs: List[RetrievalResult] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)
    verification_results: List[dict] = Field(default_factory=list)
    decision: Optional[str] = None  # "answer" or "continue"
    confidence: Optional[float] = None
    final_answer: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    
    def add_reasoning(self, step: str, content: str):
        """Add a reasoning step with context."""
        self.reasoning.append(f"[Iteration {self.iteration}] {step}: {content}")
    
    def should_continue(self, max_iterations: int) -> bool:
        """Check if agent should continue iterating."""
        return self.iteration < max_iterations and self.decision == "continue"


class Document(BaseModel):
    """Metadata for an uploaded document."""
    filename: str
    source: str
    file_size: int
    content_type: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: int = 0
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
