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
        self.fallback_provider = None
        self.phase_max_tokens = {
            "plan": 180,
            "reason": 260,
            "verify": 220,
            "answer": 420,
            "refine": 100
        }
        
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
        elif provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="openrouter",
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
                max_output_tokens=self.max_output_tokens
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect provider rate-limit errors."""
        message = str(error).lower()
        return any(token in message for token in [
            "429",
            "rate limit",
            "too many requests",
            "temporarily rate-limited"
        ])

    def _get_fallback_provider(self):
        """Lazily initialize ollama fallback provider for OpenRouter rate limits."""
        if self.fallback_provider:
            return self.fallback_provider

        try:
            self.fallback_provider = create_llm_provider(
                provider="ollama",
                base_url=settings.ollama_base_url,
                model=settings.ollama_llm_model,
                max_output_tokens=self.max_output_tokens
            )
            logger.warning(
                f"Initialized fallback LLM provider: ollama ({settings.ollama_llm_model})"
            )
            return self.fallback_provider
        except Exception as fallback_error:
            logger.error(f"Failed to initialize fallback LLM provider: {fallback_error}")
            return None
    
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
                system = "Answer directly. Do not reveal chain-of-thought."
            
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
            if settings.ai_provider == "openrouter" and self._is_rate_limit_error(e):
                logger.warning(
                    "OpenRouter rate-limited. Attempting fallback with local Ollama provider."
                )
                fallback_provider = self._get_fallback_provider()
                if fallback_provider:
                    content = await fallback_provider.generate(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    logger.info(
                        f"Fallback LLM response received from ollama ({len(content)} chars)"
                    )
                    return content

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

    def get_phase_max_tokens(self, phase: str, fallback: int) -> int:
        """Return per-phase max_tokens budget."""
        return self.phase_max_tokens.get(phase, fallback)
    
    def create_plan_prompt(self, query: str) -> str:
        """Create prompt for the planning phase."""
        return f"""Plan retrieval for this query.
Query: {query}

Output format:
Needed Information:
- ...
Search Terms:
- ...
Relevant Source Types:
- ...
Potential Gaps:
- ...

Keep concise. Return ONLY this structure."""
    
    def create_reason_prompt(self, query: str, retrieved_docs: str) -> str:
        """Create prompt for the reasoning phase."""
        return f"""Evaluate answer readiness from context.
Query: {query}
Retrieved Context:
{retrieved_docs}

Output format:
Relevance:
...
Sufficiency:
...
Gaps:
- ...
Decision:
[answer|retrieve_more]

Return ONLY this analysis."""
    
    def create_verify_prompt(self, query: str, answer: str, context: str) -> str:
        """Create prompt for verification phase."""
        return f"""Verify whether answer is fully supported by context.
Query: {query}
Answer: {answer}
Context:
{context}

YOU MUST respond in this exact format:
Verified: [yes/no]
Confidence score: [0.0-1.0]
Issues: [none OR short semicolon-separated issues]

Return ONLY these three lines."""
    
    def create_answer_prompt(self, query: str, context: str) -> str:
        """Create prompt for final answer generation."""
        return f"""Answer using ONLY the provided context.
Question: {query}
Context:
{context}

Rules:
1. Be direct and factual.
2. Add in-text citations after factual claims.
3. Include a References section.
4. If context is insufficient, explicitly say what is missing and that web search is required before a final answer.

Output structure:
Answer:
[answer with citations]

References:
- [reference 1]
- [reference 2]"""
    
    def create_refine_query_prompt(self, original_query: str, reasoning: str) -> str:
        """Create prompt for query refinement."""
        return f"""Refine query for retrieval.
Original Query: {original_query}
Previous Reasoning: {reasoning}

Return ONE improved query only.
Keep same intent, add missing terms, max 20 words."""


# Global LLM service instance
llm_service = LLMService()
