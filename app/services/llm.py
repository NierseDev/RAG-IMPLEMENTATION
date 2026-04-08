"""
LLM service with multi-provider support and prompt management.
"""
from typing import Optional, AsyncGenerator
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.services.llm_providers import create_llm_provider
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM interactions with multi-provider support."""
    
    def __init__(self):
        self.max_context_tokens = settings.max_context_tokens
        self.max_output_tokens = settings.max_output_tokens
        
        # Initialize provider based on configuration
        self._init_provider()
        
        logger.info(f"LLM service initialized")
        logger.info(f"  Provider: {settings.ai_provider}")
        logger.info(f"  Model: {settings.current_llm_model}")
        logger.info(f"  Context: {self.max_context_tokens} tokens")
        logger.info(f"  Max output: {self.max_output_tokens} tokens")
    
    def _init_provider(self):
        """Initialize the LLM provider based on configuration."""
        provider = settings.ai_provider
        
        if provider == "ollama":
            self.provider = create_llm_provider(
                provider="ollama",
                base_url=settings.ollama_base_url,
                model=settings.ollama_llm_model,
                max_output_tokens=self.max_output_tokens
            )
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="openai",
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                max_output_tokens=self.max_output_tokens
            )
        elif provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="anthropic",
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                max_output_tokens=self.max_output_tokens
            )
        elif provider == "google":
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="google",
                api_key=settings.google_api_key,
                model=settings.google_model,
                max_output_tokens=self.max_output_tokens
            )
        elif provider == "groq":
            if not settings.groq_api_key:
                raise ValueError("GROQ_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="groq",
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                max_output_tokens=self.max_output_tokens
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    
    def _validate_and_truncate_prompt(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> tuple[str, Optional[str]]:
        """
        Validate and truncate prompt to fit within context window.
        
        Returns: (truncated_prompt, truncated_system)
        """
        max_tokens = max_tokens or self.max_output_tokens
        
        # Calculate available tokens for input
        available_tokens = self.max_context_tokens - max_tokens
        
        # Estimate system prompt tokens
        system_tokens = estimate_tokens(system) if system else 0
        
        # Calculate available tokens for user prompt
        prompt_available = available_tokens - system_tokens
        
        if prompt_available < 100:
            logger.warning("Very little space left for prompt after system message")
            # Truncate system message if needed
            if system and system_tokens > available_tokens // 2:
                system = truncate_to_token_limit(system, available_tokens // 2)
                system_tokens = estimate_tokens(system)
                prompt_available = available_tokens - system_tokens
        
        # Check if prompt needs truncation
        prompt_tokens = estimate_tokens(prompt)
        if prompt_tokens > prompt_available:
            logger.warning(
                f"Prompt ({prompt_tokens} tokens) exceeds limit ({prompt_available} available). Truncating."
            )
            prompt = truncate_to_token_limit(prompt, prompt_available, reserve_tokens=50)
        
        return prompt, system
    
    async def generate(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response from the LLM."""
        try:
            # Validate and truncate if needed
            prompt, system = self._validate_and_truncate_prompt(prompt, system, max_tokens)
            
            # Add default system message if none provided
            if not system:
                system = "You are a helpful AI assistant. Provide your answer directly without showing your thinking process."
            
            # DEBUG: Log generation details
            logger.info("=" * 80)
            logger.info("DEBUG LLM: Generating response")
            logger.info(f"  Provider: {settings.ai_provider}")
            logger.info(f"  Model: {settings.current_llm_model}")
            logger.info(f"  Temperature: {temperature}")
            logger.info(f"  Max tokens: {max_tokens if max_tokens else self.max_output_tokens}")
            logger.info(f"  System length: {len(system) if system else 0}")
            logger.info(f"  Prompt length: {len(prompt)}")
            logger.info(f"  Prompt preview: {prompt[:200]}...")
            logger.info("=" * 80)
            
            # Generate using provider
            content = await self.provider.generate(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            logger.info(f"DEBUG LLM: ✅ Response received ({len(content)} chars)")
            logger.info("=" * 80)
            
            return content
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["context", "length", "token", "too long"]):
                logger.error(f"Context length error in LLM generation: {e}")
                # Try with more aggressive truncation
                try:
                    logger.info("Retrying with more aggressive truncation")
                    safe_limit = int(self.max_context_tokens * 0.6)
                    
                    if system:
                        system = truncate_to_token_limit(system, safe_limit // 3)
                    prompt = truncate_to_token_limit(prompt, safe_limit // 3 * 2)
                    
                    content = await self.provider.generate(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens or self.max_output_tokens // 2
                    )
                    return content
                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}")
                    return "I apologize, but the context is too large for me to process. Please try with a smaller query or fewer documents."
            
            logger.error(f"Error generating LLM response: {e}")
            raise
    
    async def check_availability(self) -> bool:
        """Check if LLM provider is available."""
        try:
            return await self.provider.check_availability()
        except Exception as e:
            logger.error(f"LLM provider not available: {e}")
            return False
    
    # Prompt templates for different agent phases
    
    def create_plan_prompt(self, query: str) -> str:
        """Create prompt for the planning phase."""
        return f"""Analyze the following user query and create a retrieval strategy.

User Query: {query}

Create a plan that describes:
1. What information is needed to answer this query
2. What search terms or concepts to look for
3. What type of documents would be most relevant

Provide ONLY the plan, no preamble or explanation."""
    
    def create_reason_prompt(self, query: str, retrieved_docs: str) -> str:
        """Create prompt for the reasoning phase."""
        return f"""Evaluate the retrieved information and determine if it's sufficient to answer the query.

User Query: {query}

Retrieved Information:
{retrieved_docs}

Analyze:
1. Is the information relevant to the query?
2. Is there enough information to provide a complete answer?
3. Are there any gaps or missing information?

Provide ONLY your analysis, no preamble."""
    
    def create_verify_prompt(self, query: str, answer: str, context: str) -> str:
        """Create prompt for verification phase."""
        return f"""Check if the answer is grounded in the provided context and detect any hallucinations.

User Query: {query}

Proposed Answer: {answer}

Context:
{context}

Verify:
1. Is every claim in the answer supported by the context?
2. Are there any fabricated or unsupported statements?
3. What is your confidence level (0.0-1.0)?

Provide ONLY the verification result in this exact format:
Verified: [yes/no]
Confidence: [0.0-1.0]
Issues: [list any problems or write "none"]"""
    
    def create_answer_prompt(self, query: str, context: str) -> str:
        """Create prompt for final answer generation."""
        system = """You are a helpful AI assistant. Answer the user's question based ONLY on the provided context. 
If the context doesn't contain enough information, say so. Always cite your sources using APA format in-text citations."""
        
        prompt = f"""Context:
{context}

Question: {query}

Provide a clear, accurate answer based solely on the context above. 

IMPORTANT: 
- If the context does NOT contain relevant information, respond ONLY with: "I don't have information about [topic] in the provided context."
- Do NOT list what other topics are mentioned if information is unavailable.
- When answering, use APA format for citations:
  * For in-text citations: (Author, Year) or (Author, Year, p. X)
  * For PDF sources without clear author/year: (Source Title, n.d.)
  * Include full references at the end under "References"

Example answer with citations:
"Deep Q-Learning uses neural networks to approximate Q-functions (Smith, 2020). According to recent research (Johnson & Lee, 2021), this approach has shown significant improvements..."

References:
Smith, J. (2020). Deep reinforcement learning. Journal of AI, 15(2), 45-67.
Johnson, M., & Lee, K. (2021). Adaptive game AI techniques. In Proceedings of AI Conference (pp. 123-145).

Example when information is unavailable:
"I don't have information about BTRFS in the provided context.\""""
        
        return prompt
    
    def create_refine_query_prompt(self, original_query: str, reasoning: str) -> str:
        """Create prompt for query refinement."""
        return f"""You are a query refinement agent. Based on the reasoning below, create a better search query.

Original Query: {original_query}

Reasoning: {reasoning}

Create a refined query that will retrieve more relevant information. Output only the refined query, nothing else."""


# Global LLM service instance
llm_service = LLMService()
