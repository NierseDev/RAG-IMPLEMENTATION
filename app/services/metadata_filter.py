"""
Metadata filtering service for RAG retrieval pipeline.
Filters chunks based on document metadata: type, date, entities, document ID.
Supports AND/OR combinations and scoring for ranking integration.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from app.models.entities import RetrievalResult
import logging

logger = logging.getLogger(__name__)


class MetadataFilter:
    """
    Filters and scores retrieval results based on document metadata.
    Applies filtering strategies and calculates relevance scores.
    """

    def __init__(self):
        """Initialize MetadataFilter."""
        logger.info("MetadataFilter initialized")
        # Supported document types
        self.supported_types = {"pdf", "docx", "pptx", "txt", "html", "markdown", "doc", "xls", "xlsx", "csv"}

    def filter_by_type(
        self,
        chunks: List[RetrievalResult],
        doc_types: List[str]
    ) -> List[RetrievalResult]:
        """
        Filter chunks by document type.

        Args:
            chunks: List of retrieval results
            doc_types: List of document types to keep (e.g., ["pdf", "docx"])

        Returns:
            Filtered list of chunks matching the specified document types
        """
        if not doc_types:
            return chunks

        # Normalize doc_types to lowercase
        doc_types_lower = [t.lower() for t in doc_types]

        filtered = []
        for chunk in chunks:
            # Extract file extension from source
            source_lower = chunk.source.lower()
            ext = source_lower.split(".")[-1] if "." in source_lower else ""

            if ext in doc_types_lower:
                filtered.append(chunk)

        logger.info(f"Filtered by type: {len(chunks)} -> {len(filtered)} chunks")
        return filtered

    def filter_by_date(
        self,
        chunks: List[RetrievalResult],
        date_range: Dict[str, Any]
    ) -> List[RetrievalResult]:
        """
        Filter chunks by date range.

        Args:
            chunks: List of retrieval results
            date_range: Date filter config with options:
                - "before": ISO string or datetime to filter documents created before this date
                - "after": ISO string or datetime to filter documents created after this date
                - "days_back": Number of days back from now (e.g., 7 for last 7 days)
                - "between": Dict with "start" and "end" ISO strings or datetimes

        Returns:
            Filtered list of chunks matching the date range
        """
        if not date_range:
            return chunks

        filtered = []

        for chunk in chunks:
            if self._matches_date_range(chunk.created_at, date_range):
                filtered.append(chunk)

        logger.info(f"Filtered by date: {len(chunks)} -> {len(filtered)} chunks")
        return filtered

    def _matches_date_range(self, created_at: datetime, date_range: Dict[str, Any]) -> bool:
        """Check if a chunk's creation date matches the specified range."""
        if "days_back" in date_range:
            cutoff_date = datetime.utcnow() - timedelta(days=date_range["days_back"])
            return created_at >= cutoff_date

        if "before" in date_range:
            before_date = self._parse_date(date_range["before"])
            return created_at <= before_date

        if "after" in date_range:
            after_date = self._parse_date(date_range["after"])
            return created_at >= after_date

        if "between" in date_range:
            between = date_range["between"]
            start_date = self._parse_date(between.get("start"))
            end_date = self._parse_date(between.get("end"))
            return start_date <= created_at <= end_date

        return True

    def _parse_date(self, date_input: Any) -> datetime:
        """Parse date from ISO string or datetime object."""
        if isinstance(date_input, datetime):
            return date_input
        if isinstance(date_input, str):
            try:
                return datetime.fromisoformat(date_input.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Could not parse date: {date_input}")
                return datetime.utcnow()
        return datetime.utcnow()

    def filter_by_entities(
        self,
        chunks: List[RetrievalResult],
        entities: List[str]
    ) -> List[RetrievalResult]:
        """
        Filter chunks by entities mentioned in the text.

        Args:
            chunks: List of retrieval results
            entities: List of entities to filter by (e.g., ["AI", "Machine Learning"])

        Returns:
            Filtered list of chunks mentioning at least one of the specified entities
        """
        if not entities:
            return chunks

        # Normalize entities to lowercase for case-insensitive matching
        entities_lower = [e.lower() for e in entities]

        filtered = []
        for chunk in chunks:
            text_lower = chunk.text.lower()
            # Check if any entity is mentioned in the chunk text
            if any(entity in text_lower for entity in entities_lower):
                filtered.append(chunk)

        logger.info(f"Filtered by entities: {len(chunks)} -> {len(filtered)} chunks")
        return filtered

    def filter_by_document_id(
        self,
        chunks: List[RetrievalResult],
        document_ids: List[str]
    ) -> List[RetrievalResult]:
        """
        Filter chunks by document ID (source filename).

        Args:
            chunks: List of retrieval results
            document_ids: List of document IDs/sources to keep

        Returns:
            Filtered list of chunks from the specified documents
        """
        if not document_ids:
            return chunks

        filtered = [chunk for chunk in chunks if chunk.source in document_ids]

        logger.info(f"Filtered by document ID: {len(chunks)} -> {len(filtered)} chunks")
        return filtered

    def apply_filters(
        self,
        chunks: List[RetrievalResult],
        filter_config: Dict[str, Any],
        logic: str = "AND"
    ) -> List[RetrievalResult]:
        """
        Apply multiple filters with AND/OR logic.

        Args:
            chunks: List of retrieval results
            filter_config: Dictionary with filter specifications:
                - "doc_type": List[str] - document types to include
                - "date_range": Dict - date filtering options
                - "entities": List[str] - entities to filter by
                - "document_ids": List[str] - specific documents to include
            logic: "AND" to require all filters, "OR" to require any filter

        Returns:
            Filtered list of chunks
        """
        if not filter_config:
            return chunks

        if logic.upper() == "AND":
            return self._apply_filters_and(chunks, filter_config)
        else:
            return self._apply_filters_or(chunks, filter_config)

    def _apply_filters_and(
        self,
        chunks: List[RetrievalResult],
        filter_config: Dict[str, Any]
    ) -> List[RetrievalResult]:
        """Apply filters with AND logic (all must match)."""
        result = chunks

        if "doc_type" in filter_config and filter_config["doc_type"]:
            result = self.filter_by_type(result, filter_config["doc_type"])

        if "date_range" in filter_config and filter_config["date_range"]:
            result = self.filter_by_date(result, filter_config["date_range"])

        if "entities" in filter_config and filter_config["entities"]:
            result = self.filter_by_entities(result, filter_config["entities"])

        if "document_ids" in filter_config and filter_config["document_ids"]:
            result = self.filter_by_document_id(result, filter_config["document_ids"])

        logger.info(f"Applied AND filters: {len(chunks)} -> {len(result)} chunks")
        return result

    def _apply_filters_or(
        self,
        chunks: List[RetrievalResult],
        filter_config: Dict[str, Any]
    ) -> List[RetrievalResult]:
        """Apply filters with OR logic (any can match)."""
        matching_chunks = set()

        if "doc_type" in filter_config and filter_config["doc_type"]:
            typed_chunks = self.filter_by_type(chunks, filter_config["doc_type"])
            matching_chunks.update(chunk.chunk_id for chunk in typed_chunks)

        if "date_range" in filter_config and filter_config["date_range"]:
            dated_chunks = self.filter_by_date(chunks, filter_config["date_range"])
            matching_chunks.update(chunk.chunk_id for chunk in dated_chunks)

        if "entities" in filter_config and filter_config["entities"]:
            entity_chunks = self.filter_by_entities(chunks, filter_config["entities"])
            matching_chunks.update(chunk.chunk_id for chunk in entity_chunks)

        if "document_ids" in filter_config and filter_config["document_ids"]:
            doc_chunks = self.filter_by_document_id(chunks, filter_config["document_ids"])
            matching_chunks.update(chunk.chunk_id for chunk in doc_chunks)

        # Return chunks that matched any filter
        result = [chunk for chunk in chunks if chunk.chunk_id in matching_chunks]

        logger.info(f"Applied OR filters: {len(chunks)} -> {len(result)} chunks")
        return result

    def calculate_filter_score(
        self,
        chunk: RetrievalResult,
        filters: Dict[str, Any]
    ) -> float:
        """
        Calculate a metadata relevance score for a chunk based on filter matching.
        Score ranges from 0 to 1, where 1 means perfect match to all filters.

        Args:
            chunk: Retrieval result to score
            filters: Dictionary with filter specifications

        Returns:
            Score between 0 and 1 based on how many filters the chunk matches
        """
        if not filters:
            return 1.0

        total_filters = 0
        matching_filters = 0

        # Check document type
        if "doc_type" in filters and filters["doc_type"]:
            total_filters += 1
            source_lower = chunk.source.lower()
            ext = source_lower.split(".")[-1] if "." in source_lower else ""
            if ext in [t.lower() for t in filters["doc_type"]]:
                matching_filters += 1

        # Check date range
        if "date_range" in filters and filters["date_range"]:
            total_filters += 1
            if self._matches_date_range(chunk.created_at, filters["date_range"]):
                matching_filters += 1

        # Check entities
        if "entities" in filters and filters["entities"]:
            total_filters += 1
            text_lower = chunk.text.lower()
            entities_lower = [e.lower() for e in filters["entities"]]
            if any(entity in text_lower for entity in entities_lower):
                matching_filters += 1

        # Check document IDs
        if "document_ids" in filters and filters["document_ids"]:
            total_filters += 1
            if chunk.source in filters["document_ids"]:
                matching_filters += 1

        # Avoid division by zero
        if total_filters == 0:
            return 1.0

        return matching_filters / total_filters

    def rerank_by_filters(
        self,
        chunks: List[RetrievalResult],
        filters: Dict[str, Any],
        filter_weight: float = 0.2
    ) -> List[RetrievalResult]:
        """
        Rerank chunks by combining vector similarity with metadata filter score.

        Args:
            chunks: List of retrieval results with vector similarity scores
            filters: Filter configuration for metadata scoring
            filter_weight: Weight of filter score in combined ranking (0-1)
                          - 0: pure vector similarity
                          - 0.2: 20% filter score, 80% vector similarity (default)
                          - 1: pure filter score

        Returns:
            Reranked list of chunks with adjusted scores
        """
        if not filters or filter_weight == 0:
            return chunks

        # Calculate combined scores
        scored_chunks = []
        for chunk in chunks:
            filter_score = self.calculate_filter_score(chunk, filters)
            # Combine vector similarity with filter score
            combined_score = (chunk.similarity * (1 - filter_weight)) + (filter_score * filter_weight)

            # Create new chunk with updated similarity score
            reranked_chunk = RetrievalResult(
                chunk_id=chunk.chunk_id,
                source=chunk.source,
                text=chunk.text,
                ai_provider=chunk.ai_provider,
                embedding_model=chunk.embedding_model,
                similarity=combined_score,
                created_at=chunk.created_at
            )
            scored_chunks.append((reranked_chunk, filter_score))

        # Sort by combined score (descending)
        scored_chunks.sort(key=lambda x: x[0].similarity, reverse=True)

        logger.info(f"Reranked {len(chunks)} chunks with filter weight {filter_weight}")

        # Return chunks without the filter score tuple
        return [chunk for chunk, _ in scored_chunks]

    def get_filter_metadata(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get metadata about the applied filters for response/logging.

        Args:
            filters: Filter configuration

        Returns:
            Dictionary with filter metadata
        """
        metadata = {}

        if "doc_type" in filters and filters["doc_type"]:
            metadata["filtered_doc_types"] = filters["doc_type"]

        if "date_range" in filters and filters["date_range"]:
            metadata["date_filter"] = filters["date_range"]

        if "entities" in filters and filters["entities"]:
            metadata["filtered_entities"] = filters["entities"]

        if "document_ids" in filters and filters["document_ids"]:
            metadata["filtered_documents"] = filters["document_ids"]

        return metadata


# Global instance
metadata_filter = MetadataFilter()
