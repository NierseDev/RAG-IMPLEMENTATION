"""
Metadata extraction service for documents.
Extracts structured metadata: title, author, date, document type, key entities.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """
    Extracts metadata from document content and filenames.
    Supports various document formats and content patterns.
    """
    
    def __init__(self):
        logger.info("MetadataExtractor initialized")
    
    def extract(
        self,
        text: str,
        filename: str,
        file_size: int,
        docling_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from document.
        
        Args:
            text: Document text content
            filename: Original filename
            file_size: File size in bytes
            docling_metadata: Metadata from Docling processor (if available)
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            'filename': filename,
            'file_size': file_size,
            'file_extension': Path(filename).suffix.lower(),
            'extracted_at': datetime.utcnow().isoformat(),
        }
        
        # Extract from docling if available
        if docling_metadata:
            metadata.update(self._extract_from_docling(docling_metadata))
        
        # Extract from content
        content_metadata = self._extract_from_content(text)
        metadata.update(content_metadata)
        
        # Extract from filename
        filename_metadata = self._extract_from_filename(filename)
        metadata.update(filename_metadata)
        
        # Calculate statistics
        metadata['statistics'] = self._calculate_statistics(text)
        
        logger.info(f"Extracted metadata: {list(metadata.keys())}")
        return metadata
    
    def _extract_from_docling(self, docling_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from Docling processor output."""
        extracted = {}
        
        # Map common Docling fields
        field_mapping = {
            'title': 'title',
            'author': 'author',
            'creator': 'author',
            'subject': 'subject',
            'keywords': 'keywords',
            'creation_date': 'created_date',
            'modification_date': 'modified_date',
            'page_count': 'page_count',
        }
        
        for docling_key, our_key in field_mapping.items():
            if docling_key in docling_metadata and docling_metadata[docling_key]:
                extracted[our_key] = docling_metadata[docling_key]
        
        return extracted
    
    def _extract_from_content(self, text: str) -> Dict[str, Any]:
        """Extract metadata from document text content."""
        metadata = {}
        
        # Extract title (first heading or first line)
        title = self._extract_title(text)
        if title:
            metadata['title'] = title
        
        # Extract dates
        dates = self._extract_dates(text)
        if dates:
            metadata['dates_mentioned'] = dates[:5]  # Keep first 5
            if not metadata.get('created_date'):
                metadata['probable_date'] = dates[0]
        
        # Extract emails and authors
        emails = self._extract_emails(text)
        if emails:
            metadata['emails'] = emails[:3]
            if not metadata.get('author') and emails:
                # First email might be author
                metadata['probable_author'] = emails[0]
        
        # Extract key entities
        entities = self._extract_key_entities(text)
        if entities:
            metadata['key_entities'] = entities
        
        # Document type classification
        doc_type = self._classify_document_type(text)
        if doc_type:
            metadata['document_type'] = doc_type
        
        # Language detection (simple heuristic)
        language = self._detect_language(text)
        if language:
            metadata['language'] = language
        
        return metadata
    
    def _extract_from_filename(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from filename patterns."""
        metadata = {}
        
        # Remove extension
        name = Path(filename).stem
        
        # Extract date patterns from filename (YYYY-MM-DD, YYYYMMDD)
        date_patterns = [
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{4})(\d{2})(\d{2})',
            r'(\d{2})-(\d{2})-(\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, name)
            if match:
                try:
                    groups = match.groups()
                    if len(groups[0]) == 4:  # YYYY first
                        date_str = f"{groups[0]}-{groups[1]}-{groups[2]}"
                    else:  # DD first
                        date_str = f"{groups[2]}-{groups[0]}-{groups[1]}"
                    metadata['filename_date'] = date_str
                    break
                except:
                    pass
        
        # Extract version patterns (v1.0, version-2.3)
        version_match = re.search(r'v?(\d+)\.(\d+)(?:\.(\d+))?', name, re.IGNORECASE)
        if version_match:
            metadata['version'] = version_match.group(0)
        
        # Extract common keywords
        keywords = ['report', 'manual', 'guide', 'specification', 'whitepaper', 'proposal', 'contract']
        for keyword in keywords:
            if keyword in name.lower():
                metadata['filename_type'] = keyword
                break
        
        return metadata
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract document title from content."""
        lines = text.split('\n')
        
        # Try markdown heading
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('#'):
                title = re.sub(r'^#+\s*', '', line).strip()
                if len(title) > 3 and len(title) < 200:
                    return title
        
        # Try first non-empty line
        for line in lines[:5]:
            line = line.strip()
            if line and len(line) > 3 and len(line) < 200:
                # Check if it looks like a title (not too long, proper case)
                if not line.endswith('.') or line[0].isupper():
                    return line
        
        return None
    
    def _extract_dates(self, text: str) -> List[str]:
        """Extract date mentions from text."""
        date_patterns = [
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',  # Month DD, YYYY
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return list(set(dates))  # Remove duplicates
    
    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return list(set(emails[:10]))  # Limit to 10 unique emails
    
    def _extract_key_entities(self, text: str) -> List[str]:
        """Extract key entities (simple heuristic-based approach)."""
        # Extract capitalized phrases (potential entities)
        entity_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        entities = re.findall(entity_pattern, text)
        
        # Count frequencies
        entity_counts = {}
        for entity in entities:
            if len(entity) > 2:  # Skip short words
                entity_counts[entity] = entity_counts.get(entity, 0) + 1
        
        # Get top entities
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        return [entity for entity, count in sorted_entities[:10] if count > 1]
    
    def _classify_document_type(self, text: str) -> Optional[str]:
        """Classify document type based on content patterns."""
        text_lower = text.lower()
        
        # Check for common document type indicators
        if 'abstract' in text_lower[:500] and 'introduction' in text_lower[:2000]:
            return 'research_paper'
        elif 'table of contents' in text_lower[:1000]:
            return 'manual'
        elif any(word in text_lower[:500] for word in ['agreement', 'contract', 'terms']):
            return 'legal'
        elif any(word in text_lower[:500] for word in ['proposal', 'executive summary']):
            return 'business'
        elif 'readme' in text_lower[:100]:
            return 'documentation'
        elif text.count('\n```') > 2:  # Code blocks
            return 'technical'
        
        return 'general'
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection (English-focused for now)."""
        # Simple heuristic: if mostly ASCII, probably English
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text) if text else 0
        return 'en' if ascii_ratio > 0.9 else 'unknown'
    
    def _calculate_statistics(self, text: str) -> Dict[str, int]:
        """Calculate text statistics."""
        words = text.split()
        return {
            'char_count': len(text),
            'word_count': len(words),
            'line_count': text.count('\n') + 1,
            'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
        }


# Global instance
metadata_extractor = MetadataExtractor()
