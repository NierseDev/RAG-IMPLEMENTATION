-- Copyright 2024
-- Directory: yt-rag/sql/init_supabase.sql
-- 
-- Complete Supabase Database Setup for RAG Application
-- Run this script on a FRESH Supabase project
-- 
-- Instructions:
-- 1. Create a new Supabase project at https://supabase.com
-- 2. Wait for project initialization to complete
-- 3. Go to SQL Editor in your Supabase dashboard
-- 4. Create a new query
-- 5. Copy and paste this ENTIRE script
-- 6. Click "Run" to execute everything at once
--
-- This script creates everything from scratch

-- =============================================================================
-- STEP 1: Enable pgvector extension for vector similarity search
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- STEP 2: Create the main RAG chunks table
-- =============================================================================

CREATE TABLE rag_chunks (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    ai_provider TEXT NOT NULL DEFAULT 'ollama' CHECK (ai_provider IN ('ollama', 'openai')),
    embedding_model TEXT NOT NULL DEFAULT 'mxbai-embed-large',
    embedding VECTOR NOT NULL,  -- Supports multiple dimensions (for example 1024 and 1536)
    CHECK (vector_dims(embedding) IN (1024, 1536)),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================================================================
-- STEP 3: Create performance indexes for fast vector search
-- =============================================================================

-- Create per-dimension vector indexes for supported embedding models.
-- This supports both:
-- - Ollama mxbai-embed-large (1024 dimensions)
-- - OpenAI text-embedding-3-small (1536 dimensions)
CREATE INDEX rag_chunks_vec_1024_idx
  ON rag_chunks USING ivfflat ((embedding::vector(1024)) vector_cosine_ops)
  WITH (lists = 100)
  WHERE vector_dims(embedding) = 1024;

CREATE INDEX rag_chunks_vec_1536_idx
  ON rag_chunks USING ivfflat ((embedding::vector(1536)) vector_cosine_ops)
  WITH (lists = 100)
  WHERE vector_dims(embedding) = 1536;

-- Regular B-tree indexes for filtering and sorting
CREATE INDEX rag_chunks_src_idx ON rag_chunks (source);
CREATE INDEX rag_chunks_chunk_id_idx ON rag_chunks (chunk_id);
CREATE INDEX rag_chunks_created_at_idx ON rag_chunks (created_at DESC);
CREATE INDEX rag_chunks_provider_idx ON rag_chunks (ai_provider);
CREATE INDEX rag_chunks_model_idx ON rag_chunks (embedding_model);

-- =============================================================================
-- STEP 4: Create vector similarity search function
-- =============================================================================

CREATE OR REPLACE FUNCTION match_chunks (
  query_embedding vector,
  match_count int DEFAULT 6,
  min_similarity float DEFAULT 0.0,
  filter_source text DEFAULT NULL,
  filter_provider text DEFAULT NULL,
  filter_model text DEFAULT NULL
)
RETURNS TABLE (
  chunk_id text,
  source text,
  ai_provider text,
  embedding_model text,
  text text,
  similarity float,
  created_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    rag_chunks.chunk_id,
    rag_chunks.source,
    rag_chunks.ai_provider,
    rag_chunks.embedding_model,
    rag_chunks.text,
    1 - (rag_chunks.embedding <=> query_embedding) as similarity,
    rag_chunks.created_at
  FROM rag_chunks
  WHERE vector_dims(rag_chunks.embedding) = vector_dims(query_embedding)
    AND 1 - (rag_chunks.embedding <=> query_embedding) >= min_similarity
    AND (filter_source IS NULL OR rag_chunks.source = filter_source)
    AND (filter_provider IS NULL OR rag_chunks.ai_provider = filter_provider)
    AND (filter_model IS NULL OR rag_chunks.embedding_model = filter_model)
  ORDER BY rag_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 5: Create helper function to get database statistics
-- =============================================================================

CREATE OR REPLACE FUNCTION get_chunk_stats()
RETURNS TABLE (
  total_chunks bigint,
  unique_sources bigint,
  unique_models bigint,
  latest_chunk timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*) as total_chunks,
    COUNT(DISTINCT source) as unique_sources,
    COUNT(DISTINCT embedding_model) as unique_models,
    MAX(created_at) as latest_chunk
  FROM rag_chunks;
END;
$$;

-- =============================================================================
-- STEP 6: Create Row Level Security (RLS) policies
-- =============================================================================

-- Enable RLS on the table
ALTER TABLE rag_chunks ENABLE ROW LEVEL SECURITY;

-- Allow all operations for service role (your backend)
CREATE POLICY "Allow service role full access" ON rag_chunks
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Allow read access for authenticated users (future frontend)
CREATE POLICY "Allow authenticated read access" ON rag_chunks
  FOR SELECT USING (auth.role() = 'authenticated');

-- Allow anonymous read access for development (remove in production)
CREATE POLICY "Allow anonymous read access" ON rag_chunks
  FOR SELECT USING (true);

-- =============================================================================
-- STEP 7: Verification - Test that everything was created correctly
-- =============================================================================

-- Test 1: Check pgvector extension
SELECT 'pgvector extension installed' as test_result 
WHERE EXISTS (
  SELECT 1 FROM pg_extension WHERE extname = 'vector'
);

-- Test 2: Check table creation
SELECT 'rag_chunks table created' as test_result 
WHERE EXISTS (
  SELECT 1 FROM information_schema.tables 
  WHERE table_schema = 'public' AND table_name = 'rag_chunks'
);

-- Test 3: Check vector column exists
SELECT 
  'Vector column configured' as test_result,
  'VECTOR type supports multiple dimensions' as details
WHERE EXISTS (
  SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'rag_chunks' 
  AND column_name = 'embedding'
);

-- Test 4: Check functions
SELECT 'match_chunks function created' as test_result 
WHERE EXISTS (
  SELECT 1 FROM information_schema.routines 
  WHERE routine_schema = 'public' AND routine_name = 'match_chunks'
);

SELECT 'get_chunk_stats function created' as test_result 
WHERE EXISTS (
  SELECT 1 FROM information_schema.routines 
  WHERE routine_schema = 'public' AND routine_name = 'get_chunk_stats'
);

-- Test 5: Check indexes
SELECT '1024 vector index created' as test_result
WHERE EXISTS (
  SELECT 1 FROM pg_indexes 
  WHERE tablename = 'rag_chunks' AND indexname = 'rag_chunks_vec_1024_idx'
);

SELECT '1536 vector index created' as test_result
WHERE EXISTS (
  SELECT 1 FROM pg_indexes 
  WHERE tablename = 'rag_chunks' AND indexname = 'rag_chunks_vec_1536_idx'
);

-- Test 6: Show initial database stats (should be empty)
SELECT 
  'Database ready - ' || total_chunks::text || ' chunks' as test_result
FROM get_chunk_stats();

-- =============================================================================
-- STEP 8: Create documents_registry table (Phase 2.5)
-- =============================================================================

CREATE TABLE documents_registry (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID DEFAULT auth.uid(),
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    upload_date TIMESTAMPTZ DEFAULT now(),
    source_type TEXT NOT NULL CHECK (source_type IN ('pdf', 'docx', 'pptx', 'html', 'markdown', 'txt', 'other')),
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed')),
    chunk_count INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for documents_registry
CREATE INDEX documents_registry_hash_idx ON documents_registry (file_hash);
CREATE INDEX documents_registry_filename_idx ON documents_registry (filename);
CREATE INDEX documents_registry_upload_date_idx ON documents_registry (upload_date DESC);
CREATE INDEX documents_registry_status_idx ON documents_registry (status);
CREATE INDEX documents_registry_user_id_idx ON documents_registry (user_id, created_at DESC);

-- Enable RLS on documents_registry
ALTER TABLE documents_registry ENABLE ROW LEVEL SECURITY;

-- Service role policy (for DEBUG/backend access)
CREATE POLICY "Service role full access" ON documents_registry
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- User read access
CREATE POLICY "Users can read own documents" ON documents_registry
  FOR SELECT USING (auth.uid() = user_id);

-- User insert access (default user_id)
CREATE POLICY "Users can insert own documents" ON documents_registry
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- User update access
CREATE POLICY "Users can update own documents" ON documents_registry
  FOR UPDATE USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- User delete access
CREATE POLICY "Users can delete own documents" ON documents_registry
  FOR DELETE USING (auth.uid() = user_id);

-- =============================================================================
-- STEP 9: Create document_metadata table (Phase 2.5)
-- =============================================================================

CREATE TABLE document_metadata (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents_registry(id) ON DELETE CASCADE,
    user_id UUID DEFAULT auth.uid(),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    value_json JSONB,
    extracted_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, key)
);

-- Indexes for document_metadata
CREATE INDEX document_metadata_doc_id_idx ON document_metadata (document_id);
CREATE INDEX document_metadata_key_idx ON document_metadata (key);
CREATE INDEX document_metadata_json_idx ON document_metadata USING gin (value_json);
CREATE INDEX document_metadata_user_id_idx ON document_metadata (user_id, extracted_at DESC);

-- Enable RLS on document_metadata
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;

-- Service role policy
CREATE POLICY "Service role full access" ON document_metadata
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- User read access (only for their own documents)
CREATE POLICY "Users can read own document metadata" ON document_metadata
  FOR SELECT USING (auth.uid() = user_id);

-- User insert access (default user_id)
CREATE POLICY "Users can insert own document metadata" ON document_metadata
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- User update access
CREATE POLICY "Users can update own document metadata" ON document_metadata
  FOR UPDATE USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- User delete access
CREATE POLICY "Users can delete own document metadata" ON document_metadata
  FOR DELETE USING (auth.uid() = user_id);

-- =============================================================================
-- STEP 10: Add full-text search to rag_chunks (Phase 2.5)
-- =============================================================================

-- Add tsvector column for full-text search
ALTER TABLE rag_chunks ADD COLUMN text_search tsvector;

-- Create GIN index for fast full-text search
CREATE INDEX rag_chunks_text_search_idx ON rag_chunks USING gin (text_search);

-- Create trigger to automatically update tsvector on insert/update
CREATE OR REPLACE FUNCTION update_text_search()
RETURNS TRIGGER AS $$
BEGIN
    NEW.text_search := to_tsvector('english', NEW.text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_text_search
BEFORE INSERT OR UPDATE ON rag_chunks
FOR EACH ROW
EXECUTE FUNCTION update_text_search();

-- Update existing rows
UPDATE rag_chunks SET text_search = to_tsvector('english', text) WHERE text_search IS NULL;

-- =============================================================================
-- STEP 11: Add document_id foreign key to rag_chunks
-- =============================================================================

ALTER TABLE rag_chunks ADD COLUMN document_id BIGINT REFERENCES documents_registry(id) ON DELETE CASCADE;
CREATE INDEX rag_chunks_document_id_idx ON rag_chunks (document_id);

-- =============================================================================
-- STEP 12: Create helper functions for cleanup
-- =============================================================================

-- Function to cleanup orphaned chunks (chunks without a document)
CREATE OR REPLACE FUNCTION cleanup_orphaned_chunks()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM rag_chunks
    WHERE document_id IS NULL 
       OR document_id NOT IN (SELECT id FROM documents_registry);
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Function to cleanup old failed documents
CREATE OR REPLACE FUNCTION cleanup_failed_documents(hours INTEGER DEFAULT 24)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM documents_registry
    WHERE status = 'failed'
      AND created_at < NOW() - (hours || ' hours')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- =============================================================================
-- STEP 13: Create chat sessions tables (Phase 2)
-- =============================================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID DEFAULT auth.uid(),
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID DEFAULT auth.uid(),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for chat tables
CREATE INDEX chat_messages_session_id_idx ON chat_messages (session_id);
CREATE INDEX chat_sessions_updated_at_idx ON chat_sessions (updated_at DESC);
CREATE INDEX chat_sessions_user_id_idx ON chat_sessions (user_id, created_at DESC);
CREATE INDEX chat_messages_user_id_idx ON chat_messages (user_id, created_at DESC);

-- Enable RLS on chat_sessions
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

-- Service role policy
CREATE POLICY "Service role full access" ON chat_sessions
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- User read access
CREATE POLICY "Users can read own sessions" ON chat_sessions
  FOR SELECT USING (auth.uid() = user_id);

-- User insert access (default user_id)
CREATE POLICY "Users can create own sessions" ON chat_sessions
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- User update access
CREATE POLICY "Users can update own sessions" ON chat_sessions
  FOR UPDATE USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- User delete access
CREATE POLICY "Users can delete own sessions" ON chat_sessions
  FOR DELETE USING (auth.uid() = user_id);

-- Enable RLS on chat_messages
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Service role policy
CREATE POLICY "Service role full access" ON chat_messages
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- User read access (only messages from their sessions)
CREATE POLICY "Users can read own messages" ON chat_messages
  FOR SELECT USING (
    auth.uid() = user_id AND EXISTS (
      SELECT 1 FROM chat_sessions 
      WHERE chat_sessions.id = chat_messages.session_id 
      AND chat_sessions.user_id = auth.uid()
    )
  );

-- User insert access (default user_id)
CREATE POLICY "Users can create own messages" ON chat_messages
  FOR INSERT WITH CHECK (
    auth.uid() = user_id AND EXISTS (
      SELECT 1 FROM chat_sessions 
      WHERE chat_sessions.id = session_id 
      AND chat_sessions.user_id = auth.uid()
    )
  );

-- User update access
CREATE POLICY "Users can update own messages" ON chat_messages
  FOR UPDATE USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- User delete access
CREATE POLICY "Users can delete own messages" ON chat_messages
  FOR DELETE USING (auth.uid() = user_id);

-- =============================================================================
-- SUCCESS MESSAGE
-- =============================================================================

SELECT '🎉 SUCCESS! Your Supabase database is ready for RAG with RLS!' as final_result;

-- =============================================================================
-- WHAT WAS CREATED:
-- =============================================================================
-- 
-- ✅ Extensions:
--    - pgvector (for vector operations)
-- 
-- ✅ Tables:
--    - rag_chunks (with VECTOR for multi-model dimensions)
--    - documents_registry (with user_id for RLS)
--    - document_metadata (with user_id for RLS)
--    - chat_sessions (with user_id for RLS)
--    - chat_messages (with user_id for RLS)
-- 
-- ✅ Indexes:
--    - IVFFlat vector indexes for 1024 and 1536 dimensions
--    - B-tree indexes for fast filtering
--    - User-scoped indexes: (user_id, created_at DESC) on all auth tables
-- 
-- ✅ Functions:
--    - match_chunks() - vector similarity search
--    - get_chunk_stats() - database statistics
--    - cleanup_orphaned_chunks() - cleanup helper
--    - cleanup_failed_documents() - cleanup helper
-- 
-- ✅ Security (Row Level Security):
--    - rag_chunks: anonymous/authenticated read access
--    - documents_registry: user-scoped access + service role bypass
--    - document_metadata: user-scoped access + service role bypass
--    - chat_sessions: user-scoped access + service role bypass
--    - chat_messages: user-scoped access with session isolation + service role bypass
--
--    For each table:
--      • Service role can access everything (FOR ALL)
--      • Users can SELECT only their own records (user_id = auth.uid())
--      • Users can INSERT only with their user_id
--      • Users can UPDATE only their own records
--      • Users can DELETE only their own records
-- 
-- ✅ Multi-User Isolation:
--    - All user tables default user_id to auth.uid()
--    - Policies enforce user_id ownership at database level
--    - Foreign key cascades maintain isolation boundaries
--    - Service role (backend) can bypass RLS for admin operations
-- 
-- =============================================================================
-- NEXT STEPS:
-- =============================================================================
-- 
-- 1. Update your .env file with Supabase credentials:
--    SUPABASE_URL=https://your-project.supabase.co
--    SUPABASE_ANON_KEY=your_anon_key
--    SUPABASE_SERVICE_ROLE_KEY=your_service_key
--    AI_PROVIDER=ollama or openai
--    OLLAMA_EMBED_MODEL=mxbai-embed-large
--    OPENAI_EMBED_MODEL=text-embedding-3-small
-- 
-- 2. Update your Python backend to use service_role for admin operations
--    (e.g., seeding, migrations, batch operations)
-- 
-- 3. Start your FastAPI backend:
--    uvicorn main:app --reload --port 8000
-- 
-- 4. Test the health check:
--    curl http://localhost:8000/healthz
-- 
-- 5. Seed your knowledge base (using service role):
--    curl -X POST http://localhost:8000/seed
-- 
-- 6. Ask your first question (using authenticated token):
--    curl -X POST http://localhost:8000/answer \
--      -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
--      -H "Content-Type: application/json" \
--      -d '{"query": "What is your return policy?"}'
-- 
-- 7. Visit interactive docs:
--    http://localhost:8000/docs
-- 
-- =============================================================================
