"""
Full Document Agent - Processes entire documents without chunking.

Use case: When users want comprehensive analysis of specific documents
without losing coherence from chunking.

Optimizes context window to fit entire document + reasoning.
"""

from typing import Optional, Dict, Any, List
import logging
from app.services.subagent_base import SubAgent
from app.models.entities import RetrievalResult, AgentState

logger = logging.getLogger(__name__)


class FullDocumentAgent(SubAgent):
    """
    Specialized sub-agent for full document analysis.
    
    Instead of analyzing chunks separately, this agent:
    1. Concatenates full document text
    2. Optimizes context to fit token limits
    3. Performs comprehensive analysis on complete document
    4. Extracts insights that may span multiple chunks
    """
    
    def __init__(self, parent_context: Dict[str, Any]):
        """
        Initialize Full Document Agent.
        
        Args:
            parent_context: Context from parent agent
        """
        super().__init__(
            agent_type='full_document',
            parent_context=parent_context,
            # Slightly fewer iterations since full context is available
            max_iterations=3
        )
        
        logger.info(
            f"FullDocumentAgent initialized with {len(self.document_set)} documents"
        )
    
    async def specialize_context_window(
        self,
        docs: List[RetrievalResult],
        query: str,
        max_tokens: int = 6000
    ) -> str:
        """
        Consolidate multiple document chunks into cohesive full-document context.
        
        Strategy:
        1. Group chunks by source document
        2. Preserve document boundaries and ordering
        3. Prioritize earlier chunks (often most relevant)
        4. Fit within token limit
        
        Args:
            docs: Retrieved document chunks
            query: Query being processed
            max_tokens: Maximum tokens to allocate (higher for full docs)
            
        Returns:
            Formatted context combining full document views
        """
        if not docs:
            return "No documents available."
        
        try:
            # Group chunks by source
            docs_by_source: Dict[str, List[RetrievalResult]] = {}
            for doc in docs:
                if doc.source not in docs_by_source:
                    docs_by_source[doc.source] = []
                docs_by_source[doc.source].append(doc)
            
            # Build context with document boundaries
            context_parts = []
            total_chars = 0
            max_chars = max_tokens * 4  # Rough estimate: 4 chars per token
            
            for source, source_docs in docs_by_source.items():
                # Sort by position in document (earlier chunks first)
                source_docs.sort(key=lambda d: d.chunk_id)
                
                source_text = f"\n{'='*60}\n📄 Document: {source}\n{'='*60}\n"
                source_text += "\n".join([d.text for d in source_docs])
                
                if total_chars + len(source_text) <= max_chars:
                    context_parts.append(source_text)
                    total_chars += len(source_text)
                else:
                    # Truncate message if exceeding limit
                    remaining = max_chars - total_chars
                    if remaining > 200:
                        truncated = source_text[:remaining] + "\n[... content truncated ...]"
                        context_parts.append(truncated)
                    break
            
            context = "\n".join(context_parts)
            logger.info(
                f"FullDocumentAgent context window: {len(context)} chars from {len(docs_by_source)} sources"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Error specializing context window: {e}")
            # Fallback to standard formatting
            from app.services.retrieval import retrieval_service
            return retrieval_service.format_context(docs, max_tokens=max_tokens)
    
    async def _reason_phase(self, state: AgentState) -> str:
        """
        Override reasoning phase to consider full document context.
        
        The full document view often reveals cross-chunk relationships
        and document structure patterns missed by chunk-level analysis.
        """
        try:
            # Use specialized context window for full document
            context = await self.specialize_context_window(
                state.retrieved_docs,
                state.current_query,
                max_tokens=6000  # Larger budget for full doc analysis
            )
            
            from app.services.llm import llm_service
            from app.core.config import settings
            
            # Enhanced prompt for full-document reasoning
            base_prompt = llm_service.create_reason_prompt(
                state.current_query,
                context,
                state.conversation_context
            )
            enhanced_prompt = f"""{base_prompt}

Note: You have access to the full document(s) without chunking.
Consider cross-document patterns, overall document structure, and
relationships between sections in your reasoning."""
            
            reasoning = await llm_service.generate(
                enhanced_prompt,
                temperature=0.5,
                max_tokens=400
            )
            
            return reasoning.strip()
            
        except Exception as e:
            logger.error(f"Error in reason phase: {e}")
            return "Unable to perform full-document reasoning"
    
    async def _answer_phase(self, state: AgentState) -> str:
        """
        Override answer phase to synthesize full-document insights.
        """
        try:
            context = await self.specialize_context_window(
                state.retrieved_docs,
                state.current_query,
                max_tokens=6000
            )
            
            from app.services.llm import llm_service
            from app.core.config import settings
            
            # Enhanced prompt for comprehensive answer
            base_prompt = llm_service.create_answer_prompt(
                state.original_query,
                context,
                state.conversation_context
            )
            enhanced_prompt = f"""{base_prompt}

Provide a comprehensive answer that synthesizes insights from the entire document(s).
Consider document structure, cross-section relationships, and overall themes."""
            
            answer = await llm_service.generate(
                enhanced_prompt,
                temperature=0.7,
                max_tokens=600
            )
            
            return answer.strip()
            
        except Exception as e:
            logger.error(f"Error in answer phase: {e}")
            return "I couldn't generate a full-document analysis."
