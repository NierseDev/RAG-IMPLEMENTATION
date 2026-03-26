"""
Document processing service using Docling.
"""
from typing import List, Tuple
from pathlib import Path
import hashlib
from docling.document_converter import DocumentConverter
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.models.entities import RAGChunk
from app.services.embedding import embedding_service
import logging

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Service for processing documents into chunks with embeddings."""
    
    def __init__(self):
        self.converter = DocumentConverter()
        self.chunk_size = settings.max_chunk_tokens  # Use safe chunk size
        self.chunk_overlap = settings.chunk_overlap
        logger.info(f"Document processor initialized (chunk_size={self.chunk_size}, overlap={self.chunk_overlap})")
    
    async def process_document(self, file_path: str, source: str) -> Tuple[List[RAGChunk], dict]:
        """
        Process a document into chunks with embeddings.
        Returns: (chunks, metadata)
        """
        try:
            # Convert document using Docling
            result = self.converter.convert(file_path)
            doc = result.document
            
            # Extract text content
            text_content = doc.export_to_markdown()
            
            # Create chunks with size validation
            chunks_text = self._create_chunks(text_content)
            
            # Validate chunk sizes before embedding
            validated_chunks = []
            for idx, chunk in enumerate(chunks_text):
                tokens = estimate_tokens(chunk)
                if tokens > settings.embedding_context_window:
                    logger.warning(f"Chunk {idx} ({tokens} tokens) exceeds embedding limit. Truncating.")
                    chunk = truncate_to_token_limit(chunk, settings.embedding_context_window - 10)
                validated_chunks.append(chunk)
            
            # Generate embeddings
            embeddings = await embedding_service.embed_batch(validated_chunks)
            
            # Create RAGChunk objects
            chunks = []
            for idx, (chunk_text, embedding) in enumerate(zip(validated_chunks, embeddings)):
                if not embedding:  # Skip if embedding failed
                    logger.warning(f"Skipping chunk {idx} due to embedding failure")
                    continue
                
                chunk_id = self._generate_chunk_id(source, idx, chunk_text)
                chunk = RAGChunk(
                    chunk_id=chunk_id,
                    source=source,
                    text=chunk_text,
                    ai_provider="ollama",
                    embedding_model=settings.ollama_embed_model,
                    embedding=embedding
                )
                chunks.append(chunk)
            
            metadata = {
                "total_chunks": len(chunks),
                "page_count": getattr(doc, 'page_count', None),
                "content_type": "document",
                "original_chunks": len(chunks_text),
                "successful_chunks": len(chunks)
            }
            
            logger.info(f"Processed document: {source} -> {len(chunks)} chunks (from {len(chunks_text)} attempted)")
            return chunks, metadata
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def _create_chunks(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.
        Ensures chunks stay within token limits.
        """
        # Approximate tokens as words (rough estimation: 1 token ≈ 0.75 words)
        avg_chars_per_token = 4
        chunk_chars = self.chunk_size * avg_chars_per_token
        overlap_chars = self.chunk_overlap * avg_chars_per_token
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_chars
            
            # Try to break at sentence or paragraph boundary
            if end < text_length:
                # Look for period, newline, or space near the end
                for boundary in ['. ', '\n\n', '\n', ' ']:
                    boundary_pos = text.rfind(boundary, start, end)
                    if boundary_pos > start + chunk_chars // 2:  # At least halfway
                        end = boundary_pos + len(boundary)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                # Double-check token count
                tokens = estimate_tokens(chunk)
                if tokens > self.chunk_size * 1.2:  # Allow 20% overage
                    logger.warning(f"Chunk exceeds target size ({tokens} > {self.chunk_size}), will be truncated")
                    chunk = truncate_to_token_limit(chunk, self.chunk_size)
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap_chars
            if start <= 0 or start >= text_length:
                break
        
        logger.info(f"Created {len(chunks)} chunks from {text_length} characters")
        return chunks
    
    def _generate_chunk_id(self, source: str, index: int, text: str) -> str:
        """Generate a unique chunk ID."""
        # Create hash from source and text
        content_hash = hashlib.md5(f"{source}:{text[:100]}".encode()).hexdigest()[:8]
        return f"{source}_chunk_{index}_{content_hash}"
    
    def validate_file(self, filename: str, file_size: int) -> Tuple[bool, str]:
        """Validate file before processing."""
        # Check file size
        if file_size > settings.max_file_size_bytes:
            return False, f"File too large. Max size: {settings.max_file_size_mb}MB"
        
        # Check extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in settings.allowed_extensions:
            return False, f"File type not supported. Allowed: {', '.join(settings.allowed_extensions)}"
        
        return True, "Valid"


# Global document processor instance
document_processor = DocumentProcessor()
