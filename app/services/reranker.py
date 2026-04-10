"""
Reranking module for the RAG system (Sprint 5).
Implements advanced ranking algorithms: BM25-semantic fusion, query expansion,
and diversity scoring for re-ranking retrieval results.
"""
import logging
import math
from typing import List, Optional, Dict, Any, Literal
from collections import Counter
import time

from app.models.entities import RetrievalResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Service for re-ranking search results using multiple strategies.
    Supports BM25, semantic, hybrid, and diversity-based ranking.
    """
    
    # Common query expansion synonyms and related terms
    QUERY_EXPANSIONS = {
        'api': ['interface', 'endpoint', 'service', 'method', 'protocol'],
        'bug': ['defect', 'error', 'issue', 'problem', 'failure'],
        'feature': ['functionality', 'capability', 'component', 'module'],
        'performance': ['speed', 'efficiency', 'optimization', 'throughput', 'latency'],
        'security': ['authentication', 'authorization', 'encryption', 'vulnerability'],
        'database': ['storage', 'backend', 'persistence', 'data', 'schema'],
        'frontend': ['ui', 'interface', 'client', 'presentation', 'view'],
        'backend': ['server', 'service', 'api', 'infrastructure'],
    }
    
    def __init__(self):
        """Initialize reranker with configuration."""
        self.enabled = settings.use_reranking
        self.strategy = settings.rerank_strategy
        self.top_k = settings.rerank_top_k
        
        # Performance metrics
        self.metrics = {
            'total_reranks': 0,
            'total_queries_expanded': 0,
            'total_diversity_calculated': 0,
            'avg_rerank_time_ms': 0.0
        }
        
        logger.info(
            f"RerankerService initialized: enabled={self.enabled}, "
            f"strategy={self.strategy}, top_k={self.top_k}"
        )
    
    def rerank(
        self,
        results: List[RetrievalResult],
        query: str,
        strategy: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        Re-rank retrieval results using specified strategy.
        
        Args:
            results: List of retrieval results to rerank
            query: Original query for context
            strategy: Override default strategy ('semantic', 'bm25', 'hybrid', 'diversity')
            
        Returns:
            Re-ranked list of results
        """
        if not self.enabled or not results:
            return results
        
        start_time = time.time()
        strategy = strategy or self.strategy
        
        try:
            if strategy == 'semantic':
                ranked = self._rerank_semantic(results, query)
            elif strategy == 'bm25':
                ranked = self._rerank_bm25(results, query)
            elif strategy == 'hybrid':
                ranked = self._rerank_hybrid(results, query)
            elif strategy == 'diversity':
                ranked = self._rerank_diversity(results, query)
            else:
                logger.warning(f"Unknown strategy {strategy}, returning original order")
                ranked = results
            
            # Update metrics
            elapsed_ms = (time.time() - start_time) * 1000
            self._update_metrics(elapsed_ms)
            
            logger.info(
                f"Reranked {len(results)} results using {strategy} strategy "
                f"in {elapsed_ms:.1f}ms"
            )
            
            return ranked[:self.top_k]
        
        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            return results
    
    def _rerank_semantic(
        self,
        results: List[RetrievalResult],
        query: str
    ) -> List[RetrievalResult]:
        """
        Re-rank using semantic similarity (already present in results).
        Useful for refining existing similarity scores.
        """
        # Results are already scored by semantic similarity
        # This applies confidence weighting to existing scores
        scored_results = []
        
        for result in results:
            # Apply confidence-based weighting
            confidence_boost = 1.0 if result.similarity > 0.7 else 0.95
            adjusted_score = result.similarity * confidence_boost
            
            # Store rerank score
            result.rerank_score = adjusted_score
            scored_results.append(result)
        
        return sorted(scored_results, key=lambda x: x.rerank_score or x.similarity, reverse=True)
    
    def _rerank_bm25(
        self,
        results: List[RetrievalResult],
        query: str
    ) -> List[RetrievalResult]:
        """
        Re-rank using BM25-style scoring (term frequency, IDF approximation).
        BM25 formula: score = sum(IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl)))
        """
        # BM25 parameters
        k1 = 1.5  # term frequency saturation
        b = 0.75  # document length normalization
        
        # Calculate average document length
        doc_lengths = [len(r.text.split()) for r in results]
        avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        
        # Calculate IDF for each query term
        idf_scores = {}
        for token in query_tokens:
            # Count documents containing this term
            doc_count = sum(1 for r in results if token in self._tokenize(r.text.lower()))
            # IDF approximation: log(N / (df + 1))
            idf = math.log((len(results) + 1) / (doc_count + 0.5))
            idf_scores[token] = idf
        
        # Calculate BM25 score for each result
        scored_results = []
        for result in results:
            doc_tokens = self._tokenize(result.text.lower())
            doc_length = len(doc_tokens)
            
            score = 0.0
            for token in query_tokens:
                term_freq = doc_tokens.count(token)
                if term_freq > 0:
                    idf = idf_scores.get(token, 0)
                    numerator = idf * term_freq * (k1 + 1)
                    denominator = term_freq + k1 * (1 - b + b * doc_length / avg_doc_length)
                    score += numerator / denominator
            
            result.rerank_score = score
            scored_results.append(result)
        
        return sorted(scored_results, key=lambda x: x.rerank_score, reverse=True)
    
    def _rerank_hybrid(
        self,
        results: List[RetrievalResult],
        query: str
    ) -> List[RetrievalResult]:
        """
        Re-rank using hybrid approach: combine semantic + BM25 scores.
        Semantic weight: 0.6, BM25 weight: 0.4
        """
        # Get semantic scores
        semantic_results = self._rerank_semantic(results.copy(), query)
        semantic_scores = {r.chunk_id: r.rerank_score for r in semantic_results}
        
        # Get BM25 scores
        bm25_results = self._rerank_bm25(results.copy(), query)
        bm25_scores = {r.chunk_id: r.rerank_score for r in bm25_results}
        
        # Normalize scores to 0-1 range
        semantic_max = max(semantic_scores.values()) if semantic_scores else 1.0
        bm25_max = max(bm25_scores.values()) if bm25_scores else 1.0
        
        semantic_normalized = {k: v / semantic_max if semantic_max > 0 else 0 
                              for k, v in semantic_scores.items()}
        bm25_normalized = {k: v / bm25_max if bm25_max > 0 else 0 
                          for k, v in bm25_scores.items()}
        
        # Combine scores
        scored_results = []
        for result in results:
            sem_score = semantic_normalized.get(result.chunk_id, 0.0)
            bm25_score = bm25_normalized.get(result.chunk_id, 0.0)
            
            # Weighted combination
            hybrid_score = 0.6 * sem_score + 0.4 * bm25_score
            result.rerank_score = hybrid_score
            scored_results.append(result)
        
        return sorted(scored_results, key=lambda x: x.rerank_score, reverse=True)
    
    def _rerank_diversity(
        self,
        results: List[RetrievalResult],
        query: str
    ) -> List[RetrievalResult]:
        """
        Re-rank to maximize diversity (avoid redundant results).
        Penalizes results that are too similar to already-selected results.
        """
        if len(results) <= 1:
            return results
        
        # Start with highest semantic similarity
        sorted_results = sorted(results, key=lambda x: x.similarity, reverse=True)
        
        selected = []
        remaining = list(sorted_results)
        
        # Greedily select diverse results
        while remaining and len(selected) < self.top_k:
            # Add best remaining result
            best = remaining.pop(0)
            best.diversity_score = 1.0 if not selected else self._calculate_diversity(best, selected)
            selected.append(best)
            
            # Penalize similar remaining results
            for result in remaining:
                similarity_to_selected = max(
                    self._text_similarity(result.text, s.text) 
                    for s in selected
                )
                # Penalty factor: reduce score based on similarity to selected
                penalty = 0.9 ** (1 - similarity_to_selected)
                result.rerank_score = result.similarity * penalty
            
            # Re-sort remaining by penalized score
            remaining.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # Combine diversity score with semantic similarity
        for result in selected:
            if hasattr(result, 'diversity_score'):
                result.rerank_score = 0.7 * result.similarity + 0.3 * result.diversity_score
            else:
                result.rerank_score = result.similarity
        
        return sorted(selected, key=lambda x: x.rerank_score, reverse=True)
    
    def score_result(
        self,
        result: RetrievalResult,
        query: str,
        strategy: Optional[str] = None
    ) -> float:
        """
        Score a single result based on query and strategy.
        
        Args:
            result: Result to score
            query: Query for context
            strategy: Scoring strategy
            
        Returns:
            Score between 0 and 1
        """
        strategy = strategy or self.strategy
        
        if strategy == 'semantic':
            return result.similarity
        
        elif strategy == 'bm25':
            results_copy = [result]
            scored = self._rerank_bm25(results_copy, query)
            return scored[0].rerank_score if scored else 0.0
        
        elif strategy == 'hybrid':
            results_copy = [result]
            scored = self._rerank_hybrid(results_copy, query)
            return scored[0].rerank_score if scored else 0.0
        
        elif strategy == 'diversity':
            # Diversity score requires comparison with other results
            return result.similarity
        
        return result.similarity
    
    def expand_query(
        self,
        query: str,
        max_expansions: int = 3
    ) -> List[str]:
        """
        Expand query with synonyms and related terms.
        Returns original query plus expanded versions.
        
        Args:
            query: Original query
            max_expansions: Maximum number of expanded queries to generate
            
        Returns:
            List of query variations
        """
        expanded_queries = [query]
        self.metrics['total_queries_expanded'] += 1
        
        query_lower = query.lower()
        tokens = self._tokenize(query_lower)
        
        # Find matching expansion terms
        expansions_found = []
        for token in tokens:
            if token in self.QUERY_EXPANSIONS:
                expansions_found.extend(self.QUERY_EXPANSIONS[token][:2])  # Top 2 synonyms
        
        # Create expanded query versions
        for expansion_term in expansions_found[:max_expansions]:
            expanded = query + f" {expansion_term}"
            if expanded not in expanded_queries:
                expanded_queries.append(expanded)
        
        logger.debug(f"Query expanded to {len(expanded_queries)} variations")
        return expanded_queries
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.
        
        Returns:
            Dictionary with reranking metrics
        """
        return {
            'enabled': self.enabled,
            'strategy': self.strategy,
            'top_k': self.top_k,
            'metrics': self.metrics
        }
    
    def _calculate_diversity(
        self,
        result: RetrievalResult,
        selected: List[RetrievalResult]
    ) -> float:
        """
        Calculate diversity score: how different is this result from selected ones.
        Returns score between 0 and 1, higher is more diverse.
        """
        if not selected:
            return 1.0
        
        similarities = [self._text_similarity(result.text, s.text) for s in selected]
        avg_similarity = sum(similarities) / len(similarities)
        
        # Diversity is inverse of average similarity
        diversity = 1.0 - avg_similarity
        return max(0.0, diversity)
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity using token overlap (Jaccard).
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        tokens1 = set(self._tokenize(text1.lower()))
        tokens2 = set(self._tokenize(text2.lower()))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        
        return intersection / union if union > 0 else 0.0
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization: lowercase, split on whitespace and punctuation.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        import re
        # Split on whitespace and common punctuation
        tokens = re.findall(r'\b\w+\b', text.lower())
        # Filter out very short tokens
        return [t for t in tokens if len(t) > 2]
    
    def _update_metrics(self, elapsed_ms: float):
        """Update performance metrics."""
        self.metrics['total_reranks'] += 1
        # Update running average
        current_avg = self.metrics['avg_rerank_time_ms']
        total = self.metrics['total_reranks']
        self.metrics['avg_rerank_time_ms'] = (
            (current_avg * (total - 1) + elapsed_ms) / total
        )


# Global instance
reranker_service = RerankerService()
