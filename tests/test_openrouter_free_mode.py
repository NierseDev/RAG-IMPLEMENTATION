from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.models.entities import RetrievalResult
from app.services.agent import AgenticRAG
from app.services.llm import llm_service, LLMBudgetExceededError, LLMRateLimitError
from app.services.retrieval import retrieval_service


def _sample_docs() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="doc_1",
            source="sample_a.txt",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="First evidence chunk with product policy details.",
            similarity=0.91,
            created_at=datetime.now(timezone.utc),
        ),
        RetrievalResult(
            chunk_id="doc_2",
            source="sample_b.txt",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Second evidence chunk with timing and eligibility details.",
            similarity=0.87,
            created_at=datetime.now(timezone.utc),
        ),
    ]


@pytest.mark.asyncio
async def test_llm_budget_caps_call_volume(monkeypatch):
    class DummyProvider:
        async def generate(self, prompt, system=None, temperature=0.7, max_tokens=None):
            return "ok"

        async def check_availability(self):
            return True

        def get_rate_limit_state(self):
            return {}

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "google/gemma-4-31b-it:free")
    monkeypatch.setattr(settings, "openrouter_free_mode_enabled", True)
    monkeypatch.setattr(settings, "openrouter_free_min_inter_call_delay_seconds", 0.0)
    monkeypatch.setattr(llm_service, "provider", DummyProvider())

    async with llm_service.request_budget("agentic", max_calls=1):
        result = await llm_service.generate("first", phase="answer")
        assert result == "ok"
        with pytest.raises(LLMBudgetExceededError):
            await llm_service.generate("second", phase="verify")


@pytest.mark.asyncio
async def test_llm_tracks_rate_limit_degraded_state(monkeypatch):
    class RateLimitedProvider:
        def __init__(self):
            self.calls = 0

        async def generate(self, prompt, system=None, temperature=0.7, max_tokens=None):
            self.calls += 1
            raise Exception("429 Too Many Requests")

        async def check_availability(self):
            return False

        def get_rate_limit_state(self):
            return {"reset_after": 0.0}

    provider = RateLimitedProvider()
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "google/gemma-4-31b-it:free")
    monkeypatch.setattr(settings, "openrouter_free_mode_enabled", True)
    monkeypatch.setattr(settings, "openrouter_free_retry_attempts", 1)
    monkeypatch.setattr(settings, "openrouter_free_retry_backoff_seconds", 0.0)
    monkeypatch.setattr(settings, "openrouter_free_retry_max_backoff_seconds", 0.0)
    monkeypatch.setattr(settings, "openrouter_free_min_inter_call_delay_seconds", 0.0)
    monkeypatch.setattr(settings, "openrouter_free_cooldown_seconds", 0.0)
    monkeypatch.setattr(llm_service, "provider", provider)

    async with llm_service.request_budget("simple", max_calls=2):
        with pytest.raises(LLMRateLimitError):
            await llm_service.generate("will fail", phase="answer")
        budget = llm_service.get_budget_snapshot()

    assert provider.calls == 2
    assert budget is not None
    assert budget["degraded"] is True
    assert budget["rate_limit_hits"] >= 1


@pytest.mark.asyncio
async def test_agent_free_mode_short_circuits_optional_phases(monkeypatch):
    async def fake_retrieve(*args, **kwargs):
        return _sample_docs()

    phase_calls: list[str] = []

    async def fake_generate(prompt, system=None, temperature=0.7, max_tokens=None, phase=None):
        phase_calls.append(phase or "unknown")
        return "final answer"

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "google/gemma-4-31b-it:free")
    monkeypatch.setattr(settings, "openrouter_free_mode_enabled", True)
    monkeypatch.setattr(settings, "openrouter_free_max_iterations", 1)
    monkeypatch.setattr(settings, "openrouter_free_disable_verification", True)
    monkeypatch.setattr(retrieval_service, "retrieve", fake_retrieve)
    monkeypatch.setattr(llm_service, "generate", fake_generate)

    agent = AgenticRAG(max_iterations=3, enable_verification=True, enable_tools=False)
    state = await agent.query("What changed?")

    assert state.iteration == 1
    assert state.final_answer == "final answer"
    assert phase_calls == ["answer"]
    assert any("DEGRADED_MODE" in step for step in state.reasoning)


@pytest.mark.asyncio
async def test_agent_answer_fallback_when_rate_limited(monkeypatch):
    async def fake_retrieve(*args, **kwargs):
        return _sample_docs()

    async def rate_limited_generate(prompt, system=None, temperature=0.7, max_tokens=None, phase=None):
        if phase == "answer":
            raise LLMRateLimitError("OpenRouter rate-limited")
        return "unused"

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "google/gemma-4-31b-it:free")
    monkeypatch.setattr(settings, "openrouter_free_mode_enabled", True)
    monkeypatch.setattr(settings, "openrouter_free_max_iterations", 1)
    monkeypatch.setattr(settings, "openrouter_free_disable_verification", True)
    monkeypatch.setattr(retrieval_service, "retrieve", fake_retrieve)
    monkeypatch.setattr(llm_service, "generate", rate_limited_generate)

    agent = AgenticRAG(max_iterations=2, enable_verification=False, enable_tools=False)
    state = await agent.query("Summarize docs")

    assert "temporarily rate-limited" in (state.final_answer or "").lower()
    assert any("DEGRADED_MODE" in step for step in state.reasoning)
