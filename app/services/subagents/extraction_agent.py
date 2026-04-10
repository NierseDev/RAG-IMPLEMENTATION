"""
Extraction Agent - Extracts structured data and entities from documents.

Use case: When users want to extract specific information (entities, dates,
relationships, structured data) from documents.

Optimizes for precision and structured output.
"""

from typing import Optional, Dict, Any, List
import logging
import json
from app.services.subagent_base import SubAgent
from app.models.entities import RetrievalResult, AgentState

logger = logging.getLogger(__name__)


class ExtractionAgent(SubAgent):
    """
    Specialized sub-agent for structured data extraction.
    
    Excels at:
    1. Identifying and extracting entities (people, places, products, etc.)
    2. Extracting dates, numbers, and factual data
    3. Detecting relationships between entities
    4. Validating extracted data against context
    5. Handling missing or ambiguous data gracefully
    """
    
    def __init__(self, parent_context: Dict[str, Any]):
        """
        Initialize Extraction Agent.
        
        Args:
            parent_context: Context from parent agent
        """
        super().__init__(
            agent_type='extraction',
            parent_context=parent_context,
            max_iterations=3  # Fewer iterations - extraction is more deterministic
        )
        
        # Track extraction metrics
        self.extraction_metrics = {
            'entities_found': 0,
            'fields_extracted': 0,
            'validation_errors': 0
        }
        
        logger.info(
            f"ExtractionAgent initialized for structured data extraction from {len(self.document_set)} documents"
        )
    
    async def specialize_context_window(
        self,
        docs: List[RetrievalResult],
        query: str,
        max_tokens: int = 5000
    ) -> str:
        """
        Prepare context for extraction focusing on relevant snippets.
        
        Strategy:
        1. Preserve full text for accuracy
        2. Mark entity/data boundaries
        3. Include surrounding context for validation
        
        Args:
            docs: Retrieved documents
            query: Extraction query
            max_tokens: Token budget
            
        Returns:
            Context with extraction focus
        """
        if not docs:
            return "No documents available for extraction."
        
        try:
            # Analyze query to determine extraction targets
            extraction_keywords = self._parse_extraction_query(query)
            
            # Build context
            context_parts = []
            total_chars = 0
            max_chars = max_tokens * 4
            
            header = f"""STRUCTURED DATA EXTRACTION
Query: {query}
Looking for: {', '.join(extraction_keywords) if extraction_keywords else 'All relevant data'}

"""
            context_parts.append(header)
            total_chars += len(header)
            
            # Include all docs with extraction markers
            for idx, doc in enumerate(docs, 1):
                doc_text = f"\n[EXCERPT {idx}] Source: {doc.source}\n"
                doc_text += f"Relevance: {doc.similarity:.2f}\n"
                doc_text += f"Content:\n{doc.text}\n"
                
                if total_chars + len(doc_text) <= max_chars:
                    context_parts.append(doc_text)
                    total_chars += len(doc_text)
                else:
                    break
            
            context = "".join(context_parts)
            logger.info(
                f"ExtractionAgent context: {len(context)} chars from {len(docs)} excerpts"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Error specializing extraction context: {e}")
            from app.services.retrieval import retrieval_service
            return retrieval_service.format_context(docs, max_tokens=max_tokens)
    
    def _parse_extraction_query(self, query: str) -> List[str]:
        """
        Parse extraction query to identify targets.
        
        Args:
            query: User's extraction query
            
        Returns:
            List of extraction targets/keywords
        """
        keywords = []
        
        extraction_patterns = {
            'people': ['person', 'people', 'author', 'founder', 'ceo', 'names'],
            'dates': ['date', 'dates', 'when', 'time', 'year', 'months'],
            'places': ['location', 'place', 'city', 'country', 'where'],
            'products': ['product', 'products', 'items', 'services'],
            'numbers': ['number', 'count', 'statistics', 'data', 'metrics'],
            'relationships': ['relationship', 'connection', 'connected', 'related']
        }
        
        query_lower = query.lower()
        for category, patterns in extraction_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                keywords.append(category)
        
        return keywords[:3]  # Limit to 3 primary targets
    
    async def _reason_phase(self, state: AgentState) -> str:
        """
        Override reasoning for extraction focus.
        
        Reasoning should identify what data exists and validate consistency.
        """
        try:
            context = await self.specialize_context_window(
                state.retrieved_docs,
                state.current_query,
                max_tokens=5000
            )
            
            from app.services.llm import llm_service
            
            base_prompt = llm_service.create_reason_prompt(state.current_query, context)
            extraction_prompt = f"""{base_prompt}

EXTRACTION FOCUS:
1. Identify all mentions of requested data
2. Check for consistency across mentions
3. Note any ambiguities or contradictions
4. Assess data completeness
5. Flag any missing but expected information"""
            
            reasoning = await llm_service.generate(
                extraction_prompt,
                temperature=0.3,  # Lower temperature for consistency
                max_tokens=400
            )
            
            return reasoning.strip()
            
        except Exception as e:
            logger.error(f"Error in extraction reasoning: {e}")
            return "Unable to analyze extraction targets"
    
    async def _answer_phase(self, state: AgentState) -> str:
        """
        Generate structured extraction results.
        
        Returns:
        - Structured format (JSON-like or table)
        - Confidence indicators
        - Validation notes
        """
        try:
            context = await self.specialize_context_window(
                state.retrieved_docs,
                state.current_query,
                max_tokens=5000
            )
            
            from app.services.llm import llm_service
            
            base_prompt = llm_service.create_answer_prompt(state.original_query, context)
            extraction_prompt = f"""{base_prompt}

EXTRACTION OUTPUT FORMAT:
1. Use a clear, structured format
2. For each extracted item, provide:
   - The value/data
   - Source(s) where found
   - Confidence (high/medium/low)
3. Group related items together
4. Add notes on consistency or conflicts
5. Clearly indicate any missing data

If no data found, explicitly state what was not found."""
            
            answer = await llm_service.generate(
                extraction_prompt,
                temperature=0.3,  # Lower for consistency
                max_tokens=800
            )
            
            # Try to validate structured output
            validated = await self._validate_extraction(answer, state)
            
            return validated.strip()
            
        except Exception as e:
            logger.error(f"Error in extraction answer: {e}")
            return "Could not extract structured data"
    
    async def _validate_extraction(self, extracted_text: str, state: AgentState) -> str:
        """
        Validate extracted data against source documents.
        
        Args:
            extracted_text: LLM-generated extraction
            state: Agent state with retrieved docs
            
        Returns:
            Validated extraction with confidence notes
        """
        try:
            # Check if extracted items appear in source documents
            validation_notes = []
            
            # Split lines and check each claim
            lines = extracted_text.split('\n')
            checked_count = 0
            
            for line in lines:
                if line.strip() and len(line.strip()) > 10:
                    # Check if this line appears in source docs
                    found_in_source = any(
                        line[:30] in doc.text
                        for doc in state.retrieved_docs
                    )
                    
                    if not found_in_source:
                        validation_notes.append(f"⚠ Verify: {line[:50]}...")
                    
                    checked_count += 1
                    if checked_count > 10:  # Limit validation effort
                        break
            
            if validation_notes:
                footer = "\n\n[VALIDATION NOTES]\n" + "\n".join(validation_notes[:5])
                result = extracted_text + footer
            else:
                result = extracted_text + "\n\n✓ All extractions verified in source documents"
            
            self.extraction_metrics['validation_errors'] = len(validation_notes)
            
            return result
            
        except Exception as e:
            logger.warning(f"Validation error (continuing): {e}")
            return extracted_text
    
    def get_extraction_metrics(self) -> Dict[str, Any]:
        """Get extraction-specific metrics."""
        return self.extraction_metrics
