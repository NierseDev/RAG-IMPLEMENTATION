from datetime import datetime

import pytest

from app.models.entities import RetrievalResult
from app.services.document_processor import ChunkFragment, DocumentProcessor
from app.services.retrieval import retrieval_service


class _PrimaryConverter:
    def __init__(self):
        self.calls = 0

    def convert(self, file_path):
        self.calls += 1
        raise IndexError("list index out of range")


class _FallbackDocument:
    page_count = 3
    title = "Sample PDF"


class _FallbackConverter:
    def __init__(self, document):
        self.calls = 0
        self.document = document

    def convert(self, file_path):
        self.calls += 1
        return type("Result", (), {"document": self.document})()


async def _embed_stub(chunks):
    return [[0.1, 0.2, 0.3] for _ in chunks]


def test_validate_file_checks_type_and_size():
    processor = DocumentProcessor()

    valid, message = processor.validate_file("report.pdf", 1024)
    assert valid is True
    assert message == "Valid"

    valid, message = processor.validate_file("report.exe", 1024)
    assert valid is False
    assert "not supported" in message

    valid, message = processor.validate_file("report.pdf", 10**12)
    assert valid is False
    assert "too large" in message


def test_split_fragment_block_keeps_formula_context():
    processor = DocumentProcessor()

    fragments = processor._split_fragment_block("In physics, $$E=mc^2$$ describes mass-energy.")
    formula = next(fragment for fragment in fragments if fragment.is_formula)

    assert formula.metadata["content_type"] == "formula"
    assert formula.metadata["formula_context_before"] == "In physics,"
    assert formula.metadata["formula_context_after"] == "describes mass-energy."


@pytest.mark.asyncio
async def test_process_text_file_uses_text_path(tmp_path, monkeypatch):
    processor = DocumentProcessor()
    source = tmp_path / "notes.txt"
    source.write_text("Short prose block.", encoding="utf-8")

    converter = _PrimaryConverter()
    monkeypatch.setattr(processor, "_get_converter", lambda: converter)
    monkeypatch.setattr(processor, "_create_chunk_fragments", lambda text: [ChunkFragment(text)])
    monkeypatch.setattr(
        processor,
        "_create_chunks",
        lambda fragments: [{"text": fragments[0].text, "metadata": {"content_type": "prose"}}],
    )
    monkeypatch.setattr(processor, "_embed_batch_with_fallback", _embed_stub)

    chunks, metadata = await processor.process_document(str(source), "notes.txt", file_size=source.stat().st_size)

    assert converter.calls == 0
    assert len(chunks) == 1
    assert chunks[0].text == "Short prose block."
    assert metadata["text_extraction_mode"] == "plain-text"


@pytest.mark.asyncio
async def test_process_pdf_file_uses_fallback_converter(tmp_path, monkeypatch):
    processor = DocumentProcessor()
    processor.metadata_extractor = None

    primary = _PrimaryConverter()
    fallback = _FallbackConverter(_FallbackDocument())

    monkeypatch.setattr(processor, "_get_converter", lambda: primary)
    monkeypatch.setattr(processor, "_get_fallback_converter", lambda: fallback)
    monkeypatch.setattr(processor, "_extract_document_text", lambda doc: ("Recovered text", "markdown"))
    monkeypatch.setattr(processor, "_create_chunk_fragments", lambda text: [ChunkFragment(text)])
    monkeypatch.setattr(
        processor,
        "_create_chunks",
        lambda fragments: [{"text": fragments[0].text, "metadata": {"content_type": "prose"}}],
    )
    monkeypatch.setattr(processor, "_embed_batch_with_fallback", _embed_stub)

    pdf_path = tmp_path / "problem.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")

    chunks, metadata = await processor.process_document(str(pdf_path), "problem.pdf", file_size=16 * 1024 * 1024)

    assert primary.calls == 1
    assert fallback.calls == 1
    assert len(chunks) == 1
    assert chunks[0].text == "Recovered text"
    assert metadata["text_extraction_mode"] == "markdown"
    assert metadata["page_count"] == 3


def test_format_context_keeps_formula_metadata():
    result = RetrievalResult(
        chunk_id="chunk-1",
        source="doc.pdf",
        ai_provider="ollama",
        embedding_model="mxbai-embed-large",
        text="$$E=mc^2$$",
        similarity=0.95,
        metadata={
            "content_type": "formula",
            "formula_context_before": "In physics,",
            "formula_context_after": "describes mass-energy.",
        },
        created_at=datetime.utcnow(),
    )

    context = retrieval_service.format_context([result], max_tokens=200)

    assert "context-before: In physics," in context
    assert "context-after: describes mass-energy." in context
    assert "evidence: $$E=mc^2$$" in context
