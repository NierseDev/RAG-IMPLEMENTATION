from datetime import datetime, timezone

import pytest

from app.models.entities import AgentState, RetrievalResult
from app.services.agent import AgenticRAG
from app.services.llm import llm_service
from app.services.verification import verification_service
from app.tools.web_search_tool import web_search_tool


def _strong_docs() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="doc_1",
            source="policy_a.txt",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Eligible users may request refunds within thirty days if they include receipt and order information.",
            similarity=0.92,
            created_at=datetime.now(timezone.utc),
        ),
        RetrievalResult(
            chunk_id="doc_2",
            source="policy_b.txt",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Refund requests require receipt and order information within thirty days of purchase.",
            similarity=0.88,
            created_at=datetime.now(timezone.utc),
        ),
    ]


@pytest.mark.asyncio
async def test_verification_confidence_leans_on_strong_evidence(monkeypatch):
    async def fake_generate(prompt, system=None, temperature=0.7, max_tokens=None, phase=None):
        return """Verified: no
Confidence score: 0.18
Issues: none"""

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    result = await verification_service.verify_answer(
        query="What are the refund rules?",
        answer="Eligible users may request refunds within thirty days if they include receipt and order information.",
        retrieved_docs=_strong_docs(),
    )

    assert result["verified"] is False
    assert result["grounding_score"] > 0.5
    assert result["retrieval_strength"] > 0.8
    assert result["evidence_score"] >= result["grounding_score"]
    assert result["confidence"] >= 0.7


@pytest.mark.asyncio
async def test_decide_phase_answers_on_grounded_evidence_override():
    agent = AgenticRAG(enable_verification=True, enable_tools=False)
    state = AgentState(
        iteration=1,
        original_query="What are the refund rules?",
        current_query="What are the refund rules?",
        retrieved_docs=_strong_docs(),
        confidence=0.58,
        verification_results=[
            {
                "verified": False,
                "confidence": 0.58,
                "grounding_score": 0.82,
                "retrieval_strength": 0.9,
                "evidence_score": 0.9,
            }
        ],
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        verification_service,
        "detect_information_gaps",
        lambda query, docs: (True, ["Low average similarity"]),
    )
    try:
        decision = await agent._decide_phase(state, "answer")
    finally:
        monkeypatch.undo()

    assert decision == "answer"


@pytest.mark.asyncio
async def test_decide_phase_keeps_conservative_behavior_on_weak_evidence():
    agent = AgenticRAG(enable_verification=True, enable_tools=False)
    state = AgentState(
        iteration=1,
        original_query="What are the refund rules?",
        current_query="What are the refund rules?",
        retrieved_docs=[
            RetrievalResult(
                chunk_id="doc_1",
                source="policy_a.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text="Short note about refunds.",
                similarity=0.21,
                created_at=datetime.now(timezone.utc),
            ),
            RetrievalResult(
                chunk_id="doc_2",
                source="policy_b.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text="Another short note.",
                similarity=0.19,
                created_at=datetime.now(timezone.utc),
            ),
        ],
        confidence=0.32,
        verification_results=[
            {
                "verified": False,
                "confidence": 0.32,
                "grounding_score": 0.18,
                "retrieval_strength": 0.2,
                "evidence_score": 0.2,
            }
        ],
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        verification_service,
        "detect_information_gaps",
        lambda query, docs: (True, ["Insufficient evidence"]),
    )
    try:
        decision = await agent._decide_phase(state, "answer")
    finally:
        monkeypatch.undo()

    assert decision == "continue"


@pytest.mark.asyncio
async def test_duckduckgo_html_search_parses_and_normalizes_results(monkeypatch):
    html = """
    <html><body>
      <div class="result results_links results_links_deep web-result ">
        <div class="links_main links_deep result__body">
          <h2 class="result__title">
            <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&amp;rut=1">Example A</a>
          </h2>
          <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&amp;rut=1">First snippet.</a>
        </div>
      </div>
      <div class="result results_links results_links_deep web-result ">
        <div class="links_main links_deep result__body">
          <h2 class="result__title">
            <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fb&amp;rut=2">Example B</a>
          </h2>
          <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fb&amp;rut=2">Second snippet.</a>
        </div>
      </div>
    </body></html>
    """

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeClient:
        async def get(self, url, params=None, headers=None):
            return FakeResponse(html)

    async def fake_instant_answer_api(query):
        return []

    monkeypatch.setattr(web_search_tool, "client", FakeClient())
    monkeypatch.setattr(web_search_tool, "_instant_answer_api", fake_instant_answer_api)

    result = await web_search_tool.execute("example query", max_results=2)

    assert result["success"] is True
    assert result["count"] == 2
    assert result["results"][0]["title"] == "Example A"
    assert result["results"][0]["url"] == "https://example.com/a"
    assert result["results"][0]["snippet"] == "First snippet."
    assert result["attribution"]["result_count"] == 2
