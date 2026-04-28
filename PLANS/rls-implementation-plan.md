# Plan: Implement RLS (Row Level Security) on RAG Chat and Document Tables

## Problem Statement
The current `init_supabase.sql` has RLS on `rag_chunks` but NOT on the chat and document tables. We need to add RLS to:
- `chat_messages`
- `chat_sessions`
- `document_metadata`
- `document_registry`

This ensures multi-user data isolation: each user sees only their own data, while the DEBUG mode (service_role) can bypass RLS for testing.

## Requirements
1. **Authentication**: Use `auth.uid()` (Supabase built-in) with fallback optional support
2. **Ownership Model**: Each record belongs to a specific user
3. **Access Control**: Users see only their own data; role-based access for admins/DEBUG
4. **API-First**: Implement for API usage (web UI is debug-only and may bypass via service_role)
5. **DEBUG Support**: Service role can bypass RLS entirely

## Implementation Approach

### 1. Add `user_id` Column to Tables
- Modify `chat_sessions` to include `user_id` (extracted from `auth.uid()`)
- Modify `chat_messages` to include `user_id` (for direct filtering)
- Modify `document_registry` to include `user_id`
- Modify `document_metadata` to inherit user_id through cascade/FK

### 2. Create Indexes
- Index each table on `(user_id, created_at DESC)` for efficient user-scoped queries
- Keep existing indexes intact

### 3. Enable RLS and Create Policies
For each table:
- Enable RLS
- **Service Role Policy**: `FOR ALL` allow all (DEBUG access)
- **User Read Policy**: `FOR SELECT` where `user_id = auth.uid()`
- **User Insert Policy**: `FOR INSERT` with default `user_id = auth.uid()`
- **User Update Policy**: `FOR UPDATE` where `user_id = auth.uid()`
- **User Delete Policy**: `FOR DELETE` where `user_id = auth.uid()`

### 4. Handle Foreign Keys Correctly
- `document_metadata` → `document_registry`: ensure cascade deletes maintain `user_id` isolation
- `chat_messages` → `chat_sessions`: ensure users can't access other users' sessions

## Detailed Changes to init_supabase.sql

### STEP 8: documents_registry (lines 210-231)
```sql
-- Add user_id column
-- Create index on user_id for scoped queries
-- Enable RLS and add 5 policies
```

### STEP 9: document_metadata (lines 233-250)
```sql
-- Verify document_id FK works with RLS
-- Add user_id (denormalized or inherited)
-- Create index on user_id
-- Enable RLS and add 5 policies
```

### STEP 13: chat_sessions (lines 325-333)
```sql
-- Add user_id column
-- Create index on user_id
-- Enable RLS and add 5 policies
```

### STEP 13: chat_messages (lines 335-342)
```sql
-- Add user_id column
-- Create index on user_id
-- Enable RLS and add 5 policies
```

## Edge Cases to Handle
1. **Null user_id**: Queries with null `auth.uid()` should fail (except service_role)
2. **Foreign key constraints**: RLS + FK requires careful policy design
3. **Backward compatibility**: Existing anonymous queries will fail unless service_role is used
4. **document_metadata isolation**: Must enforce that user can only see metadata for their documents

## Verification Tests
- [ ] Service role can read all records
- [ ] Authenticated user can only read their own records
- [ ] Authenticated user can only insert with their own user_id
- [ ] Cross-user access is blocked (404 or empty results)
- [ ] Foreign key cascades respect RLS boundaries

## Files to Modify
- `init_supabase.sql` — Core implementation of RLS policies and schema changes

## Related Commands
```bash
# Validate RLS is enabled
SELECT tablename FROM pg_tables WHERE schemaname = 'public' 
AND tablename IN ('chat_sessions', 'chat_messages', 'document_registry', 'document_metadata');

SELECT * FROM pg_policies WHERE schemaname = 'public' 
AND tablename IN ('chat_sessions', 'chat_messages', 'document_registry', 'document_metadata');
```
