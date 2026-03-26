"""
Configuration management for Agentic RAG system.
Uses Pydantic Settings for environment variable management.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_role_key: str = Field(..., description="Supabase service role key for database access")
    
    # Ollama Configuration
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    ollama_llm_model: str = Field(default="qwen3.5:4b", description="Ollama LLM model for agent reasoning")
    ollama_embed_model: str = Field(default="mxbai-embed-large", description="Ollama embedding model")
    ollama_timeout: int = Field(default=300, description="Ollama API timeout in seconds")
    
    # Context Length Limits (adjust based on your models)
    llm_context_window: int = Field(default=8192, description="LLM model context window size in tokens")
    embedding_context_window: int = Field(default=512, description="Embedding model context window size in tokens")
    max_output_tokens: int = Field(default=1024, description="Maximum tokens for LLM output")
    context_reserve_tokens: int = Field(default=1500, description="Reserve tokens for system prompt and overhead")
    
    # RAG Configuration
    chunk_size: int = Field(default=400, description="Target chunk size in tokens (must fit in embedding context)")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks in tokens")
    top_k_results: int = Field(default=5, description="Number of results to retrieve per query")
    min_similarity: float = Field(default=0.0, description="Minimum similarity threshold for retrieval")
    max_context_chunks: int = Field(default=8, description="Maximum chunks to include in LLM context")
    
    # Agent Configuration
    max_agent_iterations: int = Field(default=3, description="Maximum reasoning loop iterations")
    min_confidence_threshold: float = Field(default=0.7, description="Minimum confidence to provide answer")
    enable_verification: bool = Field(default=True, description="Enable hallucination verification")
    enable_streaming: bool = Field(default=False, description="Enable LLM response streaming")
    
    # Document Processing
    max_file_size_mb: int = Field(default=50, description="Maximum file size for upload in MB")
    allowed_extensions: list[str] = Field(
        default=[".pdf", ".docx", ".pptx", ".txt", ".md", ".html", ".htm"],
        description="Allowed document extensions"
    )
    
    # API Configuration
    api_title: str = Field(default="Agentic RAG API", description="API title")
    api_version: str = Field(default="1.0.0", description="API version")
    api_prefix: str = Field(default="", description="API route prefix")
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", description="Logging level")
    
    # Development
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def max_chunk_tokens(self) -> int:
        """Get maximum chunk size ensuring it fits in embedding context."""
        # Leave some buffer for encoding overhead
        return min(self.chunk_size, self.embedding_context_window - 50)
    
    @property
    def max_context_tokens(self) -> int:
        """Get maximum tokens available for context in LLM."""
        # Reserve space for system prompt, query, and output
        return self.llm_context_window - self.context_reserve_tokens - self.max_output_tokens
    
    @property
    def embedding_dimensions(self) -> int:
        """Get embedding dimensions based on model."""
        # mxbai-embed-large uses 1024 dimensions
        if "mxbai" in self.ollama_embed_model.lower():
            return 1024
        # OpenAI text-embedding-3-small uses 1536 (for future support)
        return 1024


# Global settings instance
settings = Settings()
