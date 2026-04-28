from types import SimpleNamespace

import pytest

from app.api.ingest import compute_bytes_hash, get_source_type, ingest_documents_batch


class _DummyFile:
    def __init__(self, filename: str, content: bytes = b"sample file"):
        self.filename = filename
        self._content = content
        self.read_calls = 0

    async def read(self):
        self.read_calls += 1
        return self._content


class _FakeTable:
    def __init__(self, result_data=None):
        self.result_data = result_data if result_data is not None else []
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def delete(self):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.result_data)


class _FakeClient:
    def __init__(self):
        self.tables = {
            "documents_registry": _FakeTable([{"id": 7}]),
            "rag_chunks": _FakeTable([]),
            "document_metadata": _FakeTable([]),
        }

    def table(self, name):
        return self.tables[name]


class _FakeDB:
    def __init__(self, source_exists=False, chunk_count=0, inserted_chunks=1):
        self.source_exists_value = source_exists
        self.chunk_count_value = chunk_count
        self.inserted_chunks = inserted_chunks
        self.deleted_sources = []
        self.client = _FakeClient()

    async def source_exists(self, source):
        return self.source_exists_value

    async def get_source_chunk_count(self, source):
        return self.chunk_count_value

    async def delete_by_source(self, source):
        self.deleted_sources.append(source)
        return self.chunk_count_value

    async def insert_chunks_batch(self, chunks):
        self.client.tables["documents_registry"].payload = None
        return self.inserted_chunks


class _FakeProcessor:
    def __init__(self, valid=True, chunks=None, metadata=None):
        self.valid = valid
        self.chunks = chunks or [{"text": "chunk", "metadata": {}}]
        self.metadata = metadata or {"chunking_method": "fixed"}
        self.validate_calls = []
        self.process_calls = []

    def validate_file(self, filename, file_size):
        self.validate_calls.append((filename, file_size))
        return self.valid, "Valid"

    async def process_document(self, file_path, source, file_size=None):
        self.process_calls.append((file_path, source, file_size))
        return self.chunks, self.metadata


def test_hash_and_source_type():
    assert compute_bytes_hash(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert get_source_type("report.pdf") == "pdf"
    assert get_source_type("notes.md") == "md"
    assert get_source_type("archive.zip") == "other"


@pytest.mark.asyncio
async def test_skip_duplicate_marks_status(monkeypatch):
    from app.api import ingest as ingest_module

    fake_db = _FakeDB(source_exists=True, chunk_count=4)
    fake_processor = _FakeProcessor()
    monkeypatch.setattr(ingest_module, "db", fake_db)
    monkeypatch.setattr(ingest_module, "document_processor", fake_processor)

    file = _DummyFile("report.pdf")
    result = await ingest_documents_batch([file], source_prefix="docs", duplicate_action="skip")

    assert file.read_calls == 0
    assert result.successful == 0
    assert result.failed == 0
    assert result.results[0]["status"] == "SKIPPED"
    assert result.results[0]["skipped"] is True


@pytest.mark.asyncio
async def test_append_duplicate_marks_status(monkeypatch):
    from app.api import ingest as ingest_module

    fake_db = _FakeDB(source_exists=True, chunk_count=2, inserted_chunks=3)
    fake_processor = _FakeProcessor()
    monkeypatch.setattr(ingest_module, "db", fake_db)
    monkeypatch.setattr(ingest_module, "document_processor", fake_processor)

    file = _DummyFile("report.pdf", b"content")
    result = await ingest_documents_batch([file], source_prefix="docs", duplicate_action="append")

    assert file.read_calls == 1
    assert fake_processor.process_calls[0][1] == "docs/report.pdf"
    assert result.successful == 1
    assert result.results[0]["status"] == "APPENDED"
    assert result.results[0]["action"] == "appended"
    assert result.results[0]["existing_chunks"] == 2
    assert result.results[0]["total_chunks"] == 5


@pytest.mark.asyncio
async def test_replace_duplicate_marks_status(monkeypatch):
    from app.api import ingest as ingest_module

    fake_db = _FakeDB(source_exists=True, chunk_count=2, inserted_chunks=1)
    fake_processor = _FakeProcessor()
    monkeypatch.setattr(ingest_module, "db", fake_db)
    monkeypatch.setattr(ingest_module, "document_processor", fake_processor)

    file = _DummyFile("report.pdf", b"content")
    result = await ingest_documents_batch([file], source_prefix="docs", duplicate_action="replace")

    assert file.read_calls == 1
    assert fake_db.deleted_sources == ["docs/report.pdf"]
    assert result.successful == 1
    assert result.results[0]["status"] == "REPLACED"
    assert result.results[0]["action"] == "replaced"
    assert result.results[0]["previous_chunks"] == 2
