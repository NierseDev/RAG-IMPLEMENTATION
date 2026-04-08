"""
Reciprocal Rank Fusion (RRF) for combining multiple search results.
Implements RRF algorithm to merge vector search and keyword search results.
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ReciprocalRankFusion:
    """
    Implements Reciprocal Rank Fusion (RRF) algorithm.
    
    RRF combines multiple ranked lists by:
    1. Assigning each item a score based on its rank: 1/(k + rank)
    2. Summing scores across all lists
    3. Re-ranking by combined score
    
    Paper: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"
    """
    
    def __init__(self, k: int = 60):
        """
        Initialize RRF.
        
        Args:
            k: Constant for RRF score calculation (default: 60)
               Higher k = less weight to top results, more uniform distribution
        """
        self.k = k
        logger.info(f"RRF initialized with k={k}")
    
    def fuse(
        self,
        ranked_lists: List[List[Dict[str, Any]]],
        id_key: str = 'chunk_id',
        score_keys: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fuse multiple ranked lists using RRF.
        
        Args:
            ranked_lists: List of ranked result lists (each list is ordered by relevance)
            id_key: Key to use for identifying unique items across lists
            score_keys: Optional list of keys to store original scores
            
        Returns:
            Combined and re-ranked list
        """
        if not ranked_lists:
            return []
        
        # Calculate RRF scores
        rrf_scores: Dict[str, float] = {}
        item_data: Dict[str, Dict[str, Any]] = {}
        
        for list_idx, ranked_list in enumerate(ranked_lists):
            for rank, item in enumerate(ranked_list, start=1):
                item_id = item.get(id_key)
                if not item_id:
                    logger.warning(f"Item missing {id_key}, skipping")
                    continue
                
                # Calculate RRF score for this item in this list
                rrf_score = 1.0 / (self.k + rank)
                
                # Add to cumulative score
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_score
                
                # Store item data (from first occurrence)
                if item_id not in item_data:
                    item_data[item_id] = item.copy()
                    item_data[item_id]['rrf_score'] = 0.0
                    item_data[item_id]['source_ranks'] = []
                
                # Track which lists this item appeared in
                item_data[item_id]['source_ranks'].append({
                    'list_index': list_idx,
                    'rank': rank,
                    'rrf_contribution': rrf_score
                })
        
        # Update final RRF scores
        for item_id, score in rrf_scores.items():
            item_data[item_id]['rrf_score'] = score
        
        # Sort by RRF score (descending)
        fused_results = sorted(
            item_data.values(),
            key=lambda x: x['rrf_score'],
            reverse=True
        )
        
        logger.info(f"Fused {len(ranked_lists)} lists into {len(fused_results)} results")
        return fused_results
    
    def fuse_with_weights(
        self,
        ranked_lists: List[List[Dict[str, Any]]],
        weights: List[float],
        id_key: str = 'chunk_id'
    ) -> List[Dict[str, Any]]:
        """
        Fuse multiple ranked lists with weighted RRF.
        
        Args:
            ranked_lists: List of ranked result lists
            weights: Weight for each list (e.g., [0.7, 0.3] for 70% vector, 30% keyword)
            id_key: Key to use for identifying unique items
            
        Returns:
            Combined and re-ranked list with weighted scores
        """
        if len(ranked_lists) != len(weights):
            raise ValueError("Number of weights must match number of ranked lists")
        
        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Calculate weighted RRF scores
        rrf_scores: Dict[str, float] = {}
        item_data: Dict[str, Dict[str, Any]] = {}
        
        for list_idx, (ranked_list, weight) in enumerate(zip(ranked_lists, normalized_weights)):
            for rank, item in enumerate(ranked_list, start=1):
                item_id = item.get(id_key)
                if not item_id:
                    continue
                
                # Calculate weighted RRF score
                rrf_score = weight * (1.0 / (self.k + rank))
                
                # Add to cumulative score
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_score
                
                # Store item data
                if item_id not in item_data:
                    item_data[item_id] = item.copy()
                    item_data[item_id]['weighted_rrf_score'] = 0.0
                    item_data[item_id]['source_ranks'] = []
                
                item_data[item_id]['source_ranks'].append({
                    'list_index': list_idx,
                    'rank': rank,
                    'weight': weight,
                    'rrf_contribution': rrf_score
                })
        
        # Update final weighted RRF scores
        for item_id, score in rrf_scores.items():
            item_data[item_id]['weighted_rrf_score'] = score
        
        # Sort by weighted RRF score
        fused_results = sorted(
            item_data.values(),
            key=lambda x: x['weighted_rrf_score'],
            reverse=True
        )
        
        logger.info(f"Weighted fusion: {len(fused_results)} results (weights={weights})")
        return fused_results
    
    def explain_fusion(self, fused_item: Dict[str, Any]) -> str:
        """
        Generate explanation of how an item was ranked.
        
        Args:
            fused_item: Item from fused results (must have 'source_ranks')
            
        Returns:
            Human-readable explanation string
        """
        if 'source_ranks' not in fused_item:
            return "No fusion data available"
        
        explanation_parts = []
        total_score = fused_item.get('rrf_score') or fused_item.get('weighted_rrf_score', 0)
        
        explanation_parts.append(f"Total RRF Score: {total_score:.4f}")
        explanation_parts.append(f"Appeared in {len(fused_item['source_ranks'])} source(s):")
        
        for source in fused_item['source_ranks']:
            list_idx = source['list_index']
            rank = source['rank']
            contribution = source['rrf_contribution']
            
            if 'weight' in source:
                explanation_parts.append(
                    f"  - List {list_idx}: Rank {rank} (weight={source['weight']:.2f}, contribution={contribution:.4f})"
                )
            else:
                explanation_parts.append(
                    f"  - List {list_idx}: Rank {rank} (contribution={contribution:.4f})"
                )
        
        return "\n".join(explanation_parts)


class HybridSearchFusion:
    """
    Specialized fusion for hybrid search (vector + keyword).
    Combines vector similarity search with keyword/BM25 search using RRF.
    """
    
    def __init__(
        self,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid search fusion.
        
        Args:
            vector_weight: Weight for vector search results (default: 0.7)
            keyword_weight: Weight for keyword search results (default: 0.3)
            rrf_k: RRF constant
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.rrf = ReciprocalRankFusion(k=rrf_k)
        logger.info(f"HybridSearchFusion initialized (vector={vector_weight}, keyword={keyword_weight})")
    
    def combine(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        use_weights: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and keyword search results.
        
        Args:
            vector_results: Results from vector similarity search
            keyword_results: Results from keyword/BM25 search
            use_weights: Whether to use weighted RRF (default: True)
            
        Returns:
            Fused and re-ranked results
        """
        if not vector_results and not keyword_results:
            return []
        
        if not vector_results:
            logger.info("Only keyword results available")
            return keyword_results
        
        if not keyword_results:
            logger.info("Only vector results available")
            return vector_results
        
        # Perform fusion
        if use_weights:
            results = self.rrf.fuse_with_weights(
                ranked_lists=[vector_results, keyword_results],
                weights=[self.vector_weight, self.keyword_weight],
                id_key='chunk_id'
            )
        else:
            results = self.rrf.fuse(
                ranked_lists=[vector_results, keyword_results],
                id_key='chunk_id'
            )
        
        # Add search method annotation
        for result in results:
            in_vector = any(r.get('chunk_id') == result.get('chunk_id') for r in vector_results)
            in_keyword = any(r.get('chunk_id') == result.get('chunk_id') for r in keyword_results)
            
            if in_vector and in_keyword:
                result['search_method'] = 'hybrid'
            elif in_vector:
                result['search_method'] = 'vector'
            else:
                result['search_method'] = 'keyword'
        
        return results


# Global instances
rrf_fusion = ReciprocalRankFusion()
hybrid_fusion = HybridSearchFusion()
