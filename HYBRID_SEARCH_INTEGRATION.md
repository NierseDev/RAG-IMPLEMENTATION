"""
Hybrid Search Integration Documentation (Sprint 4)
====================================================

## Overview
Complete hybrid search integration combining vector and keyword search with RRF fusion,
metadata filtering, and performance metrics logging.

## Architecture

### Components

1. **QueryService** (app/services/query_service.py)
   - Main orchestrator for hybrid search
   - Executes vector and keyword search in parallel
   - Applies RRF fusion for result combination
   - Handles metadata filtering and fallback logic
   - Tracks performance metrics

2. **Vector Search** (existing)
   - Semantic similarity search using embeddings
   - Top 20 results by default
   - Metadata filtering support

3. **Keyword Search** (app/services/keyword_search.py - Sprint 3)
   - PostgreSQL full-text search (FTS)
   - Top 20 results by default
   - Fallback to ILIKE if FTS fails

4. **RRF Fusion** (app/services/rrf_fusion.py - Sprint 3)
   - Reciprocal Rank Fusion algorithm
   - Configurable weights (default: 0.6 vector, 0.4 keyword)
   - Combines results intelligently

5. **API Endpoint** (app/api/query.py)
   - POST /query/hybrid: New hybrid search endpoint
   - Accepts search parameters and metadata filters
   - Returns detailed search breakdown

## Configuration

Environment variables (app/core/config.py):

```
HYBRID_SEARCH_ENABLED = true  (use_hybrid_search)
VECTOR_SEARCH_WEIGHT = 0.6    (hybrid_vector_weight)
KEYWORD_SEARCH_WEIGHT = 0.4   (hybrid_keyword_weight)
```

Defaults can be adjusted in .env file.

## Workflow

### Hybrid Search Pipeline

```
User Query
    ↓
[Parallel Execution]
├── Vector Search (top 20)      → Embedding lookup
└── Keyword Search (top 20)     → FTS in PostgreSQL
    ↓
RRF Fusion
    ↓
Apply Metadata Filters (if provided)
    ↓
Final Reranking & Top-K Selection (top 10)
    ↓
Response with Search Breakdown
```

### Search Breakdown Fields

```python
{
    'vector_results': 20,          # Results from vector search
    'keyword_results': 18,         # Results from keyword search
    'vector_score': 0.65,          # Average vector score
    'keyword_score': 0.52,         # Average keyword score
    'fused_results': 25,           # Results after fusion
    'after_filter': 10,            # Results after filtering
    'method': 'hybrid'             # Search method used
}
```

### Retrieval Methods

- **hybrid**: Successfully used both vector and keyword search
- **vector-only**: Keyword search failed, fell back to vector
- **error**: Search failed completely

## API Usage

### Hybrid Search Endpoint

**POST /query/hybrid**

Request:
```json
{
    "query": "machine learning algorithms",
    "metadata_filters": {
        "source": "research_papers.pdf",
        "provider": "ollama",
        "doc_type": "academic"
    },
    "top_k": 10,
    "use_hybrid": true,
    "min_similarity": 0.3
}
```

Response:
```json
{
    "query": "machine learning algorithms",
    "results": [
        {
            "chunk_id": "chunk_001",
            "source": "research_papers.pdf",
            "text": "Neural networks are...",
            "similarity": 0.892,
            "provider": "ollama",
            "model": "mxbai-embed-large"
        }
    ],
    "retrieved_chunks": 10,
    "retrieval_method": "hybrid",
    "filter_applied": true,
    "processing_time_ms": 245.3,
    "search_breakdown": {
        "vector_results": 20,
        "keyword_results": 18,
        "fused_results": 25,
        "after_filter": 10,
        "method": "hybrid"
    }
}
```

## Performance Metrics

### Logging

Each search logs:
- Processing time (total)
- Retrieval method used
- Results count
- Whether filters were applied

Example log output:
```
Query processed in 0.24s | Method: hybrid | Results: 10/10 | Filters: True
Hybrid search complete: 20 vector + 18 keyword -> 25 fused
```

### Bottlenecks & Optimization

1. **Parallel Execution**: Vector and keyword search run concurrently
2. **Early Fallback**: If keyword search fails, vector-only used immediately
3. **Smart Filtering**: Metadata filters applied before final ranking
4. **RRF Efficiency**: O(n) fusion algorithm with configurable weights

## Error Handling

### Scenarios

1. **Keyword Search Fails**
   - Automatically falls back to vector-only
   - Logs warning with error details
   - Returns results with fallback method noted

2. **Empty Results**
   - Returns empty result list gracefully
   - No exceptions raised
   - Search breakdown still provided

3. **Invalid Metadata Filters**
   - Ignored if not found in data
   - Query still executes with remaining filters
   - Logs debug message

4. **Database Connection Error**
   - Error logged and returned in response
   - HTTP 500 status code

## Testing

### Test Suite (test_hybrid_search.py)

Comprehensive tests covering:

1. **Basic Functionality**
   - Simple query hybrid search
   - Complex entity-based queries
   - Metadata filtering

2. **Fallback & Edge Cases**
   - Vector-only fallback
   - Empty results handling
   - Error handling

3. **Performance**
   - Performance metrics tracking
   - Processing time validation
   - Result ranking verification

4. **Comparison**
   - Hybrid vs vector-only comparison
   - Search quality metrics

Run tests:
```bash
pytest test_hybrid_search.py -v -s
```

### Test Queries

1. **Simple Query**: "machine learning algorithms"
2. **Complex Entity Query**: "neural networks deep learning optimization gradient descent"
3. **Empty Query**: "xyzabc_nonexistent_query_12345"
4. **Filtered Query**: Query with metadata_filters applied

## Integration Points

### With Agentic RAG

1. **Agent Query Loop**: QueryService.search() can be used instead of retrieval_service.retrieve()
2. **Verification**: Retrieved chunks passed to verification service
3. **Context Formatting**: Results formatted for LLM context

### With Document Processing

1. **Source Filtering**: Metadata filters can include source (uploaded document)
2. **Provider/Model Filtering**: Can filter by embedding provider/model

## Configuration Best Practices

### Vector Weight Tuning

- **0.7 vector, 0.3 keyword**: Better for semantic queries
- **0.6 vector, 0.4 keyword**: Balanced approach
- **0.5 vector, 0.5 keyword**: Equal priority to both

### Filter Strategy

- **Strict Filtering**: Use AND logic to combine multiple filters
- **Loose Filtering**: Use OR logic for broader results
- **No Filtering**: Set metadata_filters=None for full search

### Top-K Selection

- **10**: Good for UI display
- **20**: For agentic reasoning
- **50+**: For large context windows

## Future Enhancements

1. **Query Expansion**: Auto-expand queries for better keyword search
2. **Dynamic Weighting**: Adjust weights based on query characteristics
3. **Result Reranking**: Cross-encoder reranking as final step
4. **Caching**: Cache vector embeddings and FTS results
5. **Analytics**: Track search quality metrics over time
6. **A/B Testing**: Compare hybrid vs vector-only effectiveness

## Troubleshooting

### Issue: All results from vector search, none from keyword
**Cause**: FTS index not properly created or query syntax issue
**Solution**: Check PostgreSQL setup, verify text_tsv column exists

### Issue: High latency in hybrid search
**Cause**: Slow keyword search query
**Solution**: Check PostgreSQL FTS index, reduce top_k for keyword search

### Issue: Unexpected fallback to vector-only
**Cause**: Keyword search service exception
**Solution**: Check logs for exception details, verify database connection

### Issue: Empty results with valid query
**Cause**: No matching data or aggressive min_similarity threshold
**Solution**: Lower min_similarity or check data exists in database

## Code Examples

### Using QueryService directly

```python
from app.services.query_service import query_service

# Simple hybrid search
result = await query_service.search(
    query="machine learning",
    use_hybrid=True,
    top_k=10
)

# With metadata filters
result = await query_service.search(
    query="deep learning",
    metadata_filters={'source': 'papers.pdf'},
    top_k=10,
    min_similarity=0.4
)

# Format for API response
formatted = query_service.format_results(result, include_breakdown=True)
```

### Using API endpoint

```python
import requests

# Hybrid search via HTTP
response = requests.post(
    "http://localhost:8000/query/hybrid",
    json={
        "query": "neural networks",
        "top_k": 10,
        "use_hybrid": True
    }
)

results = response.json()
print(f"Found {results['retrieved_chunks']} chunks")
print(f"Method: {results['retrieval_method']}")
print(f"Processing time: {results['processing_time_ms']}ms")
```

## Monitoring & Metrics

### Key Metrics to Track

1. **Retrieval Quality**
   - Hybrid vs vector-only result quality
   - User satisfaction with results
   - False positive/negative rates

2. **Performance**
   - Average query time by method
   - P50/P95/P99 latencies
   - Cache hit rates

3. **Search Patterns**
   - Most common queries
   - Filter usage patterns
   - Top-k distribution

## References

1. RRF Paper: https://www.semanticscholar.org/paper/Reciprocal-Rank-Fusion-outperforms-Condorcet-and-Cormack-Buettcher-Clarke/b15c1e73f6c5d4a3d5f9e5b5f5c5e5f5
2. BM25 Algorithm: https://en.wikipedia.org/wiki/Okapi_BM25
3. Vector Search: https://en.wikipedia.org/wiki/Vector_search_engine
"""

# Implementation Summary
# ====================
# 
# ✅ Hybrid Search Pipeline
#    - Vector search (top 20)
#    - Keyword search (top 20)
#    - RRF fusion with weights
#    - Final top-k reranking (10)
#
# ✅ Metadata Filtering
#    - Applied after fusion
#    - Supports source, provider, model
#    - Extensible for custom filters
#
# ✅ Error Handling
#    - Automatic fallback to vector-only
#    - Graceful empty result handling
#    - Detailed error logging
#
# ✅ Performance Metrics
#    - Processing time tracking
#    - Search breakdown logging
#    - Method selection tracking
#
# ✅ API Integration
#    - New /query/hybrid endpoint
#    - Updated response schema
#    - Backward compatible
#
# ✅ Testing
#    - 11 test cases covering all scenarios
#    - Comparison tests (hybrid vs vector)
#    - Integration tests
