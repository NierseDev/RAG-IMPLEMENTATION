from datetime import datetime, timezone

import pytest

from app.models.entities import AgentState, RetrievalResult
from app.services.agent import AgenticRAG


def _doc(source: str, text: str, similarity: float) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=f"{source}_chunk",
        source=source,
        ai_provider="ollama",
        embedding_model="mxbai-embed-large",
        text=text,
        similarity=similarity,
        created_at=datetime.now(timezone.utc),
    )


def test_reasoning_entry_uses_iteration():
    state = AgentState(
        iteration=2,
        original_query="What is the refund policy?",
        current_query="What is the refund policy?",
    )

    state.add_reasoning("PLAN", "Look for refund terms")

    assert state.reasoning == ["[Iteration 2] PLAN: Look for refund terms"]


def test_retrieval_strength_uses_top_three_docs():
    agent = AgenticRAG(enable_verification=False, enable_tools=False)
    docs = [
        _doc("a.pdf", "A", 0.95),
        _doc("b.pdf", "B", 0.85),
        _doc("c.pdf", "C", 0.75),
        _doc("d.pdf", "D", 0.10),
    ]

    score = agent._calculate_retrieval_strength(docs)

    assert score == pytest.approx((0.95 + 0.85 + 0.75) / 3, rel=1e-6)


def test_continue_after_answer_refines_weak_answers():
    agent = AgenticRAG(enable_verification=False, enable_tools=False)
    state = AgentState(
        iteration=1,
        original_query="What is the refund policy?",
        current_query="What is the refund policy?",
        confidence=0.42,
        retrieved_docs=[_doc("a.pdf", "A", 0.22), _doc("b.pdf", "B", 0.18)],
    )

    should_continue, quality, reasons = agent._should_continue_after_answer(
        state,
        "Short answer",
        evidence_score=0.22,
        verification={"verified": False, "issues": ["missing citation"]},
    )

    assert should_continue is True
    assert quality == "weak"
    assert "confidence" in " ".join(reasons)
    assert "evidence" in " ".join(reasons)


def test_continue_after_answer_accepts_strong_answers():
    agent = AgenticRAG(enable_verification=False, enable_tools=False)
    state = AgentState(
        iteration=1,
        original_query="What is the refund policy?",
        current_query="What is the refund policy?",
        confidence=0.9,
        retrieved_docs=[_doc("a.pdf", "A", 0.91), _doc("b.pdf", "B", 0.88)],
    )

    should_continue, quality, reasons = agent._should_continue_after_answer(
        state,
        "Strong answer",
        evidence_score=0.9,
        verification={"verified": True, "issues": []},
    )

    assert should_continue is False
    assert quality == "great"
    assert reasons == []


def test_rate_limited_fallback_answer_uses_top_three_docs():
    agent = AgenticRAG(enable_verification=False, enable_tools=False)
    state = AgentState(
        iteration=1,
        original_query="What is the refund policy?",
        current_query="What is the refund policy?",
        retrieved_docs=[
            _doc("one.pdf", "One " + "x" * 240, 0.9),
            _doc("two.pdf", "Two", 0.8),
            _doc("three.pdf", "Three", 0.7),
            _doc("four.pdf", "Four", 0.6),
        ],
    )

    answer = agent._build_rate_limited_fallback_answer(state)

    assert "one.pdf" in answer
    assert "two.pdf" in answer
    assert "three.pdf" in answer
    assert "four.pdf" not in answer
    assert "..." in answer
