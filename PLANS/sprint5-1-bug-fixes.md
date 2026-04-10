# Bug Fix Plan: RAG System Issues (Sprint 5.1)

## Problem Statement
The RAG system has four critical issues preventing it from functioning properly:

1. **Document Registry Empty** - Uploaded documents aren't synced to `documents_registry` table; chunks are pushed but metadata is missing
2. **Database Statistics Errors** - Stats endpoint fails due to malformed timestamp query (`now() - interval '1 hour'`)
3. **Continuous API Polling Loop** - Frontend polls `/ingest/documents` and `/database/status` every 3-5 seconds, causing database strain
4. **Docling Memory Errors** - Large PDFs (100+ pages) cause `std::bad_alloc` errors; embedding failures cause chunks to be skipped

## Approach

### Phase 1: Fix SQL Query Errors (HIGH PRIORITY)
- **Issue**: Supabase PostgREST doesn't support `now() - interval '1 hour'` syntax directly in REST query
- **Solution**: Use absolute timestamp or fetch in Python and filter in memory
- **Impact**: Unblocks `/database/status` endpoint which is called every 3-5 seconds

### Phase 2: Fix Document Registry Sync (HIGH PRIORITY)
- **Issue**: `documents_registry` table is populated but `ingest/documents` endpoint returns empty
- **Investigation needed**: 
  - Check if documents_registry is being populated on upload
  - Check if `ingest/documents` endpoint is reading from correct table
  - Check if there's a mismatch between what gets pushed and what UI expects
- **Solution**: Ensure document_processor creates registry entries and endpoint queries correctly

### Phase 3: Fix API Polling Loop (MEDIUM PRIORITY)
- **Issue**: Frontend polls endpoints continuously, causing unnecessary database load
- **Solution**: 
  - Add polling interval configuration (default 5-10s instead of 3-5s)
  - Add polling debounce/throttle in frontend
  - Implement conditional polling (stop polling when no changes detected)
  - Add exponential backoff for failed requests

### Phase 4: Handle Large PDF Processing (MEDIUM PRIORITY)
- **Issue**: Docling preprocessing fails with `std::bad_alloc` on large PDFs; embeddings fail partially
- **Solution**:
  - Implement page-based splitting before processing (process first 50 pages, then skip large PDFs)
  - Add memory monitoring and graceful degradation
  - Improve embedding failure handling (don't skip chunks, use fallback embedding)
  - Add configuration for max document pages

## Implementation Tasks

### Task 1: Fix Timestamp Query in cleanup.py
- File: `app/services/cleanup.py` line 161
- Issue: `.lt('created_at', 'now() - interval \'1 hour\'')` is invalid PostgREST syntax
- Fix: Use Python datetime arithmetic instead of SQL in query
- Impact: Unblocks `/database/status` endpoint

### Task 2: Verify Document Registry Population
- File: `app/services/document_processor.py`
- Investigate: Check if documents_registry entries are created on upload
- Fix: Ensure document metadata is saved before chunks are inserted
- Impact: Documents will appear in UI after upload

### Task 3: Fix ingest/documents Endpoint
- File: `app/api/ingest.py` line 316-336
- Issue: `list_documents()` only returns sources from `rag_chunks`, not full document metadata
- Fix: Query `documents_registry` table directly for complete document info with stats
- Impact: UI will show actual documents with metadata

### Task 4: Add Polling Throttling to Frontend
- File: `static/js/state-manager.js`
- Fix: Add polling interval configuration and debounce mechanism
- Impact: Reduce database load from continuous polling

### Task 5: Implement Memory-Safe PDF Processing
- File: `app/services/document_processor.py`
- Fix: Add page limit and graceful handling of large PDFs
- Impact: Large PDFs won't crash the system

### Task 6: Improve Embedding Failure Handling
- File: `app/services/document_processor.py`
- Issue: Chunks are skipped when embeddings fail (generates 0-2 successful embeddings from 22 total)
- Fix: Use fallback embedding strategy or retry mechanism
- Impact: No more lost chunks due to embedding failures

## Dependencies & Order
1. Task 1 must complete first (fixes immediate errors blocking /database/status)
2. Task 2 & 3 can run in parallel (both needed for document registry display)
3. Task 4 can run immediately (frontend change, low risk)
4. Task 5 & 6 can run in parallel (both improve PDF processing robustness)

## Success Criteria
✅ No SQL errors in logs for `/database/status` endpoint
✅ Uploaded documents appear in document registry within 5 seconds
✅ UI displays accurate document statistics
✅ Polling frequency reduced to < 1 request per 10 seconds per endpoint
✅ Large PDFs (100+ pages) process without memory errors or chunk loss
✅ Embedding failures don't result in lost chunks
