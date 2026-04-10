# Database Status Loop - Root Cause & Fixes

## Problem Statement
The `/database/status` endpoint was stuck in a loop reporting statistics that never changed, despite the database containing documents and chunks.

## Root Causes Identified

### 1. **Database Status Query Bug** (admin.py)
**Issue**: The endpoint was using incorrect Supabase query syntax:
```python
# WRONG: This doesn't populate data properly
doc_stats = client.table('documents_registry') \
    .select('status', count='exact') \
    .execute()
```

**Fix**: Changed to use proper SELECT query that retrieves all data:
```python
# CORRECT: Select all records and count manually
doc_result = client.table('documents_registry').select('*').execute()
total_docs = len(doc_result.data)
```

**Impact**: Now the status endpoint correctly reports document counts and status breakdowns.

### 2. **Missing Source Field in Registry Entry** (ingest.py)
**Issue**: When creating document registry entries, the `source` field was not being saved:
```python
registry_entry = {
    "filename": file.filename,
    # MISSING: "source": source,
    "file_hash": file_hash,
    ...
}
```

**Fix**: Added the `source` field to registry entries in both single and batch ingest endpoints.

### 3. **Missing Document-Chunk Linking** (ingest.py)
**Issue**: Chunks were created but never linked to their document registry entry. No `document_id` was being set on chunks.

**Fix**: Added code to link chunks to documents after registry creation:
```python
# After creating registry entry, link chunks to it
client.table('rag_chunks') \
    .update({'document_id': document_id}) \
    .eq('source', source) \
    .execute()
```

### 4. **Schema Missing Critical Fields** (init_supabase.sql)
**Issues**:
- `documents_registry` table lacked a `source` column to identify which documents created which chunks
- `rag_chunks` table lacked a `document_id` column to link chunks back to their source document

**Fixes Applied**:
- Added `source TEXT UNIQUE` to `documents_registry`
- Added `document_id BIGINT REFERENCES documents_registry(id) ON DELETE CASCADE` to `rag_chunks`
- Added `CREATE INDEX rag_chunks_document_id_idx ON rag_chunks (document_id)` for efficient lookups

## Why This Caused the Loop

1. Documents were never registered → `documents_registry` stayed empty
2. Chunks were created and stored → `rag_chunks` had 123 orphaned records
3. `/database/status` detected orphaned chunks and kept reporting them
4. Cleanup service couldn't remove them (no document registry to clean)
5. Loop: query → detect orphans → can't clean → query again

## Solution Components

### File Changes:
1. **app/api/admin.py**: Fixed `/database/status` endpoint query
2. **app/api/ingest.py**: Added `source` field and document-chunk linking (2 locations)
3. **init_supabase.sql**: Added `source` and `document_id` schema fields

### New Behavior:
- Document uploads now create proper registry entries with source tracking
- Chunks are automatically linked to their source documents
- Orphaned chunks can now be properly identified and cleaned
- Status endpoint reports accurate statistics

## For Existing Databases
If you have an existing Supabase project with orphaned chunks, you'll need to:

1. Add the missing columns:
   ```sql
   ALTER TABLE documents_registry ADD COLUMN source TEXT UNIQUE;
   ALTER TABLE rag_chunks ADD COLUMN document_id BIGINT REFERENCES documents_registry(id) ON DELETE CASCADE;
   ```

2. Re-ingest your documents to populate the registry and link chunks.

3. Alternatively, you can delete and reset to start fresh with the corrected schema.
