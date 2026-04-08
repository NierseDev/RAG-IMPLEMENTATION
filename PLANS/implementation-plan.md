# Agentic RAG Implementation Plan

## Executive Summary

This plan implements a production-ready Agentic RAG system with multi-agent capabilities, optimized document processing, and a comprehensive web interface for testing and debugging. The implementation focuses on balancing performance, cost, and user experience while avoiding over-engineering.

**Current State:**
- Basic FastAPI-based RAG API with agent reasoning loop
- Single document ingestion endpoint
- Simple debug HTML interface (debug.html)
- Using Ollama with qwen3.5:4b (LLM) and mxbai-embed-large (embeddings)
- Supabase vector database for storage
- Docling for document processing

**Target State:**
- Multi-agent system with main agent + sub-agents
- Optimized document ingestion with deduplication and hybrid search
- Two-tab web interface: Agentic Chat + Document Ingestion
- Support for both local (CPU/GPU) and cloud agents
- Additional tools (Text-to-SQL, Web search fallback)
- Metadata extraction and enhanced retrieval

---

## Phase 1: Agent Research & Selection

**Objective:** Research and document agent options for local and cloud deployments using publicly available benchmarks.

### Research Areas

#### 1.1 Local CPU Agents (PRIORITY)
**Goal:** Find balanced models for AMD Ryzen 5 8600G CPU

**Research Tasks:**
- Survey publicly available benchmarks for small-to-medium LLMs (1B-7B parameters)
- Focus on models optimized for CPU inference (quantized models)
- Document performance metrics: tokens/sec, latency, memory usage
- Compare reasoning quality vs speed trade-offs

**Candidate Models to Research:**
- Current: qwen3.5:4b
- Alternatives: Llama 3.2 3B, Phi-3.5 Mini, Gemma 2 2B/4B, Mistral 7B (quantized)
- Embedding models: mxbai-embed-large (current), nomic-embed-text, all-minilm

**Deliverable:** Document comparing 5-7 models with:
- Benchmark results (MMLU, HumanEval, latency)
- Memory requirements
- RAG-specific performance (context following, grounding)
- Recommendation for production use

#### 1.2 Local GPU Agents
**Goal:** Identify high-performance models for GPU acceleration

**Research Tasks:**
- Research GPU-optimized models for consumer GPUs
- Document VRAM requirements and throughput improvements
- Compare FP16 vs quantized (Q4, Q8) trade-offs

**Candidate Models:**
- Llama 3.1 8B, Mistral 7B, Qwen2.5 7B/14B
- GPU-specific optimizations (Flash Attention, vLLM)

**Deliverable:** Document GPU model options with VRAM requirements and expected speedup

#### 1.3 Cloud Agents - Low Cost
**Goal:** Best performing RAG agent at minimal cost

**Research Tasks:**
- Survey cloud LLM pricing (per million tokens)
- Analyze cost vs performance for small models
- Document API latency and rate limits

**Candidate Services:**
- OpenAI GPT-4o-mini, Anthropic Claude Haiku
- Google Gemini Flash, Groq (Llama-based)
- Together.ai, Replicate (smaller models)

**Deliverable:** Cost comparison matrix with $/M tokens and quality benchmarks

#### 1.4 Cloud Agents - Balanced Cost
**Goal:** High-performance RAG with reasonable cost

**Research Tasks:**
- Compare mid-tier cloud models
- Analyze reasoning capabilities for complex RAG tasks
- Document long-context handling (100K+ tokens)

**Candidate Services:**
- OpenAI GPT-4o, Anthropic Claude Sonnet
- Google Gemini Pro 1.5

**Deliverable:** Performance vs cost analysis with recommendations

#### 1.5 Sub-Agent Architecture Research
**Goal:** Determine optimal sub-agent models for specialized tasks

**Research Tasks:**
- Research agent delegation patterns (main agent → sub-agents)
- Document when to use same model vs specialized models
- Identify lightweight models for specific tasks:
  - Text-to-SQL: CodeLlama, StarCoder, SQLCoder
  - Web search summarization: smaller models sufficient
  - Document-specific reasoning: could use same as main agent

**Deliverable:** Sub-agent architecture diagram with model recommendations

---

## Phase 2: Debug Application Shell Redesign

**Objective:** Build a production-ready web interface with two tabs for testing the Agentic RAG system.

### Architecture

**UI Framework:** Single-page application using Vanilla JS (no framework overhead)
**Backend:** FastAPI (existing)
**Styling:** Tailwind CSS (CDN) for rapid development
**Components:** Modular JS with clear separation of concerns

### 2.1 Tab 1: Agentic Chat Interface

**Layout:**
```
+------------------+------------------------+-----------------+
| Header           | Chat Area              | Debug Sidebar   |
+------------------+------------------------+-----------------+
| Logo, Settings   | Messages (scrollable)  | Agent Status    |
|                  | Input Box              | Database Info   |
|                  |                        | Trace View      |
+------------------+------------------------+-----------------+
```

**Features:**

**Chat History (Left Sidebar - 25% width):**
- Session list with timestamps
- Search/filter conversations
- Clear history button
- Auto-save to localStorage or backend

**Main Chat Area (Center - 50% width):**
- Message bubbles (user vs assistant)
- Streaming response support
- Agent reasoning steps display:
  - Show iteration count
  - Retrieved documents preview
  - Confidence scores
  - Verification results
- Copy message button
- Regenerate response

**Debug Tools (Right Sidebar - 25% width):**

*Agent Status Panel:*
- Current iteration (e.g., "Iteration 2/3")
- Active step (Planning, Retrieving, Reasoning, Verifying)
- Confidence level (progress bar)
- Model in use (local/cloud)
- Response time metrics

*Database Status Panel:*
- Document count
- Chunk count
- Storage used
- Last ingestion timestamp
- Connection status indicator

*Trace Viewer:*
- Expandable sections per iteration
- Show retrieved chunks with scores
- LLM prompts (toggleable)
- Verification results
- Sub-agent calls (when implemented)

**Non-Functional Placeholder:**
- File upload button (disabled)
- Tooltip: "Document ingestion available in Tab 2"

### 2.2 Tab 2: Document Ingestion

**Layout:**
```
+--------------------------------+--------------------------------+
| Upload Area                    | Document History               |
+--------------------------------+--------------------------------+
| Drag & Drop Box                | Table: Name, Size, Date, Status|
| File Selection                 | Filters, Search                |
| Batch Upload Button            | Actions (View, Delete)         |
+--------------------------------+--------------------------------+
```

**Features:**

**Upload Box:**
- Drag-and-drop zone (visual feedback)
- File selection dialog (multi-select)
- Allowed formats: PDF, DOCX, PPTX, TXT, MD, HTML (per Docling)
- Size limit indicator (50MB default)
- Upload progress bars (per file)
- Batch processing queue

**Document History Table:**
- Columns: Filename, Size, Upload Date, Status, Actions
- Status indicators:
  - ✓ Processed successfully
  - ⏳ Processing
  - ❌ Failed (with error tooltip)
  - ⚠ Duplicate (will be implemented in Phase 2.5)
- Pagination (50 items per page)
- Search by filename
- Filter by status, date range
- Bulk actions: Delete selected

**Processing Feedback:**
- Real-time status updates (WebSocket or polling)
- Show chunk count per document
- Estimated processing time
- Error messages with actionable advice

### 2.3 API Endpoints to Create/Modify

**New Endpoints:**
```python
# Chat session management
GET /api/chat/sessions - List all chat sessions
POST /api/chat/sessions - Create new session
GET /api/chat/sessions/{id}/messages - Get messages
DELETE /api/chat/sessions/{id} - Delete session

# Enhanced query endpoint
POST /api/query - Enhanced with streaming, trace data

# Document management
GET /api/documents - List uploaded documents
GET /api/documents/{id} - Get document details
DELETE /api/documents/{id} - Delete document
POST /api/ingest/batch - Batch upload (modify existing)

# Status endpoints
GET /api/status/agent - Current agent status
GET /api/status/database - Database statistics
```

**Modified Endpoints:**
- `POST /api/ingest` - Add file validation, better error handling
- `POST /api/query` - Return structured trace data for UI

### 2.4 Implementation Tasks

**Backend Tasks:**
1. Create new API routes (api/chat_sessions.py)
2. Add chat session storage (database or in-memory cache)
3. Enhance query endpoint to return trace data
4. Add streaming support (if enabled in config)
5. Create document list/management endpoints
6. Add batch upload handling

**Frontend Tasks:**
1. Create base HTML structure with two tabs
2. Implement tab switching logic
3. Build Chat UI components:
   - Message rendering
   - Input handling
   - Chat history sidebar
   - Debug panels
4. Build Document Ingestion UI:
   - Drag-and-drop handler
   - Upload queue manager
   - Document table with pagination
5. Create shared components:
   - Loading spinners
   - Error notifications
   - Confirmation modals
6. API integration layer (fetch wrapper)
7. State management (simple Pub/Sub pattern)

---

## Phase 2.5: Document Injection Optimization

**Objective:** Implement robust, production-ready document ingestion with deduplication, metadata extraction, and hybrid search.

### Guiding Principles
1. **Don't Over-Engineer:** Use simple, proven solutions
2. **O(1) Lookups:** Fast duplicate detection using hashes
3. **Optimize for Agents:** Chunk sizes balanced for context limits
4. **Incremental Updates:** Process only new/changed content

### 2.5.1 Safe & Fast Document Ingestion

**Current Issues:**
- No duplicate detection → same file processed multiple times
- No incremental updates → re-upload required for changes
- No content hash tracking → can't detect identical content with different filenames

**Solution: Content-Based Deduplication**

**New Supabase Table: `documents_registry`**
```sql
CREATE TABLE documents_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,  -- SHA-256 of file content
    file_size BIGINT NOT NULL,
    upload_date TIMESTAMPTZ DEFAULT now(),
    last_modified TIMESTAMPTZ,
    source_path TEXT,  -- Optional: original file path
    chunk_count INTEGER DEFAULT 0,
    processing_status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,  -- Store extracted metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_documents_content_hash ON documents_registry(content_hash);
CREATE INDEX idx_documents_status ON documents_registry(processing_status);
CREATE INDEX idx_documents_upload_date ON documents_registry(upload_date DESC);
```

**Processing Flow:**
1. **Pre-Upload Check:**
   - Compute SHA-256 hash of file content
   - Query `documents_registry` by `content_hash`
   - If exists and status='completed': Skip (return existing doc_id)
   - If exists and status='failed': Allow retry
   - If not exists: Proceed to ingestion

2. **Incremental Updates:**
   - For modified files, compare hash
   - If hash changed: Mark old chunks as deleted, process new version
   - Track version history in metadata

3. **Batch Optimization:**
   - Hash all files first (parallel)
   - Filter out duplicates before processing
   - Process unique files in parallel (up to N workers)

**Implementation:**
- Add `compute_file_hash()` utility in `app/core/text_utils.py`
- Modify `POST /api/ingest` to check registry before processing
- Update document_processor.py to record entries in registry
- Add cleanup job to remove orphaned chunks when document deleted

### 2.5.2 Optimize Chunking for Agent Context

**Current Chunking:** 400 tokens, 50 overlap (from config.py)

**Challenges:**
- Different models have different context limits
- Need to balance: more context vs more chunks
- Semantic boundaries vs fixed token counts

**Optimization Strategy:**

**1. Semantic Chunking (Enhancement):**
- Use Docling's structural extraction (headings, sections, tables)
- Respect document structure when possible
- Fall back to token-based splitting for unstructured content

**2. Dynamic Chunk Sizing:**
- Local models (small context): 400-500 tokens
- Cloud models (large context): 800-1200 tokens
- Configurable via settings

**3. Context Optimization:**
```python
# Compute available context budget
max_context = llm_context_window - system_prompt - query - output_buffer
chunk_budget = max_context / top_k_chunks

# Adjust retrieval strategy
if chunk_budget < 400:
    # Use fewer, more relevant chunks
    top_k = max_context // 500
else:
    # Use standard retrieval
    top_k = settings.top_k_results
```

**Implementation:**
- Add `semantic_chunker.py` in app/services/
- Enhance document_processor.py to use semantic chunking
- Add chunk strategy selection in config (semantic, fixed, hybrid)

### 2.5.3 Metadata Extraction & Enhanced Retrieval

**Metadata to Extract:**
- **Document-Level:** Title, author, creation date, file type, page count
- **Chunk-Level:** Section heading, page number, table/figure indicator
- **Content-Level:** Named entities (people, orgs, dates), key topics

**New Supabase Table: `document_metadata`**
```sql
CREATE TABLE document_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents_registry(id) ON DELETE CASCADE,
    metadata_type TEXT NOT NULL,  -- 'document', 'chunk', 'entity'
    key TEXT NOT NULL,
    value TEXT,
    value_json JSONB,  -- For complex metadata
    chunk_id UUID,  -- Reference to specific chunk if applicable
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_metadata_document_id ON document_metadata(document_id);
CREATE INDEX idx_metadata_type_key ON document_metadata(metadata_type, key);
CREATE INDEX idx_metadata_chunk_id ON document_metadata(chunk_id);
```

**Metadata Extraction Pipeline:**
1. **Document Parsing (Docling):**
   - Extract title from first heading or filename
   - Extract creation date from PDF metadata
   - Identify document structure (sections, pages)

2. **Chunk Annotation:**
   - Store section heading with each chunk
   - Store page number for citation
   - Tag chunks containing tables/figures

3. **Entity Extraction (Optional - Phase 3):**
   - Use lightweight NER (spaCy) to extract entities
   - Store in metadata for faceted search

**Enhanced Retrieval Using Metadata:**
```python
# Example: Prioritize recent documents
WHERE upload_date > NOW() - INTERVAL '30 days'

# Example: Filter by document type
WHERE metadata->>'file_type' = 'PDF'

# Example: Search within specific sections
WHERE metadata->>'section' ILIKE '%Introduction%'
```

**Implementation:**
- Create `metadata_extractor.py` in app/services/
- Update document_processor.py to call metadata extraction
- Store metadata in new table during ingestion
- Modify retrieval_service.py to accept metadata filters

### 2.5.4 Hybrid Search Implementation

**Why Hybrid Search?**
- **Vector search alone:** Misses exact keyword matches, poor for acronyms/names
- **Keyword search alone:** No semantic understanding, synonym mismatch
- **Hybrid:** Combines strengths, more robust retrieval

**Approach: Reciprocal Rank Fusion (RRF)**

**Architecture:**
```
User Query
    ├─→ Vector Search (Supabase pgvector) → Results A
    └─→ Keyword Search (PostgreSQL full-text) → Results B
            ↓
        RRF Fusion
            ↓
    Combined Ranked Results
            ↓
    Optional Reranking (Cross-encoder)
            ↓
    Final Top-K Results
```

**Supabase Schema Changes:**
```sql
-- Add full-text search column to chunks table
ALTER TABLE rag_chunks 
ADD COLUMN content_tsv TSVECTOR 
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX idx_chunks_fts ON rag_chunks USING gin(content_tsv);

-- Optional: Add metadata search
ALTER TABLE rag_chunks 
ADD COLUMN metadata_tsv TSVECTOR 
GENERATED ALWAYS AS (
    to_tsvector('english', 
        COALESCE(metadata->>'title', '') || ' ' || 
        COALESCE(metadata->>'section', '')
    )
) STORED;
```

**RRF Formula:**
```python
def reciprocal_rank_fusion(results_list, k=60):
    """
    Combine multiple ranked result lists using RRF.
    RRF(d) = Σ 1 / (k + rank(d))
    """
    scores = {}
    for results in results_list:
        for rank, doc in enumerate(results, start=1):
            doc_id = doc['id']
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**Retrieval Flow:**
1. **Parallel Search:**
   - Execute vector search (cosine similarity)
   - Execute keyword search (ts_rank)
   - Both return top 50 results

2. **Fusion:**
   - Apply RRF to combine rankings
   - Top-K results from fused list

3. **Optional Reranking:**
   - Use cross-encoder model (e.g., bge-reranker-base)
   - Re-score top-20 fusion results
   - Return final top-K

**Implementation Files:**
- Create `app/services/hybrid_search.py`
- Add keyword search function to retrieval_service.py
- Implement RRF fusion
- Add optional reranker (can use Ollama or HuggingFace)
- Update `/api/query` to use hybrid search

**Configuration:**
```python
# Add to Settings
enable_hybrid_search: bool = True
hybrid_vector_weight: float = 0.7  # Weight for vector vs keyword
enable_reranking: bool = False  # Experimental
reranker_model: str = "bge-reranker-base"
```

### 2.5.5 Understanding & Best Practices

**Document Parsing Challenges:**
- **PDFs:** Scanned vs text-based, multi-column layouts, tables
- **DOCX:** Embedded images, complex formatting
- **PPTX:** Slide structure, speaker notes
- **Solution:** Docling handles most formats; validate output quality

**Naive Ingestion Pitfalls:**
1. **Duplicate Processing:** Without hashing, same doc processed multiple times
2. **No Update Strategy:** Can't update existing documents without deleting all
3. **Memory Issues:** Large files processed in memory without streaming
4. **No Error Recovery:** Failed chunks halt entire document

**Incremental Update Strategy:**
- Track document version via content hash
- Support partial updates (e.g., new pages added to PDF)
- Maintain chunk provenance (which document/version)

**Why Vector Alone Isn't Enough:**
- Semantic search: "ML" ≠ "machine learning" in vector space (depends on training)
- Exact matches: User searches "GPT-4" but vector retrieves "GPT-3" content
- Hybrid fixes: Keyword ensures exact match, vector ensures semantic coverage

**Reranking Benefits:**
- Cross-encoder models score query-document pairs directly (vs bi-encoder embeddings)
- More accurate but slower (only use on top-K, not all corpus)
- Typical improvement: 5-10% better relevance

---

## Phase 3: Multi-Tool & Sub-Agent Architecture

**Objective:** Extend the agentic system with additional tools and hierarchical sub-agents for complex reasoning tasks.

### 3.1 Additional Tools

#### 3.1.1 Text-to-SQL Tool

**Use Case:** Agent needs to query structured data in Supabase (e.g., "How many documents uploaded last week?")

**Architecture:**
```
User Query: "Show me stats on uploaded PDFs"
    ↓
Main Agent: Detects need for structured data query
    ↓
Text-to-SQL Tool: Generates SQL from natural language
    ↓
Execute query on Supabase
    ↓
Return results to Agent
    ↓
Agent: Formats results in natural language
```

**Implementation:**

**SQL Generation Approach:**
- **Option 1:** Use LLM with schema context (prompt engineering)
- **Option 2:** Use specialized Text-to-SQL model (SQLCoder, CodeLlama)
- **Recommendation:** Option 1 for simplicity, Option 2 if quality issues

**Safety Measures:**
- Read-only queries (SELECT only)
- Query validation (prevent DROP, DELETE, UPDATE)
- Timeout limits
- Result size limits

**Schema Context:**
```python
# Provide agent with database schema
SCHEMA_CONTEXT = """
Available tables:
1. documents_registry (id, filename, content_hash, upload_date, chunk_count, ...)
2. rag_chunks (id, document_id, content, embedding, metadata, ...)
3. document_metadata (id, document_id, key, value, ...)

Example queries:
- Count documents: SELECT COUNT(*) FROM documents_registry
- Recent uploads: SELECT * FROM documents_registry WHERE upload_date > NOW() - INTERVAL '7 days'
"""
```

**Tool Interface:**
```python
# app/services/tools/sql_tool.py
class TextToSQLTool:
    async def generate_sql(self, natural_language_query: str) -> str:
        """Generate SQL from natural language."""
        
    async def execute_query(self, sql: str) -> dict:
        """Execute read-only SQL query."""
        
    async def query(self, nl_query: str) -> dict:
        """End-to-end: generate and execute."""
```

**Integration with Agent:**
- Agent detects keywords: "count", "statistics", "how many", "show data"
- Calls SQL tool, receives structured results
- Formats results in conversational response

#### 3.1.2 Web Search Fallback Tool

**Use Case:** User asks question not covered by documents (e.g., "What's the latest news on AI?")

**Architecture:**
```
User Query: "Latest OpenAI announcements"
    ↓
Main Agent: Retrieves from vector DB
    ↓
Verification: Low confidence (no relevant docs)
    ↓
Fallback to Web Search Tool
    ↓
Search API (e.g., SerpAPI, DuckDuckGo)
    ↓
Summarize search results
    ↓
Return with attribution
```

**Implementation:**

**Search Provider Options:**
- **DuckDuckGo API:** Free, no API key, limited results
- **SerpAPI / ScaleSerp:** Paid, comprehensive, structured results
- **Brave Search API:** Privacy-focused, affordable
- **Recommendation:** Start with DuckDuckGo, upgrade if needed

**Tool Interface:**
```python
# app/services/tools/web_search_tool.py
class WebSearchTool:
    async def search(self, query: str, max_results: int = 5) -> List[dict]:
        """Search web and return top results."""
        
    async def summarize_results(self, results: List[dict]) -> str:
        """Summarize search results using LLM."""
```

**Attribution Strategy:**
- Always cite sources: "According to [Source], published [Date]..."
- Include disclaimer: "This information is from web search, not your documents."
- Store search results in chat history for reference

**Graceful Fallback Logic:**
```python
if verification_confidence < threshold:
    if not search_allowed:
        return "I don't have enough information in your documents to answer this."
    else:
        web_results = await web_search_tool.search(query)
        summary = await llm_service.summarize(web_results)
        return f"From web search: {summary} [Sources: ...]"
```

#### 3.1.3 Multi-Tool Agent Router

**Goal:** Agent decides which tool(s) to use based on query

**Routing Logic:**
```python
# app/services/agent_router.py
class AgentRouter:
    async def route(self, query: str, context: dict) -> str:
        """
        Determine which tool(s) to use.
        Returns: 'retrieval', 'sql', 'web_search', 'multi'
        """
        # Use LLM to classify query intent
        prompt = f"""
        Classify this query into one or more categories:
        - retrieval: Search knowledge base
        - sql: Query structured data/statistics
        - web_search: External information needed
        
        Query: {query}
        """
```

**Multi-Tool Workflow:**
```python
async def handle_query(query: str):
    route = await router.route(query)
    
    if route == 'retrieval':
        return await rag_agent.query(query)
    
    elif route == 'sql':
        sql_result = await sql_tool.query(query)
        return format_sql_response(sql_result)
    
    elif route == 'web_search':
        web_result = await web_search_tool.search(query)
        return format_web_response(web_result)
    
    elif route == 'multi':
        # Use multiple tools in sequence or parallel
        rag_result = await rag_agent.query(query)
        if rag_result.confidence < threshold:
            web_result = await web_search_tool.search(query)
            return combine_results(rag_result, web_result)
```

### 3.2 Sub-Agent Architecture

**Goal:** Handle complex, full-document scenarios by delegating to specialized sub-agents

**Use Cases:**
1. **Document Summarization:** User uploads 100-page PDF, asks "Summarize this"
2. **Deep Analysis:** "Compare the methodologies in these three research papers"
3. **Multi-Step Reasoning:** "Extract all dates, then create a timeline"

**Architecture:**

```
Main Agent (Coordinator)
    ├─→ RAG Sub-Agent (retrieval-focused)
    ├─→ Summarization Sub-Agent (full-doc processing)
    ├─→ Analysis Sub-Agent (comparative reasoning)
    └─→ Extraction Sub-Agent (structured data extraction)
```

**Sub-Agent Types:**

**1. RAG Sub-Agent (default):**
- Current implementation
- Retrieves chunks, reasons, verifies

**2. Full-Document Sub-Agent:**
- For queries like "summarize document X"
- Loads entire document (or large sections) into context
- Uses long-context models (cloud preferred)
- Returns comprehensive analysis

**3. Comparison Sub-Agent:**
- For "compare X and Y" queries
- Retrieves from multiple documents
- Builds comparison matrix
- Uses structured output

**Context Management:**

**Challenge:** Sub-agents need isolated context to avoid confusion

**Solution:**
```python
class SubAgent:
    def __init__(self, parent_agent_id: str, task_description: str):
        self.parent_id = parent_agent_id
        self.task = task_description
        self.context = []  # Isolated context
        self.tools = []    # Specialized tools
    
    async def execute(self, query: str) -> dict:
        """Execute sub-agent task, return results to parent."""
```

**Delegation Flow:**
```python
# Main agent detects need for delegation
if query.contains("summarize entire document"):
    sub_agent = FullDocumentAgent(parent_id=self.id, task="summarization")
    result = await sub_agent.execute(query)
    self.reasoning_trace.append({
        "step": "delegation",
        "sub_agent": "FullDocumentAgent",
        "result": result
    })
    return result
```

**UI Display (Hierarchical):**

```
Main Agent
├─ Iteration 1: Planning
├─ Iteration 2: Retrieval
└─ Iteration 3: Delegation
    └─ Sub-Agent: FullDocumentAgent
        ├─ Step 1: Load document
        ├─ Step 2: Chunk processing
        └─ Step 3: Summarization
            → Result: [Summary text]
```

**Implementation:**
- Create base `SubAgent` class in `app/services/sub_agents/base.py`
- Implement specific sub-agents:
  - `app/services/sub_agents/full_document.py`
  - `app/services/sub_agents/comparison.py`
  - `app/services/sub_agents/extraction.py`
- Update main agent to detect delegation scenarios
- Enhance UI to display nested agent activity

**When to Isolate (Delegation Triggers):**
- Query mentions "entire document", "full text", "whole paper"
- Query requires cross-document comparison (multiple sources)
- Query needs structured extraction (tables, lists, timelines)
- Main agent determines task too complex for single iteration

### 3.3 Understanding: Multi-Agent Systems

**Agent Delegation Benefits:**
- **Specialization:** Each sub-agent optimized for specific task
- **Context Isolation:** Prevents context bleeding between tasks
- **Scalability:** Can run sub-agents in parallel
- **Debuggability:** Clear trace of which agent did what

**Hierarchical Display Importance:**
- User sees full reasoning chain
- Transparency builds trust
- Easier debugging when something goes wrong
- Educational: Shows how complex queries are decomposed

**Graceful Fallbacks:**
- If sub-agent fails, main agent can retry with different strategy
- Attribution: Always show which agent/tool provided which information
- Confidence propagation: Sub-agent confidence affects main agent confidence

---

## Implementation Roadmap

### Parallelization Strategy

**Tracks that can run in parallel:**

**Track A: Research & Documentation**
- Phase 1: Agent Research (no code dependencies)
- Deliverable: Research documents in PLANS/ folder

**Track B: UI Development**
- Phase 2: Debug Application Shell
- Dependencies: Basic FastAPI endpoints (already exist)
- Can start immediately with mock data

**Track C: Backend Optimization**
- Phase 2.5: Document Injection Optimization
- Dependencies: UI from Track B (but can develop independently)
- Focus: Database schema, ingestion logic, hybrid search

**Track D: Advanced Features**
- Phase 3: Tools & Sub-Agents
- Dependencies: Tracks B & C (needs UI and optimized backend)

### Suggested Execution Order

**Sprint 1 (Parallel):**
- Track A: Complete Agent Research (Phase 1)
- Track B: Build UI skeleton and Tab 1 (Phase 2.1)

**Sprint 2 (Parallel):**
- Track B: Complete Tab 2 and API integration (Phase 2.2-2.4)
- Track C: Database schema and deduplication (Phase 2.5.1)

**Sprint 3 (Parallel):**
- Track C: Chunking optimization and metadata (Phase 2.5.2-2.5.3)
- Track D: Text-to-SQL tool (Phase 3.1.1) - Independent

**Sprint 4 (Sequential):**
- Track C: Hybrid search implementation (Phase 2.5.4) - Needs schema from Sprint 2
- Track D: Web search tool (Phase 3.1.2)

**Sprint 5 (Sequential):**
- Track D: Multi-tool routing (Phase 3.1.3) - Needs tools from Sprint 3-4
- Track D: Sub-agent architecture (Phase 3.2) - Needs routing

### Dependencies Graph

```
Phase 1 (Research) → [No dependencies] → Informs model selection

Phase 2 (UI)
  ├─ 2.1 Chat UI → [Basic API exists] → Can start immediately
  ├─ 2.2 Ingest UI → [Basic API exists] → Can start immediately
  └─ 2.3-2.4 API → [Depends on 2.1, 2.2 requirements]

Phase 2.5 (Optimization)
  ├─ 2.5.1 Deduplication → [No dependencies] → Can start with Sprint 2
  ├─ 2.5.2 Chunking → [Depends on 2.5.1 schema]
  ├─ 2.5.3 Metadata → [Depends on 2.5.1 schema]
  └─ 2.5.4 Hybrid Search → [Depends on 2.5.3]

Phase 3 (Tools & Agents)
  ├─ 3.1.1 SQL Tool → [Independent] → Can start anytime
  ├─ 3.1.2 Web Search → [Independent] → Can start anytime
  ├─ 3.1.3 Router → [Depends on 3.1.1, 3.1.2]
  └─ 3.2 Sub-Agents → [Depends on 3.1.3, Phase 2.5 complete]
```

---

## Testing & Validation Strategy

### Phase 1 Validation
- Document research findings in PLANS/agent-research.md
- Create comparison matrices for local/cloud options
- Review with stakeholders before implementation

### Phase 2 Validation
- Manual testing of UI in browser
- Test responsiveness (mobile, tablet, desktop)
- Verify all API endpoints return expected data
- Test error states (network failures, invalid inputs)

### Phase 2.5 Validation
- Test deduplication: Upload same file twice, verify single entry
- Test chunking: Verify chunks fit in model context limits
- Test hybrid search: Compare pure vector vs hybrid relevance
- Benchmark query performance (latency, accuracy)

### Phase 3 Validation
- Test SQL tool: Verify only read queries allowed
- Test web search: Verify attribution and fallback logic
- Test sub-agents: Verify context isolation and result propagation
- End-to-end test: Complex multi-tool query

### Success Metrics

**Performance:**
- Query response time < 3s (local), < 5s (cloud)
- Document ingestion < 1s per page
- Zero duplicate documents in database
- Hybrid search relevance > 85% (manual evaluation)

**Functionality:**
- All UI features working without errors
- Agent successfully uses all tools when appropriate
- Sub-agents properly isolated and traceable
- Chat history persists across sessions

**User Experience:**
- UI responsive on desktop and mobile
- Clear error messages with actionable advice
- Debug panels provide useful insights
- Document upload supports drag-and-drop

---

## File Structure

### New Files to Create

```
PLANS/
├─ implementation-plan.md (this file)
├─ agent-research.md (Phase 1 output)
└─ testing-results.md (validation documentation)

app/
├─ api/
│  ├─ chat_sessions.py (Phase 2)
│  └─ documents.py (Phase 2)
│
├─ services/
│  ├─ hybrid_search.py (Phase 2.5)
│  ├─ metadata_extractor.py (Phase 2.5)
│  ├─ semantic_chunker.py (Phase 2.5)
│  │
│  ├─ tools/
│  │  ├─ base.py
│  │  ├─ sql_tool.py (Phase 3)
│  │  └─ web_search_tool.py (Phase 3)
│  │
│  └─ sub_agents/
│     ├─ base.py (Phase 3)
│     ├─ full_document.py (Phase 3)
│     ├─ comparison.py (Phase 3)
│     └─ extraction.py (Phase 3)
│
├─ models/
│  └─ entities.py (add new models for metadata, sessions)
│
└─ core/
   └─ agent_router.py (Phase 3)

static/
├─ debug.html (replace with new two-tab UI)
├─ css/
│  └─ styles.css
└─ js/
   ├─ app.js (main entry point)
   ├─ chat.js (Tab 1 logic)
   ├─ ingest.js (Tab 2 logic)
   ├─ api.js (API wrapper)
   └─ utils.js (shared utilities)

migrations/
└─ supabase/
   ├─ 001_documents_registry.sql (Phase 2.5)
   ├─ 002_document_metadata.sql (Phase 2.5)
   └─ 003_hybrid_search.sql (Phase 2.5)
```

### Files to Modify

```
app/
├─ services/
│  ├─ document_processor.py (Phase 2.5: add deduplication, metadata)
│  ├─ retrieval.py (Phase 2.5: add hybrid search)
│  └─ agent.py (Phase 3: add tool routing, sub-agent delegation)
│
├─ api/
│  ├─ ingest.py (Phase 2: add validation, batch handling)
│  └─ query.py (Phase 2: add trace data, streaming)
│
└─ core/
   └─ config.py (add new settings for features)

requirements.txt (add: spacy, beautifulsoup4, ddg-search-api)
```

---

## Risk Mitigation

### Technical Risks

**Risk: Hybrid search may be slower than pure vector search**
- Mitigation: Make configurable, benchmark before deploying
- Fallback: Keep pure vector as option

**Risk: Sub-agents may increase latency**
- Mitigation: Use delegation only when necessary
- Fallback: Make sub-agents optional via config

**Risk: Large documents may exceed model context limits**
- Mitigation: Implement chunking strategies, use summarization
- Fallback: Provide clear error message with file size limits

### Process Risks

**Risk: Scope creep (over-engineering)**
- Mitigation: Follow "don't over-engineer" principle
- Review: After each phase, evaluate if adding complexity is justified

**Risk: UI development takes longer than expected**
- Mitigation: Use simple vanilla JS, avoid framework learning curve
- Fallback: Deliver Tab 1 first, Tab 2 can follow

**Risk: Cloud agent costs higher than expected**
- Mitigation: Phase 1 research includes cost analysis
- Fallback: Stick with local agents for development

---

## Next Steps

1. **Review this plan** and provide feedback
2. **Approve to proceed** or request modifications
3. **Begin Track A & B in parallel** (Research + UI)
4. **Weekly check-ins** to review progress and adjust priorities

---

## Notes

- **Configuration Management:** All new features should be configurable via environment variables (settings.py)
- **Documentation:** Update README.md after each phase with new features
- **Error Handling:** Every new API endpoint needs proper error handling and logging
- **Testing:** Manual testing is acceptable for MVP; automated tests can be added later
- **Performance:** Benchmark and optimize only after basic functionality works
- **Security:** Validate all user inputs, sanitize SQL queries, limit API rate

---

**Plan Version:** 1.0  
**Created:** Based on PLAN.md requirements  
**Target:** Production-ready Agentic RAG system with multi-agent capabilities
