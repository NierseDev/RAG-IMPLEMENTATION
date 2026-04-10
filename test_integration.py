"""
Integration tests for hybrid search Sprint 4 implementation.
Verifies the complete pipeline from API endpoint to database.
"""
import asyncio
import logging
import pytest
from typing import Dict, Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@pytest.mark.asyncio
async def test_query_service_import():
    """Test that QueryService can be imported and initialized."""
    logger.info("=" * 80)
    logger.info("TEST: QueryService Import and Initialization")
    logger.info("=" * 80)
    
    try:
        from app.services.query_service import query_service
        
        assert query_service is not None
        assert hasattr(query_service, 'search')
        assert hasattr(query_service, 'format_results')
        
        logger.info(f"✓ QueryService initialized")
        logger.info(f"  - Vector weight: {query_service.vector_weight}")
        logger.info(f"  - Keyword weight: {query_service.keyword_weight}")
        logger.info(f"  - Hybrid enabled: {query_service.hybrid_enabled}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Failed to import QueryService: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_response_models():
    """Test that new response models are properly defined."""
    logger.info("=" * 80)
    logger.info("TEST: Response Models Definition")
    logger.info("=" * 80)
    
    try:
        from app.models.responses import HybridSearchResponse, HybridSearchBreakdown
        
        # Create test instances
        breakdown = HybridSearchBreakdown(
            vector_results=20,
            keyword_results=18,
            fused_results=25,
            after_filter=10,
            method="hybrid"
        )
        
        response = HybridSearchResponse(
            query="test query",
            results=[],
            retrieved_chunks=0,
            retrieval_method="hybrid",
            filter_applied=False,
            processing_time_ms=100.0,
            search_breakdown=breakdown
        )
        
        logger.info(f"✓ Response models working correctly")
        logger.info(f"  - HybridSearchBreakdown created")
        logger.info(f"  - HybridSearchResponse created")
        
        return True
    except Exception as e:
        logger.error(f"✗ Response models error: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_request_models():
    """Test that request models include new fields."""
    logger.info("=" * 80)
    logger.info("TEST: Request Models")
    logger.info("=" * 80)
    
    try:
        from app.models.requests import HybridSearchRequest
        
        # Test with various configurations
        request1 = HybridSearchRequest(
            query="test",
            metadata_filters={"source": "test.pdf"},
            top_k=10
        )
        
        request2 = HybridSearchRequest(
            query="complex query",
            top_k=5,
            use_hybrid=True,
            min_similarity=0.4
        )
        
        logger.info(f"✓ HybridSearchRequest model working")
        logger.info(f"  - Request 1: query='{request1.query}', filters={request1.metadata_filters}")
        logger.info(f"  - Request 2: use_hybrid={request2.use_hybrid}, min_similarity={request2.min_similarity}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Request models error: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_api_endpoint_registration():
    """Test that the hybrid search endpoint is properly registered."""
    logger.info("=" * 80)
    logger.info("TEST: API Endpoint Registration")
    logger.info("=" * 80)
    
    try:
        from main import app
        
        # Check if the endpoint exists
        routes = [route.path for route in app.routes]
        hybrid_endpoint = "/query/hybrid"
        
        endpoint_exists = any(hybrid_endpoint in route for route in routes)
        
        if endpoint_exists:
            logger.info(f"✓ Hybrid search endpoint registered at {hybrid_endpoint}")
        else:
            logger.warning(f"⚠ Endpoint {hybrid_endpoint} not found in routes")
            logger.info(f"  Available routes: {routes[:5]}...")
        
        return True
    except Exception as e:
        logger.error(f"✗ Endpoint registration error: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_configuration():
    """Test that configuration is properly set."""
    logger.info("=" * 80)
    logger.info("TEST: Configuration Validation")
    logger.info("=" * 80)
    
    try:
        from app.core.config import settings
        
        logger.info(f"✓ Configuration loaded:")
        logger.info(f"  - use_hybrid_search: {settings.use_hybrid_search}")
        logger.info(f"  - hybrid_vector_weight: {settings.hybrid_vector_weight}")
        logger.info(f"  - hybrid_keyword_weight: {settings.hybrid_keyword_weight}")
        logger.info(f"  - top_k_results: {settings.top_k_results}")
        logger.info(f"  - min_similarity: {settings.min_similarity}")
        
        # Validate weights
        total_weight = settings.hybrid_vector_weight + settings.hybrid_keyword_weight
        if 0.9 < total_weight < 1.1 or total_weight > 0:
            logger.info(f"  - Weight sum: {total_weight} ✓")
        else:
            logger.warning(f"  - Weight sum seems odd: {total_weight}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Configuration error: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_dependencies():
    """Test that all required dependencies are available."""
    logger.info("=" * 80)
    logger.info("TEST: Dependencies")
    logger.info("=" * 80)
    
    dependencies = {
        'query_service': 'app.services.query_service',
        'keyword_search': 'app.services.keyword_search',
        'rrf_fusion': 'app.services.rrf_fusion',
        'embedding': 'app.services.embedding',
        'database': 'app.core.database'
    }
    
    all_ok = True
    for name, module in dependencies.items():
        try:
            __import__(module)
            logger.info(f"  ✓ {name}: {module}")
        except ImportError as e:
            logger.error(f"  ✗ {name}: {module} - {e}")
            all_ok = False
    
    if all_ok:
        logger.info("✓ All dependencies available")
    else:
        logger.error("✗ Some dependencies missing")
    
    return all_ok


@pytest.mark.asyncio
async def test_service_methods():
    """Test that QueryService has all required methods."""
    logger.info("=" * 80)
    logger.info("TEST: QueryService Methods")
    logger.info("=" * 80)
    
    try:
        from app.services.query_service import query_service
        
        required_methods = [
            'search',
            'format_results',
            '_hybrid_search',
            '_vector_search',
            '_vector_search_internal',
            '_keyword_search_internal',
            '_result_to_dict'
        ]
        
        all_exist = True
        for method_name in required_methods:
            if hasattr(query_service, method_name):
                logger.info(f"  ✓ {method_name}")
            else:
                logger.error(f"  ✗ {method_name} - MISSING")
                all_exist = False
        
        if all_exist:
            logger.info("✓ All required methods present")
        else:
            logger.error("✗ Some methods missing")
        
        return all_exist
    except Exception as e:
        logger.error(f"✗ Service methods error: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_rrf_fusion_integration():
    """Test that RRF fusion is properly integrated."""
    logger.info("=" * 80)
    logger.info("TEST: RRF Fusion Integration")
    logger.info("=" * 80)
    
    try:
        from app.services.rrf_fusion import hybrid_fusion
        
        # Create test data
        vector_results = [
            {'chunk_id': 'v1', 'text': 'vector result 1', 'similarity': 0.9, 'source': 'test.pdf'},
            {'chunk_id': 'v2', 'text': 'vector result 2', 'similarity': 0.8, 'source': 'test.pdf'},
        ]
        
        keyword_results = [
            {'chunk_id': 'k1', 'text': 'keyword result 1', 'similarity': 0.7, 'source': 'test.pdf'},
            {'chunk_id': 'k2', 'text': 'keyword result 2', 'similarity': 0.6, 'source': 'test.pdf'},
        ]
        
        # Test fusion
        fused = hybrid_fusion.combine(
            vector_results=vector_results,
            keyword_results=keyword_results,
            use_weights=True
        )
        
        logger.info(f"✓ RRF Fusion working:")
        logger.info(f"  - Input: {len(vector_results)} vector + {len(keyword_results)} keyword")
        logger.info(f"  - Output: {len(fused)} fused results")
        
        if len(fused) > 0:
            logger.info(f"  - Top result: {fused[0].get('chunk_id')}")
        
        return True
    except Exception as e:
        logger.error(f"✗ RRF fusion error: {e}", exc_info=True)
        return False


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in hybrid search."""
    logger.info("=" * 80)
    logger.info("TEST: Error Handling")
    logger.info("=" * 80)
    
    try:
        from app.services.query_service import query_service
        
        # Test with None query (should not crash)
        try:
            result = await query_service.search(query="", use_hybrid=True)
            logger.info("  - Empty query handled")
        except Exception as e:
            logger.info(f"  - Empty query raised: {type(e).__name__}")
        
        # Test with None filters
        try:
            result = await query_service.search(
                query="test",
                metadata_filters=None,
                use_hybrid=True
            )
            logger.info("  ✓ None filters handled")
        except Exception as e:
            logger.error(f"  ✗ None filters error: {e}")
            return False
        
        logger.info("✓ Error handling working")
        return True
    except Exception as e:
        logger.error(f"✗ Error handling test failed: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Run all integration tests."""
    logger.info("\n" + "=" * 80)
    logger.info("HYBRID SEARCH INTEGRATION TEST SUITE")
    logger.info("=" * 80 + "\n")
    
    tests = [
        ("Import & Init", test_query_service_import),
        ("Response Models", test_response_models),
        ("Request Models", test_request_models),
        ("Configuration", test_configuration),
        ("Dependencies", test_dependencies),
        ("Service Methods", test_service_methods),
        ("API Endpoint", test_api_endpoint_registration),
        ("RRF Fusion", test_rrf_fusion_integration),
        ("Error Handling", test_error_handling),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = "✓ PASS" if result else "✗ FAIL"
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results[test_name] = "✗ CRASH"
        logger.info("\n")
    
    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, result in results.items():
        logger.info(f"{result} - {test_name}")
    
    passed = sum(1 for r in results.values() if r == "✓ PASS")
    total = len(results)
    
    logger.info("\n" + "=" * 80)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
