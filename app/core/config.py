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
    ai_provider: Literal["ollama", "openrouter", "openai"] = Field(
        default="ollama",
        description="AI provider to use: ollama (local), openrouter (cloud), or openai"
    )
    
    # Ollama Configuration (Local)
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    ollama_llm_model: str = Field(default="qwen3.5:4b", description="Ollama LLM model for agent reasoning")
    ollama_embed_model: str = Field(default="mxbai-embed-large", description="Ollama embedding model")
    ollama_timeout: int = Field(default=300, description="Ollama API timeout in seconds")
    
    # Cloud Provider (OpenRouter-only)
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL"
    )
    openrouter_model: str = Field(
        default="google/gemma-4-31b-it:free",
        description="OpenRouter model slug (e.g., google/gemma-4-31b-it:free)"
    )
    openrouter_free_mode_enabled: bool = Field(
        default=False,
        description="Enable rate-limit-aware OpenRouter free-model execution mode"
    )
    openrouter_free_max_calls_per_request: int = Field(
        default=2,
        ge=1,
        description="Maximum LLM calls allowed per request in OpenRouter free mode"
    )
    openrouter_free_disable_verification: bool = Field(
        default=True,
        description="Disable verification phase in OpenRouter free mode to reduce call volume"
    )
    openrouter_free_max_iterations: int = Field(
        default=1,
        ge=1,
        description="Maximum agent iterations allowed in OpenRouter free mode"
    )
    openrouter_free_retry_attempts: int = Field(
        default=2,
        ge=0,
        description="Retry attempts for OpenRouter 429 responses in free mode"
    )
    openrouter_free_retry_backoff_seconds: float = Field(
        default=2.0,
        ge=0.0,
        description="Base exponential backoff delay for OpenRouter free-mode retries"
    )
    openrouter_free_retry_max_backoff_seconds: float = Field(
        default=20.0,
        ge=0.0,
        description="Maximum backoff delay cap for OpenRouter free-mode retries"
    )
    openrouter_free_min_inter_call_delay_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Minimum delay between OpenRouter calls in free mode"
    )
    openrouter_free_cooldown_seconds: float = Field(
        default=15.0,
        ge=0.0,
        description="Cooldown applied after OpenRouter 429 when reset headers are unavailable"
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (used when AI_PROVIDER=openai or EMBEDDING_PROVIDER=openai)"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL"
    )
    openai_model: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI model slug"
    )

    # Tavily Web Search Configuration
    tavily_api_key: Optional[str] = Field(default=None, description="Tavily API key")
    tavily_base_url: str = Field(
        default="https://api.tavily.com/search",
        description="Tavily search API base URL"
    )
    tavily_search_depth: Literal["basic", "advanced"] = Field(
        default="basic",
        description="Tavily search depth"
    )
    tavily_include_answer: bool = Field(
        default=False,
        description="Include Tavily answer summary in search response"
    )
    tavily_include_raw_content: bool = Field(
        default=False,
        description="Include Tavily raw content in search response"
    )
    tavily_max_results: int = Field(
        default=5,
        ge=1,
        description="Maximum Tavily results to request"
    )

    # Observability
    langsmith_enabled: bool = Field(
        default=False,
        description="Enable LangSmith tracing when the dependency is installed"
    )
    langsmith_api_key: Optional[str] = Field(
        default=None,
        description="LangSmith API key"
    )
    langsmith_project: str = Field(
        default="rag-implementation",
        description="LangSmith project name"
    )
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint"
    )
    
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
    plan_context_chunks: int = Field(default=0, description="Maximum retrieved chunks carried into planning")
    reason_context_chunks: int = Field(default=6, description="Maximum retrieved chunks carried into reasoning")
    answer_context_chunks: int = Field(default=8, description="Maximum retrieved chunks carried into answer generation")
    verify_context_chunks: int = Field(default=4, description="Maximum retrieved chunks carried into verification")
    refine_context_chunks: int = Field(default=1, description="Maximum reasoning entries carried into query refinement")
    
    # Sprint 3: Advanced Retrieval Configuration
    min_retrieval_chunks: int = Field(default=3, description="Minimum chunks to retrieve")
    max_retrieval_chunks: int = Field(default=20, description="Maximum chunks to retrieve")
    use_semantic_chunking: bool = Field(default=True, description="Use semantic chunking instead of fixed-size")
    use_dynamic_chunking: bool = Field(default=False, description="Use dynamic chunk sizing based on density")
    use_hybrid_search: bool = Field(default=True, description="Enable hybrid search (vector + keyword)")
    hybrid_vector_weight: float = Field(default=0.7, description="Weight for vector search in hybrid mode")
    hybrid_keyword_weight: float = Field(default=0.3, description="Weight for keyword search in hybrid mode")
    
    # Sprint 5: Reranking Configuration
    use_reranking: bool = Field(default=False, description="Enable optional reranking of results")
    rerank_strategy: Literal["semantic", "bm25", "hybrid", "diversity"] = Field(
        default="hybrid",
        description="Reranking strategy: semantic, bm25, hybrid, or diversity"
    )
    rerank_top_k: int = Field(default=10, description="Number of results to return after reranking")
    
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
        elif self.ai_provider == "openrouter":
            return self.openrouter_model
        elif self.ai_provider == "openai":
            return self.openai_model
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

