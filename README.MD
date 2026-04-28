# Agentic RAG API

FastAPI app for agentic retrieval-augmented generation. It ingests documents, stores chunks in Supabase, and answers queries with hybrid retrieval and verification.

## Features

- Agentic reasoning loop
- Hybrid search with metadata filters
- Document ingestion with duplicate handling
- Chat session storage
- Debug and admin endpoints

## Tech Stack

- FastAPI
- Supabase and pgvector
- Ollama
- Docling
- Pytest

## Quick Start

### Production Start

```bash
pip install -r requirements.txt
python main.py
```

Set `.env` with Supabase credentials and the AI provider settings you want to use.

### Debug Start

```bash
python main.py
```

Open `/debug` in the browser. Set `DEBUG_MODE=true` in `.env` if you want reload behavior.

## API Endpoints

| API Endpoint | Description |
| --- | --- |
| `GET /health` | System health check |
| `GET /stats` | Chunk and source statistics |
| `DELETE /reset` | Clear stored chunk data |
| `GET /agent/status` | Current agent and provider status |
| `GET /database/status` | Database and maintenance status |
| `POST /cleanup` | Run cleanup tasks |
| `POST /ingest` | Upload one document |
| `POST /ingest/upload` | Upload alias for one document |
| `POST /ingest/check-duplicates` | Check file existence before upload |
| `POST /ingest/batch` | Upload multiple documents |
| `POST /query/agentic` | Full agentic query flow |
| `POST /query/simple` | Single-pass RAG query |
| `POST /query/hybrid` | Hybrid vector and keyword search |
| `POST /query/sessions` | Create a chat session |
| `GET /query/sessions` | List chat sessions |
| `GET /query/sessions/{session_id}` | Get one session and messages |
| `PATCH /query/sessions/{session_id}` | Update session title |
| `DELETE /query/sessions/{session_id}` | Delete a session |
