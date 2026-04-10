# Frontend JavaScript Libraries

This directory contains two production-ready JavaScript systems for the Agentic RAG frontend:
1. **State Manager** - Pub/sub state management with persistence
2. **API Client** - FastAPI wrapper with full endpoint coverage

---

## 🎯 Quick Navigation

| System | Start Here | Full Docs | Examples | Tests |
|--------|-----------|-----------|----------|-------|
| **State Manager** | [Quick Ref](#state-manager-quick-reference) | [STATE-MANAGER-DOCS.md](#full-documentation-legacy) | [examples.js](#examples) | [state-manager-test.js](#testing) |
| **API Client** | [Quick Ref](#api-client-quick-reference) | [README-API-CLIENT.md](#full-documentation-legacy) | [api-client-example.html](#examples-1) | [api-client-test.html](#testing-1) |

---

## 📦 What's Included

### Files Overview

```
static/js/
├── Core Libraries
│   ├── state-manager.js              (950 lines) - State management system
│   └── api-client.js                 (793 lines) - API wrapper
│
├── Tests & Examples
│   ├── state-manager-test.js         (20+ tests)
│   ├── state-manager-examples.js     (Real-world usage)
│   ├── api-client-test.js            (28 tests)
│   ├── api-client-test.html          (Interactive test runner)
│   └── api-client-example.html       (Interactive demos)
│
├── Documentation (Legacy - consolidated here)
│   ├── STATE-MANAGER-DOCS.md         (Full reference)
│   ├── STATE-MANAGER-QUICK-REF.md    (Quick lookup)
│   ├── README-API-CLIENT.md          (Full reference)
│   ├── QUICK-REFERENCE.md            (Quick lookup)
│   ├── INTEGRATION-GUIDE.md          (Framework integration)
│   ├── API-CLIENT-SUMMARY.md         (Summary)
│   ├── DELIVERY-CHECKLIST.md         (Delivery details)
│   └── INDEX.md                      (File index)
│
└── HTML Pages
    ├── index.html                    (Initializes both systems)
    ├── chat.html, debug.html, etc.   (Use both systems)
```

---

# STATE MANAGER

Production-ready pub/sub state management with localStorage persistence and React-like hooks.

## Features

✅ **Vanilla JavaScript** (no dependencies)  
✅ **Pub/Sub Pattern** (reactive updates)  
✅ **localStorage Persistence** (automatic state saving)  
✅ **React-like Hooks** (useState, useDispatch, useSelector, useEffect)  
✅ **4 State Trees** (chat, document, debug, ui)  
✅ **18 Built-in Actions** (API integration)  
✅ **Middleware Support** (logging, analytics)  

## State Manager Quick Reference

### Initialization

```javascript
// Global instance (already initialized in index.html)
const sm = window.StateManagerInstance;
```

### Reading State

```javascript
// Get all state
sm.getState()

// Get specific path
sm.getState('chat.messages')
sm.getState('chat')
```

### Updating State

```javascript
// Single value
sm.setState('chat.currentSession', 'session-123')

// Multiple values
sm.setState({
    'chat.currentSession': 'session-123',
    'chat.loadingQuery': true
})
```

### Hook-Like Utilities

```javascript
// Listen to changes (React-like)
StateHooks.useState('chat.messages', (messages) => {
    updateUI(messages)
})

// Dispatch actions
const send = StateHooks.useDispatch('sendQuery')
await send({ query: 'Hello', sessionId: 'sid-123' })

// Select from state
StateHooks.useSelector('chat.messages', (msgs) => {
    console.log(msgs)
})

// React to multiple changes
StateHooks.useEffect((state) => {
    // Handle state changes
}, ['chat', 'document'])
```

### Built-in Actions

#### Chat Actions
```javascript
await sm.dispatch('loadSessions')                  // Load all sessions
await sm.dispatch('createSession', 'Title')       // Create new session
await sm.dispatch('setCurrentSession', 'sid')     // Set active session
await sm.dispatch('sendQuery', {                  // Send query
    query: 'Question',
    sessionId: 'sid-123'
})
await sm.dispatch('addMessage', {                 // Add message
    role: 'user',
    content: 'Hello',
    timestamp: new Date().toISOString()
})
await sm.dispatch('clearMessages')                // Clear all messages
```

#### Document Actions
```javascript
await sm.dispatch('loadDocuments')                // Load all documents
await sm.dispatch('addDocument', {...})           // Add document
await sm.dispatch('removeDocument', docId)        // Delete document
await sm.dispatch('selectDocument', docId)        // Select document
await sm.dispatch('updateDocumentProgress', {     // Update progress
    docId: 1,
    progress: 75
})
```

#### Debug Actions
```javascript
await sm.dispatch('refreshSystemStatus')          // Update status
await sm.dispatch('setTraceData', [...])          // Set trace data
await sm.dispatch('setDebugOpen', true)           // Toggle debug panel
```

#### UI Actions
```javascript
await sm.dispatch('setActiveTab', 'chat')         // Set tab
await sm.dispatch('toggleSidebar')                // Toggle sidebar
await sm.dispatch('setSidebarOpen', true)         // Set sidebar
await sm.dispatch('addNotification', {            // Show notification
    message: 'Success!',
    type: 'success',
    duration: 3000
})
```

### State Tree Structure

```javascript
state.chat = {
    messages: [],           // Array of message objects
    currentSession: null,   // Current session ID
    sessionList: [],        // List of all sessions
    loadingQuery: false     // Loading indicator
}

state.document = {
    uploadedDocs: [],       // Array of documents
    uploadProgress: {},     // { docId: percent }
    selectedDoc: null,      // Selected document ID
    loadingDocs: false      // Loading indicator
}

state.debug = {
    systemStatus: {         // System health info
        agentHealthy: null,
        dbHealthy: null,
        llmModel: null,
        embeddingModel: null
    },
    debugOpen: false,       // Debug panel visible
    traceData: [],          // Reasoning trace
    agentStatus: null       // Full agent status
}

state.ui = {
    activeTab: 'chat',      // Current tab
    sidebarOpen: true,      // Sidebar visible
    notifications: []       // Notifications array
}
```

### Subscribe to Changes

```javascript
// Listen to all changes
const unsub = sm.subscribe((state) => {
    console.log('State changed:', state)
})

// Listen to specific paths only
const unsub = sm.subscribe(() => {
    console.log('Chat or docs changed')
}, ['chat', 'document'])

// Stop listening
unsub()
```

### Persistence

```javascript
sm.persist()                // Save to localStorage
sm.hydrate()                // Load from localStorage
sm.reset()                  // Clear all state
```

### Utilities

```javascript
sm.use((updates, state) => {})          // Add middleware
sm.stopStatusUpdates()                   // Stop polling
sm.startStatusUpdates()                  // Resume polling
sm.destroy()                             // Cleanup
```

## State Manager - Common Patterns

### Pattern 1: Listen to Messages and Update UI
```javascript
StateHooks.useState('chat.messages', (messages) => {
    const container = document.getElementById('messages')
    container.innerHTML = messages.map(msg => `
        <div class="msg-${msg.role}">${msg.content}</div>
    `).join('')
})
```

### Pattern 2: Send Query with Error Handling
```javascript
async function handleSendClick() {
    const text = document.getElementById('input').value
    const dispatch = StateHooks.useDispatch('sendQuery')
    
    try {
        const result = await dispatch({
            query: text,
            sessionId: sm.getState('chat.currentSession')
        })
        console.log('Response:', result)
    } catch (error) {
        console.error('Error:', error)
    }
}
```

### Pattern 3: Show Notifications
```javascript
function showNotification(message, type = 'info') {
    StateHooks.useDispatch('addNotification')({
        message,
        type,
        duration: 3000
    })
}

showNotification('Document uploaded!', 'success')
showNotification('Failed to process', 'error')
```

### Pattern 4: Monitor Multiple State Changes
```javascript
StateHooks.useEffect((state) => {
    if (!state.document.loadingDocs && 
        state.document.uploadedDocs.length > 0) {
        const hasProcessing = state.document.uploadedDocs.some(
            d => d.status === 'processing'
        )
        if (!hasProcessing) {
            showNotification('All documents processed!', 'success')
        }
    }
}, ['document.loadingDocs', 'document.uploadedDocs'])
```

---

# API CLIENT

Production-ready JavaScript wrapper for the Agentic RAG FastAPI backend.

## Features

✅ **23+ API Methods** (full endpoint coverage)  
✅ **Error Handling** (custom APIError class)  
✅ **Retry Logic** (exponential backoff)  
✅ **Request/Response Interceptors** (middleware)  
✅ **Session Management** (create, list, delete)  
✅ **Upload Progress Tracking** (progress callbacks)  
✅ **Batch Operations** (parallel & sequential)  
✅ **TypeScript-like JSDoc** (type definitions)  

## API Client Quick Reference

### Initialization

```javascript
// Default
const client = new APIClient()

// Custom config
const client = new APIClient('http://localhost:8000', {
    timeout: 30000,      // Request timeout (ms)
    retries: 3,          // Retry attempts
    retryDelay: 1000,    // Initial retry delay (exponential backoff)
    headers: {}          // Custom headers
})
```

### Authentication & Session

```javascript
// Auth token
client.setAuthToken('your-token')
client.clearAuthToken()

// Session management
client.setSessionId(sessionId)
const sessionId = client.getSessionId()
```

### Query Endpoints

```javascript
// Agentic reasoning query (full 6-phase pipeline)
const result = await client.query('What is machine learning?', {
    top_k: 5,              // Number of documents to retrieve
    filter_source: 'docs', // Optional source filter
    timeout: 60000         // Request timeout in ms
})
console.log(result.answer)           // Generated answer
console.log(result.confidence)       // Confidence score (0-1)
console.log(result.reasoning_trace)  // Reasoning steps
console.log(result.sources)          // Retrieved sources

// Simple RAG query (retrieval + generation only)
const result = await client.querySimple('Your question', {
    top_k: 5,
    timeout: 30000
})

// Get chat history
const history = await client.getChatHistory(sessionId)
console.log(history.messages)
```

### Chat Session Management

```javascript
// Create new session
const result = await client.createChatSession('My Chat')
const sessionId = result.session.id
client.setSessionId(sessionId)

// List all sessions
const { sessions } = await client.listChatSessions(limit, offset)

// Get session with messages
const { session, messages } = await client.getChatSession(sessionId)

// Delete session
await client.deleteChatSession(sessionId)
```

### Document Ingestion

```javascript
// Upload single file
const file = document.querySelector('input[type="file"]').files[0]
const result = await client.ingest(file, {
    sourcePrefix: 'documents',  // Optional prefix
    timeout: 120000,            // Longer timeout for uploads
    onProgress: (percent) => {
        console.log(`Upload progress: ${percent}%`)
    }
})
console.log(result.chunks_created)      // Number of chunks
console.log(result.processing_time)     // Processing time

// Upload multiple files
const files = document.querySelector('input[type="file"]').files
const result = await client.ingestBatch(files, {
    sourcePrefix: 'documents',
    duplicateAction: 'replace',  // 'skip' | 'replace' | 'append'
    timeout: 300000,
    onProgress: (percent) => {
        updateProgressBar(percent)
    }
})
console.log(result.successful)          // Number successful
console.log(result.failed)              // Number failed
console.log(result.total_chunks_created)

// Check for duplicates
const result = await client.checkDuplicates(
    ['file1.pdf', 'file2.pdf'],
    'documents'
)
// result.results: { 'file1.pdf': { exists, source, chunk_count }, ... }

// Get all documents
const { documents, total } = await client.getDocuments()

// Get document details
const { document } = await client.getDocumentDetails(docId)

// Get document chunks
const { chunks, total } = await client.getDocumentChunks(docId, limit, offset)

// Delete document by source
const result = await client.deleteDocument('documents/report.pdf')
console.log(`Deleted ${result.deleted_chunks} chunks`)

// Delete by document ID
const result = await client.deleteDocumentById(docId)
```

### System Status & Health

```javascript
// Health check
const health = await client.getStatus()
// { status: 'healthy'|'degraded'|'unhealthy', database_connected, ollama_available }

// Database statistics
const stats = await client.getDatabaseStats()
// { total_chunks, unique_sources, unique_models, latest_chunk }

// Agent status
const status = await client.getAgentStatus()
// { llm: {available, model, provider}, embeddings: {...}, configuration: {...} }

// Database status (detailed)
const status = await client.getDatabaseStatus()
// { documents: {...}, chunks: {...}, maintenance: {...} }

// Database cleanup
const result = await client.runCleanup()
// { orphaned_chunks, failed_documents }

// Database reset (⚠️ DESTRUCTIVE - deletes all data!)
const result = await client.resetDatabase()
console.log(`Deleted ${result.deleted_chunks} chunks`)
```

### Interceptors

```javascript
// Request interceptor
client.addRequestInterceptor(async (config) => {
    config.headers['X-Request-ID'] = generateRequestId()
    return config
})

// Response interceptor
client.addResponseInterceptor(async (response) => {
    console.log('Response received:', response)
    return response
})

// Error interceptor
client.addErrorInterceptor(async (error) => {
    if (error.status === 429) {
        // Rate limited - return cached response
        return getCachedResponse()
    }
    return null  // rethrow error
})
```

### Batch Operations

```javascript
// Execute multiple requests in parallel (default)
const [health, stats, documents] = await client.batch([
    { method: 'get', endpoint: '/health' },
    { method: 'get', endpoint: '/stats' },
    { method: 'get', endpoint: '/ingest/documents' }
])

// Execute in sequence
const results = await client.batch(
    [
        { method: 'post', endpoint: '/query', body: { query: 'Q1' } },
        { method: 'post', endpoint: '/query', body: { query: 'Q2' } }
    ],
    { parallel: false }
)
```

### Error Handling

```javascript
try {
    const result = await client.query('Question')
} catch (error) {
    if (error instanceof APIError) {
        console.log(error.status)        // HTTP status code
        console.log(error.message)       // Error message
        console.log(error.detail)        // Detailed info
        
        if (error.isNetworkError()) {
            console.error('Network error - check connectivity')
        } else if (error.isTimeout()) {
            console.error('Request timed out - increase timeout')
        } else if (error.isClientError()) {
            console.error('Client error - check your request')
        } else if (error.isServerError()) {
            console.error('Server error - try again later')
        }
        
        console.log(error.toJSON())  // Serialize error
    }
}
```

## API Client - Common Patterns

### Pattern 1: Simple Query

```javascript
const client = new APIClient()

try {
    const response = await client.query('Your question', {
        top_k: 5,
        timeout: 60000
    })
    
    console.log('Answer:', response.answer)
    console.log('Confidence:', response.confidence)
    console.log('Sources:', response.sources)
} catch (error) {
    console.error('Query failed:', error.message)
}
```

### Pattern 2: File Upload with Progress

```javascript
const fileInput = document.querySelector('input[type="file"]')
fileInput.addEventListener('change', async (e) => {
    const files = e.target.files
    
    try {
        const result = await client.ingestBatch(files, {
            sourcePrefix: 'user-uploads',
            duplicateAction: 'append',
            onProgress: (percent) => {
                document.querySelector('.progress-bar').style.width = 
                    percent + '%'
            }
        })
        
        console.log(`Successfully uploaded ${result.successful} files`)
    } catch (error) {
        console.error('Upload failed:', error.message)
    }
})
```

### Pattern 3: Chat Session

```javascript
// Create session
const sessionResult = await client.createChatSession('My Chat')
const sessionId = sessionResult.session.id
client.setSessionId(sessionId)

// Ask multiple questions
const q1 = await client.query('First question')
const q2 = await client.query('Follow-up question')
const q3 = await client.query('Another question')

// Get chat history
const history = await client.getChatHistory()
console.log('All messages:', history.messages)

// Delete session
await client.deleteChatSession(sessionId)
```

### Pattern 4: System Monitoring Dashboard

```javascript
async function updateDashboard() {
    const [health, stats, agentStatus] = await client.batch([
        { method: 'get', endpoint: '/health' },
        { method: 'get', endpoint: '/stats' },
        { method: 'get', endpoint: '/agent/status' }
    ])
    
    // Update UI
    document.querySelector('.health-status').textContent = health.status
    document.querySelector('.total-chunks').textContent = stats.total_chunks
    document.querySelector('.unique-sources').textContent = 
        stats.unique_sources
    document.querySelector('.llm-model').textContent = agentStatus.llm.model
    
    // Refresh every 30 seconds
    setTimeout(updateDashboard, 30000)
}

updateDashboard()
```

---

## Integration Examples

### React Integration

```jsx
import { useState, useEffect } from 'react'

function ChatComponent() {
    const [client] = useState(() => new APIClient())
    const [answer, setAnswer] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleQuery = async (question) => {
        setLoading(true)
        setError(null)
        
        try {
            const result = await client.query(question)
            setAnswer(result.answer)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <input onSubmit={(e) => handleQuery(e.target.value)} />
            {loading && <p>Loading...</p>}
            {error && <p className="error">{error}</p>}
            {answer && <p className="answer">{answer}</p>}
        </div>
    )
}
```

### Vue Integration

```vue
<template>
    <div>
        <input v-model="question" @keyup.enter="submitQuery" />
        <p v-if="loading">Loading...</p>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="answer" class="answer">{{ answer }}</p>
    </div>
</template>

<script>
export default {
    data() {
        return {
            client: new APIClient(),
            question: '',
            answer: '',
            loading: false,
            error: null
        }
    },
    methods: {
        async submitQuery() {
            this.loading = true
            this.error = null
            
            try {
                const result = await this.client.query(this.question)
                this.answer = result.answer
            } catch (err) {
                this.error = err.message
            } finally {
                this.loading = false
            }
        }
    }
}
</script>
```

---

## Full Documentation (Legacy)

The following files contain detailed documentation for both systems:

### State Manager Documentation
- **`STATE-MANAGER-DOCS.md`** - Complete API reference with all methods, hooks, and patterns
- **`STATE-MANAGER-QUICK-REF.md`** - Quick reference card for developers (quick lookup)
- **`README-STATE-MANAGER.md`** - Implementation report and feature overview

### API Client Documentation
- **`README-API-CLIENT.md`** - Complete API reference with all methods and examples
- **`QUICK-REFERENCE.md`** - Quick reference card (quick copy-paste snippets)
- **`INTEGRATION-GUIDE.md`** - Integration patterns and framework examples (React, Vue)
- **`API-CLIENT-SUMMARY.md`** - Executive summary and delivery details
- **`DELIVERY-CHECKLIST.md`** - Complete delivery checklist and verification

### Index
- **`INDEX.md`** - Complete file index with navigation and quick links

---

## Testing

### State Manager Testing

```bash
# Tests run automatically when state-manager-test.js is included
# Check browser console for test results

# Or run the test file directly:
# Include in HTML: <script src="state-manager-test.js"></script>
```

### API Client Testing

**Browser:**
1. Open `api-client-test.html` in your browser
2. Click "Run All Tests"
3. View results (28 tests, 100% pass rate)

**Node.js:**
```bash
node static/js/api-client-test.js
```

---

## Examples

### State Manager Examples

File: `state-manager-examples.js`

Contains real-world integration examples showing:
- ChatApp integration with state manager
- IngestApp integration with state manager
- Notification system usage
- State debugging utilities

### API Client Examples

File: `api-client-example.html`

Open in browser to see:
- Query demonstrations (agentic + simple)
- Chat session examples
- Document upload with progress tracking
- Batch ingestion demo
- Document management UI
- System status monitoring

---

## Troubleshooting

### State Manager Issues

**State not updating:**
- Verify you're using `setState()` or `dispatch()`
- Check listeners are subscribed with correct paths
- Use `sm.getState()` to verify current state

**localStorage not working:**
- Check browser allows localStorage
- Verify persistence is enabled
- Use `sm.persist()` and `sm.hydrate()` manually

### API Client Issues

**CORS Errors:**
- Ensure backend has CORS middleware enabled
- Check `Access-Control-Allow-Origin` headers

**Timeout Errors:**
- Increase `timeout` option in config or request
- Check network connectivity
- Verify server is running

**404 Errors:**
- Check endpoint path spelling
- Verify base URL is correct
- Check server routing configuration

---

## Performance Tips

1. **State Manager**: Listen only to paths you need with `useEffect(callback, deps)`
2. **API Client**: Use `batch()` for multiple independent requests
3. **Uploads**: Implement `onProgress` callback for large files
4. **Polling**: Use `stopStatusUpdates()` when not needed
5. **Caching**: Add response interceptor to cache responses

---

## Browser & Environment Support

- **Browsers**: All modern browsers (Chrome, Firefox, Safari, Edge)
- **JavaScript**: ES6+ required
- **Node.js**: 12.0+ (for testing)
- **Dependencies**: None (100% vanilla JavaScript)

---

## Version Information

- **State Manager**: v1.0.0
- **API Client**: v1.0.0
- **Last Updated**: Sprint 4
- **Status**: Production Ready ✅

---

## Getting Started (3 Steps)

### Step 1: Include Scripts
```html
<script src="/static/js/state-manager.js"></script>
<script src="/static/js/api-client.js"></script>
```

### Step 2: Access Global Instances
```javascript
const sm = window.StateManagerInstance;  // State Manager
const client = new APIClient();          // API Client
```

### Step 3: Start Using
```javascript
// State Manager
StateHooks.useState('chat.messages', (msgs) => console.log(msgs))

// API Client
const result = await client.query('What is RAG?')
```

---

## Need Help?

| Question | Answer Location |
|----------|-----------------|
| How do I use a specific method? | Check QUICK-REFERENCE.md or README-*.md |
| How do I integrate with React/Vue? | Check INTEGRATION-GUIDE.md |
| How do I run tests? | See Testing section above |
| What state is available? | Check State Tree Structure section |
| What endpoints are available? | Check API methods in quick reference |
| How do I handle errors? | Check Error Handling sections |

---

**All systems are production-ready and fully tested. Pick the library you need and get started!**

**Most Popular Starting Points:**
1. For quick code snippets → QUICK-REFERENCE.md
2. For interactive demos → api-client-example.html
3. For full details → README-*.md files
4. For validation → api-client-test.html or state-manager-test.js
