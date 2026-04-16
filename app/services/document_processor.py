"""
Document processing service using Docling.
Enhanced with semantic chunking, dynamic sizing, and metadata extraction (Sprint 3).
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import hashlib
import html
import re
from docling.document_converter import (
    DocumentConverter,
    HTMLFormatOption,
    ImageFormatOption,
    MarkdownFormatOption,
    PdfFormatOption,
    PowerpointFormatOption,
    WordFormatOption,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, OcrAutoOptions
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.core.hash_utils import compute_stream_hash, compute_bytes_hash
from app.core.database import get_supabase_client
from app.models.entities import RAGChunk
from app.services.embedding import embedding_service
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChunkFragment:
    """Normalized text fragment used for chunking."""

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_formula(self) -> bool:
        return self.metadata.get("content_type") == "formula"


class DocumentProcessor:
    """Service for processing documents into chunks with embeddings."""
    
    def __init__(self):
        self.converter = self._build_converter(lightweight=False)
        self.lightweight_pdf_converter = self._build_converter(lightweight=True)
        self.chunk_size = settings.max_chunk_tokens  # Use safe chunk size
        self.chunk_overlap = settings.chunk_overlap
        self.client = get_supabase_client()
        self.large_pdf_size_threshold = min(settings.max_file_size_bytes, 20 * 1024 * 1024)
        self.large_pdf_page_threshold = 80
        self.large_pdf_char_cap = 180_000
        
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

    def _build_converter(self, lightweight: bool = False) -> DocumentConverter:
        """Build a Docling converter tuned for richer text extraction."""
        try:
            pdf_options = self._build_pdf_pipeline_options(lightweight=lightweight)
            format_options = {
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pdf_options),
                InputFormat.HTML: HTMLFormatOption(),
                InputFormat.MD: MarkdownFormatOption(),
                InputFormat.DOCX: WordFormatOption(),
                InputFormat.PPTX: PowerpointFormatOption(),
            }
            return DocumentConverter(format_options=format_options)
        except Exception as e:
            logger.warning(f"Custom Docling configuration failed, using default converter: {e}")
            return DocumentConverter()

    def _build_pdf_pipeline_options(self, lightweight: bool = False) -> PdfPipelineOptions:
        """Build PDF pipeline options for either rich or memory-safe extraction."""
        if lightweight:
            return PdfPipelineOptions(
                do_ocr=False,
                do_formula_enrichment=True,
                do_code_enrichment=False,
                force_backend_text=True,
                generate_parsed_pages=False,
                ocr_options=OcrAutoOptions(
                    force_full_page_ocr=False,
                    bitmap_area_threshold=0.1,
                ),
            )

        return PdfPipelineOptions(
            do_ocr=True,
            do_formula_enrichment=True,
            do_code_enrichment=True,
            ocr_options=OcrAutoOptions(
                force_full_page_ocr=True,
                bitmap_area_threshold=0.02,
            ),
            generate_parsed_pages=False,
        )
    
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
        Sprint 5: Add memory-safe PDF processing and embedding failure handling
        """
        try:
            file_suffix = Path(file_path).suffix.lower()
            result = None
            text_content = ""
            max_chars = None

            if file_suffix == ".txt":
                text_content = self._read_plain_text_file(file_path)
                result = None
            elif file_suffix == ".pdf":
                # Sprint 5: Memory-safe PDF processing - pick a lighter path for large PDFs.
                try:
                    converter = self.lightweight_pdf_converter if self._should_use_lightweight_pdf(file_size) else self.converter
                    result = converter.convert(file_path)
                    doc = result.document
                    page_count = getattr(doc, 'page_count', 0)
                    if converter is self.lightweight_pdf_converter:
                        max_chars = self.large_pdf_char_cap
                    if page_count > self.large_pdf_page_threshold:
                        logger.warning(
                            f"PDF has {page_count} pages, truncating extracted text for memory safety"
                        )
                        max_chars = self.large_pdf_char_cap
                except MemoryError:
                    logger.warning(f"Memory error processing PDF: {source}. Retrying with lightweight PDF path.")
                    try:
                        result = self.lightweight_pdf_converter.convert(file_path)
                        doc = result.document
                        max_chars = self.large_pdf_char_cap
                    except Exception:
                        logger.error(f"Memory error processing PDF: {source}. File too large.")
                        raise
            
            if file_suffix != ".txt" and not result:
                raise ValueError("Document conversion failed")
            
            doc = result.document if result else None

            # Extract text content using the richest available representation.
            if doc:
                text_content, extraction_mode = self._extract_document_text(doc)
            else:
                extraction_mode = "plain-text"

            if not text_content.strip():
                raise ValueError("No text could be extracted from document")

            if max_chars and len(text_content) > max_chars:
                text_content = text_content[:max_chars]
                logger.info(f"Truncated content to {len(text_content)} characters for memory safety")

            logger.info(
                f"Extracted text for {source} using {extraction_mode} "
                f"({len(text_content)} characters)"
            )
            
            # Sprint 3: Extract metadata
            metadata = {}
            if self.metadata_extractor:
                try:
                    docling_meta = {
                        'page_count': getattr(doc, 'page_count', None) if doc else None,
                        'title': getattr(doc, 'title', None) if doc else Path(source).stem,
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
            fragments = self._create_chunk_fragments(text_content)
            chunks_text = self._create_chunks(fragments)
            
            # Validate chunk sizes before embedding
            validated_chunks = []
            for idx, chunk in enumerate(chunks_text):
                tokens = estimate_tokens(chunk["text"])
                if tokens > settings.embedding_context_window:
                    logger.warning(f"Chunk {idx} ({tokens} tokens) exceeds embedding limit. Truncating.")
                    chunk = {
                        "text": truncate_to_token_limit(chunk["text"], settings.embedding_context_window - 10),
                        "metadata": dict(chunk.get("metadata", {}))
                    }
                validated_chunks.append(chunk)
            
            # Generate embeddings with retry logic (Sprint 5: Improved failure handling)
            embeddings = await self._embed_batch_with_fallback([chunk["text"] for chunk in validated_chunks])
            
            # Create RAGChunk objects
            chunks = []
            skipped_chunks = 0
            for idx, (chunk_data, embedding) in enumerate(zip(validated_chunks, embeddings)):
                if not embedding:  # Skip if embedding failed
                    logger.warning(f"Skipping chunk {idx} due to embedding failure")
                    skipped_chunks += 1
                    continue
                
                chunk_text = chunk_data["text"]
                chunk_metadata = dict(chunk_data.get("metadata", {}))
                chunk_id = self._generate_chunk_id(source, idx, chunk_text)
                chunk = RAGChunk(
                    chunk_id=chunk_id,
                    source=source,
                    text=chunk_text,
                    ai_provider=settings.ai_provider,
                    embedding_model=settings.current_embedding_model,
                    embedding=embedding,
                    metadata=chunk_metadata
                )
                chunks.append(chunk)
            
            # Update metadata with processing results
            metadata.update({
                "total_chunks": len(chunks),
                "page_count": getattr(doc, 'page_count', None) if doc else None,
                "content_type": "document",
                "original_chunks": len(chunks_text),
                "successful_chunks": len(chunks),
                "chunking_method": self._get_chunking_method(),
                "text_extraction_mode": extraction_mode,
            })
            
            logger.info(f"Processed document: {source} -> {len(chunks)} chunks (from {len(chunks_text)} attempted)")
            return chunks, metadata
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise

    def _read_plain_text_file(self, file_path: str) -> str:
        """Read plain text files with a small encoding fallback set."""
        raw_bytes = Path(file_path).read_bytes()
        if not raw_bytes:
            return ""

        if b"\x00" in raw_bytes:
            raise ValueError("Binary content detected in plain text upload")

        for encoding in ("utf-8", "utf-8-sig", "utf-16", "cp1252", "latin-1"):
            try:
                text = raw_bytes.decode(encoding)
                normalized = self._normalize_extracted_text(text)
                if normalized:
                    return normalized
            except UnicodeDecodeError:
                continue

        raise ValueError("Unable to decode plain text file")

    def _extract_document_text(self, doc) -> Tuple[str, str]:
        """Extract the best text representation from a Docling document."""
        candidates = {
            "text": getattr(doc, "export_to_text", lambda: "")() or "",
            "markdown": getattr(doc, "export_to_markdown", lambda: "")() or "",
            "html": self._strip_html(getattr(doc, "export_to_html", lambda: "")() or ""),
        }

        best_mode = "markdown"
        best_text = ""
        best_score = -1

        for mode, candidate in candidates.items():
            normalized = self._normalize_extracted_text(candidate)
            score = self._score_extracted_text(normalized, mode)
            if score > best_score:
                best_mode = mode
                best_text = normalized
                best_score = score

        return best_text, best_mode

    def _normalize_extracted_text(self, text: str) -> str:
        """Normalize Docling output into clean chunkable text."""
        if not text:
            return ""

        normalized = html.unescape(text)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\u00a0", " ")
        normalized = re.sub(r"[ \t]+\n", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        normalized = re.sub(r"[ \t]{2,}", " ", normalized)
        return normalized.strip()

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from Docling HTML exports."""
        if not text:
            return ""

        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</\s*div\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return text

    def _score_extracted_text(self, text: str, mode: str) -> int:
        """Score a text candidate so the richest representation wins."""
        if not text:
            return 0

        word_count = len(re.findall(r"\b\w+\b", text))
        line_count = text.count("\n") + 1
        alpha_count = sum(1 for ch in text if ch.isalpha())
        structure_bonus = 0

        if mode == "markdown":
            structure_bonus += 8
        elif mode == "text":
            structure_bonus += 10
        elif mode == "html":
            structure_bonus += 2

        if "\n- " in text or "\n* " in text or "|" in text:
            structure_bonus += 4
        if "#" in text:
            structure_bonus += 3

        return (word_count * 4) + min(line_count, 40) + (alpha_count // 25) + structure_bonus

    def _should_use_lightweight_pdf(self, file_size: int) -> bool:
        """Decide when to use the lightweight PDF pipeline."""
        return file_size >= self.large_pdf_size_threshold

    def _create_chunk_fragments(self, text: str) -> List[ChunkFragment]:
        """Split normalized text into prose and formula-aware fragments."""
        if not text or not text.strip():
            return []

        fragments: List[ChunkFragment] = []
        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if not block:
                continue
            fragments.extend(self._split_fragment_block(block))
        return fragments

    def _split_fragment_block(self, block: str) -> List[ChunkFragment]:
        """Split a block into text and formula fragments."""
        formula_pattern = re.compile(
            r"(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\begin\{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*)\}[\s\S]+?\\end\{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*)\})",
            re.MULTILINE,
        )

        fragments: List[ChunkFragment] = []
        cursor = 0
        for match in formula_pattern.finditer(block):
            before = block[cursor:match.start()].strip()
            if before:
                fragments.append(ChunkFragment(before, {"content_type": "prose"}))

            formula_text = match.group(0).strip()
            fragments.append(ChunkFragment(formula_text, self._build_formula_metadata(formula_text)))
            cursor = match.end()

        tail = block[cursor:].strip()
        if tail:
            fragments.append(self._build_text_fragment(tail))

        if fragments:
            return fragments

        if self._looks_like_formula(block):
            return [ChunkFragment(block, self._build_formula_metadata(block))]

        return [self._build_text_fragment(block)]

    def _build_text_fragment(self, text: str) -> ChunkFragment:
        """Create a prose fragment with normalized metadata."""
        return ChunkFragment(text, {"content_type": "prose"})

    def _build_formula_metadata(self, text: str) -> Dict[str, Any]:
        """Create metadata for a standalone formula fragment."""
        return {
            "content_type": "formula",
            "is_formula": True,
            "formula_block": True,
            "formula_style": self._detect_formula_style(text),
            "token_estimate": estimate_tokens(text),
        }

    def _detect_formula_style(self, text: str) -> str:
        """Classify formula delimiter style."""
        stripped = text.strip()
        if stripped.startswith("$$") and stripped.endswith("$$"):
            return "display-math"
        if stripped.startswith("\\[") and stripped.endswith("\\]"):
            return "display-math"
        if stripped.startswith("\\begin{"):
            return "environment"
        return "heuristic"

    def _looks_like_formula(self, text: str) -> bool:
        """Heuristic formula detector for equation-only blocks."""
        stripped = text.strip()
        if not stripped:
            return False

        if self._detect_formula_style(stripped) != "heuristic":
            return True

        word_count = len(re.findall(r"\b\w+\b", stripped))
        symbol_count = sum(1 for ch in stripped if ch in "=^_±×÷∑∫∂→←≠≤≥√")
        latex_hits = len(re.findall(r"\\[A-Za-z]+", stripped))
        line_count = stripped.count("\n") + 1

        if word_count <= 40 and (symbol_count >= 2 or latex_hits >= 1):
            return True
        if line_count <= 3 and "=" in stripped and len(stripped) <= 180:
            return True
        return False
    
    def _get_chunking_method(self) -> str:
        """Get the current chunking method name."""
        if settings.use_dynamic_chunking and self.dynamic_chunker:
            return "dynamic"
        elif settings.use_semantic_chunking and self.semantic_chunker:
            return "semantic"
        else:
            return "fixed"
    
    def _create_chunks(self, fragments: List[ChunkFragment]) -> List[Dict[str, Any]]:
        """
        Split fragments into chunks with overlap.
        Sprint 3: Uses semantic or dynamic chunking if enabled.
        """
        # Try semantic chunking first
        if settings.use_semantic_chunking and self.semantic_chunker:
            try:
                chunks = self.semantic_chunker.chunk_fragments(fragments)
                logger.info(f"Used semantic chunking: {len(chunks)} chunks")
                return self._normalize_chunk_records(chunks)
            except Exception as e:
                logger.warning(f"Semantic chunking failed: {e}, falling back to default")
        
        # Try dynamic chunking
        if settings.use_dynamic_chunking and self.dynamic_chunker:
            try:
                chunk_tuples = self.dynamic_chunker.chunk_fragments(fragments)
                chunks = [chunk_text for chunk_text, meta in chunk_tuples]
                logger.info(f"Used dynamic chunking: {len(chunks)} chunks")
                return self._normalize_chunk_records(chunk_tuples)
            except Exception as e:
                logger.warning(f"Dynamic chunking failed: {e}, falling back to default")
        
        # Fall back to default fixed-size chunking
        return self._create_chunks_default(fragments)
    
    def _normalize_chunk_records(self, chunks: List[Any]) -> List[Dict[str, Any]]:
        """Normalize chunk outputs into text + metadata dictionaries."""
        normalized: List[Dict[str, Any]] = []
        for chunk in chunks:
            if isinstance(chunk, tuple):
                text, metadata = chunk
            elif isinstance(chunk, dict):
                text = chunk.get("text", "")
                metadata = chunk.get("metadata", {})
            else:
                text = str(chunk)
                metadata = {}
            normalized.append({
                "text": text.strip(),
                "metadata": dict(metadata or {})
            })
        return [chunk for chunk in normalized if chunk["text"]]

    def _finalize_chunk(self, fragments: List[ChunkFragment], chunk_type: str) -> Dict[str, Any]:
        """Join fragments into a persisted chunk record."""
        text = "\n\n".join(fragment.text.strip() for fragment in fragments if fragment.text.strip())
        metadata: Dict[str, Any] = {
            "content_type": chunk_type,
            "fragment_count": len(fragments),
            "contains_formula": any(fragment.is_formula for fragment in fragments),
        }
        if len(fragments) == 1:
            metadata.update(fragments[0].metadata)
        else:
            content_types = sorted({
                fragment.metadata.get("content_type", "unknown")
                for fragment in fragments
            })
            metadata["content_types"] = content_types
        return {"text": text, "metadata": metadata}

    def _create_chunks_default(self, fragments: List[ChunkFragment]) -> List[Dict[str, Any]]:
        """
        Default fixed-size chunking with overlap.
        Ensures chunks stay within token limits.
        """
        chunks: List[Dict[str, Any]] = []
        current_fragments: List[ChunkFragment] = []
        current_tokens = 0

        for fragment in fragments:
            text = fragment.text.strip()
            if not text:
                continue

            if fragment.is_formula:
                if current_fragments:
                    chunks.append(self._finalize_chunk(current_fragments, "prose"))
                    current_fragments = []
                    current_tokens = 0
                chunks.append(self._finalize_chunk([fragment], "formula"))
                continue

            fragment_tokens = estimate_tokens(text)
            if current_fragments and current_tokens + fragment_tokens > self.chunk_size:
                chunks.append(self._finalize_chunk(current_fragments, "prose"))
                current_fragments = []
                current_tokens = 0

            current_fragments.append(fragment)
            current_tokens += fragment_tokens

        if current_fragments:
            chunks.append(self._finalize_chunk(current_fragments, "prose"))

        logger.info(f"Created {len(chunks)} chunks from {len(fragments)} fragments")
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
    
    async def _embed_batch_with_fallback(self, chunks: List[str]) -> List:
        """
        Embed a batch of chunks with retry logic and fallback handling.
        Sprint 5: Improve embedding failure handling with retries.
        
        Args:
            chunks: List of text chunks to embed
            
        Returns:
            List of embeddings (None for failed chunks)
        """
        try:
            # Try primary embedding service
            embeddings = await embedding_service.embed_batch(chunks)
            
            # Check for failed embeddings and retry individually
            failed_indices = [i for i, e in enumerate(embeddings) if not e]
            if failed_indices:
                logger.warning(f"Failed to embed {len(failed_indices)} chunks, attempting individual retry")
                for idx in failed_indices:
                    try:
                        # Retry individual chunk with delay
                        import asyncio
                        await asyncio.sleep(0.5)  # Brief delay between retries
                        single_embedding = await embedding_service.embed_batch([chunks[idx]])
                        if single_embedding and single_embedding[0]:
                            embeddings[idx] = single_embedding[0]
                            logger.info(f"Successfully embedded chunk {idx} on retry")
                        else:
                            logger.warning(f"Chunk {idx} retry failed, will be skipped")
                    except Exception as e:
                        logger.warning(f"Retry failed for chunk {idx}: {e}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            # Return list of None values to indicate all failed
            return [None] * len(chunks)


# Global document processor instance
document_processor = DocumentProcessor()
