"""
LLM service using Ollama for agent reasoning.
"""
from typing import Optional, AsyncGenerator
import ollama
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM interactions using Ollama."""
    
    def __init__(self):
        self.client = ollama.Client(host=settings.ollama_base_url)
        self.model = settings.ollama_llm_model
        self.max_context_tokens = settings.max_context_tokens
        self.max_output_tokens = settings.max_output_tokens
        logger.info(f"LLM service initialized with model: {self.model} (context: {self.max_context_tokens}, output: {self.max_output_tokens})")
    
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
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens if max_tokens else self.max_output_tokens
                }
            )
            return response['message']['content']
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["context", "length", "token", "too long"]):
                logger.error(f"Context length error in LLM generation: {e}")
                # Try with more aggressive truncation
                try:
                    logger.info("Retrying with more aggressive truncation")
                    prompt_tokens = estimate_tokens(prompt)
                    system_tokens = estimate_tokens(system) if system else 0
                    # Use only 60% of available space
                    safe_limit = int(self.max_context_tokens * 0.6)
                    
                    if system:
                        system = truncate_to_token_limit(system, safe_limit // 3)
                    prompt = truncate_to_token_limit(prompt, safe_limit // 3 * 2)
                    
                    messages = []
                    if system:
                        messages.append({"role": "system", "content": system})
                    messages.append({"role": "user", "content": prompt})
                    
                    response = self.client.chat(
                        model=self.model,
                        messages=messages,
                        options={
                            "temperature": temperature,
                            "num_predict": max_tokens if max_tokens else self.max_output_tokens // 2
                        }
                    )
                    return response['message']['content']
                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}")
                    return "I apologize, but the context is too large for me to process. Please try with a smaller query or fewer documents."
            
            logger.error(f"Error generating LLM response: {e}")
            raise
    
    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM."""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options={"temperature": temperature}
            )
            
            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise
    
    async def check_availability(self) -> bool:
        """Check if LLM model is available."""
        try:
            response = await self.generate("test", max_tokens=5)
            return len(response) > 0
        except Exception as e:
            logger.error(f"LLM model not available: {e}")
            return False
    
    # Prompt templates for different agent phases
    
    def create_plan_prompt(self, query: str) -> str:
        """Create prompt for the planning phase."""
        return f"""You are a planning agent. Analyze the following user query and create a retrieval strategy.

User Query: {query}

Create a plan that describes:
1. What information is needed to answer this query
2. What search terms or concepts to look for
3. What type of documents would be most relevant

Be specific and concise. Output only the plan."""
    
    def create_reason_prompt(self, query: str, retrieved_docs: str) -> str:
        """Create prompt for the reasoning phase."""
        return f"""You are a reasoning agent. Evaluate the retrieved information and determine if it's sufficient to answer the query.

User Query: {query}

Retrieved Information:
{retrieved_docs}

Analyze:
1. Is the information relevant to the query?
2. Is there enough information to provide a complete answer?
3. Are there any gaps or missing information?

Output your reasoning in a structured format."""
    
    def create_verify_prompt(self, query: str, answer: str, context: str) -> str:
        """Create prompt for verification phase."""
        return f"""You are a verification agent. Check if the answer is grounded in the provided context and detect any hallucinations.

User Query: {query}

Proposed Answer: {answer}

Context:
{context}

Verify:
1. Is every claim in the answer supported by the context?
2. Are there any fabricated or unsupported statements?
3. What is your confidence level (0.0-1.0)?

Output format:
Verified: [yes/no]
Confidence: [0.0-1.0]
Issues: [list any problems]"""
    
    def create_answer_prompt(self, query: str, context: str) -> str:
        """Create prompt for final answer generation."""
        system = """You are a helpful AI assistant. Answer the user's question based ONLY on the provided context. 
If the context doesn't contain enough information, say so. Always cite your sources by mentioning the relevant parts of the context."""
        
        prompt = f"""Context:
{context}

Question: {query}

Provide a clear, accurate answer based solely on the context above. Include citations where appropriate."""
        
        return prompt
    
    def create_refine_query_prompt(self, original_query: str, reasoning: str) -> str:
        """Create prompt for query refinement."""
        return f"""You are a query refinement agent. Based on the reasoning below, create a better search query.

Original Query: {original_query}

Reasoning: {reasoning}

Create a refined query that will retrieve more relevant information. Output only the refined query, nothing else."""


# Global LLM service instance
llm_service = LLMService()
