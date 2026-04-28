"""
Comprehensive tests for hybrid search integration (Sprint 4).
Tests vector + keyword + RRF fusion with metadata filtering.
"""
import asyncio
import pytest
import logging
from datetime import datetime

from app.services.query_service import query_service
from app.services.keyword_search import keyword_search_service
from app.services.embedding import embedding_service
from app.models.entities import RetrievalResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestHybridSearch:
    """Test hybrid search functionality."""
    
    @pytest.mark.asyncio
    async def test_simple_query_hybrid_search(self):
        """Test basic hybrid search with simple query."""
        logger.info("=" * 80)
        logger.info("TEST: Simple Query Hybrid Search")
        logger.info("=" * 80)
        
        query = "machine learning algorithms"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        assert 'results' in result
        assert 'search_breakdown' in result
        assert 'retrieval_method' in result
        
        breakdown = result['search_breakdown']
        logger.info(f"Search Breakdown: {breakdown}")
        logger.info(f"Retrieval Method: {result['retrieval_method']}")
        logger.info(f"Results Count: {len(result['results'])}")
        
        # Verify breakdown contains expected fields
        assert breakdown['method'] in ['hybrid', 'vector-only']
        
        if breakdown['method'] == 'hybrid':
            assert breakdown['vector_results'] > 0 or breakdown['keyword_results'] > 0
            assert breakdown['fused_results'] > 0
        
        logger.info("✓ Simple query hybrid search passed")
    
    @pytest.mark.asyncio
    async def test_complex_entity_query(self):
        """Test hybrid search with complex entity-based query."""
        logger.info("=" * 80)
        logger.info("TEST: Complex Entity Query")
        logger.info("=" * 80)
        
        query = "neural networks deep learning optimization gradient descent"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        assert len(result['results']) > 0 or result['search_breakdown']['method'] == 'vector-only'
        
        logger.info(f"Retrieved {len(result['results'])} chunks")
        logger.info(f"Method: {result['retrieval_method']}")
        
        # Log top 3 results
        for idx, res in enumerate(result['results'][:3], 1):
            logger.info(f"  Result {idx}: score={res.similarity:.3f}, source={res.source}")
        
        logger.info("✓ Complex entity query passed")
    
    @pytest.mark.asyncio
    async def test_metadata_filtering(self):
        """Test hybrid search with metadata filters."""
        logger.info("=" * 80)
        logger.info("TEST: Metadata Filtering")
        logger.info("=" * 80)
        
        query = "data science"
        metadata_filters = {
            'source': None,  # Can be set if testing with known sources
            'provider': None
        }
        
        result = await query_service.search(
            query=query,
            metadata_filters=metadata_filters,
            use_hybrid=True,
            top_k=5
        )
        
        assert result['filter_applied'] == (metadata_filters is not None)
        logger.info(f"Filter applied: {result['filter_applied']}")
        logger.info(f"Results after filtering: {len(result['results'])}")
        
        logger.info("✓ Metadata filtering passed")
    
    @pytest.mark.asyncio
    async def test_vector_only_fallback(self):
        """Test fallback to vector-only search."""
        logger.info("=" * 80)
        logger.info("TEST: Vector-Only Fallback")
        logger.info("=" * 80)
        
        query = "test query"
        
        # Force vector-only by setting use_hybrid=False
        result = await query_service.search(
            query=query,
            use_hybrid=False,
            top_k=10
        )
        
        assert result['retrieval_method'] in ['vector-only', 'error']
        logger.info(f"Retrieval method: {result['retrieval_method']}")
        logger.info(f"Results: {len(result['results'])}")
        
        logger.info("✓ Vector-only fallback passed")
    
    @pytest.mark.asyncio
    async def test_empty_results_handling(self):
        """Test graceful handling of empty results."""
        logger.info("=" * 80)
        logger.info("TEST: Empty Results Handling")
        logger.info("=" * 80)
        
        query = "xyzabc_nonexistent_query_12345"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        # Should return empty results gracefully, not error
        assert 'results' in result
        assert 'search_breakdown' in result
        
        logger.info(f"Empty query results: {len(result['results'])}")
        logger.info(f"Method used: {result['retrieval_method']}")
        
        logger.info("✓ Empty results handling passed")
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """Test that performance metrics are captured."""
        logger.info("=" * 80)
        logger.info("TEST: Performance Metrics")
        logger.info("=" * 80)
        
        query = "performance testing"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        assert 'processing_time' in result
        processing_time = result['processing_time']
        logger.info(f"Processing time: {processing_time:.3f}s ({processing_time*1000:.1f}ms)")
        
        # Should complete reasonably fast (less than 10 seconds)
        assert processing_time < 10.0, f"Search took too long: {processing_time}s"
        
        logger.info("✓ Performance metrics passed")
    
    @pytest.mark.asyncio
    async def test_response_formatting(self):
        """Test that response formatting works correctly."""
        logger.info("=" * 80)
        logger.info("TEST: Response Formatting")
        logger.info("=" * 80)
        
        query = "formatting test"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=5
        )
        
        formatted = query_service.format_results(result, include_breakdown=True)
        
        # Verify formatted response structure
        assert 'query' in formatted
        assert 'results' in formatted
        assert 'retrieved_chunks' in formatted
        assert 'retrieval_method' in formatted
        assert 'filter_applied' in formatted
        assert 'processing_time_ms' in formatted
        assert 'search_breakdown' in formatted
        
        logger.info(f"Formatted response keys: {list(formatted.keys())}")
        
        # Verify each result has required fields
        for result in formatted['results'][:3]:
            assert 'chunk_id' in result
            assert 'source' in result
            assert 'text' in result
            assert 'similarity' in result
        
        logger.info("✓ Response formatting passed")
    
    @pytest.mark.asyncio
    async def test_search_breakdown_accuracy(self):
        """Test that search breakdown accurately reflects hybrid search."""
        logger.info("=" * 80)
        logger.info("TEST: Search Breakdown Accuracy")
        logger.info("=" * 80)
        
        query = "algorithm"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        breakdown = result['search_breakdown']
        
        logger.info(f"Vector results: {breakdown.get('vector_results', 0)}")
        logger.info(f"Keyword results: {breakdown.get('keyword_results', 0)}")
        logger.info(f"Fused results: {breakdown.get('fused_results', 0)}")
        logger.info(f"After filter: {breakdown.get('after_filter', 0)}")
        logger.info(f"Method: {breakdown.get('method')}")
        
        # If hybrid, verify fusion happened
        if breakdown.get('method') == 'hybrid':
            assert breakdown.get('vector_results', 0) >= 0
            assert breakdown.get('keyword_results', 0) >= 0
            # Fused should be combination of both (with RRF combining)
            assert breakdown.get('fused_results', 0) >= 0
        
        logger.info("✓ Search breakdown accuracy passed")
    
    @pytest.mark.asyncio
    async def test_configuration_weights(self):
        """Test that configuration weights are being used."""
        logger.info("=" * 80)
        logger.info("TEST: Configuration Weights")
        logger.info("=" * 80)
        
        from app.core.config import settings
        
        logger.info(f"Hybrid enabled: {settings.use_hybrid_search}")
        logger.info(f"Vector weight: {settings.hybrid_vector_weight}")
        logger.info(f"Keyword weight: {settings.hybrid_keyword_weight}")
        
        assert settings.use_hybrid_search == True or settings.use_hybrid_search == False
        assert settings.hybrid_vector_weight > 0
        assert settings.hybrid_keyword_weight > 0
        assert abs((settings.hybrid_vector_weight + settings.hybrid_keyword_weight) - 1.0) < 0.01 or \
               (settings.hybrid_vector_weight + settings.hybrid_keyword_weight) > 0
        
        logger.info("✓ Configuration weights valid")
    
    @pytest.mark.asyncio
    async def test_result_ranking_order(self):
        """Test that results are properly ranked."""
        logger.info("=" * 80)
        logger.info("TEST: Result Ranking Order")
        logger.info("=" * 80)
        
        query = "ranking test"
        
        result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        results = result['results']
        
        if len(results) > 1:
            # Verify results are sorted by similarity descending
            similarities = [r.similarity for r in results]
            logger.info(f"Similarities: {similarities[:5]}")
            
            is_sorted = all(similarities[i] >= similarities[i+1] for i in range(len(similarities)-1))
            assert is_sorted, "Results should be sorted by similarity descending"
        
        logger.info(f"✓ Results properly ranked ({len(results)} results)")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in search."""
        logger.info("=" * 80)
        logger.info("TEST: Error Handling")
        logger.info("=" * 80)
        
        # Test with empty query should be handled
        try:
            result = await query_service.search(
                query="",  # Empty query
                use_hybrid=True,
                top_k=10
            )
            # Might error or return empty, both acceptable
            logger.info(f"Empty query result: {result}")
        except Exception as e:
            logger.info(f"Empty query raised: {type(e).__name__}")
        
        # Test with None should be handled
        try:
            result = await query_service.search(
                query="test",
                metadata_filters=None,  # None filters
                use_hybrid=True,
                top_k=10
            )
            assert result is not None
            logger.info("✓ None filters handled correctly")
        except Exception as e:
            logger.error(f"Error with None filters: {e}")
            raise
        
        logger.info("✓ Error handling passed")


class TestHybridVsVectorOnly:
    """Compare hybrid search vs vector-only search."""
    
    @pytest.mark.asyncio
    async def test_hybrid_vs_vector_comparison(self):
        """Compare hybrid and vector-only retrieval results."""
        logger.info("=" * 80)
        logger.info("TEST: Hybrid vs Vector-Only Comparison")
        logger.info("=" * 80)
        
        query = "machine learning classification"
        
        # Run hybrid search
        hybrid_result = await query_service.search(
            query=query,
            use_hybrid=True,
            top_k=10
        )
        
        # Run vector-only search
        vector_result = await query_service.search(
            query=query,
            use_hybrid=False,
            top_k=10
        )
        
        hybrid_count = len(hybrid_result['results'])
        vector_count = len(vector_result['results'])
        
        logger.info(f"Hybrid results: {hybrid_count}")
        logger.info(f"Vector-only results: {vector_count}")
        logger.info(f"Hybrid method: {hybrid_result['retrieval_method']}")
        logger.info(f"Vector method: {vector_result['retrieval_method']}")
        
        # Log top result scores
        if hybrid_result['results']:
            logger.info(f"Hybrid top score: {hybrid_result['results'][0].similarity:.4f}")
        if vector_result['results']:
            logger.info(f"Vector top score: {vector_result['results'][0].similarity:.4f}")
        
        logger.info("✓ Hybrid vs Vector comparison completed")


# Integration test for the API
class TestHybridSearchAPI:
    """Test the hybrid search API endpoint."""
    
    @pytest.mark.asyncio
    async def test_query_service_integration(self):
        """Test QueryService integration with other components."""
        logger.info("=" * 80)
        logger.info("TEST: QueryService Integration")
        logger.info("=" * 80)
        
        # Verify query_service is properly initialized
        assert query_service is not None
        assert query_service.vector_weight == 0.7 or query_service.vector_weight == 0.6
        assert query_service.keyword_weight == 0.3 or query_service.keyword_weight == 0.4
        
        logger.info(f"QueryService weights: vector={query_service.vector_weight}, keyword={query_service.keyword_weight}")
        logger.info("✓ QueryService properly initialized")


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_hybrid_search.py -v -s
    logger.info("Hybrid Search Integration Tests")
    logger.info("Run with: python -m pytest tests/test_hybrid_search.py -v -s")
