"""
Comparison Agent - Performs cross-document and cross-entity analysis.

Use case: When users want to compare concepts, entities, or information
across multiple documents.

Optimizes retrieval and analysis for comparative reasoning.
"""

from typing import Optional, Dict, Any, List
import logging
from app.services.subagent_base import SubAgent
from app.models.entities import RetrievalResult, AgentState

logger = logging.getLogger(__name__)


class ComparisonAgent(SubAgent):
    """
    Specialized sub-agent for comparative analysis.
    
    Excels at:
    1. Comparing entities across documents
    2. Identifying similarities and differences
    3. Contrasting viewpoints or approaches
    4. Analyzing evolution over time (if documents are dated)
    5. Highlighting gaps and unique aspects
    """
    
    def __init__(self, parent_context: Dict[str, Any]):
        """
        Initialize Comparison Agent.
        
        Args:
            parent_context: Context from parent agent
        """
        super().__init__(
            agent_type='comparison',
            parent_context=parent_context,
            max_iterations=4  # More iterations for multi-round comparison
        )
        
        logger.info(
            f"ComparisonAgent initialized with {len(self.document_set)} documents for comparison"
        )
    
    async def specialize_context_window(
        self,
        docs: List[RetrievalResult],
        query: str,
        max_tokens: int = 6000
    ) -> str:
        """
        Organize context for comparative analysis.
        
        Strategy:
        1. Group by document source
        2. Mark document boundaries clearly
        3. Preserve relatedness of similar content
        4. Balance representation across sources
        
        Args:
            docs: Retrieved document chunks
            query: Comparison query
            max_tokens: Maximum tokens
            
        Returns:
            Context organized for comparison
        """
        if not docs:
            return "No documents available for comparison."
        
        try:
            # Group and analyze by source
            docs_by_source: Dict[str, List[RetrievalResult]] = {}
            for doc in docs:
                if doc.source not in docs_by_source:
                    docs_by_source[doc.source] = []
                docs_by_source[doc.source].append(doc)
            
            # Build comparative context
            context_parts = []
            total_chars = 0
            max_chars = max_tokens * 4
            
            # Add header for comparison
            header = f"""COMPARATIVE ANALYSIS CONTEXT
Question: {query}
Sources being compared: {len(docs_by_source)}

"""
            context_parts.append(header)
            total_chars += len(header)
            
            # Add each document's content with source label
            for idx, (source, source_docs) in enumerate(docs_by_source.items(), 1):
                source_docs.sort(key=lambda d: d.chunk_id)
                
                source_section = f"\n[SOURCE {idx}] {source}\n{'-'*50}\n"
                source_section += "\n".join([d.text for d in source_docs])
                source_section += f"\n{'-'*50}\n"
                
                if total_chars + len(source_section) <= max_chars:
                    context_parts.append(source_section)
                    total_chars += len(source_section)
                else:
                    remaining = max_chars - total_chars
                    if remaining > 200:
                        truncated = source_section[:remaining] + "\n[... truncated ...]"
                        context_parts.append(truncated)
                    break
            
            context = "".join(context_parts)
            logger.info(
                f"ComparisonAgent context: {len(context)} chars from {len(docs_by_source)} documents"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Error specializing context: {e}")
            from app.services.retrieval import retrieval_service
            return retrieval_service.format_context(docs, max_tokens=max_tokens)
    
    async def _reason_phase(self, state: AgentState) -> str:
        """
        Override reasoning for comparative analysis.
        
        Focus on:
        - Similarities and differences
        - Patterns across sources
        - Contradictions or inconsistencies
        - Unique contributions of each source
        """
        try:
            context = await self.specialize_context_window(
                state.retrieved_docs,
                state.current_query,
                max_tokens=6000
            )
            
            from app.services.llm import llm_service
            
            base_prompt = llm_service.create_reason_prompt(state.current_query, context)
            comparative_prompt = f"""{base_prompt}

COMPARISON ANALYSIS INSTRUCTIONS:
1. Identify key similarities across sources
2. Highlight important differences
3. Note any contradictions or conflicts
4. Assess the relative importance of each perspective
5. Consider contextual factors that explain differences"""
            
            reasoning = await llm_service.generate(
                comparative_prompt,
                temperature=0.6,
                max_tokens=500
            )
            
            return reasoning.strip()
            
        except Exception as e:
            logger.error(f"Error in comparison reasoning: {e}")
            return "Unable to perform comparative reasoning"
    
    async def _answer_phase(self, state: AgentState) -> str:
        """
        Generate comparative answer synthesizing multiple sources.
        """
        try:
            context = await self.specialize_context_window(
                state.retrieved_docs,
                state.current_query,
                max_tokens=6000
            )
            
            from app.services.llm import llm_service
            
            base_prompt = llm_service.create_answer_prompt(state.original_query, context)
            comparative_prompt = f"""{base_prompt}

ANSWER REQUIREMENTS:
1. Present a balanced comparison
2. Use structured format (e.g., "Source 1 says...", "Source 2 says...")
3. Highlight key differences and similarities
4. Provide synthesis or reconciliation where possible
5. Note any limitations or contradictions in the sources"""
            
            answer = await llm_service.generate(
                comparative_prompt,
                temperature=0.7,
                max_tokens=700
            )
            
            return answer.strip()
            
        except Exception as e:
            logger.error(f"Error in comparison answer: {e}")
            return "Could not generate comparative analysis"
    
    async def _retrieve_phase(
        self,
        state: AgentState,
        top_k: Optional[int],
        filter_source: Optional[str],
        metadata_filters: Optional[Dict[str, Any]] = None,
        filter_logic: str = "AND"
    ) -> List[RetrievalResult]:
        """
        Override retrieval to ensure diverse source representation.
        
        For comparison, we want results from multiple sources, not just
        the highest-scoring results (which may all come from one source).
        """
        try:
            from app.services.retrieval import retrieval_service
            from app.core.config import settings
            
            # Retrieve more docs to ensure source diversity
            results = await retrieval_service.retrieve(
                query=state.current_query,
                top_k=(top_k or settings.top_k_results) * 2,  # Get more to diversify
                filter_source=None,  # Don't filter by source - we want comparison!
                metadata_filters=metadata_filters,
                filter_logic=filter_logic
            )
            
            # Balance results across sources
            if len(results) > top_k or settings.top_k_results:
                diversified = self._balance_sources(results, top_k or settings.top_k_results)
                logger.info(
                    f"Diversified retrieval: {len(diversified)} docs from "
                    f"{len(set(d.source for d in diversified))} sources"
                )
                return diversified
            
            return results
            
        except Exception as e:
            logger.error(f"Error in comparison retrieval: {e}")
            return []
    
    def _balance_sources(
        self,
        results: List[RetrievalResult],
        target_count: int
    ) -> List[RetrievalResult]:
        """
        Balance retrieval results to represent multiple sources evenly.
        
        Args:
            results: All retrieved results
            target_count: Desired number of results
            
        Returns:
            Balanced results with diverse sources
        """
        # Group by source
        by_source = {}
        for result in results:
            if result.source not in by_source:
                by_source[result.source] = []
            by_source[result.source].append(result)
        
        # Round-robin selection from each source
        balanced = []
        sources = list(by_source.keys())
        idx = 0
        
        while len(balanced) < target_count and sources:
            source = sources[idx % len(sources)]
            if by_source[source]:
                balanced.append(by_source[source].pop(0))
            idx += 1
            
            # Clean up empty sources
            sources = [s for s in sources if by_source[s]]
        
        return balanced[:target_count]
