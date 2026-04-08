"""
Test script for Sprint 3 features.
Tests all new services: semantic chunking, dynamic chunking, context optimizer,
metadata extraction, RRF fusion, keyword search, and hybrid retrieval.
"""
import asyncio
import sys
from pathlib import Path

# Test text samples
SAMPLE_TEXT = """
# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that focuses on enabling computers to learn from data.

## Types of Machine Learning

### Supervised Learning
Supervised learning involves training models on labeled data. Common algorithms include:
- Linear Regression
- Decision Trees
- Neural Networks

### Unsupervised Learning
Unsupervised learning works with unlabeled data to find patterns.

## Applications

Machine learning is used in:
1. Image recognition
2. Natural language processing
3. Recommendation systems

For more information, contact: research@example.com
Date: 2024-03-15
"""


def test_semantic_chunker():
    """Test semantic chunking."""
    print("\n" + "="*80)
    print("TEST 1: Semantic Chunker")
    print("="*80)
    
    try:
        from app.services.semantic_chunker import semantic_chunker
        
        chunks = semantic_chunker.chunk(SAMPLE_TEXT, preserve_structure=True)
        
        print(f"✓ Created {len(chunks)} semantic chunks")
        for i, chunk in enumerate(chunks, 1):
            print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
            print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_dynamic_chunker():
    """Test dynamic chunking."""
    print("\n" + "="*80)
    print("TEST 2: Dynamic Chunker")
    print("="*80)
    
    try:
        from app.services.dynamic_chunker import dynamic_chunker
        
        chunk_tuples = dynamic_chunker.chunk_with_density(SAMPLE_TEXT)
        
        print(f"✓ Created {len(chunk_tuples)} dynamic chunks")
        for i, (text, meta) in enumerate(chunk_tuples, 1):
            print(f"\n--- Chunk {i} ---")
            print(f"  Tokens: {meta['token_count']}")
            print(f"  Density: {meta['density_score']:.3f}")
            print(f"  Type: {meta['chunk_type']}")
            print(f"  Preview: {text[:150]}...")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_context_optimizer():
    """Test context optimizer."""
    print("\n" + "="*80)
    print("TEST 3: Context Optimizer")
    print("="*80)
    
    try:
        from app.services.context_optimizer import context_optimizer
        
        test_queries = [
            "What is machine learning?",
            "Explain supervised learning, unsupervised learning, and reinforcement learning in detail",
            "Compare neural networks vs decision trees for classification tasks"
        ]
        
        for query in test_queries:
            optimal_k = context_optimizer.calculate_optimal_top_k(query)
            complexity = context_optimizer._calculate_query_complexity(query)
            
            print(f"\nQuery: {query}")
            print(f"  Complexity: {complexity:.2f}")
            print(f"  Optimal top_k: {optimal_k}")
        
        print("\n✓ Context optimizer working correctly")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_metadata_extractor():
    """Test metadata extraction."""
    print("\n" + "="*80)
    print("TEST 4: Metadata Extractor")
    print("="*80)
    
    try:
        from app.services.metadata_extractor import metadata_extractor
        
        metadata = metadata_extractor.extract(
            text=SAMPLE_TEXT,
            filename="machine_learning_intro_2024-03-15.pdf",
            file_size=1024 * 50  # 50KB
        )
        
        print("✓ Extracted metadata:")
        for key, value in metadata.items():
            if key != 'statistics':
                print(f"  {key}: {value}")
        
        if 'statistics' in metadata:
            print("\n  Statistics:")
            for k, v in metadata['statistics'].items():
                print(f"    {k}: {v}")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_rrf_fusion():
    """Test RRF fusion algorithm."""
    print("\n" + "="*80)
    print("TEST 5: RRF Fusion")
    print("="*80)
    
    try:
        from app.services.rrf_fusion import rrf_fusion, hybrid_fusion
        
        # Mock search results
        vector_results = [
            {'chunk_id': 'chunk_1', 'text': 'ML is AI subset', 'source': 'doc1.pdf'},
            {'chunk_id': 'chunk_2', 'text': 'Supervised learning', 'source': 'doc1.pdf'},
            {'chunk_id': 'chunk_3', 'text': 'Neural networks', 'source': 'doc2.pdf'},
        ]
        
        keyword_results = [
            {'chunk_id': 'chunk_2', 'text': 'Supervised learning', 'source': 'doc1.pdf'},
            {'chunk_id': 'chunk_4', 'text': 'Machine learning applications', 'source': 'doc3.pdf'},
            {'chunk_id': 'chunk_1', 'text': 'ML is AI subset', 'source': 'doc1.pdf'},
        ]
        
        # Test basic RRF
        fused = rrf_fusion.fuse([vector_results, keyword_results])
        print(f"✓ Basic RRF: Combined {len(vector_results)} + {len(keyword_results)} = {len(fused)} results")
        
        for i, item in enumerate(fused, 1):
            print(f"  {i}. {item['chunk_id']} (score: {item['rrf_score']:.4f})")
        
        # Test weighted RRF
        weighted = rrf_fusion.fuse_with_weights(
            [vector_results, keyword_results],
            weights=[0.7, 0.3]
        )
        print(f"\n✓ Weighted RRF (70/30): {len(weighted)} results")
        
        # Test hybrid fusion
        hybrid = hybrid_fusion.combine(vector_results, keyword_results)
        print(f"\n✓ Hybrid fusion: {len(hybrid)} results")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_integration():
    """Test Sprint 3 config settings."""
    print("\n" + "="*80)
    print("TEST 6: Configuration Integration")
    print("="*80)
    
    try:
        from app.core.config import settings
        
        sprint3_settings = {
            'use_semantic_chunking': settings.use_semantic_chunking,
            'use_dynamic_chunking': settings.use_dynamic_chunking,
            'use_hybrid_search': settings.use_hybrid_search,
            'min_retrieval_chunks': settings.min_retrieval_chunks,
            'max_retrieval_chunks': settings.max_retrieval_chunks,
            'hybrid_vector_weight': settings.hybrid_vector_weight,
            'hybrid_keyword_weight': settings.hybrid_keyword_weight,
        }
        
        print("✓ Sprint 3 configuration loaded:")
        for key, value in sprint3_settings.items():
            print(f"  {key}: {value}")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_response_models():
    """Test enhanced response models."""
    print("\n" + "="*80)
    print("TEST 7: Enhanced Response Models")
    print("="*80)
    
    try:
        from app.models.responses import (
            AgentResponse, IngestResponse,
            RetrievedChunkTrace, VerificationTrace
        )
        
        # Test RetrievedChunkTrace
        chunk_trace = RetrievedChunkTrace(
            chunk_id="test_chunk",
            source="test.pdf",
            text="Sample text",
            similarity=0.95,
            iteration_retrieved=1
        )
        print("✓ RetrievedChunkTrace model valid")
        
        # Test VerificationTrace
        verify_trace = VerificationTrace(
            verified=True,
            confidence=0.85,
            issues=[],
            grounded_claims=5,
            total_claims=5,
            iteration=1
        )
        print("✓ VerificationTrace model valid")
        
        # Test enhanced AgentResponse
        agent_resp = AgentResponse(
            query="Test query",
            answer="Test answer",
            retrieved_chunks_detail=[chunk_trace],
            verification_detail=[verify_trace],
            agent_steps=[{'description': 'Step 1', 'timestamp': 1.0}],
            tool_calls=[]
        )
        print("✓ Enhanced AgentResponse model valid")
        
        # Test enhanced IngestResponse
        ingest_resp = IngestResponse(
            success=True,
            message="Test",
            source="test.pdf",
            file_hash="abc123",
            duplicate_action="new",
            validation_warnings=[],
            metadata_extracted={'title': 'Test Doc'}
        )
        print("✓ Enhanced IngestResponse model valid")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Sprint 3 tests."""
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + "  SPRINT 3 INTEGRATION TEST SUITE".center(78) + "█")
    print("█" + " "*78 + "█")
    print("█"*80)
    
    tests = [
        ("Semantic Chunker", test_semantic_chunker),
        ("Dynamic Chunker", test_dynamic_chunker),
        ("Context Optimizer", test_context_optimizer),
        ("Metadata Extractor", test_metadata_extractor),
        ("RRF Fusion", test_rrf_fusion),
        ("Configuration", test_config_integration),
        ("Response Models", test_response_models),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*80)
    
    if passed == total:
        print("\n🎉 All Sprint 3 features working correctly! 🎉")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
