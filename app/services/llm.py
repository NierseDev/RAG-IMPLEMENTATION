"""
LLM service with multi-provider support and prompt management.
"""
from typing import Optional, AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager
import contextvars
import asyncio
import time
import re
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.services.llm_providers import create_llm_provider
from app.services.observability import build_run_metadata, log_run, traceable
import logging

logger = logging.getLogger(__name__)


class LLMBudgetExceededError(RuntimeError):
    """Raised when a request exceeds configured LLM call budget."""


class LLMRateLimitError(RuntimeError):
    """Raised when provider is rate-limited and retries are exhausted."""


class LLMService:
    """Service for LLM interactions with multi-provider support."""
    
    def __init__(self):
        self.max_context_tokens = settings.max_context_tokens
        self.max_output_tokens = settings.max_output_tokens
        self.phase_max_tokens = {
            "plan": 120,
            "reason": 200,
            "verify": 160,
            "answer": 240,
            "refine": 80
        }
        self._request_budget_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
            contextvars.ContextVar("llm_request_budget", default=None)
        )
        self._provider_status: Dict[str, Any] = {
            "available": True,
            "rate_limited": False,
            "last_error": None,
            "last_rate_limit_at": None,
            "cooldown_until": None
        }
        self._openrouter_last_call_at: float = 0.0
        self._openrouter_cooldown_until: float = 0.0
        self._last_rate_limit_state: Dict[str, Any] = {}
        
        # Initialize provider based on configuration
        self._init_provider()
        
        logger.info(f"LLM service initialized")
        logger.info(f"  Provider: {settings.ai_provider}")
        logger.info(f"  Model: {settings.current_llm_model}")
        logger.info(f"  Context: {self.max_context_tokens} tokens")
        logger.info(f"  Max output: {self.max_output_tokens} tokens")
    
    def _init_provider(self):
        """Initialize the LLM provider based on configuration."""
        provider = settings.ai_provider
        
        if provider == "ollama":
            self.provider = create_llm_provider(
                provider="ollama",
                base_url=settings.ollama_base_url,
                model=settings.ollama_llm_model,
                max_output_tokens=self.max_output_tokens
            )
        elif provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="openrouter",
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
                max_output_tokens=self.max_output_tokens
            )
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
            self.provider = create_llm_provider(
                provider="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                max_output_tokens=self.max_output_tokens
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect provider rate-limit errors."""
        message = str(error).lower()
        return any(token in message for token in [
            "429",
            "rate limit",
            "too many requests",
            "temporarily rate-limited"
        ])

    def is_openrouter_free_mode(self) -> bool:
        """Check whether OpenRouter free-mode throttling/budget controls are active."""
        if settings.ai_provider != "openrouter":
            return False
        if not settings.openrouter_free_mode_enabled:
            return False
        return settings.openrouter_model.endswith(":free")

    @asynccontextmanager
    async def request_budget(self, request_type: str, max_calls: Optional[int] = None):
        """Context manager to track per-request LLM call budget and degradation metadata."""
        effective_max_calls = max_calls
        if effective_max_calls is None and self.is_openrouter_free_mode():
            effective_max_calls = settings.openrouter_free_max_calls_per_request

        budget = {
            "request_type": request_type,
            "free_mode": self.is_openrouter_free_mode(),
            "max_calls": effective_max_calls,
            "calls_made": 0,
            "phase_calls": [],
            "skipped_phases": [],
            "degraded": False,
            "degrade_reasons": [],
            "rate_limit_hits": 0,
            "started_at": time.time()
        }
        token = self._request_budget_ctx.set(budget)
        try:
            yield
        finally:
            self._request_budget_ctx.reset(token)

    def can_execute_phase(self, phase: str, optional: bool = True) -> bool:
        """Check whether a phase should run without exhausting request budget."""
        budget = self._request_budget_ctx.get()
        if not budget:
            return True

        max_calls = budget.get("max_calls")
        if max_calls is None:
            return True

        if budget["calls_made"] < max_calls:
            return True

        if optional:
            budget["degraded"] = True
            budget["skipped_phases"].append(phase)
            budget["degrade_reasons"].append(f"budget_exhausted_before_{phase}")
            return False

        raise LLMBudgetExceededError(
            f"LLM call budget exhausted before required phase '{phase}' "
            f"({budget['calls_made']}/{max_calls})"
        )

    def get_budget_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get current request budget and degradation metadata snapshot."""
        budget = self._request_budget_ctx.get()
        if not budget:
            return None

        snapshot = dict(budget)
        max_calls = snapshot.get("max_calls")
        snapshot["remaining_calls"] = (max_calls - snapshot["calls_made"]) if max_calls is not None else None
        snapshot["rate_limit"] = self.get_rate_limit_state()
        return snapshot

    def get_rate_limit_state(self) -> Dict[str, Any]:
        """Return latest provider rate-limit state + cooldown timers."""
        state = dict(self._last_rate_limit_state)
        state["cooldown_until"] = self._openrouter_cooldown_until
        state["now"] = time.monotonic()
        return state
    
    def _validate_and_truncate_prompt(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> tuple[str, Optional[str]]:
        """
        Validate and truncate prompt to fit within context window.
        
        Returns: (truncated_prompt, truncated_system)
        """
        max_tokens = max_tokens or self.max_output_tokens
        
        # Calculate available tokens for input
        available_tokens = self.max_context_tokens - max_tokens
        
        # Estimate system prompt tokens
        system_tokens = estimate_tokens(system) if system else 0
        
        # Calculate available tokens for user prompt
        prompt_available = available_tokens - system_tokens
        
        if prompt_available < 100:
            logger.warning("Very little space left for prompt after system message")
            # Truncate system message if needed
            if system and system_tokens > available_tokens // 2:
                system = truncate_to_token_limit(system, available_tokens // 2)
                system_tokens = estimate_tokens(system)
                prompt_available = available_tokens - system_tokens
        
        # Check if prompt needs truncation
        prompt_tokens = estimate_tokens(prompt)
        if prompt_tokens > prompt_available:
            logger.warning(
                f"Prompt ({prompt_tokens} tokens) exceeds limit ({prompt_available} available). Truncating."
            )
            prompt = truncate_to_token_limit(prompt, prompt_available, reserve_tokens=50)
        
        return prompt, system
    
    @traceable(name="llm.generate", run_type="llm")
    async def generate(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        phase: Optional[str] = None
    ) -> str:
        """Generate a response from the LLM."""
        phase = phase or "unknown"
        try:
            # Validate and truncate if needed
            prompt, system = self._validate_and_truncate_prompt(prompt, system, max_tokens)
            log_run(
                "llm.generate",
                build_run_metadata(
                    provider=settings.ai_provider,
                    model=settings.current_llm_model,
                    phase=phase,
                    temperature=temperature,
                    max_tokens=max_tokens or self.max_output_tokens,
                    prompt_tokens=estimate_tokens(prompt),
                    system_tokens=estimate_tokens(system) if system else 0
                )
            )
            
            # Add default system message if none provided
            if not system:
                system = "Answer directly. Do not reveal chain-of-thought."
            
            # DEBUG: Log generation details
            logger.info("=" * 80)
            logger.info("DEBUG LLM: Generating response")
            logger.info(f"  Provider: {settings.ai_provider}")
            logger.info(f"  Model: {settings.current_llm_model}")
            logger.info(f"  Temperature: {temperature}")
            logger.info(f"  Max tokens: {max_tokens if max_tokens else self.max_output_tokens}")
            logger.info(f"  System length: {len(system) if system else 0}")
            logger.info(f"  Prompt length: {len(prompt)}")
            logger.info(f"  Prompt preview: {prompt[:200]}...")
            logger.info("=" * 80)

            self._consume_budget_call(phase)
            retry_attempts = settings.openrouter_free_retry_attempts if self.is_openrouter_free_mode() else 0
            rate_limit_error: Optional[Exception] = None

            for attempt in range(retry_attempts + 1):
                await self._apply_openrouter_throttle()

                try:
                    content = await self.provider.generate(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    self._update_rate_limit_state_from_provider()
                    self._provider_status.update({
                        "available": True,
                        "rate_limited": False,
                        "last_error": None
                    })
                    break
                except Exception as e:
                    if settings.ai_provider == "openrouter" and self._is_rate_limit_error(e):
                        rate_limit_error = e
                        self._record_rate_limit_hit(e, phase=phase)
                        if attempt < retry_attempts:
                            delay = min(
                                settings.openrouter_free_retry_backoff_seconds * (2 ** attempt),
                                settings.openrouter_free_retry_max_backoff_seconds
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise LLMRateLimitError(
                            f"OpenRouter rate-limited after {retry_attempts + 1} attempts"
                        ) from e
                    raise
            else:
                raise LLMRateLimitError("OpenRouter rate-limited and no response was produced") from rate_limit_error
            
            logger.info(f"DEBUG LLM: ✅ Response received ({len(content)} chars)")
            logger.info("=" * 80)
            
            if phase == "answer":
                content = self.normalize_answer_output(content)

            return content
            
        except Exception as e:
            if isinstance(e, (LLMBudgetExceededError, LLMRateLimitError)):
                raise

            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["context", "length", "token", "too long"]):
                logger.error(f"Context length error in LLM generation: {e}")
                # Try with more aggressive truncation
                try:
                    logger.info("Retrying with more aggressive truncation")
                    safe_limit = min(int(self.max_context_tokens * 0.6), 12000)
                    
                    if system:
                        system = truncate_to_token_limit(system, safe_limit // 3)
                    prompt = truncate_to_token_limit(prompt, safe_limit // 3 * 2)
                    
                    content = await self.provider.generate(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens or self.max_output_tokens // 2
                    )
                    return content
                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}")
                    return "I apologize, but the source texts are too large for me to process. Please try with a smaller query or fewer documents."
            
            logger.error(f"Error generating LLM response: {e}")
            raise
    
    async def check_availability(self) -> bool:
        """Check if LLM provider is available."""
        try:
            available = await self.provider.check_availability()
            self._provider_status.update({
                "available": available,
                "rate_limited": False,
                "last_error": None
            })
            return available
        except Exception as e:
            if settings.ai_provider == "openrouter" and self._is_rate_limit_error(e):
                self._provider_status.update({
                    "available": True,
                    "rate_limited": True,
                    "last_error": str(e),
                    "last_rate_limit_at": time.time()
                })
                return True
            logger.error(f"LLM provider not available: {e}")
            self._provider_status.update({
                "available": False,
                "rate_limited": False,
                "last_error": str(e)
            })
            return False

    def get_provider_status(self) -> Dict[str, Any]:
        """Get latest provider health + rate-limit status."""
        status = dict(self._provider_status)
        status["rate_limit"] = self.get_rate_limit_state()
        return status

    def get_effective_max_iterations(self, configured_iterations: int) -> int:
        """Return max iterations adjusted for free mode."""
        if self.is_openrouter_free_mode():
            return min(configured_iterations, settings.openrouter_free_max_iterations)
        return configured_iterations

    def get_effective_verification_enabled(self, configured_enabled: bool) -> bool:
        """Return verification flag adjusted for free mode."""
        if self.is_openrouter_free_mode() and settings.openrouter_free_disable_verification:
            return False
        return configured_enabled

    def _consume_budget_call(self, phase: str) -> None:
        budget = self._request_budget_ctx.get()
        if not budget:
            return

        max_calls = budget.get("max_calls")
        if max_calls is not None and budget["calls_made"] >= max_calls:
            budget["degraded"] = True
            budget["degrade_reasons"].append(f"budget_exhausted_at_{phase}")
            raise LLMBudgetExceededError(
                f"LLM call budget exhausted during phase '{phase}' ({budget['calls_made']}/{max_calls})"
            )

        budget["calls_made"] += 1
        budget["phase_calls"].append(phase)

    async def _apply_openrouter_throttle(self) -> None:
        if settings.ai_provider != "openrouter":
            return

        now = time.monotonic()
        if now < self._openrouter_cooldown_until:
            await asyncio.sleep(self._openrouter_cooldown_until - now)

        min_delay = settings.openrouter_free_min_inter_call_delay_seconds if self.is_openrouter_free_mode() else 0.0
        if min_delay > 0 and self._openrouter_last_call_at > 0:
            elapsed = time.monotonic() - self._openrouter_last_call_at
            if elapsed < min_delay:
                await asyncio.sleep(min_delay - elapsed)

        self._openrouter_last_call_at = time.monotonic()

    def _update_rate_limit_state_from_provider(self) -> None:
        if settings.ai_provider != "openrouter":
            return

        getter = getattr(self.provider, "get_rate_limit_state", None)
        if not callable(getter):
            return

        state = getter() or {}
        self._last_rate_limit_state = state
        reset_after = state.get("reset_after")
        if isinstance(reset_after, (float, int)) and reset_after > 0:
            self._openrouter_cooldown_until = max(self._openrouter_cooldown_until, time.monotonic() + float(reset_after))

    def _record_rate_limit_hit(self, error: Exception, phase: str) -> None:
        self._update_rate_limit_state_from_provider()
        cooldown = settings.openrouter_free_cooldown_seconds
        reset_after = self._last_rate_limit_state.get("reset_after")
        if isinstance(reset_after, (float, int)) and reset_after > 0:
            cooldown = float(reset_after)

        self._openrouter_cooldown_until = max(self._openrouter_cooldown_until, time.monotonic() + cooldown)
        self._provider_status.update({
            "available": True,
            "rate_limited": True,
            "last_error": str(error),
            "last_rate_limit_at": time.time(),
            "cooldown_until": self._openrouter_cooldown_until
        })

        budget = self._request_budget_ctx.get()
        if budget:
            budget["degraded"] = True
            budget["rate_limit_hits"] += 1
            budget["degrade_reasons"].append(f"rate_limited_at_{phase}")
    
    # Prompt templates for different agent phases

    def get_phase_max_tokens(self, phase: str, fallback: int) -> int:
        """Return per-phase max_tokens budget."""
        return self.phase_max_tokens.get(phase, fallback)
    
    def _session_memory_block(self, conversation_context: Optional[str]) -> str:
        """Format session memory for prompt injection."""
        if not conversation_context:
            return ""

        return (
            "Session memory (reference only; not evidence):\n"
            f"{conversation_context}\n"
            "Use this to resolve follow-up references and maintain continuity.\n"
        )

    def create_plan_prompt(self, query: str, conversation_context: Optional[str] = None) -> str:
        """Create prompt for the planning phase."""
        return (
            "Plan retrieval.\n"
            f"{self._session_memory_block(conversation_context)}"
            f"Query: {query}\n"
            "Return 4 bullets: needs, search terms, source types, gaps.\n"
            "Be concise."
        )
    
    def create_reason_prompt(
        self,
        query: str,
        retrieved_docs: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """Create prompt for the reasoning phase."""
        return (
            "Judge if the context is enough to answer.\n"
            f"{self._session_memory_block(conversation_context)}"
            f"Query: {query}\n"
            f"Context:\n{retrieved_docs}\n"
            "Return 4 bullets: relevance, sufficiency, gaps, decision (answer|retrieve_more).\n"
            "Return only the analysis."
        )
    
    def create_verify_prompt(
        self,
        query: str,
        answer: str,
        context: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """Create prompt for verification phase."""
        return (
            "Check whether the answer's claims are supported by the context.\n"
            f"{self._session_memory_block(conversation_context)}"
            f"Query: {query}\n"
            f"Answer: {answer}\n"
            f"Context:\n{context}\n"
            "Allow concise paraphrase, simplification, and synthesis when the meaning matches the context.\n"
            "Only mark unsupported claims when the answer adds facts, numbers, entities, or conclusions not grounded in the context.\n"
            "Reply exactly:\n"
            "Verified: [yes/no]\n"
            "Confidence score: [0.0-1.0]\n"
            "Issues: [none or short semicolon-separated issues]"
        )
    
    def create_answer_prompt(
        self,
        query: str,
        context: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """Create prompt for final answer generation."""
        return (
            "Answer using only the provided source texts and evidence.\n"
            f"{self._session_memory_block(conversation_context)}"
            f"Question: {query}\n"
            f"Source texts and evidence:\n{context}\n"
            "Be direct, factual, and cite claims inline.\n"
            "Keep the answer to 2-4 short sentences.\n"
            "Prefer a single compact paragraph unless bullets make it clearer.\n"
            "Paraphrase and simplify the source when helpful; do not copy wording unless an exact term matters.\n"
            "Synthesize across sources when they agree instead of repeating each source verbatim.\n"
            "Keep the answer plain text. Do not use markdown emphasis like **bold**.\n"
            "Use the Source numbers exactly as shown. Each Source block is one document, even if it contains multiple chunks.\n"
            "For web sources, cite the webpage title or URL shown in the source data.\n"
            "Do not cite chunk numbers.\n"
            "If the source texts are thin, use any available web evidence blocks; if none exist, say what is missing in one short sentence.\n"
            "Format:\n"
            "Answer:\n"
            "[answer with citations]\n\n"
            "References:\n"
            "- [reference 1]"
        )

    def normalize_answer_output(self, content: str) -> str:
        """Strip answer envelope text while preserving the answer body."""
        if not content:
            return content

        lines = content.strip().splitlines()
        cleaned_lines = []
        saw_content = False

        for line in lines:
            stripped = line.strip()
            if not saw_content and not stripped:
                continue

            if not saw_content:
                answer_match = re.match(r"^(?:answer|final answer)\s*:\s*(.*)$", stripped, re.IGNORECASE)
                if answer_match:
                    remainder = answer_match.group(1).strip()
                    if remainder:
                        cleaned_lines.append(remainder)
                        saw_content = True
                    continue

            if re.match(r"^(?:references?|sources?)\s*:\s*$", stripped, re.IGNORECASE):
                break

            cleaned_lines.append(line)
            if stripped:
                saw_content = True

        cleaned = "\n".join(cleaned_lines).strip()
        cleaned = cleaned or content.strip()
        return re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    
    def create_refine_query_prompt(
        self,
        original_query: str,
        reasoning: str,
        conversation_context: Optional[str] = None,
        current_query: Optional[str] = None,
        refinement_mode: str = "broaden"
    ) -> str:
        """Create prompt for query refinement."""
        current_search_query = current_query or original_query
        if refinement_mode not in {"broaden", "narrow"}:
            refinement_mode = "broaden"

        return (
            "Rewrite this retrieval query with a small edit.\n"
            f"{self._session_memory_block(conversation_context)}"
            f"Original query: {original_query}\n"
            f"Current search query: {current_search_query}\n"
            f"Refinement mode: {refinement_mode}\n"
            f"Reasoning: {reasoning}\n"
            "Return one new query only.\n"
            "Keep the same intent.\n"
            "If mode is broaden, add 1-3 helpful keywords or context.\n"
            "If mode is narrow, remove filler and keep the core terms.\n"
            "Stay under 20 words."
        )


# Global LLM service instance
llm_service = LLMService()
