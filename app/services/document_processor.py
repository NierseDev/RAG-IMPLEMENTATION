"""
Document processing service using Docling.
Enhanced with semantic chunking, dynamic sizing, and metadata extraction (Sprint 3).
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import gc
import hashlib
import html
import re
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.core.hash_utils import compute_stream_hash, compute_bytes_hash
from app.models.entities import RAGChunk
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
        self.converter = None
        self.fallback_converter = None
        self.chunk_size = settings.max_chunk_tokens  # Use safe chunk size
        self.chunk_overlap = settings.chunk_overlap
        self._client = None
        
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

    @property
    def client(self):
        """Get the Supabase client lazily."""
        if self._client is None:
            from app.core.database import get_supabase_client
            self._client = get_supabase_client()
        return self._client

    def _build_converter(self):
        """Build a Docling converter tuned for rich text extraction."""
        try:
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
            from docling.datamodel.pipeline_options import PdfPipelineOptions, LayoutObjectDetectionOptions, RapidOcrOptions
            from docling.datamodel.object_detection_engine_options import OnnxRuntimeObjectDetectionEngineOptions

            pdf_options = self._build_pdf_pipeline_options()
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
            from docling.document_converter import DocumentConverter
            return DocumentConverter()

    def _build_fallback_converter(self):
        """Build a conservative Docling converter for problematic PDFs."""
        from docling.document_converter import DocumentConverter
        return DocumentConverter()

    def _build_pdf_pipeline_options(self):
        """Build the full-fidelity PDF pipeline options."""
        from docling.datamodel.pipeline_options import PdfPipelineOptions, LayoutObjectDetectionOptions, RapidOcrOptions
        from docling.datamodel.object_detection_engine_options import OnnxRuntimeObjectDetectionEngineOptions

        return PdfPipelineOptions(
            do_ocr=True,
            do_formula_enrichment=True,
            do_code_enrichment=True,
            layout_options=LayoutObjectDetectionOptions(
                engine_options=OnnxRuntimeObjectDetectionEngineOptions(
                    providers=["CPUExecutionProvider"],
                ),
                create_orphan_clusters=True,
                skip_cell_assignment=False,
                keep_empty_clusters=False,
            ),
            ocr_options=RapidOcrOptions(
                force_full_page_ocr=True,
                bitmap_area_threshold=0.02,
                rapidocr_params={"padding": True},
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
        Sprint 5: Stream uploads to disk and keep full-fidelity parsing for all supported formats
        """
        result = None
        doc = None
        try:
            file_suffix = Path(file_path).suffix.lower()
            text_content = ""

            if file_suffix == ".txt":
                text_content = self._read_plain_text_file(file_path)
            else:
                try:
                    result = self._get_converter().convert(file_path)
                except Exception as e:
                    if self._is_memory_pressure_error(e):
                        logger.error(
                            f"Memory pressure processing {source} with full-fidelity Docling; "
                            f"no lightweight fallback is used so tables and images stay intact."
                        )
                        raise

                    if file_suffix == ".pdf":
                        logger.warning(
                            f"Full-fidelity Docling PDF conversion failed for {source}; "
                            f"retrying with conservative fallback: {e}"
                        )
                        try:
                            result = self._get_fallback_converter().convert(file_path)
                        except Exception as fallback_error:
                            logger.error(
                                f"Fallback Docling PDF conversion failed for {source}: {fallback_error}"
                            )
                            raise fallback_error from e
                    else:
                        raise

                if not result:
                    raise ValueError("Document conversion failed")

                doc = result.document
                if not doc:
                    raise ValueError("Document conversion returned no document")

            # Extract text content using the richest available representation.
            if doc:
                text_content, extraction_mode = self._extract_document_text(doc)
            else:
                extraction_mode = "plain-text"

            if not text_content.strip():
                raise ValueError("No text could be extracted from document")

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
        finally:
            # Docling/pdfium objects need to be released before interpreter teardown.
            result = None
            doc = None
            gc.collect()

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
        candidates = [
            ("text", self._safe_export_docling_text(doc, "export_to_text")),
            ("markdown", self._safe_export_docling_text(doc, "export_to_markdown")),
            ("html", self._safe_export_docling_text(doc, "export_to_html", strip_html=True)),
        ]

        best_mode = "markdown"
        best_text = ""
        best_score = -1

        for mode, candidate in candidates:
            normalized = self._normalize_extracted_text(candidate)
            score = self._score_extracted_text(normalized, mode)
            if score > best_score:
                best_mode = mode
                best_text = normalized
                best_score = score

        return best_text, best_mode

    def _safe_export_docling_text(
        self,
        doc,
        export_method: str,
        strip_html: bool = False
    ) -> str:
        """Export Docling text without failing the whole ingest on one bad representation."""
        exporter = getattr(doc, export_method, None)
        if not callable(exporter):
            return ""

        try:
            text = exporter() or ""
        except Exception as e:
            logger.warning(f"Docling {export_method} failed; skipping representation: {e}")
            return ""

        if strip_html:
            text = self._strip_html(text)

        return text

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

    def _is_memory_pressure_error(self, error: Exception) -> bool:
        """Detect Docling failures caused by memory pressure."""
        if isinstance(error, MemoryError):
            return True

        message = str(error).lower()
        return any(token in message for token in (
            "bad_alloc",
            "std::bad_alloc",
            "memoryerror",
            "memory error",
            "out of memory",
            "cannot allocate memory",
            "alloc",
        ))

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
        last_formula_fragment: Optional[ChunkFragment] = None
        for match in formula_pattern.finditer(block):
            before = block[cursor:match.start()].strip()
            if before:
                fragments.append(ChunkFragment(before, {"content_type": "prose"}))

            formula_text = match.group(0).strip()
            formula_fragment = ChunkFragment(
                formula_text,
                self._build_formula_metadata(formula_text, context_before=before or None),
            )
            fragments.append(formula_fragment)
            last_formula_fragment = formula_fragment
            cursor = match.end()

        tail = block[cursor:].strip()
        if tail:
            fragments.append(self._build_text_fragment(tail))
            if last_formula_fragment is not None:
                last_formula_fragment.metadata["formula_context_after"] = self._shorten_formula_context(tail)

        if fragments:
            return fragments

        if self._looks_like_formula(block):
            return [ChunkFragment(block, self._build_formula_metadata(block))]

        return [self._build_text_fragment(block)]

    def _build_text_fragment(self, text: str) -> ChunkFragment:
        """Create a prose fragment with normalized metadata."""
        return ChunkFragment(text, {"content_type": "prose"})

    def _build_formula_metadata(
        self,
        text: str,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create metadata for a standalone formula fragment."""
        metadata = {
            "content_type": "formula",
            "is_formula": True,
            "formula_block": True,
            "formula_style": self._detect_formula_style(text),
            "token_estimate": estimate_tokens(text),
        }
        if context_before:
            metadata["formula_context_before"] = self._shorten_formula_context(context_before)
        if context_after:
            metadata["formula_context_after"] = self._shorten_formula_context(context_after)
        return metadata

    def _shorten_formula_context(self, text: str, max_tokens: int = 60) -> str:
        """Keep formula context compact while preserving the local source relation."""
        normalized = self._normalize_extracted_text(text)
        return truncate_to_token_limit(normalized, max_tokens)

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
            from app.services.embedding import embedding_service

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

    def _get_converter(self):
        """Lazily initialize the Docling converter."""
        if self.converter is None:
            self.converter = self._build_converter()
        return self.converter

    def _get_fallback_converter(self):
        """Lazily initialize the conservative PDF fallback converter."""
        if self.fallback_converter is None:
            self.fallback_converter = self._build_fallback_converter()
        return self.fallback_converter


# Global document processor instance
document_processor = DocumentProcessor()
