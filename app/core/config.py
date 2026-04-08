"""
Configuration management for Agentic RAG system.
Uses Pydantic Settings for environment variable management.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


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
    
    # ============================================================================
    # AI Provider Configuration
    # ============================================================================
    ai_provider: Literal["ollama", "openai", "anthropic", "google", "groq"] = Field(
        default="ollama",
        description="AI provider to use: ollama (local), openai, anthropic, google, groq"
    )
    
    # Ollama Configuration (Local)
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    ollama_llm_model: str = Field(default="qwen3.5:4b", description="Ollama LLM model for agent reasoning")
    ollama_embed_model: str = Field(default="mxbai-embed-large", description="Ollama embedding model")
    ollama_timeout: int = Field(default=300, description="Ollama API timeout in seconds")
    
    # Cloud Provider API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google AI API key")
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key")
    
    # Cloud Model Configuration
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model: gpt-4o-mini, gpt-4o, etc.")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", description="Anthropic model: claude-3-5-sonnet, etc.")
    google_model: str = Field(default="gemini-2.0-flash-exp", description="Google model: gemini-2.0-flash-exp, gemini-1.5-pro, etc.")
    groq_model: str = Field(default="llama-3.3-70b-versatile", description="Groq model: llama-3.3-70b-versatile, etc.")
    
    # Embedding Provider (can be different from LLM provider)
    embedding_provider: Literal["ollama", "openai"] = Field(
        default="ollama",
        description="Embedding provider: ollama (local), openai"
    )
    openai_embedding_model: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")
    
    # Context Length Limits (auto-adjusted based on provider/model)
    llm_context_window: int = Field(default=262144, description="LLM model context window size in tokens")
    embedding_context_window: int = Field(default=512, description="Embedding model context window size in tokens")
    max_output_tokens: int = Field(default=2048, description="Maximum tokens for LLM output")
    context_reserve_tokens: int = Field(default=2000, description="Reserve tokens for system prompt and overhead")
    
    # RAG Configuration
    chunk_size: int = Field(default=400, description="Target chunk size in tokens (must fit in embedding context)")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks in tokens")
    top_k_results: int = Field(default=30, description="Number of results to retrieve per query")
    min_similarity: float = Field(default=0.0, description="Minimum similarity threshold for retrieval")
    max_context_chunks: int = Field(default=100, description="Maximum chunks to include in LLM context")
    
    # Sprint 3: Advanced Retrieval Configuration
    min_retrieval_chunks: int = Field(default=3, description="Minimum chunks to retrieve")
    max_retrieval_chunks: int = Field(default=20, description="Maximum chunks to retrieve")
    use_semantic_chunking: bool = Field(default=True, description="Use semantic chunking instead of fixed-size")
    use_dynamic_chunking: bool = Field(default=False, description="Use dynamic chunk sizing based on density")
    use_hybrid_search: bool = Field(default=True, description="Enable hybrid search (vector + keyword)")
    hybrid_vector_weight: float = Field(default=0.7, description="Weight for vector search in hybrid mode")
    hybrid_keyword_weight: float = Field(default=0.3, description="Weight for keyword search in hybrid mode")
    
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
        """Get embedding dimensions based on provider and model."""
        if self.embedding_provider == "ollama":
            # mxbai-embed-large: 1024, nomic-embed-text: 768
            if "mxbai" in self.ollama_embed_model.lower():
                return 1024
            elif "nomic" in self.ollama_embed_model.lower():
                return 768
            return 1024
        elif self.embedding_provider == "openai":
            # text-embedding-3-small: 1536, text-embedding-3-large: 3072
            if "small" in self.openai_embedding_model.lower():
                return 1536
            elif "large" in self.openai_embedding_model.lower():
                return 3072
            return 1536
        return 1024
    
    @property
    def current_llm_model(self) -> str:
        """Get the current LLM model based on provider."""
        if self.ai_provider == "ollama":
            return self.ollama_llm_model
        elif self.ai_provider == "openai":
            return self.openai_model
        elif self.ai_provider == "anthropic":
            return self.anthropic_model
        elif self.ai_provider == "google":
            return self.google_model
        elif self.ai_provider == "groq":
            return self.groq_model
        return self.ollama_llm_model
    
    @property
    def current_embedding_model(self) -> str:
        """Get the current embedding model based on provider."""
        if self.embedding_provider == "ollama":
            return self.ollama_embed_model
        elif self.embedding_provider == "openai":
            return self.openai_embedding_model
        return self.ollama_embed_model


# Global settings instance
settings = Settings()

