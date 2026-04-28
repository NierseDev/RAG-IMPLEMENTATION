"""
Context budget calculator for optimizing chunk retrieval.
Determines optimal number of chunks based on model context window and query complexity.
"""
from typing import Optional, Dict, Any
from app.core.text_utils import estimate_tokens
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class ContextOptimizer:
    """
    Optimizes context window usage for RAG queries.
    Calculates optimal number of chunks to retrieve based on:
    - Model context window size
    - Query complexity
    - System prompt overhead
    - Response generation budget
    """
    
    def __init__(
        self,
        model_context_window: Optional[int] = None,
        system_prompt_overhead: int = 500,
        response_budget: int = 1000,
        safety_margin: float = 0.1
    ):
        self.model_context_window = model_context_window or settings.llm_context_window
        self.system_prompt_overhead = system_prompt_overhead
        self.response_budget = response_budget
        self.safety_margin = safety_margin
        
        # Calculate available context budget
        self.available_context = int(
            (self.model_context_window - system_prompt_overhead - response_budget) * (1 - safety_margin)
        )
        
        logger.info(f"ContextOptimizer initialized (window={self.model_context_window}, available={self.available_context})")
    
    def calculate_optimal_top_k(
        self,
        query: str,
        avg_chunk_tokens: Optional[int] = None,
        query_complexity: Optional[float] = None
    ) -> int:
        """
        Calculate optimal number of chunks (top_k) to retrieve.
        
        Args:
            query: The user query
            avg_chunk_tokens: Average tokens per chunk (estimated if not provided)
            query_complexity: Query complexity score 0.0-1.0 (calculated if not provided)
            
        Returns:
            Optimal top_k value
        """
        # Estimate query tokens
        query_tokens = estimate_tokens(query)
        
        # Calculate query complexity if not provided
        if query_complexity is None:
            query_complexity = self._calculate_query_complexity(query)
        
        # Estimate average chunk size if not provided
        if avg_chunk_tokens is None:
            avg_chunk_tokens = settings.max_chunk_tokens
        
        # Calculate remaining budget after query
        remaining_budget = self.available_context - query_tokens
        
        # Adjust for query complexity:
        # - Simple queries: fewer chunks, more focused
        # - Complex queries: more chunks, broader context
        complexity_multiplier = 0.7 + (query_complexity * 0.6)  # Range: 0.7 to 1.3
        
        # Calculate top_k
        optimal_top_k = int((remaining_budget * complexity_multiplier) / avg_chunk_tokens)
        
        # Apply bounds
        min_k = settings.min_retrieval_chunks if hasattr(settings, 'min_retrieval_chunks') else 3
        max_k = settings.max_retrieval_chunks if hasattr(settings, 'max_retrieval_chunks') else 20
        optimal_top_k = max(min_k, min(optimal_top_k, max_k))
        
        logger.info(f"Optimal top_k={optimal_top_k} (query_tokens={query_tokens}, complexity={query_complexity:.2f})")
        return optimal_top_k
    
    def estimate_context_fit(
        self,
        query: str,
        chunks: list,
        include_reasoning: bool = True
    ) -> Dict[str, Any]:
        """
        Estimate if chunks will fit within context window.
        
        Returns:
            {
                'fits': bool,
                'total_tokens': int,
                'available_tokens': int,
                'chunks_that_fit': int,
                'overflow_tokens': int
            }
        """
        query_tokens = estimate_tokens(query)
        
        # Calculate chunk tokens
        chunk_tokens = sum(estimate_tokens(str(chunk)) for chunk in chunks)
        
        # Add reasoning overhead if enabled
        reasoning_overhead = 300 if include_reasoning else 0
        
        # Total tokens needed
        total_tokens = (
            self.system_prompt_overhead +
            query_tokens +
            chunk_tokens +
            reasoning_overhead +
            self.response_budget
        )
        
        fits = total_tokens <= self.model_context_window
        overflow = max(0, total_tokens - self.model_context_window)
        
        # Calculate how many chunks fit
        chunks_that_fit = len(chunks)
        if not fits:
            # Binary search to find how many fit
            accumulated = self.system_prompt_overhead + query_tokens + reasoning_overhead + self.response_budget
            for i, chunk in enumerate(chunks):
                accumulated += estimate_tokens(str(chunk))
                if accumulated > self.model_context_window:
                    chunks_that_fit = i
                    break
        
        return {
            'fits': fits,
            'total_tokens': total_tokens,
            'available_tokens': self.model_context_window,
            'chunks_that_fit': chunks_that_fit,
            'overflow_tokens': overflow,
            'utilization': total_tokens / self.model_context_window
        }
    
    def _calculate_query_complexity(self, query: str) -> float:
        """
        Calculate query complexity score (0.0 = simple, 1.0 = complex).
        
        Factors:
        - Query length
        - Number of concepts (question words, entities)
        - Specificity indicators
        - Multiple sub-questions
        """
        # Length score
        words = query.split()
        length_score = min(len(words) / 30.0, 1.0)  # Normalize to 0-1
        
        # Question words indicate complexity
        question_words = ['what', 'why', 'how', 'when', 'where', 'who', 'which', 'compare', 'explain', 'describe']
        question_count = sum(1 for word in question_words if word in query.lower())
        question_score = min(question_count / 3.0, 1.0)
        
        # Multiple sentences/questions
        sentences = [s.strip() for s in query.split('?') if s.strip()]
        multi_question_score = min(len(sentences) / 3.0, 1.0)
        
        # Technical terms (numbers, caps, specific keywords)
        technical_count = sum(1 for word in words if any(c.isdigit() or c.isupper() for c in word))
        technical_score = min(technical_count / len(words), 1.0) if words else 0.0
        
        # Weighted combination
        complexity = (
            length_score * 0.3 +
            question_score * 0.3 +
            multi_question_score * 0.2 +
            technical_score * 0.2
        )
        
        return min(complexity, 1.0)
    
    def adjust_for_iteration(self, base_top_k: int, iteration: int, max_iterations: int) -> int:
        """
        Adjust top_k for iterative retrieval.
        Later iterations may need more or fewer chunks based on confidence.
        """
        if iteration == 1:
            return base_top_k
        
        # Increase slightly in later iterations to gather more context
        iteration_ratio = iteration / max_iterations
        adjusted = int(base_top_k * (1 + iteration_ratio * 0.3))  # Up to 30% increase
        
        max_k = settings.max_retrieval_chunks if hasattr(settings, 'max_retrieval_chunks') else 20
        return min(adjusted, max_k)


# Global instance
context_optimizer = ContextOptimizer()
