# Agentic RAG System

A sophisticated **Agentic RAG (Retrieval-Augmented Generation)** system with multi-step reasoning, self-reflection, and hallucination detection. Built with FastAPI, Supabase (pgvector), and Ollama.

## ≡ƒîƒ Features

- **≡ƒñû Agentic Reasoning Loop**: 6-phase reasoning cycle (Plan ΓåÆ Retrieve ΓåÆ Reason ΓåÆ Verify ΓåÆ Decide ΓåÆ Answer/Iterate)
- **Γ£à Hallucination Prevention**: Ground checking, citation requirements, and confidence scoring
- **≡ƒöä Iterative Query Refinement**: Agent refines queries based on retrieved information
- **≡ƒôä Multi-Format Documents**: Process PDF, DOCX, PPTX, HTML, Markdown using Docling
- **≡ƒöì Vector Semantic Search**: Fast similarity search with Supabase pgvector
- **≡ƒÄ» Verification System**: Validates answers against retrieved context
- **≡ƒîÉ REST API**: Clean FastAPI endpoints with auto-generated docs
- **≡ƒÆ╗ Debug Web UI**: Real-time visualization of agent reasoning
- **≡ƒôª Batch Upload**: Multiple file upload with duplicate detection
- **≡ƒöä Smart Duplicate Handling**: Skip, Replace, or Append modes for existing files

## ≡ƒÅù∩╕Å Architecture

**Tech Stack:**
- **Frontend**: Web UI with chat interface
- **Backend**: FastAPI with REST endpoints
- **Vector Database**: Supabase (PostgreSQL + pgvector)
- **AI**: Ollama (local LLM + embeddings)
- **Document Processing**: Docling (multi-format support)

**Core Components:**
- **Agentic RAG Coordinator**: 6-phase reasoning loop (Plan ΓåÆ Retrieve ΓåÆ Reason ΓåÆ Verify ΓåÆ Decide ΓåÆ Answer)
- **Document Processor**: Converts documents to searchable chunks
- **Embedding Service**: Generates vector representations
- **Retrieval Service**: Semantic search with pgvector
- **Verification Service**: Hallucination detection and confidence scoring

## ≡ƒÜÇ Quick Start

### Prerequisites

1. **Python 3.10+**
2. **Supabase Account**: Create a project at [supabase.com](https://supabase.com)
3. **Ollama**: Install from [ollama.ai](https://ollama.ai)

### Installation

#### Step 1: Clone and Install Dependencies
```bash
git clone <repository-url>
cd RAG-IMPLEMENTATION
pip install -r requirements.txt
```

#### Step 2: Pull Ollama Models
```bash
ollama pull qwen3.5:4b
ollama pull mxbai-embed-large
```

#### Step 3: Setup Supabase
1. Create a Supabase project at https://supabase.com
2. Go to SQL Editor
3. Run the entire `init_supabase.sql` script

#### Step 4: Configure Environment
```bash
cp .env.example .env
# Edit .env and add your Supabase credentials:
# - SUPABASE_URL
# - SUPABASE_SERVICE_ROLE_KEY
```

#### Step 5: Start the Server
```bash
python main.py
# Or: python run.bat (Windows) or ./run.sh (Linux/Mac)
```

### Access Points

- **Web UI**: http://localhost:8000
- **Debug Chat**: http://localhost:8000/debug
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redocdoc

### Quick Test

#### Option A: Use the Web UI
Open http://localhost:8000 in your browser and upload documents directly.

#### Option B: Seed Sample Data
```bash
python seed_sample.py
```

#### Option C: Test with Python
```bash
python test_agent.py
```

#### Option D: Use cURL
```bash
# Health check
curl http://localhost:8000/health

# Upload a document
curl -X POST http://localhost:8000/ingest -F "file=@document.pdf"

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is your return policy?"}'
```

## ≡ƒÆ¼ Debug Chat Interface

An interactive chat-style debugging interface at `/debug` that provides real-time insights into the agent's reasoning process.

### Features
- **≡ƒÆ¼ Conversational UI**: Chat-style interface with message history
- **≡ƒÉ¢ Debug Information**: Collapsible panels showing statistics, reasoning trace, and sources
- **ΓÜÖ∩╕Å Configuration**: Toggle between Agentic/Simple modes, adjust Top K, and toggle debug info
- **≡ƒôè Real-time Metrics**: Processing time, iterations, confidence scores, and verification status

### Usage
1. Navigate to `http://localhost:8000/debug`
2. Type your question and select query mode
3. View detailed reasoning steps and retrieved sources
4. Use debug toggle to show/hide detailed information

### Tips
- Use **Agentic Mode** for complex questions requiring multi-step reasoning
- Keep **Debug ON** during development to see full reasoning process
- **Check Reasoning Trace** to understand how the agent reached its answer
- **Review Sources** to verify answer is grounded in retrieved documents

## ≡ƒôª Multiple File Upload with Duplicate Detection

### How to Upload Multiple Files

1. **Select Multiple Files**: Hold Ctrl (Windows/Linux) or Cmd (Mac) to select multiple files
2. **Automatic Duplicate Check**: System automatically detects existing files
3. **Choose Action**: Select how to handle duplicates:
   - **Skip (Default)**: Don't upload files that already exist
   - **Replace**: Delete old chunks and upload new version
   - **Append**: Keep old chunks and add new chunks
4. **Upload & Review**: See detailed results for each file

### Duplicate Handling Modes

#### Γ£à Skip (Recommended)
- **What it does**: Doesn't upload files that already exist
- **When to use**: Default safe option, prevents accidental overwrites
- **Use case**: Bulk uploads with some duplicates

#### ≡ƒöä Replace
- **What it does**: Deletes old chunks and uploads new version
- **When to use**: File content has changed significantly
- **Use case**: Daily/regular updates (e.g., daily reports)

#### Γ₧ò Append
- **What it does**: Keeps old chunks and adds new chunks
- **When to use**: Adding new information to existing document
- **Use case**: Incremental content addition (e.g., documentation expansion)

### Example Scenarios

- **Daily Report Update**: Use "Replace" to update with latest version
- **Documentation Expansion**: Use "Append" to add new content while keeping existing
- **Mixed Batch Upload**: Use "Skip" to only upload new files, skipping existing ones

## ≡ƒôÜ API Endpoints

### Health & Stats

#### GET /health
Check system health and component availability.

**Response:**
```json
{
  "status": "healthy",
  "database_connected": true,
  "ollama_available": true,
  "ollama_models": {
    "llm": true,
    "embeddings": true
  }
}
```

#### GET /stats
Get database statistics.

**Response:**
```json
{
  "total_chunks": 150,
  "unique_sources": 5,
  "unique_models": 1,
  "latest_chunk": "2024-01-15T10:30:00Z"
}
```

### Document Ingestion

#### POST /ingest
Upload and process a single document into the knowledge base.

**Request:**
- **file**: Document file (multipart/form-data)
- **source**: Optional source identifier (defaults to filename)

**Supported Formats**: PDF, DOCX, PPTX, TXT, MD, HTML, HTM

**Example:**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf" \
  -F "source=my-document"
```

**Response:**
```json
{
  "success": true,
  "message": "Document processed successfully",
  "source": "my-document",
  "chunks_created": 25,
  "file_size": 1048576,
  "processing_time": 3.45
}
```

#### POST /ingest/batch
Upload and process multiple documents with duplicate handling.

**Request:**
- **files**: Multiple document files (multipart/form-data)
- **source_prefix**: Optional prefix for all sources
- **duplicate_action**: How to handle duplicates: "skip", "replace", or "append" (default: "skip")

**Example:**
```bash
curl -X POST http://localhost:8000/ingest/batch \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "duplicate_action=skip"
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "filename": "doc1.pdf",
      "source": "doc1.pdf",
      "status": "NEW",
      "chunks_created": 25,
      "message": "Document uploaded successfully"
    },
    {
      "filename": "doc2.pdf",
      "source": "doc2.pdf",
      "status": "SKIPPED",
      "chunks_created": 0,
      "message": "Document already exists"
    }
  ],
  "summary": {
    "total": 2,
    "successful": 1,
    "skipped": 1,
    "failed": 0
  }
}
```

#### POST /ingest/check-duplicates
Check if files already exist in the database.

**Request:**
```json
{
  "filenames": ["doc1.pdf", "doc2.pdf"],
  "source_prefix": ""
}
```

**Response:**
```json
{
  "duplicates": [
    {
      "filename": "doc1.pdf",
      "exists": true,
      "chunk_count": 25
    },
    {
      "filename": "doc2.pdf",
      "exists": false,
      "chunk_count": 0
    }
  ]
}
```

#### GET /ingest/documents
List all documents in the knowledge base.

**Response:**
```json
{
  "documents": [
    {"source": "document1.pdf", "type": "document"},
    {"source": "document2.docx", "type": "document"}
  ],
  "total": 2
}
```

#### DELETE /ingest/documents/{source}
Delete all chunks from a specific document.

**Example:**
```bash
curl -X DELETE http://localhost:8000/ingest/documents/my-document
```

### Querying

#### POST /query
Execute an **agentic RAG query** with full reasoning loop.

**Request Body:**
```json
{
  "query": "What is the return policy?",
  "top_k": 6,
  "filter_source": null,
  "enable_agent": true
}
```

**Response:**
```json
{
  "query": "What is the return policy?",
  "answer": "Based on the documents, you can return items within 30 days...",
  "confidence": 0.85,
  "sources": ["policy.pdf (similarity: 0.92)", "faq.pdf (similarity: 0.78)"],
  "reasoning_trace": [
    "[Iteration 1] PLAN: Search for return policy information",
    "[Iteration 1] RETRIEVE: Retrieved 6 documents",
    "[Iteration 1] REASON: Found relevant policy information",
    "[Iteration 1] VERIFY: Verified: true, Confidence: 0.85",
    "[Iteration 1] DECIDE: Providing final answer with confidence 0.85"
  ],
  "iterations": 1,
  "retrieved_chunks": 6,
  "verification_passed": true,
  "processing_time": 4.23
}
```

#### POST /query/simple
Execute a **simple RAG query** (single retrieval, no agent loop).

**Request Body:**
```json
{
  "query": "What is the return policy?",
  "top_k": 6
}
```

**Response:**
```json
{
  "query": "What is the return policy?",
  "answer": "You can return items within 30 days...",
  "sources": [
    {
      "source": "policy.pdf",
      "similarity": 0.92,
      "text": "Return Policy: All items can be returned..."
    }
  ],
  "retrieved_chunks": 6
}
```

### Admin

#### DELETE /reset
**ΓÜá∩╕Å DANGER**: Clear all chunks from the database. Use with caution!

```bash
curl -X DELETE http://localhost:8000/reset
```

## ≡ƒöº Configuration

All configuration is managed through environment variables (see .env.example):

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| OLLAMA_LLM_MODEL | qwen3.5:4b | LLM for agent reasoning |
| OLLAMA_EMBED_MODEL | mxbai-embed-large | Embedding model (1024d) |
| CHUNK_SIZE | 800 | Target chunk size in tokens |
| CHUNK_OVERLAP | 100 | Overlap between chunks |
| TOP_K_RESULTS | 6 | Documents retrieved per query |
| MAX_AGENT_ITERATIONS | 3 | Max reasoning loop iterations |
| MIN_CONFIDENCE_THRESHOLD | 0.7 | Min confidence to finalize answer |
| ENABLE_VERIFICATION | true | Enable hallucination detection |

## ≡ƒºá How the Agent Works

### 6-Phase Reasoning Loop

1. **PLAN**: Agent analyzes the query and creates a retrieval strategy
2. **RETRIEVE**: Executes semantic search in the vector database
3. **REASON**: Evaluates if retrieved information is sufficient and relevant
4. **VERIFY**: Checks for hallucinations and ensures grounding in context
5. **DECIDE**: Determines if ready to answer or needs more information
6. **ANSWER/ITERATE**: Provides final answer or refines query and loops

### Hallucination Prevention

- **Ground Checking**: Every claim verified against retrieved context
- **Citation Requirements**: Forces model to reference specific sources
- **Confidence Scoring**: Agent rates confidence before finalizing
- **Low Confidence Trigger**: Re-retrieval triggered if confidence < 0.7

### Query Refinement Strategies

- **Expansion**: Broadens query if no results found
- **Focusing**: Narrows query if results too broad
- **Rewriting**: Rephrases using terminology from retrieved docs
- **Decomposition**: Breaks complex queries into sub-questions

## ≡ƒôû Example Usage

### Python Client

```python
import requests

# Ingest a document
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/ingest',
        files={'file': f},
        data={'source': 'my-doc'}
    )
    print(response.json())

# Query with agent
response = requests.post(
    'http://localhost:8000/query',
    json={
        'query': 'What are the key benefits?',
        'top_k': 6
    }
)
result = response.json()
print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence']}")
print(f"Iterations: {result['iterations']}")
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Upload document
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf"

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the main topic?"}'

# Get stats
curl http://localhost:8000/stats
```

## ΓÜí Performance Optimization

### Speed vs Quality Trade-offs

#### Development Settings (Fast)
```env
OLLAMA_LLM_MODEL=qwen2.5:3b
OLLAMA_EMBED_MODEL=all-minilm
OLLAMA_TIMEOUT=120
MAX_AGENT_ITERATIONS=2
TOP_K_RESULTS=3
ENABLE_VERIFICATION=false
```

#### Production Settings (Balanced)
```env
OLLAMA_LLM_MODEL=qwen3.5:4b
OLLAMA_EMBED_MODEL=mxbai-embed-large
OLLAMA_TIMEOUT=300
MAX_AGENT_ITERATIONS=3
TOP_K_RESULTS=6
ENABLE_VERIFICATION=true
```

#### High Quality Settings (Slower)
```env
OLLAMA_LLM_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=mxbai-embed-large
OLLAMA_TIMEOUT=600
MAX_AGENT_ITERATIONS=3
TOP_K_RESULTS=10
ENABLE_VERIFICATION=true
```

### Expected Performance Targets
- **Simple Query**: 2-5 seconds
- **Agentic Query (2 iterations)**: 5-15 seconds
- **Agentic Query (3 iterations)**: 10-30 seconds

### Optimization Tips

1. **Reduce Agent Iterations** for faster responses
2. **Lower Top K Results** to retrieve fewer chunks
3. **Use Smaller Models** for speed (e.g., qwen2.5:3b)
4. **Disable Verification** for testing (not recommended for production)
5. **Pre-load Models**: Run `ollama run qwen3.5:4b "hello"` to load model into memory

### Check Ollama Performance
```bash
# Test connection
curl http://localhost:11434/api/tags

# Test generation speed
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3.5:4b",
  "prompt": "Hello",
  "stream": false
}'
```

### Ollama Server Optimization
```env
# Increase parallel requests
OLLAMA_NUM_PARALLEL=2

# Increase max loaded models
OLLAMA_MAX_LOADED_MODELS=2

# Use all GPU layers (if using GPU)
OLLAMA_NUM_GPU=999
```

## ≡ƒÉ¢ Troubleshooting

### Ollama Connection Issues
```bash
# Check Ollama is running
ollama list

# Test models are available
ollama run qwen3.5:4b "test"
ollama pull mxbai-embed-large

# Check if Ollama service is running
curl http://localhost:11434
```

**If "Connection Refused":**
```bash
# Start Ollama service
ollama serve
```

**If "Timeout" errors:**
- Increase `OLLAMA_TIMEOUT` in .env
- Use a smaller model
- Reduce `MAX_AGENT_ITERATIONS`

### Database Connection Issues
- Verify SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
- Ensure init_supabase.sql was run successfully
- Check Supabase project is active and not paused
- Test connection from Supabase dashboard

### Document Processing Errors
- Verify file format is supported (PDF, DOCX, PPTX, TXT, MD, HTML, HTM)
- Check file size is under limit (default 50MB)
- Ensure Docling dependencies are installed: `pip install -r requirements.txt`
- Check file is not corrupted

### Duplicate Upload Issues

**Q: File was skipped but I wanted to upload it**
- Change duplicate action from "Skip" to "Replace" or "Append"

**Q: What's the difference between Replace and Append?**
- **Replace**: Deletes old chunks, uploads new version (for updates)
- **Append**: Keeps old chunks, adds new chunks (for additions)

**Q: How do I see what files already exist?**
- Switch to "Ingest" tab and view "Uploaded Documents" list
- Or use API: `GET /ingest/documents`

### Low Quality Answers
- Increase TOP_K_RESULTS for more context (try 10 instead of 6)
- Adjust CHUNK_SIZE and CHUNK_OVERLAP in .env
- Try different embedding models (mxbai-embed-large is good)
- Check document quality and relevance
- Use Agentic mode instead of Simple mode for complex questions
- Check reasoning trace in debug console to see what went wrong

### Slow Performance
- Use smaller models (qwen2.5:3b vs qwen3.5:4b)
- Reduce MAX_AGENT_ITERATIONS (2 instead of 3)
- Lower TOP_K_RESULTS (3 instead of 6)
- Disable ENABLE_VERIFICATION for testing
- Check system resources (CPU, RAM)
- Restart Ollama service

## ≡ƒöÉ Security Notes

- Never commit .env file with real credentials
- Use SUPABASE_SERVICE_ROLE_KEY only in backend
- Implement authentication for production use
- Review RLS policies in Supabase for multi-tenant scenarios

## ≡ƒôä License

MIT License - see LICENSE file for details

## ≡ƒñ¥ Contributing

Contributions welcome! Please open an issue or submit a pull request.

## ≡ƒº¬ Testing Scripts

### Test Agent Reasoning
```bash
python test_agent.py
```
Tests the agentic reasoning loop with sample queries.

### Test Batch Upload
```bash
python test_batch_upload.py
```
Tests multiple file upload with duplicate handling.

### Test Duplicate Handling
```bash
python test_duplicate_handling.py
```
Tests skip, replace, and append modes for duplicate files.

### Seed Sample Data
```bash
python seed_sample.py
```
Populates the database with sample documents for testing.

## ≡ƒô¼ Support

For issues and questions, please open a GitHub issue.
