
# Comprehensive Bug Fix Plan: Chat Agent & RAG System Issues

## Problem Statement

The RAG system has **7 critical issues** preventing the chat agent and document processing from functioning:

### Chat Agent Issues (Sprint 5.1 - Immediate)
1. **Chat Agent 500 Error** - `/agent/status` endpoint crashes with `'Settings' object has no attribute 'top_k'`
2. **Chat Agent Endpoint Missing** - `/query/agentic` returns 404 (endpoint routes to `/query/` instead)
3. **Session Initialization** - Chat sessions show undefined ID, causing 422 errors

### System-Wide Issues
4. **SQL Timestamp Query Errors** - Cleanup service fails with invalid PostgREST syntax (`now() - interval '1 hour'`)
5. **Document Registry Empty** - Uploaded documents aren't synced to `documents_registry`; chunks created but metadata missing
6. **Continuous API Polling Loop** - Frontend polls `/ingest/documents` and `/database/status` every 3-5 seconds, causing database strain
7. **Large PDF Processing Failures** - PDFs 100+ pages cause `std::bad_alloc` errors; embedding failures skip chunks

## Root Causes

### Chat Agent (Immediate Blocking Issues)
| Issue | Root Cause | File | Line |
|-------|-----------|------|------|
| Settings typo | Code references `settings.top_k` but config defines `top_k_results` | `app/api/admin.py` | 124 |
| Missing endpoint | Router uses empty path `@router.post("")` but client expects `/agentic` | `app/api/query.py` | 21 |
| Session undefined | Frontend doesn't initialize session ID before API calls | `static/chat.html` | Session init logic |

### System Issues (Long-term Stability)
| Issue | Root Cause | Impact |
|-------|-----------|--------|
| SQL errors | Supabase REST API doesn't support timestamp arithmetic in queries | `/database/status` endpoint fails; cleanup tasks blocked |
| Empty registry | Document processor doesn't save metadata to `documents_registry` | Documents don't appear in UI after upload |
| High polling | Frontend polls status endpoints on 3-5s interval | Unnecessary database load |
| PDF crashes | Large PDFs exceed memory limits; embedding service fails silently | Large documents cause system instability |

## Solution Approach

### Tier 1: Critical Chat Agent Fixes (Immediate)
- Fix `settings.top_k` → `settings.top_k_results` typo
- Add `/agentic` endpoint routing to query service
- Initialize and validate session ID before API calls
- **Impact**: Chat interface becomes functional

### Tier 2: System Stability Fixes (High Priority)
- Replace invalid SQL with server-side timestamp calculations
- Fix document registry population on upload
- Update `ingest/documents` endpoint to query registry correctly
- **Impact**: Document management and statistics endpoints work

### Tier 3: Performance & Robustness (Medium Priority)
- Add polling throttling to frontend (reduce frequency)
- Implement page-based splitting for large PDFs
- Add fallback embedding strategy for failure handling
- **Impact**: System handles larger workloads without performance degradation

## Implementation Plan

### Phase 1: Chat Agent Restoration (T1 Todos)

#### T1.1: Fix Settings Attribute Typo
- **File**: `app/api/admin.py` line 124
- **Change**: `settings.top_k` → `settings.top_k_results`
- **Validation**: `/agent/status` returns 200 with proper configuration

#### T1.2: Add /query/agentic Endpoint
- **File**: `app/api/query.py` line 21
- **Change**: Add `@router.post("/agentic")` route or rename empty path to `"/agentic"`
- **Validation**: `POST /query/agentic` returns proper response

#### T1.3: Fix Chat Session Initialization
- **File**: `static/chat.html`
- **Issue**: Session ID not initialized before making API calls
- **Fix**: Ensure session is created and ID is available before any query requests
- **Validation**: Chat interface no longer shows undefined session ID

### Phase 2: System Stability (T2 Todos)

#### T2.1: Fix Timestamp Query in Cleanup
- **File**: `app/services/cleanup.py` line 161
- **Issue**: `.lt('created_at', 'now() - interval \'1 hour\'')` is invalid PostgREST syntax
- **Fix**: Calculate timestamp in Python before querying
  ```python
  from datetime import datetime, timedelta
  cutoff_time = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
  stuck_result = self.client.table('documents_registry') \
      .select('id', count='exact') \
      .eq('status', 'processing') \
      .lt('created_at', cutoff_time) \
      .execute()
  ```
- **Validation**: `/database/status` returns 200 with correct stats

#### T2.2: Verify Document Registry Population
- **File**: `app/services/document_processor.py`
- **Investigate**: Ensure documents_registry entries are created during upload
- **Fix**: Verify metadata is saved before chunks are inserted (transaction order)
- **Validation**: Uploaded documents appear in `/ingest/documents` response

#### T2.3: Fix ingest/documents Endpoint
- **File**: `app/api/ingest.py` (around lines 316-336)
- **Issue**: `list_documents()` returns only chunk sources, not document metadata
- **Fix**: Query `documents_registry` table directly with aggregated chunk stats
- **Validation**: UI shows documents with proper metadata and counts

### Phase 3: Performance & Robustness (T3 Todos)

#### T3.1: Add Polling Throttle to Frontend
- **File**: `static/js/state-manager.js`
- **Fix**: Add configurable polling interval (default 10s minimum)
- **Impact**: Reduce database load from continuous polling

#### T3.2: Implement Memory-Safe PDF Processing
- **File**: `app/services/document_processor.py`
- **Fix**: Add page limit (e.g., max 100 pages), process in chunks
- **Impact**: Large PDFs won't crash with memory errors

#### T3.3: Improve Embedding Failure Handling
- **File**: `app/services/document_processor.py`
- **Fix**: Add fallback or retry mechanism for failed embeddings
- **Impact**: No more lost chunks due to embedding failures

## Implementation Order

```
Phase 1 (Chat Agent - BLOCKERS):
├── T1.1: Fix settings typo
├── T1.2: Add /query/agentic endpoint
└── T1.3: Fix session initialization

Phase 2 (System Stability - can start after Phase 1):
├── T2.1: Fix timestamp query (highest priority - runs every 3-5s)
├── T2.2 & T2.3: Document registry (can run in parallel)

Phase 3 (Robustness - lower priority):
├── T3.1: Polling throttle
├── T3.2 & T3.3: PDF handling (can run in parallel)
```

## Success Criteria

### Chat Agent (Tier 1)
✅ `/agent/status` returns 200 with configuration including `top_k_results`  
✅ `POST /query/agentic` is accessible and returns proper AgentResponse  
✅ Chat interface initializes with valid session ID  
✅ No 500 or 404 errors in agent/chat flow  

### System Stability (Tier 2)
✅ `/database/status` returns 200 without SQL errors  
✅ Cleanup tasks complete without timestamp errors  
✅ Uploaded documents appear in document registry within 5 seconds  
✅ UI displays accurate document statistics  

### Performance (Tier 3)
✅ Polling frequency reduced to ≤1 request per 10 seconds per endpoint  
✅ Large PDFs (100+ pages) process without memory errors  
✅ No lost chunks due to embedding failures  

## Testing Strategy

1. **Unit Tests**: Verify each service function works correctly
2. **Integration Tests**: Test full workflows (upload → query → verify)
3. **API Tests**: Hit each endpoint and verify response format
4. **Load Tests**: Verify polling doesn't overwhelm database
5. **Edge Cases**: Test with large files, long chat sessions, rapid requests

## Dependencies & Risks

### Dependencies
- Phase 1 must complete before Phase 2 (chat agent must work first)
- T2.1 has highest priority - runs frequently and blocks other services
- T2.2 & T2.3 are interdependent (registry population affects documents endpoint)

### Risks
- **High**: If Phase 1 not fixed, chat interface is completely broken
- **Medium**: If T2.1 not fixed, database status monitoring fails (cascading errors)
- **Low**: Phase 3 fixes improve robustness but aren't blocking

## Files Modified

### Phase 1
- `app/api/admin.py`
- `app/api/query.py`
- `static/chat.html`

### Phase 2
- `app/services/cleanup.py`
- `app/services/document_processor.py`
- `app/api/ingest.py`

### Phase 3
- `static/js/state-manager.js`
- `app/services/document_processor.py` (additional changes)

## Progress Tracking

See SQL `todos` table for real-time progress:
- `fix-settings-typo` (T1.1)
- `add-agentic-endpoint` (T1.2)
- `verify-session-init` (T1.3)
- `fix-cleanup-sql` (T2.1)
- `verify-doc-registry` (T2.2/T2.3)
- `run-validation` (Final verification)

---

**Created**: 2026-04-10  
**Priority**: CRITICAL - Chat agent non-functional  
**Owner**: Development Team  
**Status**: Planning phase complete, ready for implementation
