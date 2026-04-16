from datetime import datetime, timezone

from app.models.entities import RetrievalResult
from app.services.agent import AgenticRAG
from app.services.llm import llm_service
from app.services.retrieval import retrieval_service
from app.services.verification import verification_service


def _sample_result(
    chunk_id: str = "doc_page_12_chunk_3",
    source: str = "sample_doc.pdf",
    text: str = "Sample evidence text about machine learning evaluation metrics."
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        source=source,
        ai_provider="ollama",
        embedding_model="mxbai-embed-large",
        text=text,
        similarity=0.87,
        created_at=datetime.now(timezone.utc)
    )


def test_verify_prompt_has_explicit_format_requirements():
    prompt = llm_service.create_verify_prompt("What is X?", "X is Y", "Context text")
    assert "Reply exactly:" in prompt
    assert "Confidence score:" in prompt
    assert "Issues: [none or short semicolon-separated issues]" in prompt


def test_answer_prompt_mentions_web_search_when_source_texts_insufficient():
    prompt = llm_service.create_answer_prompt("What is X?", "Context text")
    assert "web evidence blocks" in prompt.lower()
    assert "2-4 short sentences" in prompt
    assert "Format:" in prompt
    assert "References:" in prompt
    assert "Do not cite chunk numbers." in prompt
    assert "Output structure:" not in prompt


def test_answer_output_normalizer_strips_wrapper_text():
    raw = """Answer: The policy is 30 days [1].

References:
- sample_doc.pdf"""
    cleaned = llm_service.normalize_answer_output(raw)
    assert cleaned == "The policy is 30 days [1]."


def test_source_references_use_document_titles_when_available():
    refs = retrieval_service.build_source_references(
        [
            _sample_result(chunk_id="chunk-1", source="sample_doc.pdf"),
            _sample_result(chunk_id="chunk-2", source="another_doc.md")
        ],
        document_names={"sample_doc.pdf": "Sample Document Title"}
    )

    assert refs[0]["document_name"] == "Sample Document Title"
    assert refs[0]["source"] == "sample_doc.pdf"
    assert refs[1]["document_name"] == "another_doc"
    assert refs[1]["chunk_id"] == "chunk-2"


def test_source_references_use_web_titles_and_urls():
    refs = retrieval_service.build_source_references(
        [
            RetrievalResult(
                chunk_id="web_1_1",
                source="web:example.com",
                ai_provider="web_search",
                embedding_model="tavily_result",
                text="Web evidence",
                similarity=0.55,
                created_at=datetime.now(timezone.utc),
                title="Example Article",
                url="https://example.com/article",
            )
        ]
    )

    assert refs[0]["document_name"] == "Example Article"
    assert refs[0]["title"] == "Example Article"
    assert refs[0]["url"] == "https://example.com/article"


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
    assert "score:" in context
    assert "text:" in context
    assert "END OF CONTEXT" in context


def test_context_formatting_groups_chunks_by_source():
    context = retrieval_service.format_context([
        _sample_result(chunk_id="one"),
        _sample_result(chunk_id="two")
    ])
    assert context.count("=== Source 1 ===") == 1
    assert "=== Source 2 ===" not in context
    assert "chunk_count: 2" in context


def test_verification_context_formatting_has_markers_and_end_section():
    context = verification_service._format_context([_sample_result()])
    assert "=== Source 1 ===" in context
    assert "source:" in context
    assert "chunk:" in context
    assert context.strip().endswith("END OF CONTEXT")


def test_context_formatting_respects_max_results():
    context = retrieval_service.format_context([_sample_result("one"), _sample_result("two")], max_results=1)
    assert "Source 1" in context
    assert "Source 2" not in context


def test_context_formatting_truncates_large_chunk_text():
    long_text = "important evidence " * 200
    context = retrieval_service.format_context(
        [_sample_result(text=long_text)],
        max_tokens=120,
        max_result_tokens=30
    )

    assert "..." in context
    assert len(context) < len(long_text)


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
    assert transformed[0].source == "web:example.com"
    assert transformed[0].title == "Doc A"
    assert transformed[0].ai_provider == "web_search"
    assert "https://example.com/a" in transformed[0].text
    assert transformed[0].url == "https://example.com/a"


def test_web_results_are_truncated_and_capped_for_agent_context():
    agent = AgenticRAG(enable_tools=False)
    web_results = [
        {
            "title": f"Doc {idx}",
            "snippet": "x" * 1000,
            "url": f"https://example.com/{idx}",
            "source": "Example"
        }
        for idx in range(3)
    ]

    transformed = agent._web_results_to_retrieval_results(web_results, iteration=1)

    assert len(transformed) == 2
    assert all(len(result.text) <= agent.WEB_CONTEXT_MAX_CHARS for result in transformed)
