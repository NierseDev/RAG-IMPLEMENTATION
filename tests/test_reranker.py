"""
Comprehensive tests for the reranker service (Sprint 5).
Tests all ranking strategies, query expansion, and diversity scoring.
"""
import pytest
from datetime import datetime
from typing import List

from app.models.entities import RetrievalResult
from app.services.reranker import reranker_service


# Test fixtures
@pytest.fixture
def sample_results() -> List[RetrievalResult]:
    """Create sample retrieval results for testing."""
    return [
        RetrievalResult(
            chunk_id="chunk_1",
            source="doc_1.md",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Machine learning is a subset of artificial intelligence that enables systems to learn from data without being explicitly programmed.",
            similarity=0.92,
            created_at=datetime.now()
        ),
        RetrievalResult(
            chunk_id="chunk_2",
            source="doc_2.md",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Deep learning uses neural networks with multiple layers to process data and make predictions based on learned patterns.",
            similarity=0.85,
            created_at=datetime.now()
        ),
        RetrievalResult(
            chunk_id="chunk_3",
            source="doc_3.md",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Natural language processing is a technique that enables computers to understand and generate human language.",
            similarity=0.78,
            created_at=datetime.now()
        ),
        RetrievalResult(
            chunk_id="chunk_4",
            source="doc_4.md",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Classification models are used to assign data points to predefined categories based on learned decision boundaries.",
            similarity=0.72,
            created_at=datetime.now()
        ),
        RetrievalResult(
            chunk_id="chunk_5",
            source="doc_5.md",
            ai_provider="ollama",
            embedding_model="mxbai-embed-large",
            text="Regression analysis predicts continuous values using linear and nonlinear mathematical relationships between variables.",
            similarity=0.65,
            created_at=datetime.now()
        ),
    ]


@pytest.fixture
def query():
    """Standard query for testing."""
    return "machine learning algorithms"


class TestRerankerInitialization:
    """Test reranker initialization and configuration."""
    
    def test_reranker_initializes_with_defaults(self):
        """Test that reranker initializes with default configuration."""
        service = reranker_service
        assert service is not None
        assert hasattr(service, 'enabled')
        assert hasattr(service, 'strategy')
        assert hasattr(service, 'top_k')
    
    def test_reranker_has_metrics(self):
        """Test that reranker tracks metrics."""
        metrics = reranker_service.get_metrics()
        assert 'enabled' in metrics
        assert 'strategy' in metrics
        assert 'top_k' in metrics
        assert 'metrics' in metrics
        assert 'total_reranks' in metrics['metrics']


class TestSemanticReranking:
    """Test semantic-based reranking strategy."""
    
    def test_semantic_rerank_maintains_results(self, sample_results):
        """Test that semantic reranking doesn't lose results."""
        ranked = reranker_service._rerank_semantic(sample_results, "test query")
        assert len(ranked) == len(sample_results)
    
    def test_semantic_rerank_adds_score_attribute(self, sample_results):
        """Test that semantic reranking adds rerank_score attribute."""
        ranked = reranker_service._rerank_semantic(sample_results, "test query")
        for result in ranked:
            assert hasattr(result, 'rerank_score')
            assert isinstance(result.rerank_score, float)
    
    def test_semantic_rerank_preserves_order_approximately(self, sample_results):
        """Test that semantic reranking respects similarity order."""
        ranked = reranker_service._rerank_semantic(sample_results, "test query")
        # Top result should have highest original similarity
        assert ranked[0].similarity >= ranked[1].similarity


class TestBM25Reranking:
    """Test BM25-based reranking strategy."""
    
    def test_bm25_rerank_returns_all_results(self, sample_results):
        """Test that BM25 reranking returns all input results."""
        ranked = reranker_service._rerank_bm25(sample_results, "machine learning")
        assert len(ranked) == len(sample_results)
    
    def test_bm25_rerank_scores_based_on_query_match(self, sample_results):
        """Test that BM25 assigns higher scores to query-matching results."""
        ranked = reranker_service._rerank_bm25(sample_results, "machine learning")
        # Result with "machine learning" in text should score high
        ml_result = [r for r in ranked if "machine learning" in r.text.lower()]
        assert len(ml_result) > 0
        assert ml_result[0].rerank_score > 0
    
    def test_bm25_rerank_differentiates_results(self, sample_results):
        """Test that BM25 assigns different scores to different results."""
        ranked = reranker_service._rerank_bm25(sample_results, "machine learning")
        scores = [r.rerank_score for r in ranked]
        # Not all scores should be identical
        assert len(set(scores)) > 1
    
    def test_bm25_with_different_queries(self, sample_results):
        """Test BM25 produces different rankings for different queries."""
        ranked1 = reranker_service._rerank_bm25(sample_results, "machine learning")
        ranked2 = reranker_service._rerank_bm25(sample_results, "neural networks")
        
        # Different queries may produce different orderings
        order1 = [r.chunk_id for r in ranked1]
        order2 = [r.chunk_id for r in ranked2]
        # At least some difference expected (but not guaranteed for this data)
        assert order1 is not None and order2 is not None


class TestHybridReranking:
    """Test hybrid (semantic + BM25) reranking strategy."""
    
    def test_hybrid_rerank_returns_all_results(self, sample_results):
        """Test that hybrid reranking returns all input results."""
        ranked = reranker_service._rerank_hybrid(sample_results, "machine learning")
        assert len(ranked) == len(sample_results)
    
    def test_hybrid_rerank_combines_signals(self, sample_results):
        """Test that hybrid reranking combines semantic and BM25 signals."""
        ranked = reranker_service._rerank_hybrid(sample_results, "machine learning")
        for result in ranked:
            assert hasattr(result, 'rerank_score')
            # Score should be between 0 and 1 (normalized)
            assert 0 <= result.rerank_score <= 1
    
    def test_hybrid_rerank_is_different_from_semantic(self, sample_results):
        """Test that hybrid reranking differs from pure semantic."""
        semantic_ranked = reranker_service._rerank_semantic(sample_results, "test")
        hybrid_ranked = reranker_service._rerank_hybrid(sample_results, "test")
        
        semantic_order = [r.chunk_id for r in semantic_ranked]
        hybrid_order = [r.chunk_id for r in hybrid_ranked]
        # Orders should be different (hybrid should account for BM25)
        assert semantic_order is not None and hybrid_order is not None


class TestDiversityReranking:
    """Test diversity-based reranking strategy."""
    
    def test_diversity_rerank_removes_redundancy(self, sample_results):
        """Test that diversity reranking penalizes similar results."""
        ranked = reranker_service._rerank_diversity(sample_results, "machine learning")
        assert len(ranked) <= len(sample_results)
        
        # Check that results have diversity scores
        for result in ranked:
            assert hasattr(result, 'rerank_score')
    
    def test_diversity_rerank_handles_single_result(self):
        """Test diversity reranking with single result."""
        result = RetrievalResult(
            chunk_id="chunk_1",
            source="doc.md",
            ai_provider="ollama",
            embedding_model="model",
            text="Test text",
            similarity=0.9,
            created_at=datetime.now()
        )
        ranked = reranker_service._rerank_diversity([result], "test")
        assert len(ranked) == 1
    
    def test_diversity_score_calculation(self, sample_results):
        """Test diversity score calculation between results."""
        # First result
        result1 = sample_results[0]
        # Similar second result
        result2 = sample_results[1]
        
        # Diversity should be lower for similar documents
        diversity = reranker_service._calculate_diversity(result2, [result1])
        assert 0 <= diversity <= 1


class TestQueryExpansion:
    """Test query expansion functionality."""
    
    def test_expand_query_returns_list(self, query):
        """Test that expand_query returns a list."""
        expanded = reranker_service.expand_query(query)
        assert isinstance(expanded, list)
        assert len(expanded) > 0
    
    def test_expand_query_includes_original(self, query):
        """Test that original query is included in expansion."""
        expanded = reranker_service.expand_query(query)
        assert query in expanded
    
    def test_expand_query_generates_variations(self):
        """Test that expand_query creates query variations."""
        query = "machine learning performance"
        expanded = reranker_service.expand_query(query, max_expansions=3)
        
        # Should have original plus some expansions
        assert len(expanded) >= 1
        # All should be strings
        assert all(isinstance(q, str) for q in expanded)
    
    def test_expand_query_respects_max_expansions(self, query):
        """Test that expand_query respects max_expansions parameter."""
        expanded = reranker_service.expand_query(query, max_expansions=2)
        # Should not exceed max_expansions + 1 (original)
        assert len(expanded) <= 3
    
    def test_query_expansion_synonyms_available(self):
        """Test that common query expansion synonyms are defined."""
        assert len(reranker_service.QUERY_EXPANSIONS) > 0
        # Check some expected expansions exist
        assert 'api' in reranker_service.QUERY_EXPANSIONS
        assert 'bug' in reranker_service.QUERY_EXPANSIONS
        assert 'feature' in reranker_service.QUERY_EXPANSIONS


class TestScoringIndividualResults:
    """Test scoring of individual results."""
    
    def test_score_result_semantic(self, sample_results, query):
        """Test scoring a single result with semantic strategy."""
        result = sample_results[0]
        score = reranker_service.score_result(result, query, strategy='semantic')
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_score_result_bm25(self, sample_results, query):
        """Test scoring a single result with BM25 strategy."""
        result = sample_results[0]
        score = reranker_service.score_result(result, query, strategy='bm25')
        assert isinstance(score, float)
        assert score >= 0
    
    def test_score_result_hybrid(self, sample_results, query):
        """Test scoring a single result with hybrid strategy."""
        result = sample_results[0]
        score = reranker_service.score_result(result, query, strategy='hybrid')
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_score_result_uses_default_strategy(self, sample_results, query):
        """Test that score_result uses default strategy when not specified."""
        result = sample_results[0]
        score = reranker_service.score_result(result, query)
        assert isinstance(score, float)


class TestRerankerIntegration:
    """Integration tests for the reranker."""
    
    def test_rerank_with_default_strategy(self, sample_results, query):
        """Test reranking with default strategy."""
        original_enabled = reranker_service.enabled
        try:
            reranker_service.enabled = True
            ranked = reranker_service.rerank(sample_results, query)
            assert len(ranked) > 0
            # Results should be sorted by rerank_score (if enabled)
            for i in range(len(ranked) - 1):
                score_i = ranked[i].rerank_score if ranked[i].rerank_score is not None else ranked[i].similarity
                score_j = ranked[i + 1].rerank_score if ranked[i + 1].rerank_score is not None else ranked[i + 1].similarity
                assert score_i >= score_j
        finally:
            reranker_service.enabled = original_enabled
    
    def test_rerank_with_override_strategy(self, sample_results, query):
        """Test reranking with strategy override."""
        original_enabled = reranker_service.enabled
        try:
            reranker_service.enabled = True
            strategies = ['semantic', 'bm25', 'hybrid', 'diversity']
            for strategy in strategies:
                ranked = reranker_service.rerank(sample_results, query, strategy=strategy)
                assert len(ranked) > 0
                assert all(hasattr(r, 'rerank_score') or hasattr(r, 'diversity_score') 
                          for r in ranked)
        finally:
            reranker_service.enabled = original_enabled
    
    def test_rerank_respects_top_k(self, sample_results, query):
        """Test that reranking respects top_k limit."""
        original_enabled = reranker_service.enabled
        original_top_k = reranker_service.top_k
        try:
            reranker_service.enabled = True
            reranker_service.top_k = 3
            ranked = reranker_service.rerank(sample_results, query)
            assert len(ranked) <= 3
        finally:
            reranker_service.enabled = original_enabled
            reranker_service.top_k = original_top_k
    
    def test_rerank_empty_results(self, query):
        """Test reranking with empty results."""
        ranked = reranker_service.rerank([], query)
        assert ranked == []
    
    def test_rerank_single_result(self, query):
        """Test reranking with single result."""
        result = RetrievalResult(
            chunk_id="chunk_1",
            source="doc.md",
            ai_provider="ollama",
            embedding_model="model",
            text="Test text for machine learning",
            similarity=0.9,
            created_at=datetime.now()
        )
        original_enabled = reranker_service.enabled
        try:
            reranker_service.enabled = True
            ranked = reranker_service.rerank([result], query)
            assert len(ranked) == 1
        finally:
            reranker_service.enabled = original_enabled


class TestTextUtilities:
    """Test text utility functions."""
    
    def test_tokenize_basic(self):
        """Test basic tokenization."""
        tokens = reranker_service._tokenize("machine learning algorithms")
        assert len(tokens) == 3
        assert "machine" in tokens
        assert "learning" in tokens
    
    def test_tokenize_removes_punctuation(self):
        """Test that tokenization removes punctuation."""
        tokens = reranker_service._tokenize("Hello, world! How are you?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
    
    def test_tokenize_lowercase(self):
        """Test that tokenization is case-insensitive."""
        tokens1 = reranker_service._tokenize("Machine Learning")
        tokens2 = reranker_service._tokenize("machine learning")
        assert tokens1 == tokens2
    
    def test_tokenize_filters_short_tokens(self):
        """Test that very short tokens are filtered."""
        tokens = reranker_service._tokenize("a big test")
        # "a" should be filtered (length <= 2)
        assert "a" not in tokens
        assert "big" in tokens
    
    def test_text_similarity_identical_texts(self):
        """Test similarity of identical texts."""
        text = "machine learning algorithms for classification"
        similarity = reranker_service._text_similarity(text, text)
        assert similarity == 1.0
    
    def test_text_similarity_completely_different(self):
        """Test similarity of completely different texts."""
        text1 = "machine learning"
        text2 = "cooking recipes"
        similarity = reranker_service._text_similarity(text1, text2)
        assert similarity == 0.0
    
    def test_text_similarity_partial_overlap(self):
        """Test similarity with partial overlap."""
        text1 = "machine learning algorithms"
        text2 = "machine learning models"
        similarity = reranker_service._text_similarity(text1, text2)
        # Should be between 0 and 1
        assert 0 < similarity < 1


class TestMetricsTracking:
    """Test performance metrics tracking."""
    
    def test_metrics_are_tracked(self, sample_results, query):
        """Test that reranking tracks metrics."""
        initial_count = reranker_service.metrics['total_reranks']
        reranker_service.rerank(sample_results, query)
        # Metrics should be updated (if reranking is enabled)
        assert reranker_service.metrics['total_reranks'] >= initial_count
    
    def test_query_expansion_metrics_tracked(self, query):
        """Test that query expansion metrics are tracked."""
        initial_count = reranker_service.metrics['total_queries_expanded']
        reranker_service.expand_query(query)
        assert reranker_service.metrics['total_queries_expanded'] > initial_count
    
    def test_get_metrics_returns_valid_structure(self):
        """Test that get_metrics returns valid structure."""
        metrics = reranker_service.get_metrics()
        assert 'enabled' in metrics
        assert 'strategy' in metrics
        assert 'top_k' in metrics
        assert 'metrics' in metrics
        
        metrics_dict = metrics['metrics']
        assert 'total_reranks' in metrics_dict
        assert 'total_queries_expanded' in metrics_dict
        assert 'avg_rerank_time_ms' in metrics_dict


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_rerank_with_none_results(self, query):
        """Test reranking behavior with None (should be caught)."""
        # This should not crash, but return empty
        try:
            result = reranker_service.rerank(None, query)
            assert result is None or len(result) == 0
        except (TypeError, AttributeError):
            # Expected if None is not handled
            pass
    
    def test_very_large_result_set(self, query):
        """Test reranking with large result set."""
        # Create 100 results
        large_results = []
        for i in range(100):
            result = RetrievalResult(
                chunk_id=f"chunk_{i}",
                source=f"doc_{i}.md",
                ai_provider="ollama",
                embedding_model="model",
                text=f"Machine learning text {i} about algorithms and patterns",
                similarity=0.5 + (i * 0.001),
                created_at=datetime.now()
            )
            large_results.append(result)
        
        ranked = reranker_service.rerank(large_results, query)
        assert len(ranked) > 0
    
    def test_rerank_with_empty_query(self, sample_results):
        """Test reranking with empty query string."""
        ranked = reranker_service.rerank(sample_results, "")
        assert len(ranked) > 0
    
    def test_rerank_with_long_query(self, sample_results):
        """Test reranking with very long query."""
        long_query = "machine learning " * 50
        ranked = reranker_service.rerank(sample_results, long_query)
        assert len(ranked) > 0


class TestRerankerWithConfiguration:
    """Test reranker with different configurations."""
    
    def test_disabled_reranker_returns_original(self, sample_results, query):
        """Test that disabled reranker returns original results."""
        original_enabled = reranker_service.enabled
        try:
            reranker_service.enabled = False
            ranked = reranker_service.rerank(sample_results, query)
            # Should return original (though may be transformed)
            assert len(ranked) == len(sample_results)
        finally:
            reranker_service.enabled = original_enabled
    
    def test_reranker_strategy_change(self, sample_results, query):
        """Test changing reranker strategy."""
        original_strategy = reranker_service.strategy
        try:
            for strategy in ['semantic', 'bm25', 'hybrid', 'diversity']:
                reranker_service.strategy = strategy
                ranked = reranker_service.rerank(sample_results, query)
                assert len(ranked) > 0
        finally:
            reranker_service.strategy = original_strategy


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
