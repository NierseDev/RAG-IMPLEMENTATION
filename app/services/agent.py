"""
Agentic RAG coordinator with multi-step reasoning loop.
Implements: Plan → Retrieve → Reason → Verify → Decide → Answer/Iterate
"""
from typing import Optional
import time
from app.models.entities import AgentState, RetrievalResult
from app.services.llm import llm_service
from app.services.retrieval import retrieval_service
from app.services.verification import verification_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class AgenticRAG:
    """
    Agentic RAG system with self-reflective reasoning loop.
    """
    
    def __init__(
        self,
        max_iterations: Optional[int] = None,
        min_confidence: Optional[float] = None,
        enable_verification: Optional[bool] = None
    ):
        self.max_iterations = max_iterations or settings.max_agent_iterations
        self.min_confidence = min_confidence or settings.min_confidence_threshold
        self.enable_verification = enable_verification if enable_verification is not None else settings.enable_verification
        logger.info(f"AgenticRAG initialized (max_iter={self.max_iterations}, min_conf={self.min_confidence})")
    
    async def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_source: Optional[str] = None
    ) -> AgentState:
        """
        Execute agentic RAG query with full reasoning loop.
        """
        start_time = time.time()
        
        # Initialize agent state
        state = AgentState(
            iteration=0,
            original_query=query,
            current_query=query
        )
        
        logger.info(f"Starting agentic query: {query}")
        
        # Main reasoning loop
        while state.iteration < self.max_iterations:
            state.iteration += 1
            logger.info(f"Iteration {state.iteration}/{self.max_iterations}")
            
            # Phase 1: Plan
            plan = await self._plan_phase(state)
            state.plan = plan
            state.add_reasoning("PLAN", plan)
            
            # Phase 2: Retrieve
            retrieved = await self._retrieve_phase(state, top_k, filter_source)
            state.retrieved_docs.extend(retrieved)
            state.add_reasoning("RETRIEVE", f"Retrieved {len(retrieved)} documents")
            
            if not retrieved:
                state.add_reasoning("RETRIEVE", "No relevant documents found")
                if state.iteration < self.max_iterations:
                    # Try query refinement
                    state.current_query = await self._refine_query(state)
                    state.add_reasoning("REFINE", f"Refined query: {state.current_query}")
                    continue
                else:
                    state.decision = "answer"
                    state.final_answer = "I couldn't find relevant information to answer your question."
                    state.confidence = 0.0
                    break
            
            # Phase 3: Reason
            reasoning = await self._reason_phase(state)
            state.add_reasoning("REASON", reasoning)
            
            # Phase 4: Generate answer
            answer = await self._answer_phase(state)
            
            # Phase 5: Verify (if enabled)
            if self.enable_verification:
                verification = await self._verify_phase(state, answer)
                state.verification_results.append(verification)
                state.confidence = verification.get('confidence', 0.5)
                state.add_reasoning(
                    "VERIFY",
                    f"Verified: {verification['verified']}, Confidence: {state.confidence:.2f}"
                )
                
                # Check for issues
                if verification.get('issues'):
                    state.add_reasoning("VERIFY", f"Issues: {', '.join(verification['issues'])}")
            else:
                state.confidence = 0.8  # Default confidence without verification
            
            # Phase 6: Decide
            decision = await self._decide_phase(state, answer)
            state.decision = decision
            
            if decision == "answer":
                state.final_answer = answer
                state.sources = retrieval_service.extract_sources(state.retrieved_docs)
                state.add_reasoning("DECIDE", f"Providing final answer with confidence {state.confidence:.2f}")
                break
            else:
                # Continue iteration - refine query
                state.add_reasoning("DECIDE", "Need more information, refining query")
                state.current_query = await self._refine_query(state)
                state.add_reasoning("REFINE", f"New query: {state.current_query}")
        
        # If max iterations reached without answer
        if not state.final_answer:
            answer = await self._answer_phase(state)
            state.final_answer = answer
            state.sources = retrieval_service.extract_sources(state.retrieved_docs)
            state.add_reasoning("COMPLETE", f"Max iterations reached, providing best answer")
        
        elapsed = time.time() - start_time
        logger.info(f"Query completed in {elapsed:.2f}s, {state.iteration} iterations")
        
        return state
    
    async def _plan_phase(self, state: AgentState) -> str:
        """Phase 1: Create retrieval plan."""
        try:
            prompt = llm_service.create_plan_prompt(state.current_query)
            plan = await llm_service.generate(prompt, temperature=0.5, max_tokens=200)
            return plan.strip()
        except Exception as e:
            logger.error(f"Error in plan phase: {e}")
            return f"Search for information about: {state.current_query}"
    
    async def _retrieve_phase(
        self,
        state: AgentState,
        top_k: Optional[int],
        filter_source: Optional[str]
    ) -> list[RetrievalResult]:
        """Phase 2: Execute retrieval."""
        try:
            results = await retrieval_service.retrieve(
                query=state.current_query,
                top_k=top_k,
                filter_source=filter_source
            )
            return results
        except Exception as e:
            logger.error(f"Error in retrieve phase: {e}")
            return []
    
    async def _reason_phase(self, state: AgentState) -> str:
        """Phase 3: Reason about retrieved information."""
        try:
            # Limit chunks to avoid context overflow
            recent_docs = state.retrieved_docs[-settings.max_context_chunks:]
            context = retrieval_service.format_context(
                recent_docs, 
                max_tokens=settings.max_context_tokens // 2  # Reserve space for prompt
            )
            prompt = llm_service.create_reason_prompt(state.current_query, context)
            reasoning = await llm_service.generate(prompt, temperature=0.5, max_tokens=300)
            return reasoning.strip()
        except Exception as e:
            logger.error(f"Error in reason phase: {e}")
            return "Unable to reason about retrieved information"
    
    async def _answer_phase(self, state: AgentState) -> str:
        """Phase 4: Generate answer from retrieved information."""
        try:
            # Use most relevant recent documents, limited by config
            recent_docs = state.retrieved_docs[-settings.max_context_chunks:]
            context = retrieval_service.format_context(
                recent_docs,
                max_tokens=settings.max_context_tokens // 2  # Reserve space for system and query
            )
            prompt = llm_service.create_answer_prompt(state.original_query, context)
            answer = await llm_service.generate(prompt, temperature=0.7, max_tokens=500)
            return answer.strip()
        except Exception as e:
            logger.error(f"Error in answer phase: {e}")
            return "I apologize, but I encountered an error generating the answer."
    
    async def _verify_phase(self, state: AgentState, answer: str) -> dict:
        """Phase 5: Verify answer and detect hallucinations."""
        try:
            # Limit docs for verification to avoid context overflow
            recent_docs = state.retrieved_docs[-settings.max_context_chunks:]
            verification = await verification_service.verify_answer(
                query=state.original_query,
                answer=answer,
                retrieved_docs=recent_docs
            )
            return verification
        except Exception as e:
            logger.error(f"Error in verify phase: {e}")
            return {'verified': False, 'confidence': 0.0, 'issues': [str(e)]}
    
    async def _decide_phase(self, state: AgentState, answer: str) -> str:
        """Phase 6: Decide whether to answer or continue."""
        # Decision logic
        if state.confidence and state.confidence >= self.min_confidence:
            return "answer"
        
        # Check if we have enough information
        if len(state.retrieved_docs) >= 10:  # Enough documents retrieved
            return "answer"
        
        # Check for information gaps
        has_gaps, gaps = verification_service.detect_information_gaps(
            state.current_query,
            state.retrieved_docs[-6:]
        )
        
        if has_gaps and state.iteration < self.max_iterations:
            return "continue"
        
        return "answer"
    
    async def _refine_query(self, state: AgentState) -> str:
        """Refine the query based on reasoning."""
        try:
            reasoning_summary = state.reasoning[-1] if state.reasoning else "No results found"
            prompt = llm_service.create_refine_query_prompt(state.original_query, reasoning_summary)
            refined = await llm_service.generate(prompt, temperature=0.5, max_tokens=100)
            return refined.strip()
        except Exception as e:
            logger.error(f"Error refining query: {e}")
            # Fallback: slightly rephrase original query
            return f"{state.original_query} information"


# Factory function for creating agent instances
def create_agent(
    max_iterations: Optional[int] = None,
    min_confidence: Optional[float] = None,
    enable_verification: Optional[bool] = None
) -> AgenticRAG:
    """Create a new AgenticRAG instance with custom config."""
    return AgenticRAG(max_iterations, min_confidence, enable_verification)
