"""
Semantic chunking service that respects document structure.
Implements intelligent chunking based on paragraphs, sections, and headings.
"""
from typing import List, Tuple, Optional, Dict, Any
import re
from app.core.text_utils import estimate_tokens
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Semantic chunking that respects document structure instead of fixed-size splitting.
    Prioritizes keeping semantic units together (paragraphs, sections, lists).
    """
    
    def __init__(
        self,
        target_chunk_size: Optional[int] = None,
        max_chunk_size: Optional[int] = None,
        min_chunk_size: int = 100
    ):
        self.target_chunk_size = target_chunk_size or settings.max_chunk_tokens
        self.max_chunk_size = max_chunk_size or int(self.target_chunk_size * 1.5)
        self.min_chunk_size = min_chunk_size
        logger.info(f"SemanticChunker initialized (target={self.target_chunk_size}, max={self.max_chunk_size})")
    
    def chunk(self, text: str, preserve_structure: bool = True) -> List[str]:
        """
        Chunk text semantically, respecting document structure.
        
        Args:
            text: The text to chunk
            preserve_structure: Whether to preserve paragraph and section boundaries
            
        Returns:
            List of semantically coherent text chunks
        """
        if not text or not text.strip():
            return []
        
        # Split into semantic units
        units = self._split_into_semantic_units(text) if preserve_structure else [text]
        chunks = self.chunk_fragments(
            [{"text": unit, "metadata": self._build_unit_metadata(unit)} for unit in units]
        )
        
        # Post-process: handle oversized chunks
        final_chunks = []
        for chunk_text, chunk_meta in chunks:
            if chunk_meta.get("content_type") == "formula":
                final_chunks.append(chunk_text)
                continue

            if estimate_tokens(chunk_text) > self.max_chunk_size:
                # Split oversized chunk with overlap
                sub_chunks = self._split_oversized_chunk(chunk_text)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk_text)
        
        logger.info(f"Created {len(final_chunks)} semantic chunks from {len(units)} units")
        return [c.strip() for c in final_chunks if c.strip()]

    def chunk_fragments(self, fragments: List[Dict[str, Any]]) -> List[Tuple[str, dict]]:
        """Chunk pre-split fragments while keeping formulas atomic."""
        if not fragments:
            return []

        units = [self._normalize_fragment(fragment) for fragment in fragments]
        units = [unit for unit in units if unit["text"]]
        return self._group_units_into_chunks(units)
    
    def _split_into_semantic_units(self, text: str) -> List[str]:
        """
        Split text into semantic units: headings, paragraphs, lists, code blocks.
        """
        units = []
        
        # Patterns for different semantic units
        # 1. Markdown headings
        heading_pattern = r'^#{1,6}\s+.+$'
        
        # 2. Lists (bullet points, numbered)
        list_pattern = r'^[\s]*[-*+•]\s+.+$|^[\s]*\d+\.\s+.+$'
        
        # 3. Code blocks
        code_block_pattern = r'```[\s\S]*?```|`[^`]+`'
        formula_pattern = r'(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\begin\{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*)\}[\s\S]+?\\end\{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*)\})'
        
        # Split by double newlines (paragraph boundaries)
        paragraphs = re.split(r'\n\s*\n', text)
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if it's a heading
            if re.match(heading_pattern, para, re.MULTILINE):
                units.append(para)
                continue
            
            # Check if it's a code block
            if re.search(code_block_pattern, para):
                units.append(para)
                continue

            # Check if it's a display formula or equation block
            if re.search(formula_pattern, para, re.MULTILINE) or self._is_formula_unit(para):
                units.append(para)
                continue
            
            # Check if it's a list
            lines = para.split('\n')
            if all(re.match(list_pattern, line) for line in lines if line.strip()):
                units.append(para)
                continue
            
            # Regular paragraph
            units.append(para)
        
        return units
    
    def _normalize_fragment(self, fragment: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a fragment dictionary."""
        text = str(fragment.get("text", "")).strip()
        metadata = dict(fragment.get("metadata", {}) or {})
        if not metadata.get("content_type"):
            metadata["content_type"] = "formula" if self._is_formula_unit(text) else "prose"
        return {"text": text, "metadata": metadata}

    def _build_unit_metadata(self, unit: str) -> Dict[str, Any]:
        """Build metadata for a semantic unit."""
        if self._is_formula_unit(unit):
            return {
                "content_type": "formula",
                "is_formula": True,
                "formula_block": True,
            }
        return {"content_type": "prose"}

    def _is_formula_unit(self, text: str) -> bool:
        """Heuristic formula detector for semantic units."""
        stripped = text.strip()
        if not stripped:
            return False
        if stripped.startswith("$$") and stripped.endswith("$$"):
            return True
        if stripped.startswith("\\[") and stripped.endswith("\\]"):
            return True
        if stripped.startswith("\\begin{"):
            return True

        word_count = len(re.findall(r"\b\w+\b", stripped))
        symbol_count = sum(1 for ch in stripped if ch in "=^_±×÷∑∫∂→←≠≤≥√")
        latex_hits = len(re.findall(r"\\[A-Za-z]+", stripped))
        return word_count <= 40 and (symbol_count >= 2 or latex_hits >= 1)

    def _group_units_into_chunks(self, units: List[Dict[str, Any]]) -> List[Tuple[str, dict]]:
        """
        Group semantic units into chunks that fit within target size.
        Keep related units together when possible.
        """
        chunks: List[Tuple[str, dict]] = []
        current_chunk: List[Dict[str, Any]] = []
        current_tokens = 0
        
        for i, unit in enumerate(units):
            unit_text = unit["text"]
            unit_tokens = estimate_tokens(unit_text)
            unit_meta = unit.get("metadata", {})
            if unit_meta.get("content_type") == "formula":
                if current_chunk:
                    chunks.append(self._finalize_chunk(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                chunks.append(self._finalize_chunk([unit]))
                continue
            
            # Check if adding this unit would exceed target
            if current_tokens + unit_tokens > self.target_chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self._finalize_chunk(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            # Add unit to current chunk
            current_chunk.append(unit)
            current_tokens += unit_tokens
            
            # Check for natural boundaries (headings)
            is_heading = unit_text.strip().startswith('#')
            next_is_heading = (i + 1 < len(units) and units[i + 1]["text"].strip().startswith('#'))
            
            # Break chunk at heading boundaries if we're near target size
            if is_heading and next_is_heading and current_tokens > self.target_chunk_size * 0.7:
                chunks.append(self._finalize_chunk(current_chunk))
                current_chunk = []
                current_tokens = 0
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(self._finalize_chunk(current_chunk))
        
        return chunks

    def _finalize_chunk(self, units: List[Dict[str, Any]]) -> Tuple[str, dict]:
        """Finalize a chunk from semantic units."""
        text = '\n\n'.join(unit["text"] for unit in units if unit["text"].strip())
        metadata = {
            "content_type": "formula" if len(units) == 1 and units[0]["metadata"].get("content_type") == "formula" else "prose",
            "fragment_count": len(units),
            "contains_formula": any(unit["metadata"].get("content_type") == "formula" for unit in units),
        }
        if len(units) == 1:
            metadata.update(units[0]["metadata"])
        else:
            metadata["content_types"] = sorted({unit["metadata"].get("content_type", "unknown") for unit in units})
        return text, metadata
    
    def _split_oversized_chunk(self, chunk: str) -> List[str]:
        """
        Split a chunk that exceeds max size, using sentence boundaries with overlap.
        """
        sentences = re.split(r'(?<=[.!?])\s+', chunk)
        sub_chunks = []
        current = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = estimate_tokens(sentence)
            
            if current_tokens + sentence_tokens > self.max_chunk_size and current:
                # Save current sub-chunk
                sub_chunks.append(' '.join(current))
                
                # Keep last sentence for overlap
                current = [current[-1]] if current else []
                current_tokens = estimate_tokens(current[0]) if current else 0
            
            current.append(sentence)
            current_tokens += sentence_tokens
        
        if current:
            sub_chunks.append(' '.join(current))
        
        logger.warning(f"Split oversized chunk into {len(sub_chunks)} sub-chunks")
        return sub_chunks


# Global instance
semantic_chunker = SemanticChunker()
