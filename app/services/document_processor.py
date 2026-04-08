"""
Document processing service using Docling.
Enhanced with semantic chunking, dynamic sizing, and metadata extraction (Sprint 3).
"""
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import hashlib
from docling.document_converter import DocumentConverter
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.core.hash_utils import compute_stream_hash, compute_bytes_hash
from app.core.database import get_supabase_client
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
        self.client = get_supabase_client()
        
        # Sprint 3: Load advanced chunking and metadata services
        self.semantic_chunker = None
        self.dynamic_chunker = None
        self.metadata_extractor = None
        
        if settings.use_semantic_chunking:
            try:
                from app.services.semantic_chunker import semantic_chunker
                self.semantic_chunker = semantic_chunker
                logger.info("Semantic chunking enabled")
            except ImportError:
                logger.warning("Semantic chunker not available, using default chunking")
        
        if settings.use_dynamic_chunking:
            try:
                from app.services.dynamic_chunker import dynamic_chunker
                self.dynamic_chunker = dynamic_chunker
                logger.info("Dynamic chunking enabled")
            except ImportError:
                logger.warning("Dynamic chunker not available")
        
        try:
            from app.services.metadata_extractor import metadata_extractor
            self.metadata_extractor = metadata_extractor
            logger.info("Metadata extraction enabled")
        except ImportError:
            logger.warning("Metadata extractor not available")
        
        logger.info(f"Document processor initialized (chunk_size={self.chunk_size}, overlap={self.chunk_overlap})")
    
    async def process_document(
        self,
        file_path: str,
        source: str,
        file_size: int = 0
    ) -> Tuple[List[RAGChunk], dict]:
        """
        Process a document into chunks with embeddings.
        Returns: (chunks, metadata)
        
        Sprint 3: Enhanced with semantic chunking and metadata extraction
        """
        try:
            # Convert document using Docling
            result = self.converter.convert(file_path)
            doc = result.document
            
            # Extract text content
            text_content = doc.export_to_markdown()
            
            # Sprint 3: Extract metadata
            metadata = {}
            if self.metadata_extractor:
                try:
                    docling_meta = {
                        'page_count': getattr(doc, 'page_count', None),
                        'title': getattr(doc, 'title', None),
                    }
                    metadata = self.metadata_extractor.extract(
                        text=text_content,
                        filename=source,
                        file_size=file_size,
                        docling_metadata=docling_meta
                    )
                    logger.info(f"Extracted metadata: {list(metadata.keys())}")
                except Exception as e:
                    logger.warning(f"Metadata extraction failed: {e}")
                    metadata = {"error": str(e)}
            
            # Create chunks with advanced chunking if available
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
                    ai_provider=settings.ai_provider,
                    embedding_model=settings.current_embedding_model,
                    embedding=embedding
                )
                chunks.append(chunk)
            
            # Update metadata with processing results
            metadata.update({
                "total_chunks": len(chunks),
                "page_count": getattr(doc, 'page_count', None),
                "content_type": "document",
                "original_chunks": len(chunks_text),
                "successful_chunks": len(chunks),
                "chunking_method": self._get_chunking_method()
            })
            
            logger.info(f"Processed document: {source} -> {len(chunks)} chunks (from {len(chunks_text)} attempted)")
            return chunks, metadata
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def _get_chunking_method(self) -> str:
        """Get the current chunking method name."""
        if settings.use_dynamic_chunking and self.dynamic_chunker:
            return "dynamic"
        elif settings.use_semantic_chunking and self.semantic_chunker:
            return "semantic"
        else:
            return "fixed"
    
    def _create_chunks(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.
        Sprint 3: Uses semantic or dynamic chunking if enabled.
        """
        # Try semantic chunking first
        if settings.use_semantic_chunking and self.semantic_chunker:
            try:
                chunks = self.semantic_chunker.chunk(text, preserve_structure=True)
                logger.info(f"Used semantic chunking: {len(chunks)} chunks")
                return chunks
            except Exception as e:
                logger.warning(f"Semantic chunking failed: {e}, falling back to default")
        
        # Try dynamic chunking
        if settings.use_dynamic_chunking and self.dynamic_chunker:
            try:
                chunk_tuples = self.dynamic_chunker.chunk_with_density(text)
                chunks = [chunk_text for chunk_text, meta in chunk_tuples]
                logger.info(f"Used dynamic chunking: {len(chunks)} chunks")
                return chunks
            except Exception as e:
                logger.warning(f"Dynamic chunking failed: {e}, falling back to default")
        
        # Fall back to default fixed-size chunking
        return self._create_chunks_default(text)
    
    def _create_chunks_default(self, text: str) -> List[str]:
        """
        Default fixed-size chunking with overlap.
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
    
    async def check_duplicate(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Check if a file with the same hash already exists.
        
        Args:
            file_hash: SHA-256 hash of the file
            
        Returns:
            Existing document record if found, None otherwise
        """
        try:
            result = self.client.table('documents_registry') \
                .select('*') \
                .eq('file_hash', file_hash) \
                .execute()
            
            if result.data and len(result.data) > 0:
                logger.info(f"Found duplicate document with hash {file_hash[:16]}...")
                return result.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking for duplicate: {e}")
            return None
    
    async def handle_duplicate(
        self, 
        file_hash: str, 
        filename: str, 
        mode: str = 'skip'
    ) -> Dict[str, Any]:
        """
        Handle duplicate file upload based on mode.
        
        Args:
            file_hash: SHA-256 hash of the file
            filename: Name of the file
            mode: 'skip', 'replace', or 'append'
            
        Returns:
            Action result dictionary
        """
        existing = await self.check_duplicate(file_hash)
        
        if not existing:
            return {
                "action": "proceed",
                "message": "No duplicate found, proceed with upload"
            }
        
        if mode == 'skip':
            return {
                "action": "skipped",
                "document_id": existing['id'],
                "message": f"Skipped: File already exists (uploaded on {existing['upload_date']})"
            }
        
        elif mode == 'replace':
            # Delete old document and its chunks (CASCADE)
            try:
                self.client.table('documents_registry') \
                    .delete() \
                    .eq('id', existing['id']) \
                    .execute()
                
                logger.info(f"Replaced existing document {existing['id']}")
                return {
                    "action": "replaced",
                    "old_document_id": existing['id'],
                    "message": f"Replaced existing file"
                }
                
            except Exception as e:
                logger.error(f"Error replacing document: {e}")
                return {
                    "action": "error",
                    "message": f"Failed to replace: {str(e)}"
                }
        
        elif mode == 'append':
            # Allow duplicate but with different source name
            new_filename = self._generate_unique_filename(filename, existing['filename'])
            return {
                "action": "append",
                "new_filename": new_filename,
                "message": f"Appending as {new_filename}"
            }
        
        else:
            return {
                "action": "error",
                "message": f"Invalid duplicate mode: {mode}"
            }
    
    def _generate_unique_filename(self, filename: str, existing_filename: str) -> str:
        """Generate a unique filename by adding a counter."""
        path = Path(filename)
        stem = path.stem
        suffix = path.suffix
        counter = 1
        
        # Extract counter from existing filename if present
        if '_v' in existing_filename:
            try:
                parts = existing_filename.rsplit('_v', 1)
                if len(parts) == 2:
                    counter = int(parts[1].split('.')[0]) + 1
            except:
                pass
        
        return f"{stem}_v{counter}{suffix}"


# Global document processor instance
document_processor = DocumentProcessor()
