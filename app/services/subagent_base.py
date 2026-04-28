"""
Base class for sub-agents in the Agentic RAG system (Sprint 5).

Sub-agents are specialized reasoning agents spawned by the main agent for:
- Full document analysis (without chunking)
- Cross-document comparison
- Structured data extraction

Each sub-agent:
- Inherits AgenticRAG capabilities
- Operates on isolated document sets
- Reports results back to main agent
- Tracks its own execution metrics
"""

from typing import Optional, Dict, Any, List
import logging
from app.models.entities import AgentState, RetrievalResult
from app.services.agent import AgenticRAG
import time

logger = logging.getLogger(__name__)


class SubAgent(AgenticRAG):
    """
    Base class for specialized sub-agents spawned by the main agent.
    
    Inherits full agentic reasoning capabilities but with specialized behavior.
    """
    
    def __init__(
        self,
        agent_type: str,
        parent_context: Dict[str, Any],
        max_iterations: Optional[int] = None,
        min_confidence: Optional[float] = None,
        enable_verification: Optional[bool] = None,
        enable_tools: bool = True
    ):
        """
        Initialize sub-agent.
        
        Args:
            agent_type: Type of sub-agent (e.g., 'full_document', 'comparison', 'extraction')
            parent_context: Context from parent agent including:
                - original_query: Main agent's original query
                - routing_decision: Routing decision that triggered delegation
                - document_set: Specific documents for this sub-agent
                - metadata_filters: Inherited filters
            max_iterations: Override max iterations (defaults to parent)
            min_confidence: Override confidence threshold
            enable_verification: Override verification setting
            enable_tools: Whether tools are available
        """
        # Initialize parent AgenticRAG
        super().__init__(
            max_iterations=max_iterations,
            min_confidence=min_confidence,
            enable_verification=enable_verification,
            enable_tools=enable_tools
        )
        
        self.agent_type = agent_type
        self.parent_context = parent_context
        self.parent_query = parent_context.get('original_query', '')
        self.document_set = parent_context.get('document_set', [])
        self.delegation_reason = parent_context.get('delegation_reason', 'specialized_analysis')
        self.sub_agent_metrics: Dict[str, Any] = {
            'agent_type': agent_type,
            'created_at': time.time(),
            'parent_query': self.parent_query,
            'document_count': len(self.document_set)
        }
        
        logger.info(
            f"SubAgent initialized: type={agent_type}, "
            f"docs={len(self.document_set)}, "
            f"reason={self.delegation_reason}"
        )
    
    async def execute(self, query: str) -> AgentState:
        """
        Execute sub-agent reasoning on specialized query.
        
        Args:
            query: Query to process
            
        Returns:
            AgentState with sub-agent reasoning trace
        """
        start_time = time.time()
        logger.info(f"SubAgent.execute: type={self.agent_type}, query={query}")
        
        # Execute standard agentic query
        state = await self.query(query)
        
        # Add sub-agent specific metadata
        duration = time.time() - start_time
        state.add_reasoning(
            "SUBAGENT_INFO",
            f"Sub-agent type={self.agent_type}, duration={duration:.2f}s"
        )
        
        # Update metrics
        self.sub_agent_metrics.update({
            'completed_at': time.time(),
            'duration': duration,
            'iterations': state.iteration,
            'confidence': state.confidence,
            'retrieved_docs': len(state.retrieved_docs),
            'final_answer_length': len(state.final_answer) if state.final_answer else 0
        })
        
        return state
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get sub-agent execution metrics."""
        return {
            'sub_agent': self.sub_agent_metrics,
            'orchestrator': self.get_orchestrator_metrics() if self.orchestrator_metrics else {}
        }
    
    async def specialize_context_window(
        self,
        docs: List[RetrievalResult],
        query: str,
        max_tokens: int = 4000
    ) -> str:
        """
        Optimize context window for specialized analysis.
        Sub-agents may process full documents, so context must be carefully managed.
        
        Override in subclasses for specialized behavior.
        
        Args:
            docs: Retrieved documents
            query: Query being processed
            max_tokens: Maximum tokens to allocate
            
        Returns:
            Formatted context string
        """
        # Default: use standard formatting
        from app.services.retrieval import retrieval_service
        return retrieval_service.format_context(docs, max_tokens=max_tokens)
    
    def report_to_parent(self) -> Dict[str, Any]:
        """
        Prepare report for parent agent.
        
        Returns:
            Dict with sub-agent results and reasoning
        """
        return {
            'agent_type': self.agent_type,
            'metrics': self.get_metrics(),
            'routing_history': self.routing_history[-5:],  # Last 5 routing decisions
            'orchestrator_metrics': self.orchestrator_metrics[-5:] if self.orchestrator_metrics else []
        }
