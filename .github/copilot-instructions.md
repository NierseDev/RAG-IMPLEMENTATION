# Copilot Instructions

Terse like caveman. Technical substance exact. Only fluff die.
Drop: articles, filler (just/really/basically), pleasantries, hedging.
Fragments OK. Short synonyms. Code unchanged.
Pattern: [thing] [action] [reason]. [next step].
ACTIVE EVERY RESPONSE. No revert after many turns. No filler drift.
Code/commits/PRs: normal. Off: "stop caveman" / "normal mode".

## Commands

- Install deps: `pip install -r requirements.txt`
- Run app: `python main.py`
- Windows: `run.bat`
- Unix: `./run.sh`
- Full tests: `pytest -q`
- One file: `pytest -q tests\test_agent_router.py`
- One test: `pytest -q tests\test_agent_router.py::test_name`
- Single query debug: `python tools\debug\debug.py query "Your question here"`
- Upload suite: `python tests\test_upload.py all`

## Architecture

- `main.py` wires `admin`, `ingest`, `query`; serves `static/`.
- Core loop in `app/services/agent.py`: Plan → Retrieve → Reason → Verify → Decide → Answer/Iterate.
- Search split across vector, keyword, hybrid RRF in `app/services/query_service.py`.
- Supabase/Postgres in `app/core/database.py`; RPCs like `match_chunks` and `get_chunk_stats`.
- Ingest stores chunks, registry rows, metadata rows.
- `app/services/workflow_orchestrator.py` handles multi-tool flows, retries, fallbacks.
- `app/services/llm.py` handles provider selection and request budgets.
- Frontend JS in `static/js/` uses global state manager + API client.

## Conventions

- Use `app.core.config.settings` for config; `.env` is source of truth.
- Keep async tests marked `@pytest.mark.asyncio`; `pytest.ini` has `asyncio_mode = auto`.
- Keep `search_breakdown.method` present, including error paths.
- Record reasoning via `AgentState.add_reasoning()`.
- Keep ingest duplicate checks, temp-file cleanup, registry + metadata writes together.
- Reuse existing singletons: `db`, `query_service`, `llm_service`, `agent_router`.
- Follow frontend globals and action names in `static/js/README.md`.
