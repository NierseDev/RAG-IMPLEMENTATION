"""
Dynamic chunk sizing service that adjusts chunk size based on content density.
Optimizes for token limits and retrieval effectiveness.
"""
from typing import List, Tuple, Optional
from app.core.text_utils import estimate_tokens
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class DynamicChunker:
    """
    Dynamic chunking that adjusts chunk size based on:
    - Content density (information-rich vs sparse)
    - Token limits for embedding models
    - Retrieval optimization (balance between context and precision)
    """
    
    def __init__(
        self,
        min_chunk_size: int = 200,
        target_chunk_size: Optional[int] = None,
        max_chunk_size: Optional[int] = None,
        density_threshold: float = 0.5
    ):
        self.min_chunk_size = min_chunk_size
        self.target_chunk_size = target_chunk_size or settings.max_chunk_tokens
        self.max_chunk_size = max_chunk_size or settings.embedding_context_window
        self.density_threshold = density_threshold
        logger.info(f"DynamicChunker initialized (min={min_chunk_size}, target={self.target_chunk_size}, max={self.max_chunk_size})")
    
    def chunk_with_density(self, text: str, semantic_units: Optional[List[str]] = None) -> List[Tuple[str, dict]]:
        """
        Chunk text with dynamic sizing based on content density.
        
        Args:
            text: The text to chunk
            semantic_units: Pre-split semantic units (optional)
            
        Returns:
            List of (chunk_text, metadata) tuples where metadata includes:
                - token_count: Number of tokens
                - density_score: Content density score
                - chunk_type: "dense" or "sparse"
        """
        if semantic_units is None:
            # Simple paragraph splitting
            semantic_units = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        current_density = 0.0
        
        for unit in semantic_units:
            unit_tokens = estimate_tokens(unit)
            unit_density = self._calculate_density(unit)
            
            # Determine target size based on density
            if unit_density > self.density_threshold:
                # Dense content: use smaller chunks for better precision
                adaptive_target = int(self.target_chunk_size * 0.7)
            else:
                # Sparse content: use larger chunks for more context
                adaptive_target = int(self.target_chunk_size * 1.2)
            
            # Ensure within bounds
            adaptive_target = max(self.min_chunk_size, min(adaptive_target, self.max_chunk_size))
            
            # Check if we should start a new chunk
            if current_tokens + unit_tokens > adaptive_target and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunk_density = current_density / len(current_chunk) if current_chunk else 0.0
                chunks.append((chunk_text, {
                    'token_count': current_tokens,
                    'density_score': chunk_density,
                    'chunk_type': 'dense' if chunk_density > self.density_threshold else 'sparse'
                }))
                
                current_chunk = []
                current_tokens = 0
                current_density = 0.0
            
            # Add unit to current chunk
            current_chunk.append(unit)
            current_tokens += unit_tokens
            current_density += unit_density
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk_density = current_density / len(current_chunk) if current_chunk else 0.0
            chunks.append((chunk_text, {
                'token_count': current_tokens,
                'density_score': chunk_density,
                'chunk_type': 'dense' if chunk_density > self.density_threshold else 'sparse'
            }))
        
        logger.info(f"Created {len(chunks)} dynamic chunks (avg tokens: {sum(c[1]['token_count'] for c in chunks) / len(chunks):.0f})")
        return chunks
    
    def _calculate_density(self, text: str) -> float:
        """
        Calculate content density score based on:
        - Unique word ratio
        - Average word length
        - Presence of technical terms
        - Sentence complexity
        
        Returns score between 0.0 and 1.0
        """
        if not text:
            return 0.0
        
        words = text.lower().split()
        if not words:
            return 0.0
        
        # Unique word ratio
        unique_ratio = len(set(words)) / len(words)
        
        # Average word length (longer words = more technical/dense)
        avg_word_length = sum(len(w) for w in words) / len(words)
        length_score = min(avg_word_length / 10.0, 1.0)  # Normalize to 0-1
        
        # Technical term indicators (numbers, caps, special chars)
        technical_count = sum(1 for w in words if any(c.isdigit() or c.isupper() for c in w))
        technical_ratio = technical_count / len(words)
        
        # Sentence complexity (words per sentence)
        sentences = [s for s in text.split('.') if s.strip()]
        words_per_sentence = len(words) / len(sentences) if sentences else 0
        complexity_score = min(words_per_sentence / 20.0, 1.0)  # Normalize to 0-1
        
        # Weighted combination
        density = (
            unique_ratio * 0.3 +
            length_score * 0.3 +
            technical_ratio * 0.2 +
            complexity_score * 0.2
        )
        
        return min(density, 1.0)
    
    def optimize_chunk_boundaries(self, chunks: List[str]) -> List[str]:
        """
        Optimize chunk boundaries by merging small chunks and splitting large ones.
        """
        optimized = []
        i = 0
        
        while i < len(chunks):
            chunk = chunks[i]
            chunk_tokens = estimate_tokens(chunk)
            
            # If chunk is too small, try to merge with next
            if chunk_tokens < self.min_chunk_size and i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                merged = chunk + '\n\n' + next_chunk
                merged_tokens = estimate_tokens(merged)
                
                if merged_tokens <= self.max_chunk_size:
                    optimized.append(merged)
                    i += 2
                    continue
            
            # If chunk is too large, split it
            if chunk_tokens > self.max_chunk_size:
                # Simple split by paragraphs
                paragraphs = chunk.split('\n\n')
                sub_chunk = []
                sub_tokens = 0
                
                for para in paragraphs:
                    para_tokens = estimate_tokens(para)
                    if sub_tokens + para_tokens > self.target_chunk_size and sub_chunk:
                        optimized.append('\n\n'.join(sub_chunk))
                        sub_chunk = []
                        sub_tokens = 0
                    sub_chunk.append(para)
                    sub_tokens += para_tokens
                
                if sub_chunk:
                    optimized.append('\n\n'.join(sub_chunk))
            else:
                optimized.append(chunk)
            
            i += 1
        
        return optimized


# Global instance
dynamic_chunker = DynamicChunker()
