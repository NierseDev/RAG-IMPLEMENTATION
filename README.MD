# Agentic RAG System

A sophisticated **Agentic RAG (Retrieval-Augmented Generation)** system with multi-step reasoning, self-reflection, and hallucination detection. Built with FastAPI, Supabase (pgvector), and Ollama.

## ✨ Features

- **🔄 Agentic Reasoning Loop**: 6-phase reasoning cycle (Plan → Retrieve → Reason → Verify → Decide → Answer/Iterate)
- **✓ Hallucination Prevention**: Ground checking, citation requirements, and confidence scoring
- **🔄 Iterative Query Refinement**: Agent refines queries based on retrieved information
- **📄 Multi-Format Documents**: Process PDF, DOCX, PPTX, HTML, Markdown using Docling
- **🔍 Hybrid Search**: Vector + keyword search with RRF fusion and metadata filtering (Sprint 4)
- **✅ Verification System**: Validates answers against retrieved context
- **🌐 REST API**: Clean FastAPI endpoints with auto-generated docs
- **🖥️ Debug Web UI**: Real-time visualization of agent reasoning
- **📤 Batch Upload**: Multiple file upload with duplicate detection
- **🔄 Smart Duplicate Handling**: Skip, Replace, or Append modes for existing files
- **🛠️ Intelligent Tool Routing**: Query classification with automatic tool selection (Sprint 4)
- **⚙️ Multi-Tool Workflows**: Sequential/parallel/conditional execution with fallbacks (Sprint 4)
- **📋 Frontend State Management**: Pub/sub state system with localStorage persistence (Sprint 4)

## 🏗️ Architecture

**Tech Stack:**
- **Frontend**: Web UI with chat interface
- **Backend**: FastAPI with REST endpoints
- **Vector Database**: Supabase (PostgreSQL + pgvector)
- **AI**: Ollama (local LLM + embeddings)
- **Document Processing**: Docling (multi-format support)

**Core Components:**
- **Agentic RAG Coordinator**: 6-phase reasoning loop (Plan → Retrieve → Reason → Verify → Decide → Answer)
- **Document Processor**: Converts documents to searchable chunks
- **Embedding Service**: Generates vector representations
- **Retrieval Service**: Semantic search with pgvector
- **Verification Service**: Hallucination detection and confidence scoring

## ⚡ Quick Start

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
python tests/test_agent.py
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

## 💬 Debug Chat Interface

An interactive chat-style debugging interface at `/debug` that provides real-time insights into the agent's reasoning process.

### Features
- **💬 Conversational UI**: Chat-style interface with message history
- **🔧 Debug Information**: Collapsible panels showing statistics, reasoning trace, and sources
- **⚙️ Configuration**: Toggle between Agentic/Simple modes, adjust Top K, and toggle debug info
- **📊 Real-time Metrics**: Processing time, iterations, confidence scores, and verification status

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

## 🌳 Hierarchical Agent Display (Sprint 5)

A comprehensive hierarchical visualization system for displaying main agent and spawned sub-agents in the web UI.

### Features
- **🎯 Agent Hierarchy Panel**: Tree view showing main agent → sub-agents relationships
- **📊 Real-time Metrics**: Duration, retrieved documents, iterations, confidence scores
- **🧠 Reasoning Traces**: Step-by-step reasoning from all agents (main + sub-agents)
- **📈 Performance Timeline**: Visual timeline of all reasoning steps
- **🔄 Expand/Collapse**: Interactive expand/collapse for each agent node
- **🎨 Color Coding**: Different colors for different agent types
- **📱 Responsive Design**: Mobile-friendly layout with adaptive grid

### Components

#### AgentHierarchyPanel
Displays the hierarchical tree of agents with real-time updates.

```javascript
// Usage
const hierarchyPanel = new AgentHierarchyPanel('agent-hierarchy-container');
```

**Features:**
- Main agent at the top (purple badge)
- Sub-agents indented below (color-coded by type)
- Status indicators (running/completed)
- Expandable reasoning traces
- Per-agent metrics display

**Agent Types & Colors:**
- Main: #667eea (blue)
- full_document: #8b5cf6 (purple)
- comparison: #06b6d4 (cyan)
- extraction: #10b981 (green)
- search: #f59e0b (amber)

#### ReasoningTimeline
Shows a chronological timeline of all reasoning steps across all agents.

```javascript
// Usage
const timeline = new ReasoningTimeline('reasoning-timeline-container');
```

**Features:**
- Vertical timeline with connecting line
- Icon indicators for step types (🔍 search, 🔀 decompose, 🚀 spawn, ✅ complete, ❌ error)
- Clickable steps
- Scrollable for long workflows

#### MetricsPanel
Displays aggregated performance metrics.

```javascript
// Usage
const metrics = new MetricsPanel('metrics-panel-container');
```

**Metrics:**
- Total Duration: Sum of all agent durations
- Documents Retrieved: Count of unique documents
- Agent Count: Total agents (main + sub-agents)
- Confidence Score: Main agent's confidence

### State Manager Actions

#### recordSubAgentSpawn
Log when a sub-agent is spawned.

```javascript
const agentId = await stateManager.dispatch('recordSubAgentSpawn', {
    agentType: 'full_document',      // Type of sub-agent
    context: 'Processing full document',  // Context info
    reasoning: ['Step 1', 'Step 2']  // Initial reasoning steps
});
```

#### recordSubAgentResult
Record completion of a sub-agent.

```javascript
await stateManager.dispatch('recordSubAgentResult', {
    subAgentId: agentId,             // ID returned from spawn
    result: 'Processing complete',   // Result text
    reasoning: ['Analysis 1', 'Analysis 2'],  // Final reasoning
    metrics: {
        retrievedDocuments: 10,
        confidence: 0.85
    }
});
```

#### updateMainAgentMetrics
Update main agent's performance metrics.

```javascript
await stateManager.dispatch('updateMainAgentMetrics', {
    metrics: {
        duration: 5.5,
        retrievedDocuments: 15,
        iterations: 2,
        confidence: 0.92
    }
});
```

#### updateMainAgentReasoning
Update main agent's reasoning trace.

```javascript
await stateManager.dispatch('updateMainAgentReasoning', {
    reasoning: [
        'Analyzed query complexity',
        'Detected multi-step scenario',
        'Spawning specialized sub-agents'
    ]
});
```

#### updateAgentHierarchy
Update the entire agent hierarchy at once.

```javascript
await stateManager.dispatch('updateAgentHierarchy', {
    hierarchy: {
        mainAgent: { /* ... */ },
        subAgents: [ /* ... */ ],
        expandedAgents: { /* ... */ }
    }
});
```

#### toggleAgentExpanded
Toggle expand/collapse state for an agent.

```javascript
await stateManager.dispatch('toggleAgentExpanded', {
    agentId: 'agent-uuid-or-main'
});
```

#### clearAgentHierarchy
Clear all agents and reset to initial state.

```javascript
await stateManager.dispatch('clearAgentHierarchy');
```

### Integration Example

```javascript
// When spawning a sub-agent in your code
const agentId = await stateManager.dispatch('recordSubAgentSpawn', {
    agentType: 'full_document',
    context: 'Processing document set',
    reasoning: ['Detected full document requirement']
});

// Update main agent reasoning
await stateManager.dispatch('updateMainAgentReasoning', {
    reasoning: ['Query analyzed', 'Spawning full_document sub-agent']
});

// ... perform work ...

// Record the result
await stateManager.dispatch('recordSubAgentResult', {
    subAgentId: agentId,
    result: 'Extracted 25 relevant sections',
    reasoning: ['Processing complete', 'Results aggregated'],
    metrics: {
        retrievedDocuments: 25,
        confidence: 0.88
    }
});

// Update main agent final metrics
await stateManager.dispatch('updateMainAgentMetrics', {
    metrics: {
        duration: 8.5,
        retrievedDocuments: 30,
        iterations: 2,
        confidence: 0.90
    }
});
```

### Testing

#### Test State Manager Actions
Open `http://localhost:8000/test-state-manager.html` to run comprehensive tests of all state management actions.

#### Test UI Components
Open `http://localhost:8000/test-hierarchy.html` to interactively test the UI components with simulated agent data.

**Test Controls:**
- 📌 Spawn Sub-Agent: Creates a random sub-agent
- ✅ Complete Sub-Agent: Marks the last sub-agent as complete
- 📊 Update Metrics: Updates main agent metrics with random values
- 🔄 Toggle Expand: Toggles main agent expansion
- 🗑️ Clear Hierarchy: Resets all agents
- ▶️ Simulate Full Workflow: Runs a complete multi-step workflow

### Styling

The components use a dark theme matching the existing UI with CSS custom properties for colors:

- **Primary**: #667eea (blue)
- **Secondary**: #764ba2 (purple)
- **Success**: #22c55e (green)
- **Warning**: #fb923c (orange)
- **Error**: #ef4444 (red)
- **Background**: #0f172a (dark)
- **Surface**: #1e293b (darker)

All components are fully responsive and work on mobile/tablet/desktop.

## 📤 Multiple File Upload with Duplicate Detection

### How to Upload Multiple Files

1. **Select Multiple Files**: Hold Ctrl (Windows/Linux) or Cmd (Mac) to select multiple files
2. **Automatic Duplicate Check**: System automatically detects existing files
3. **Choose Action**: Select how to handle duplicates:
   - **Skip (Default)**: Don't upload files that already exist
   - **Replace**: Delete old chunks and upload new version
   - **Append**: Keep old chunks and add new chunks
4. **Upload & Review**: See detailed results for each file

### Duplicate Handling Modes

#### ✓ Skip (Recommended)
- **What it does**: Doesn't upload files that already exist
- **When to use**: Default safe option, prevents accidental overwrites
- **Use case**: Bulk uploads with some duplicates

#### 🔄 Replace
- **What it does**: Deletes old chunks and uploads new version
- **When to use**: File content has changed significantly
- **Use case**: Daily/regular updates (e.g., daily reports)

#### ➕ Append
- **What it does**: Keeps old chunks and adds new chunks
- **When to use**: Adding new information to existing document
- **Use case**: Incremental content addition (e.g., documentation expansion)

### Example Scenarios

- **Daily Report Update**: Use "Replace" to update with latest version
- **Documentation Expansion**: Use "Append" to add new content while keeping existing
- **Mixed Batch Upload**: Use "Skip" to only upload new files, skipping existing ones

## 📡 API Endpoints

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
**⚠️ DANGER**: Clear all chunks from the database. Use with caution!

```bash
curl -X DELETE http://localhost:8000/reset
```

## ⚙️ Configuration

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

## 🧠 How the Agent Works

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

## 💻 Example Usage

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

## ⚡ Performance Optimization

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

## 🔧 Troubleshooting

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

## 🔒 Security Notes

- Never commit .env file with real credentials
- Use SUPABASE_SERVICE_ROLE_KEY only in backend
- Implement authentication for production use
- Review RLS policies in Supabase for multi-tenant scenarios

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 🧪 Testing & Debugging

### 🔍 Debug Tool (Consolidated)
All-in-one debugging tool for troubleshooting RAG system issues.

```bash
# Test a single query with detailed debug output
python debug.py query "What is Deep Q Learning?"

# Interactive mode for multiple queries
python debug.py interactive

# Test Ollama connection directly (isolate connection issues)
python debug.py ollama

# Show help
python debug.py help
```

**When to use:**
- Troubleshooting confidence score issues
- Investigating empty responses
- Checking Ollama connectivity
- Analyzing agent reasoning steps

### 📤 Upload Testing Tool
Consolidated tool for testing document ingestion functionality.

```bash
# Test batch file upload
python tests/test_upload.py batch

# Test duplicate handling (skip, replace, append modes)
python tests/test_upload.py duplicates

# Run all upload tests
python tests/test_upload.py all

# Show help
python tests/test_upload.py help
```

**Tests included:**
- Multiple file batch upload
- Duplicate detection
- Skip/Replace/Append modes
- API error handling

### 🤖 Agent Testing
```bash
python tests/test_agent.py
```
Tests the core agentic reasoning loop with predefined queries. Best for smoke testing after code changes.

### 🌱 Seed Sample Data
```bash
python seed_sample.py
```
Populates the database with sample documents for testing queries.

## 🎓 Citation Format

The system uses **APA format** for citations:

### In-Text Citations
```
According to Smith (2020), deep Q-learning improves game AI performance.
Recent research shows significant improvements (Johnson & Lee, 2021).
```

### References Section
The LLM automatically adds a References section at the end with full citations.

### For PDFs Without Clear Author/Year
```
Game AI has evolved significantly (Adaptive Game AI RTContinuous Environment NeuralNetwork, n.d.).
```

### Improving Citation Quality

To get better APA citations, consider:
1. **Add metadata when uploading**: Extract author, year, title from PDFs
2. **Create citation database**: Store bibliographic information separately
3. **Post-process citations**: Convert source references to proper APA format

## 🐛 Debugging

### Quick Debug Commands

```bash
# Test a single query with full debug output (RECOMMENDED)
python debug.py query "Your question here"

# Interactive debugging session
python debug.py interactive

# Test Ollama connection
python debug.py ollama

# Alternative: Test model directly via CLI
ollama run llama3.1:8b "test"
```

### Debug Output Interpretation

**Confidence Score Issues:**
Look for these markers in debug output:
```
DEBUG: Raw LLM Verification Response
DEBUG: Parsed verification - confidence=X.XX
DEBUG: Grounding score calculated: X.XX
```

**Decision Logic:**
```
DEBUG: Decision Phase
  Current confidence: 0.5
  Min confidence threshold: 0.5
  DECISION: answer/continue
```

**Answer Generation:**
```
DEBUG: Setting final_answer (length: XXX chars)
```

### Common Issues and Solutions

**Empty Responses:**
- Check Ollama model is responding: `ollama run llama3.1:8b "test"`
- Verify model in .env: `OLLAMA_LLM_MODEL=llama3.1:8b`
- Check debug logs for "Content length: 0"

**Confidence Always 0.5:**
- LLM not returning confidence scores in expected format
- Check verification prompt is being followed
- Enable debug logging to see raw LLM responses

**Slow Performance:**
- Switch to smaller model: `llama3.1:8b` → `qwen2.5:3b`
- Reduce iterations: `MAX_AGENT_ITERATIONS=2`
- Lower retrieval: `TOP_K_RESULTS=3`

### Model Recommendations

| Model | Context | Speed | Quality | Use Case |
|-------|---------|-------|---------|----------|
| llama3.1:8b | 128K | Medium | High | **Recommended** - Best balance |
| qwen2.5:7b | 32K | Slow | High | High quality answers |
| qwen2.5:3b | 32K | Fast | Medium | Development/testing |
| qwen3.5:4b | 8K | Slow | Medium | ⚠️ Has "thinking mode" issues |

**Important:** Avoid `qwen3.5:4b` - it has a "thinking mode" feature that causes empty responses.

## 📞 Support

For issues and questions, please open a GitHub issue.
