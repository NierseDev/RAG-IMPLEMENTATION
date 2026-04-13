from datetime import datetime, timezone

from app.models.entities import RetrievalResult
from app.services.agent import AgenticRAG
from app.services.llm import llm_service
from app.services.retrieval import retrieval_service
from app.services.verification import verification_service


def _sample_result(chunk_id: str = "doc_page_12_chunk_3") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        source="sample_doc.pdf",
        ai_provider="ollama",
        embedding_model="mxbai-embed-large",
        text="Sample evidence text about machine learning evaluation metrics.",
        similarity=0.87,
        created_at=datetime.now(timezone.utc)
    )


def test_verify_prompt_has_explicit_format_requirements():
    prompt = llm_service.create_verify_prompt("What is X?", "X is Y", "Context text")
    assert "YOU MUST respond in this exact format" in prompt
    assert "Confidence score:" in prompt
    assert "Return ONLY these three lines." in prompt


def test_answer_prompt_mentions_web_search_when_context_insufficient():
    prompt = llm_service.create_answer_prompt("What is X?", "Context text")
    assert "web search is required before a final answer" in prompt.lower()
    assert "Output structure:" in prompt
    assert "References:" in prompt


def test_parse_verification_supports_new_format():
    verification_text = """Verified: yes
Confidence score: 0.91
Issues: none"""
    parsed = verification_service._parse_verification(verification_text)
    assert parsed["verified"] is True
    assert parsed["confidence"] == 0.91
    assert parsed["issues"] == []


def test_parse_verification_supports_legacy_format():
    verification_text = """Verified: no
Confidence: 0.42
Issues: Unsupported claim about release year"""
    parsed = verification_service._parse_verification(verification_text)
    assert parsed["verified"] is False
    assert parsed["confidence"] == 0.42
    assert "Unsupported claim about release year" in parsed["issues"][0]


def test_context_formatting_has_markers_and_end_section():
    context = retrieval_service.format_context([_sample_result()])
    assert "=== Source 1 ===" in context
    assert "Similarity Score:" in context
    assert "END OF CONTEXT" in context


def test_verification_context_formatting_has_markers_and_end_section():
    context = verification_service._format_context([_sample_result()])
    assert "=== Source 1 ===" in context
    assert "Content:" in context
    assert context.strip().endswith("END OF CONTEXT")


def test_web_results_are_transformed_into_retrieval_context_chunks():
    agent = AgenticRAG(enable_tools=False)
    web_results = [
        {
            "title": "Doc A",
            "snippet": "Key external evidence.",
            "url": "https://example.com/a",
            "source": "Example"
        }
    ]

    transformed = agent._web_results_to_retrieval_results(web_results, iteration=1)

    assert len(transformed) == 1
    assert transformed[0].source == "web:Example"
    assert transformed[0].ai_provider == "web_search"
    assert "https://example.com/a" in transformed[0].text
