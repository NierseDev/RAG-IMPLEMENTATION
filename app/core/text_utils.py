"""
Utility functions for text processing and token management.
"""
import re
from typing import List
import logging

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text.
    Uses a simple heuristic: ~1 token per 4 characters or 0.75 words.
    
    This is a rough approximation. For production, consider using
    tiktoken or the model's actual tokenizer.
    """
    # Count words and characters
    words = len(text.split())
    chars = len(text)
    
    # Use average of both methods
    token_estimate = int((words * 1.3 + chars / 4) / 2)
    return max(1, token_estimate)


def truncate_to_token_limit(text: str, max_tokens: int, reserve_tokens: int = 0) -> str:
    """
    Truncate text to fit within token limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens allowed
        reserve_tokens: Tokens to reserve for other content
        
    Returns:
        Truncated text that fits within the limit
    """
    available_tokens = max_tokens - reserve_tokens
    
    if available_tokens <= 0:
        logger.warning("No tokens available after reserving space")
        return ""
    
    current_tokens = estimate_tokens(text)
    
    if current_tokens <= available_tokens:
        return text
    
    # Calculate target character count
    ratio = available_tokens / current_tokens
    target_chars = int(len(text) * ratio * 0.95)  # 5% safety buffer
    
    # Truncate at sentence boundary if possible
    truncated = text[:target_chars]
    
    # Try to end at a sentence
    last_period = truncated.rfind('. ')
    last_newline = truncated.rfind('\n\n')
    
    if last_period > target_chars * 0.5:
        truncated = truncated[:last_period + 1]
    elif last_newline > target_chars * 0.5:
        truncated = truncated[:last_newline]
    
    logger.info(f"Truncated text from {current_tokens} to ~{estimate_tokens(truncated)} tokens")
    return truncated + "..."


def split_text_to_fit(text: str, max_tokens: int) -> List[str]:
    """
    Split text into chunks that fit within token limit.
    
    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        
    Returns:
        List of text chunks
    """
    if estimate_tokens(text) <= max_tokens:
        return [text]
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        
        # If single paragraph is too large, split it further
        if para_tokens > max_tokens:
            # If we have accumulated text, save it
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            # Split the large paragraph by sentences
            sentences = re.split(r'([.!?]+\s+)', para)
            sentence_chunk = []
            sentence_tokens = 0
            
            for sentence in sentences:
                s_tokens = estimate_tokens(sentence)
                if sentence_tokens + s_tokens > max_tokens:
                    if sentence_chunk:
                        chunks.append(''.join(sentence_chunk))
                        sentence_chunk = []
                        sentence_tokens = 0
                sentence_chunk.append(sentence)
                sentence_tokens += s_tokens
            
            if sentence_chunk:
                chunks.append(''.join(sentence_chunk))
        
        # Check if adding this paragraph exceeds limit
        elif current_tokens + para_tokens > max_tokens:
            # Save current chunk and start new one
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_tokens = para_tokens
        else:
            # Add to current chunk
            current_chunk.append(para)
            current_tokens += para_tokens
    
    # Add remaining chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    logger.info(f"Split text into {len(chunks)} chunks (max {max_tokens} tokens each)")
    return chunks


def validate_text_length(text: str, max_tokens: int, context: str = "") -> bool:
    """
    Validate that text fits within token limit.
    
    Args:
        text: Text to validate
        max_tokens: Maximum allowed tokens
        context: Context string for logging
        
    Returns:
        True if valid, False otherwise
    """
    tokens = estimate_tokens(text)
    
    if tokens > max_tokens:
        logger.warning(
            f"{context} Text length ({tokens} tokens) exceeds limit ({max_tokens} tokens)"
        )
        return False
    
    return True


def safe_truncate_chunks(chunks: List[str], max_total_tokens: int) -> List[str]:
    """
    Truncate a list of chunks to fit within total token budget.
    Keeps the most important chunks (assumes they're sorted by relevance).
    
    Args:
        chunks: List of text chunks
        max_total_tokens: Maximum total tokens across all chunks
        
    Returns:
        Truncated list of chunks
    """
    if not chunks:
        return []
    
    result = []
    total_tokens = 0
    
    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk)
        
        if total_tokens + chunk_tokens <= max_total_tokens:
            result.append(chunk)
            total_tokens += chunk_tokens
        else:
            # Try to fit a truncated version
            remaining_tokens = max_total_tokens - total_tokens
            if remaining_tokens > 100:  # Only if we have meaningful space left
                truncated = truncate_to_token_limit(chunk, remaining_tokens)
                if truncated:
                    result.append(truncated)
            break
    
    logger.info(f"Kept {len(result)}/{len(chunks)} chunks (~{total_tokens} tokens)")
    return result
