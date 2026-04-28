"""
Agentic RAG coordinator with multi-step reasoning loop.
Implements: Plan → Retrieve → Reason → Verify → Decide → Answer/Iterate
Enhanced with: SQL Tool, Web Search Tool, Agent Router (Sprint 4), Sub-Agents
Integration: Workflow Orchestrator (Sprint 4, Group 3, Task 2)
"""
from typing import Optional, Dict, Any, List, Tuple
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from app.models.entities import AgentState, RetrievalResult
from app.services.llm import llm_service, LLMBudgetExceededError, LLMRateLimitError
from app.services.retrieval import retrieval_service
from app.services.verification import verification_service
from app.services.agent_router import agent_router, ToolType
from app.services.workflow_orchestrator import orchestrator, Workflow, ExecutionMode, RetryConfig
from app.services.tool_handlers import create_tool_handlers
from app.services.observability import build_run_metadata, log_run, traceable
from app.core.database import get_supabase_client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class AgenticRAG:
    """
    Agentic RAG system with self-reflective reasoning loop.
    Enhanced with multi-tool support, agent router (Sprint 4), and sub-agent delegation.
    Integration: Workflow Orchestrator for intelligent tool sequencing (Sprint 4, Group 3, Task 2).
    """

    WEB_CONTEXT_MAX_RESULTS = 2
    WEB_CONTEXT_MAX_CHARS = 500
    
    def __init__(
        self,
        max_iterations: Optional[int] = None,
        min_confidence: Optional[float] = None,
        enable_verification: Optional[bool] = None,
        enable_tools: bool = True
    ):
        configured_max_iterations = max_iterations or settings.max_agent_iterations
        configured_verification = enable_verification if enable_verification is not None else settings.enable_verification
        self.max_iterations = llm_service.get_effective_max_iterations(configured_max_iterations)
        self.min_confidence = min_confidence or settings.min_confidence_threshold
        self.enable_verification = llm_service.get_effective_verification_enabled(configured_verification)
        self.free_mode_enabled = llm_service.is_openrouter_free_mode()
        self.enable_tools = enable_tools
        self.routing_history: List[Dict[str, Any]] = []
        self.orchestrator = orchestrator
        self.orchestrator_metrics: List[Dict[str, Any]] = []
        
        # Initialize tools if enabled
        self.sql_tool = None
        self.web_search_tool = None
        
        if self.enable_tools:
            try:
                from app.tools.sql_tool import sql_tool
                from app.tools.web_search_tool import web_search_tool
                from app.services.query_service import query_service
                from app.services.metadata_filter import metadata_filter
                
                self.sql_tool = sql_tool
                self.web_search_tool = web_search_tool
                self.query_service = query_service
                self.metadata_filter = metadata_filter
                
                # Register tools with router
                agent_router.register_tool(ToolType.SQL, self.sql_tool)
                agent_router.register_tool(ToolType.WEB_SEARCH, self.web_search_tool)
                
                # Initialize workflow orchestrator with tool handlers (Sprint 4, Group 3, Task 2)
                handlers = create_tool_handlers(
                    retrieval_service=retrieval_service,
                    query_service=query_service,
                    sql_tool=sql_tool,
                    web_search_tool=web_search_tool,
                    metadata_filter=metadata_filter
                )
                
                for tool_type, handler in handlers.items():
                    self.orchestrator.add_tool(tool_type, handler)
                
                logger.info("AgenticRAG tools initialized: SQL, Web Search, Workflow Orchestrator (Sprint 4, Group 3, Task 2)")
            except Exception as e:
                logger.warning(f"Failed to initialize tools: {e}. Running without tools.")
                self.enable_tools = False
        
        logger.info(
            f"AgenticRAG initialized (max_iter={self.max_iterations}, min_conf={self.min_confidence}, "
            f"verify={self.enable_verification}, free_mode={self.free_mode_enabled}, tools={self.enable_tools})"
        )

    async def _load_session_context(self, session_id: int, max_messages: int = 6) -> Optional[str]:
        """Load recent chat history for a session."""
        try:
            client = get_supabase_client()
            result = client.table("chat_messages") \
                .select("role, content, created_at") \
                .eq("session_id", session_id) \
                .order("created_at", desc=True) \
                .limit(max_messages) \
                .execute()

            messages = list(reversed(result.data or []))
            if not messages:
                return None

            lines: List[str] = []
            for message in messages[-max_messages:]:
                content = str(message.get("content") or "").strip()
                if not content:
                    continue
                if len(content) > 400:
                    content = content[:397].rstrip() + "..."
                role = str(message.get("role") or "").strip().lower()
                label = "User" if role == "user" else "Assistant" if role == "assistant" else "Message"
                lines.append(f"{label}: {content}")

            if not lines:
                return None

            context = "\n".join(lines)
            if len(context) > 1600:
                return context[:1597].rstrip() + "..."
            return context
        except Exception as e:
            logger.warning(f"Could not load session history for session {session_id}: {e}")
            return None

    def _compose_contextual_query(self, query: str, conversation_context: Optional[str]) -> str:
        """Blend the current query with session memory for retrieval and routing."""
        if not conversation_context:
            return query

        return (
            f"Conversation history:\n{conversation_context}\n\n"
            f"Current user question: {query}"
        )
    
    @traceable(name="agent.query", run_type="chain")
    async def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_source: Optional[str] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        filter_logic: str = "AND",
        session_id: Optional[int] = None
    ) -> AgentState:
        """
        Execute agentic RAG query with full reasoning loop.
        Sprint 4: Supports metadata filtering.
        """
        start_time = time.time()
        log_run(
            "agent.query",
            build_run_metadata(
                query=query,
                top_k=top_k,
                filter_source=filter_source,
                metadata_filters=metadata_filters,
                filter_logic=filter_logic,
                session_id=session_id,
                max_iterations=self.max_iterations,
                verification_enabled=self.enable_verification,
                tools_enabled=self.enable_tools,
                free_mode=self.free_mode_enabled
            )
        )
        
        # Initialize agent state
        state = AgentState(
            iteration=0,
            original_query=query,
            current_query=query,
            search_query=query
        )

        if session_id:
            state.conversation_context = await self._load_session_context(session_id)
            state.current_query = self._compose_contextual_query(state.search_query, state.conversation_context)
            if state.conversation_context:
                logger.info(
                    f"Loaded session memory for session {session_id} "
                    f"({len(state.conversation_context)} chars)"
                )
        
        logger.info(f"Starting agentic query: {query}")
        
        # Main reasoning loop
        while state.iteration < self.max_iterations:
            state.iteration += 1
            logger.info(f"Iteration {state.iteration}/{self.max_iterations}")
            
            # Phase 1: Plan
            if self.free_mode_enabled:
                plan = "Plan phase skipped in OpenRouter free mode to preserve call budget."
                state.add_reasoning("DEGRADED_MODE", "Skipped PLAN phase due to free-mode budget optimization")
            else:
                plan = await self._plan_phase(state)
            state.plan = plan
            state.add_reasoning("PLAN", plan)
            
            # Phase 2: Retrieve
            retrieved = await self._retrieve_phase(
                state, 
                top_k, 
                filter_source,
                metadata_filters,
                filter_logic
            )
            state.retrieved_docs.extend(retrieved)
            state.add_reasoning("RETRIEVE", f"Retrieved {len(retrieved)} documents")
            
            if not retrieved:
                state.add_reasoning("RETRIEVE", "No relevant documents found")
                if state.iteration < self.max_iterations and not self.free_mode_enabled:
                    # Try query refinement
                    refined_query = await self._refine_query(state)
                    state.current_query = self._compose_contextual_query(refined_query, state.conversation_context)
                    state.add_reasoning("REFINE", f"Refined query: {state.current_query}")
                    continue
                else:
                    state.decision = "answer"
                    state.final_answer = "I couldn't find relevant information to answer your question."
                    state.confidence = 0.0
                    break
            
            # Phase 3: Reason
            if self.free_mode_enabled:
                reasoning = "Reason phase skipped in OpenRouter free mode to preserve call budget."
                state.add_reasoning("DEGRADED_MODE", "Skipped REASON phase due to free-mode budget optimization")
            else:
                reasoning = await self._reason_phase(state)
            state.add_reasoning("REASON", reasoning)
            
            # Phase 4: Generate answer
            answer = await self._answer_phase(state)
            
            # Phase 5: Verify (if enabled)
            if self.enable_verification:
                verification = await self._verify_phase(state, answer)
                state.verification_results.append(verification)
                confidence_from_verification = verification.get('confidence', 0.5)
                state.confidence = confidence_from_verification
                logger.info(f"DEBUG: Agent received confidence from verification: {confidence_from_verification:.2f}, assigned to state.confidence: {state.confidence:.2f}")
                state.add_reasoning(
                    "VERIFY",
                    "Verified: "
                    f"{verification['verified']}, Confidence: {state.confidence:.2f}, "
                    f"Evidence: {verification.get('evidence_score', 0.0):.2f}"
                )
                
                # Check for issues
                if verification.get('issues'):
                    state.add_reasoning("VERIFY", f"Issues: {', '.join(verification['issues'])}")
            else:
                state.confidence = 0.8  # Default confidence without verification
            
            # Phase 6: Decide
            if self.free_mode_enabled:
                decision = "answer"
                state.add_reasoning("DEGRADED_MODE", "Forced single-pass decision in OpenRouter free mode")
            else:
                decision = await self._decide_phase(state, answer)
            state.decision = decision
            logger.info(f"DEBUG: Decision made: {decision}")
            
            if decision == "answer":
                state.final_answer = answer
                logger.info(f"DEBUG: Setting final_answer (length: {len(answer)} chars)")
                state.sources = retrieval_service.extract_sources(state.retrieved_docs)
                state.add_reasoning("DECIDE", f"Providing final answer with confidence {state.confidence:.2f}")
                break
            else:
                # Continue iteration - refine query
                logger.info(f"DEBUG: Continuing to next iteration (current: {state.iteration})")
                if self.free_mode_enabled:
                    state.add_reasoning("DEGRADED_MODE", "Skipped REFINE phase due to free-mode single-pass policy")
                    state.decision = "answer"
                    state.final_answer = answer
                    state.sources = retrieval_service.extract_sources(state.retrieved_docs)
                    break
                last_verification = state.verification_results[-1] if state.verification_results else {}
                evidence_score = max(
                    last_verification.get('evidence_score', 0.0),
                    last_verification.get('grounding_score', 0.0),
                    last_verification.get('retrieval_strength', 0.0)
                )
                recent_docs = state.retrieved_docs[-settings.verify_context_chunks:] if state.retrieved_docs else []
                if recent_docs:
                    evidence_score = max(evidence_score, self._calculate_retrieval_strength(recent_docs))

                refine_mode, refine_summary = self._build_refinement_strategy(state, evidence_score, last_verification)
                state.add_reasoning("REFINE", f"Strategy: {refine_mode} ({refine_summary})")
                state.search_query = await self._refine_query(state, refine_mode, refine_summary)
                state.current_query = self._compose_contextual_query(state.search_query, state.conversation_context)
                state.add_reasoning("REFINE", f"New search query: {state.search_query}")
        
        # If max iterations reached without answer
        if not state.final_answer:
            logger.warning("DEBUG: Max iterations reached without final_answer! Generating one now...")
            answer = await self._answer_phase(state)
            state.final_answer = answer
            logger.info(f"DEBUG: Generated fallback final_answer (length: {len(answer) if answer else 0} chars)")
            state.sources = retrieval_service.extract_sources(state.retrieved_docs)
            state.add_reasoning("COMPLETE", f"Max iterations reached, providing best answer")
        
        elapsed = time.time() - start_time
        logger.info(f"Query completed in {elapsed:.2f}s, {state.iteration} iterations")
        
        return state
    
    async def _plan_phase(self, state: AgentState) -> str:
        """Phase 1: Create retrieval plan with intelligent routing (Sprint 4)."""
        try:
            if not llm_service.can_execute_phase("plan", optional=True):
                return "Plan phase skipped because call budget was exhausted."

            # Intelligent routing decision
            if self.enable_tools:
                routing_decision = agent_router.route_query(
                    state.current_query,
                    context={'iteration': state.iteration, 'use_hybrid': True}
                )
                self.routing_history.append(routing_decision.to_dict())
                state.add_reasoning("ROUTE", f"{routing_decision.reasoning}")
                logger.info(f"Routing decision: {routing_decision.query_type.value} (confidence: {routing_decision.confidence:.2f})")
            
            prompt = llm_service.create_plan_prompt(state.original_query, state.conversation_context)
            plan = await llm_service.generate(
                prompt,
                temperature=0.5,
                max_tokens=llm_service.get_phase_max_tokens("plan", 200),
                phase="plan"
            )
            return plan.strip()
        except Exception as e:
            logger.error(f"Error in plan phase: {e}")
            return f"Search for information about: {state.current_query}"
    
    async def _retrieve_phase(
        self,
        state: AgentState,
        top_k: Optional[int],
        filter_source: Optional[str],
        metadata_filters: Optional[Dict[str, Any]] = None,
        filter_logic: str = "AND"
    ) -> list[RetrievalResult]:
        """Phase 2: Execute retrieval with web fallback only when local docs are empty."""
        try:
            # Standard RAG retrieval with metadata filters (Sprint 4)
            results = await retrieval_service.retrieve(
                query=state.current_query,
                top_k=top_k,
                filter_source=filter_source,
                metadata_filters=metadata_filters,
                filter_logic=filter_logic
            )

            # Web search is a last resort: only run when local retrieval returns nothing.
            if not results and self.enable_tools and self.web_search_tool:
                should_fallback = self.web_search_tool.should_fallback_to_web(
                    rag_confidence=0.0,
                    rag_results_count=0
                )

                if should_fallback:
                    logger.info("Using web search as last-resort fallback")
                    web_response = await self.web_search_tool.execute(
                        state.current_query,
                        max_results=self.WEB_CONTEXT_MAX_RESULTS
                    )
                    if web_response.get('success'):
                        web_results = web_response.get('results', [])
                        web_context_docs = self._web_results_to_retrieval_results(web_results, state.iteration)
                        if web_context_docs:
                            results.extend(web_context_docs)
                            state.add_reasoning(
                                "WEB_SEARCH",
                                f"Added {len(web_context_docs)} web evidence snippets after empty local retrieval"
                            )
                    else:
                        error = web_response.get('error', 'unknown web search error')
                        state.add_reasoning("WEB_SEARCH", f"Web fallback unavailable: {error}")

            return results
        except Exception as e:
            logger.error(f"Error in retrieve phase: {e}")
            return []

    def _web_results_to_retrieval_results(
        self,
        web_results: List[Dict[str, Any]],
        iteration: int
    ) -> List[RetrievalResult]:
        """Convert web search results into retrieval-style chunks for downstream phases."""
        transformed: List[RetrievalResult] = []

        for idx, item in enumerate(web_results[:self.WEB_CONTEXT_MAX_RESULTS], 1):
            snippet = (item.get('snippet') or '').strip()
            if not snippet:
                continue

            source = self._web_source_label(item)
            text = self.web_search_tool.build_context_block(item, idx) if self.web_search_tool else self._build_web_context_block(item, idx)

            transformed.append(
                RetrievalResult(
                    chunk_id=f"web_{iteration}_{idx}",
                    source=source,
                    ai_provider="web_search",
                    embedding_model=(item.get("type") or source).lower(),
                    text=text,
                    similarity=0.55,
                    title=item.get("title"),
                    url=item.get("url"),
                    created_at=datetime.now(timezone.utc)
                )
            )

        return transformed

    def _estimate_retrieval_strength(self, results: List[RetrievalResult]) -> float:
        """Estimate how strong local retrieval is from the best retrieved chunks."""
        if not results:
            return 0.0
        top_results = sorted(results, key=lambda item: item.similarity, reverse=True)[:3]
        return sum(item.similarity for item in top_results) / len(top_results)

    def _web_source_label(self, item: Dict[str, Any]) -> str:
        """Create a readable source label for web results."""
        url = str(item.get("url") or "").strip()
        if url:
            parsed = urlparse(url)
            if parsed.netloc:
                return f"web:{parsed.netloc}"

        source = str(item.get("source") or "DuckDuckGo").strip()
        return f"web:{source}"

    def _build_web_context_block(self, item: Dict[str, Any], index: int) -> str:
        """Build a compact explicit context block when the web tool is disabled."""
        title = self._truncate_web_context_value(item.get("title") or "Web result")
        snippet = self._truncate_web_context_value(item.get("snippet") or "No snippet available")
        url = self._truncate_web_context_value(item.get("url") or "N/A")
        source = (item.get("source") or "Unknown").strip()
        score = item.get("score")
        query = self._truncate_web_context_value(item.get("search_query") or "")

        lines = [
            f"=== Web Result {index} ===",
            f"title: {title}",
            f"source: {source}",
            f"url: {url}",
        ]
        if query:
            lines.append(f"query: {query}")
        if score is not None:
            lines.append(f"score: {score}")
        lines.append(f"snippet: {snippet}")
        lines.append(f"=== End Web Result {index} ===")

        block = "\n".join(lines)
        if len(block) <= self.WEB_CONTEXT_MAX_CHARS:
            return block
        return block[: self.WEB_CONTEXT_MAX_CHARS - 3].rstrip() + "..."

    def _truncate_web_context_value(self, value: Any) -> str:
        text = str(value).strip()
        if len(text) <= self.WEB_CONTEXT_MAX_CHARS:
            return text
        return text[: self.WEB_CONTEXT_MAX_CHARS - 3].rstrip() + "..."

    async def _reason_phase(self, state: AgentState) -> str:
        """Phase 3: Reason about retrieved information."""
        try:
            if not llm_service.can_execute_phase("reason", optional=True):
                return "Reason phase skipped because call budget was exhausted."

            # Limit chunks to avoid context overflow
            recent_docs = state.retrieved_docs[-settings.reason_context_chunks:]
            context = retrieval_service.format_context(
                recent_docs, 
                max_tokens=settings.max_context_tokens // 4,
                max_results=settings.reason_context_chunks
            )
            prompt = llm_service.create_reason_prompt(
                state.original_query,
                context,
                state.conversation_context
            )
            reasoning = await llm_service.generate(
                prompt,
                temperature=0.5,
                max_tokens=llm_service.get_phase_max_tokens("reason", 300),
                phase="reason"
            )
            return reasoning.strip()
        except Exception as e:
            logger.error(f"Error in reason phase: {e}")
            return "Unable to reason about retrieved information"
    
    async def _answer_phase(self, state: AgentState) -> str:
        """Phase 4: Generate answer from retrieved information."""
        try:
            llm_service.can_execute_phase("answer", optional=False)

            # Context is structured with explicit source blocks and END OF CONTEXT marker
            # to make source attribution and parsing clearer for the LLM.
            recent_docs = state.retrieved_docs[-settings.answer_context_chunks:]
            context = retrieval_service.format_context(
                recent_docs,
                max_tokens=settings.max_context_tokens // 3,
                max_results=settings.answer_context_chunks
            )
            prompt = llm_service.create_answer_prompt(
                state.original_query,
                context,
                state.conversation_context
            )
            answer = await llm_service.generate(
                prompt,
                temperature=0.7,
                max_tokens=llm_service.get_phase_max_tokens("answer", 500),
                phase="answer"
            )
            return answer.strip()
        except (LLMBudgetExceededError, LLMRateLimitError) as e:
            logger.warning(f"Answer phase degraded due to budget/rate limit: {e}")
            state.add_reasoning("DEGRADED_MODE", f"Answer generated with non-LLM fallback: {str(e)}")
            return self._build_rate_limited_fallback_answer(state)
        except Exception as e:
            logger.error(f"Error in answer phase: {e}")
            return "I apologize, but I encountered an error generating the answer."
    
    async def _verify_phase(self, state: AgentState, answer: str) -> dict:
        """Phase 5: Verify answer and detect hallucinations."""
        try:
            # Limit docs for verification to avoid context overflow
            recent_docs = state.retrieved_docs[-settings.verify_context_chunks:]
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
        logger.info("=" * 80)
        logger.info("DEBUG: Decision Phase")
        logger.info(f"  Current confidence: {state.confidence}")
        logger.info(f"  Min confidence threshold: {self.min_confidence}")
        logger.info(f"  Iteration: {state.iteration}/{self.max_iterations}")
        logger.info(f"  Retrieved docs: {len(state.retrieved_docs)}")
        last_verification = state.verification_results[-1] if state.verification_results else {}
        evidence_score = max(
            last_verification.get('evidence_score', 0.0),
            last_verification.get('grounding_score', 0.0),
            last_verification.get('retrieval_strength', 0.0)
        )
        recent_docs = state.retrieved_docs[-settings.verify_context_chunks:] if state.retrieved_docs else []
        if recent_docs:
            evidence_score = max(evidence_score, self._calculate_retrieval_strength(recent_docs))
        logger.info(f"  Evidence score: {evidence_score:.2f}")

        if evidence_score >= max(0.65, self.min_confidence - 0.1) and len(state.retrieved_docs) >= 2:
            logger.info(
                f"  DECISION: answer (grounded evidence {evidence_score:.2f} supports answer despite conservative verification)"
            )
            logger.info("=" * 80)
            return "answer"

        should_continue, quality_label, quality_reasons = self._should_continue_after_answer(
            state,
            answer,
            evidence_score,
            last_verification
        )
        logger.info(f"  Answer quality: {quality_label}")
        if quality_reasons:
            logger.info(f"  Quality reasons: {', '.join(quality_reasons)}")

        if should_continue:
            state.add_reasoning(
                "DECIDE",
                f"Weak answer; refining query ({'; '.join(quality_reasons)})"
            )
            logger.info(
                f"  DECISION: continue (weak answer; iteration {state.iteration} < {self.max_iterations})"
            )
            logger.info("=" * 80)
            return "continue"

        # Decision logic
        if state.confidence and state.confidence >= self.min_confidence:
            logger.info(f"  DECISION: answer (confidence {state.confidence:.2f} >= {self.min_confidence:.2f})")
            logger.info("=" * 80)
            return "answer"
        else:
            logger.info(f"  Confidence check failed: {state.confidence} < {self.min_confidence}")

        # Check for information gaps
        has_gaps, gaps = verification_service.detect_information_gaps(
            state.current_query,
            state.retrieved_docs[-6:]
        )
        logger.info(f"  Information gaps detected: {has_gaps}")
        if gaps:
            logger.info(f"  Gaps: {gaps}")
        
        if has_gaps and state.iteration < self.max_iterations:
            logger.info(f"  DECISION: continue (has gaps and iteration {state.iteration} < {self.max_iterations})")
            logger.info("=" * 80)
            return "continue"
        
        logger.info(f"  DECISION: answer (no continuation criteria met)")
        logger.info("=" * 80)
        return "answer"

    def _calculate_retrieval_strength(self, docs: List[RetrievalResult]) -> float:
        """Estimate retrieval strength from the strongest chunks."""
        if not docs:
            return 0.0

        top_docs = sorted(docs, key=lambda doc: doc.similarity, reverse=True)[:3]
        return sum(doc.similarity for doc in top_docs) / len(top_docs)

    def _build_refinement_strategy(
        self,
        state: AgentState,
        evidence_score: float,
        verification: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Choose whether the next query should broaden or narrow."""
        query = (state.search_query or state.original_query or "").strip()
        query_length = len(query.split())
        issues = [str(issue).lower() for issue in verification.get("issues", []) if issue]
        verification_failed = not bool(verification.get("verified", False))
        low_evidence = evidence_score < 0.45
        weak_grounding = verification.get("grounding_score", 0.0) < 0.45
        weak_retrieval = verification.get("retrieval_strength", 0.0) < 0.45

        if not state.retrieved_docs or low_evidence or "no grounded evidence available" in issues:
            return "broaden", "add a few related keywords or missing context"

        if any(token in " ".join(issues) for token in ["unsupported", "hallucination", "low evidence", "weak evidence"]):
            return "narrow", "remove filler and focus on the core terms"

        if verification_failed and (weak_grounding or weak_retrieval):
            return "broaden", "add a small amount of extra context"

        if query_length > 10:
            return "narrow", "shorten the query to the essential terms"

        return "broaden", "add one or two helpful keywords"

    def _should_continue_after_answer(
        self,
        state: AgentState,
        answer: str,
        evidence_score: float,
        verification: Dict[str, Any]
    ) -> Tuple[bool, str, List[str]]:
        """Decide whether a weak answer should trigger another refinement pass."""
        answer_text = (answer or "").strip()
        confidence = state.confidence or 0.0
        verified = bool(verification.get('verified', False))
        issues = [str(issue) for issue in verification.get('issues', []) if issue]

        grounding_score = verification.get('grounding_score', 0.0) or 0.0
        retrieval_strength = verification.get('retrieval_strength', 0.0) or 0.0
        strongest_evidence = max(evidence_score, grounding_score, retrieval_strength)

        good_confidence = self.min_confidence
        good_evidence = max(0.65, self.min_confidence)
        great_confidence = max(self.min_confidence + 0.1, 0.85)
        great_evidence = max(0.8, good_evidence)

        reasons: List[str] = []
        if not answer_text:
            reasons.append("empty answer")
        if confidence < good_confidence:
            reasons.append(f"confidence {confidence:.2f} below {good_confidence:.2f}")
        if strongest_evidence < good_evidence:
            reasons.append(f"evidence {strongest_evidence:.2f} below {good_evidence:.2f}")
        if issues:
            reasons.append("verification still has issues")

        if not reasons:
            if confidence >= great_confidence and strongest_evidence >= great_evidence and verified:
                return False, "great", []
            return False, "good", []

        if state.iteration >= self.max_iterations or self.free_mode_enabled:
            return False, "weak", reasons

        return True, "weak", reasons
    
    async def _refine_query(
        self,
        state: AgentState,
        refinement_mode: str,
        refinement_summary: str
    ) -> str:
        """Refine the query based on reasoning."""
        try:
            if not llm_service.can_execute_phase("refine", optional=True):
                return state.search_query or state.original_query

            base_query = state.search_query or state.original_query

            reasoning_summary = (
                " | ".join(state.reasoning[-settings.refine_context_chunks:])
                if state.reasoning
                else "No results found"
            )
            prompt = llm_service.create_refine_query_prompt(
                state.original_query,
                reasoning_summary,
                state.conversation_context,
                current_query=base_query,
                refinement_mode=refinement_mode
            )
            refined = await llm_service.generate(
                prompt,
                temperature=0.5,
                max_tokens=llm_service.get_phase_max_tokens("refine", 100),
                phase="refine"
            )
            return self._normalize_refined_query(
                base_query,
                refined.strip(),
                refinement_mode,
                refinement_summary
            )
        except Exception as e:
            logger.error(f"Error refining query: {e}")
            return self._fallback_refined_query(
                state.search_query or state.original_query,
                refinement_mode,
                refinement_summary
            )

    def _normalize_refined_query(
        self,
        base_query: str,
        refined_query: str,
        refinement_mode: str,
        refinement_summary: str
    ) -> str:
        """Ensure refinement changes the query in a meaningful way."""
        cleaned = " ".join((refined_query or "").split()).strip(" .")
        if not cleaned:
            return self._fallback_refined_query(base_query, refinement_mode, refinement_summary)

        if self._normalized_query_text(cleaned) == self._normalized_query_text(base_query):
            return self._fallback_refined_query(base_query, refinement_mode, refinement_summary)

        return cleaned

    def _fallback_refined_query(
        self,
        base_query: str,
        refinement_mode: str,
        refinement_summary: str
    ) -> str:
        """Rewrite the query deterministically when the model does not change it."""
        base_query = " ".join(base_query.split()).strip()
        if not base_query:
            return refinement_summary

        if refinement_mode == "narrow":
            stopwords = {
                "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
                "have", "how", "if", "in", "is", "it", "its", "of", "on", "or", "that",
                "the", "their", "there", "these", "this", "to", "was", "were", "what",
                "when", "where", "which", "who", "why", "with", "will", "would", "can",
                "could", "should", "may", "might", "about", "into", "over", "under",
                "than", "then", "also", "more", "most", "please", "tell", "me", "give",
                "show", "find", "information", "details"
            }
            core_terms = [word for word in base_query.split() if word.lower().strip(".,!?") not in stopwords]
            if len(core_terms) >= 2:
                return " ".join(core_terms[:8])
            if len(base_query.split()) <= 4:
                return f"{base_query} specifics".strip()
            return f"{' '.join(base_query.split()[:6])} key terms".strip()

        additions = []
        summary_text = refinement_summary.lower()
        if "add" in summary_text or "context" in summary_text:
            additions.append("details")
        if "keyword" in summary_text or "terms" in summary_text:
            additions.append("key terms")
        if "shorten" in summary_text:
            additions.append("specifics")
        if not additions:
            additions.append("details")
        return f"{base_query} {' '.join(additions)}".strip()

    def _normalized_query_text(self, text: str) -> str:
        """Normalize query text for change detection."""
        return " ".join(text.lower().split()).strip(" .,!?:;")

    def _build_rate_limited_fallback_answer(self, state: AgentState) -> str:
        """Create deterministic fallback answer when LLM answering is unavailable."""
        if not state.retrieved_docs:
            return (
                "I am temporarily rate-limited by the current OpenRouter free model and "
                "could not generate a full answer. Please retry shortly."
            )

        top_docs = state.retrieved_docs[:3]
        excerpts = []
        for idx, doc in enumerate(top_docs, 1):
            snippet = doc.text.strip().replace("\n", " ")
            snippet = snippet[:220] + ("..." if len(snippet) > 220 else "")
            excerpts.append(f"{idx}. [{doc.source}] {snippet}")

        return (
            "I am temporarily rate-limited by the current OpenRouter free model, so this is a "
            "degraded evidence snapshot from retrieved context:\n\n"
            + "\n".join(excerpts)
            + "\n\nPlease retry shortly for a fully synthesized answer."
        )
    
    async def execute_with_orchestrator(
        self,
        query: str,
        routing_decision=None,
        top_k: Optional[int] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute tools using the workflow orchestrator with intelligent routing.
        Sprint 4, Group 3, Task 2: Workflow Orchestration
        
        Args:
            query: Input query
            routing_decision: Optional routing decision from agent_router
            top_k: Number of results
            metadata_filters: Optional metadata filters
            mode: Sequential or parallel execution
            timeout: Timeout for execution
            
        Returns:
            Dict with orchestration results and metrics
        """
        if not self.enable_tools:
            return {
                'success': False,
                'error': 'Tools not enabled',
                'results': []
            }
        
        try:
            # Use routing decision if provided, otherwise get from router
            if not routing_decision and self.enable_tools:
                routing_decision = agent_router.route_query(query)
            
            # Prepare context
            context = {
                'query': query,
                'top_k': top_k or settings.top_k_results,
                'metadata_filters': metadata_filters,
                'filter_logic': 'AND'
            }
            
            # Build workflow based on routing decision
            if routing_decision:
                tools = [routing_decision.primary_tool] + routing_decision.fallback_tools
                workflow_name = f"orchestrated_{routing_decision.query_type.value}"
            else:
                # Default: try hybrid then vector
                tools = [ToolType.HYBRID, ToolType.VECTOR]
                workflow_name = "default_orchestration"
            
            # Create and execute workflow
            workflow = Workflow(
                name=workflow_name,
                tools=tools,
                mode=mode,
                timeout=timeout or 30.0,
                retry_config=RetryConfig(max_retries=1, backoff_factor=2.0),
                context=context
            )
            
            logger.info(f"Orchestrating tool execution: {workflow_name} ({mode.value})")
            
            # Execute workflow
            if mode == ExecutionMode.PARALLEL:
                result = await self.orchestrator.execute_parallel(workflow, query)
            else:
                result = await self.orchestrator.execute_sequential(workflow, query)
            
            # Store metrics
            self.orchestrator_metrics.append({
                'workflow': workflow_name,
                'success': result.success,
                'duration': result.total_duration(),
                'executions': len(result.executions),
                'successful': len(result.successful_executions()),
                'timestamp': time.time()
            })
            
            # Format response
            return {
                'success': result.success,
                'results': result.all_results,
                'primary_result': result.primary_result,
                'execution_count': len(result.executions),
                'duration': result.total_duration(),
                'history': result.execution_history,
                'error': result.error,
                'executions': [e.to_dict() for e in result.executions]
            }
        
        except Exception as e:
            logger.exception(f"Orchestrator execution error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def get_orchestrator_metrics(self) -> Dict[str, Any]:
        """Get orchestrator execution metrics."""
        metrics = self.orchestrator.get_metrics()
        
        return {
            'orchestrator_stats': metrics,
            'workflow_executions': self.orchestrator_metrics,
            'total_orchestrated_queries': len(self.orchestrator_metrics),
            'average_success_rate': (
                sum(1 for m in self.orchestrator_metrics if m['success']) / len(self.orchestrator_metrics)
                if self.orchestrator_metrics else 0.0
            )
        }
    
    async def execute_sql_query(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Execute a SQL query from natural language.
        
        Args:
            natural_language_query: Natural language question about database
            
        Returns:
            Dict with query results and interpretation
        """
        if not self.enable_tools or not self.sql_tool:
            return {
                'success': False,
                'error': 'SQL tool not enabled'
            }
        
        try:
            result = await self.sql_tool.execute(natural_language_query)
            logger.info(f"SQL query executed: {result.get('success')}")
            return result
        except Exception as e:
            logger.error(f"SQL query error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def execute_web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Execute a web search.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            
        Returns:
            Dict with search results and attribution
        """
        if not self.enable_tools or not self.web_search_tool:
            return {
                'success': False,
                'error': 'Web search tool not enabled'
            }
        
        try:
            result = await self.web_search_tool.execute(query, max_results)
            logger.info(f"Web search executed: {result.get('success')}")
            return result
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==================== DELEGATION LOGIC (Sprint 5) ====================
    
    def should_delegate(
        self,
        state: AgentState,
        routing_decision: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if main agent should delegate to a sub-agent.
        
        Delegation triggers for:
        1. Full document analysis - large documents that should be processed whole
        2. Cross-document comparison - comparing multiple documents
        3. Structured extraction - extracting entities/data from documents
        
        Args:
            state: Current agent state
            routing_decision: Optional routing decision from agent_router
            
        Returns:
            Tuple of (should_delegate: bool, sub_agent_type: Optional[str])
            Sub-agent types: 'full_document', 'comparison', 'extraction'
        """
        # Check if we have enough documents to delegate
        if len(state.retrieved_docs) < 2:
            return False, None
        
        # Check query for delegation indicators
        query_lower = state.current_query.lower()
        
        # Full document analysis trigger
        if any(keyword in query_lower for keyword in [
            'entire document', 'whole document', 'full document',
            'complete analysis', 'full text', 'overall'
        ]):
            logger.info("Delegation trigger: Full document analysis detected")
            return True, 'full_document'
        
        # Comparison trigger
        if any(keyword in query_lower for keyword in [
            'compare', 'comparison', 'difference', 'contrast', 'versus', 'vs',
            'between', 'among', 'similar', 'different', 'both'
        ]):
            logger.info("Delegation trigger: Comparison analysis detected")
            return True, 'comparison'
        
        # Extraction trigger
        if any(keyword in query_lower for keyword in [
            'extract', 'extraction', 'list', 'enumerate', 'identify',
            'find all', 'what are', 'which', 'entities', 'items'
        ]):
            logger.info("Delegation trigger: Structured extraction detected")
            return True, 'extraction'
        
        return False, None
    
    async def spawn_subagent(
        self,
        sub_agent_type: str,
        state: AgentState,
        routing_decision: Optional[Dict[str, Any]] = None
    ) -> Optional['SubAgent']:
        """
        Spawn a sub-agent for specialized reasoning.
        
        Args:
            sub_agent_type: Type of sub-agent ('full_document', 'comparison', 'extraction')
            state: Current agent state with retrieved documents
            routing_decision: Optional routing decision context
            
        Returns:
            Initialized SubAgent instance, or None if spawn fails
        """
        try:
            from app.services.subagent_base import SubAgent
            
            # Prepare parent context
            parent_context = {
                'original_query': state.original_query,
                'current_query': state.current_query,
                'routing_decision': routing_decision,
                'document_set': state.retrieved_docs,
                'delegation_reason': sub_agent_type,
                'iteration': state.iteration
            }
            
            # Create appropriate sub-agent
            if sub_agent_type == 'full_document':
                from app.services.subagents.full_document_agent import FullDocumentAgent
                sub_agent = FullDocumentAgent(parent_context=parent_context)
                
            elif sub_agent_type == 'comparison':
                from app.services.subagents.comparison_agent import ComparisonAgent
                sub_agent = ComparisonAgent(parent_context=parent_context)
                
            elif sub_agent_type == 'extraction':
                from app.services.subagents.extraction_agent import ExtractionAgent
                sub_agent = ExtractionAgent(parent_context=parent_context)
                
            else:
                logger.error(f"Unknown sub-agent type: {sub_agent_type}")
                return None
            
            logger.info(
                f"SubAgent spawned: type={sub_agent_type}, docs={len(state.retrieved_docs)}, "
                f"query={state.current_query[:60]}..."
            )
            
            return sub_agent
            
        except Exception as e:
            logger.error(f"Failed to spawn sub-agent: {e}")
            return None
    
    async def execute_with_subagent(
        self,
        sub_agent_type: str,
        state: AgentState,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute query using a sub-agent.
        
        Args:
            sub_agent_type: Type of sub-agent
            state: Current agent state
            query: Optional query override (defaults to state.current_query)
            
        Returns:
            Dict with sub-agent results and metrics
        """
        query = query or state.current_query
        
        try:
            # Spawn sub-agent
            sub_agent = await self.spawn_subagent(sub_agent_type, state)
            if not sub_agent:
                return {
                    'success': False,
                    'error': f'Failed to spawn {sub_agent_type} sub-agent'
                }
            
            # Execute sub-agent
            start_time = time.time()
            sub_state = await sub_agent.execute(query)
            duration = time.time() - start_time
            
            # Aggregate results
            result = {
                'success': True,
                'sub_agent_type': sub_agent_type,
                'answer': sub_state.final_answer,
                'confidence': sub_state.confidence,
                'sources': sub_state.sources,
                'iterations': sub_state.iteration,
                'retrieved_docs': len(sub_state.retrieved_docs),
                'reasoning_trace': sub_state.reasoning,
                'verification_results': sub_state.verification_results,
                'duration': duration,
                'metrics': sub_agent.get_metrics()
            }
            
            # Update parent state with sub-agent reasoning
            state.add_reasoning(
                "SUBAGENT_DELEGATION",
                f"Delegated to {sub_agent_type} sub-agent, got answer: {sub_state.final_answer[:100]}..."
            )
            
            logger.info(
                f"Sub-agent execution complete: type={sub_agent_type}, "
                f"duration={duration:.2f}s, confidence={sub_state.confidence}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing with sub-agent: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Factory function for creating agent instances
def create_agent(
    max_iterations: Optional[int] = None,
    min_confidence: Optional[float] = None,
    enable_verification: Optional[bool] = None,
    enable_tools: bool = True
) -> AgenticRAG:
    """Create a new AgenticRAG instance with custom config."""
    return AgenticRAG(max_iterations, min_confidence, enable_verification, enable_tools)
