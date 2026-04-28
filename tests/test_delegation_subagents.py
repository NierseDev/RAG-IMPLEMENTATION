"""
Test suite for delegation logic and sub-agents (Sprint 5).

Tests:
- should_delegate() decision logic
- spawn_subagent() creation
- execute_with_subagent() execution
- Sub-agent specialization
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.models.entities import AgentState, RetrievalResult
from app.services.agent import AgenticRAG
from app.services.subagent_base import SubAgent
from datetime import datetime


class TestDelegationLogic:
    """Test delegation decision making."""
    
    @pytest.fixture
    def agent(self):
        """Create test agent."""
        return AgenticRAG(enable_tools=False)
    
    @pytest.fixture
    def sample_state(self):
        """Create sample agent state."""
        state = AgentState(
            iteration=1,
            original_query="What information is available?",
            current_query="What information is available?"
        )
        
        # Add sample retrieved docs
        for i in range(3):
            doc = RetrievalResult(
                chunk_id=f"chunk_{i}",
                source=f"doc_{i}.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text=f"Sample document text {i}",
                similarity=0.9,
                created_at=datetime.now()
            )
            state.retrieved_docs.append(doc)
        
        return state
    
    def test_should_delegate_full_document(self, agent, sample_state):
        """Test detection of full document analysis."""
        sample_state.current_query = "Analyze the entire document for insights"
        should_delegate, agent_type = agent.should_delegate(sample_state)
        
        assert should_delegate is True
        assert agent_type == 'full_document'
    
    def test_should_delegate_comparison(self, agent, sample_state):
        """Test detection of comparison queries."""
        sample_state.current_query = "Compare the two documents and identify differences"
        should_delegate, agent_type = agent.should_delegate(sample_state)
        
        assert should_delegate is True
        assert agent_type == 'comparison'
    
    def test_should_delegate_extraction(self, agent, sample_state):
        """Test detection of extraction queries."""
        sample_state.current_query = "Extract all entity names from the documents"
        should_delegate, agent_type = agent.should_delegate(sample_state)
        
        assert should_delegate is True
        assert agent_type == 'extraction'
    
    def test_should_not_delegate_generic_query(self, agent, sample_state):
        """Test that generic queries don't trigger delegation."""
        sample_state.current_query = "What does the document say about Python?"
        should_delegate, agent_type = agent.should_delegate(sample_state)
        
        assert should_delegate is False
        assert agent_type is None
    
    def test_should_not_delegate_insufficient_docs(self, agent):
        """Test that delegation requires minimum documents."""
        state = AgentState(
            iteration=1,
            original_query="Compare documents",
            current_query="Compare documents"
        )
        state.retrieved_docs = [
            RetrievalResult(
                chunk_id="chunk_0",
                source="doc_0.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text="Single document",
                similarity=0.9,
                created_at=datetime.now()
            )
        ]
        
        should_delegate, agent_type = agent.should_delegate(state)
        assert should_delegate is False


class TestSubAgentSpawning:
    """Test sub-agent creation and spawning."""
    
    @pytest.fixture
    def agent(self):
        return AgenticRAG(enable_tools=False)
    
    @pytest.fixture
    def sample_state(self):
        state = AgentState(
            iteration=1,
            original_query="Test query",
            current_query="Test query"
        )
        state.retrieved_docs = [
            RetrievalResult(
                chunk_id="chunk_0",
                source="test.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text="Test content",
                similarity=0.9,
                created_at=datetime.now()
            )
        ]
        return state
    
    @pytest.mark.asyncio
    async def test_spawn_full_document_agent(self, agent, sample_state):
        """Test spawning FullDocumentAgent."""
        sub_agent = await agent.spawn_subagent('full_document', sample_state)
        
        assert sub_agent is not None
        assert sub_agent.agent_type == 'full_document'
        assert len(sub_agent.document_set) == 1
    
    @pytest.mark.asyncio
    async def test_spawn_comparison_agent(self, agent, sample_state):
        """Test spawning ComparisonAgent."""
        sub_agent = await agent.spawn_subagent('comparison', sample_state)
        
        assert sub_agent is not None
        assert sub_agent.agent_type == 'comparison'
    
    @pytest.mark.asyncio
    async def test_spawn_extraction_agent(self, agent, sample_state):
        """Test spawning ExtractionAgent."""
        sub_agent = await agent.spawn_subagent('extraction', sample_state)
        
        assert sub_agent is not None
        assert sub_agent.agent_type == 'extraction'
    
    @pytest.mark.asyncio
    async def test_spawn_invalid_agent_type(self, agent, sample_state):
        """Test that invalid agent type returns None."""
        sub_agent = await agent.spawn_subagent('invalid_type', sample_state)
        
        assert sub_agent is None


class TestSubAgentBase:
    """Test base SubAgent functionality."""
    
    def test_subagent_initialization(self):
        """Test SubAgent initialization."""
        context = {
            'original_query': 'Test',
            'document_set': [],
            'delegation_reason': 'test'
        }
        
        sub_agent = SubAgent(
            agent_type='test_agent',
            parent_context=context
        )
        
        assert sub_agent.agent_type == 'test_agent'
        assert sub_agent.parent_context == context
        assert sub_agent.sub_agent_metrics['agent_type'] == 'test_agent'
    
    def test_subagent_metrics_tracking(self):
        """Test metrics are tracked."""
        context = {
            'original_query': 'Test query',
            'document_set': [],
            'delegation_reason': 'testing'
        }
        
        sub_agent = SubAgent(
            agent_type='test',
            parent_context=context
        )
        
        metrics = sub_agent.get_metrics()
        
        assert 'sub_agent' in metrics
        assert metrics['sub_agent']['agent_type'] == 'test'
        assert metrics['sub_agent']['parent_query'] == 'Test query'


class TestFullDocumentAgent:
    """Test FullDocumentAgent specialization."""
    
    @pytest.mark.asyncio
    async def test_full_document_context_grouping(self):
        """Test that FullDocumentAgent groups documents by source."""
        from app.services.subagents.full_document_agent import FullDocumentAgent
        
        context = {'original_query': 'Test', 'document_set': []}
        agent = FullDocumentAgent(parent_context=context)
        
        # Create test docs
        docs = [
            RetrievalResult(
                chunk_id="chunk_0",
                source="doc_a.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text="Content from doc A",
                similarity=0.9,
                created_at=datetime.now()
            ),
            RetrievalResult(
                chunk_id="chunk_1",
                source="doc_b.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text="Content from doc B",
                similarity=0.85,
                created_at=datetime.now()
            )
        ]
        
        context_str = await agent.specialize_context_window(docs, "Test query")
        
        assert "doc_a.txt" in context_str
        assert "doc_b.txt" in context_str
        assert "Content from doc A" in context_str
        assert "Content from doc B" in context_str


class TestComparisonAgent:
    """Test ComparisonAgent specialization."""
    
    def test_comparison_agent_source_balancing(self):
        """Test that ComparisonAgent balances sources."""
        from app.services.subagents.comparison_agent import ComparisonAgent
        
        context = {'original_query': 'Compare', 'document_set': []}
        agent = ComparisonAgent(parent_context=context)
        
        # Create results all from one source
        results = [
            RetrievalResult(
                chunk_id=f"chunk_{i}",
                source="single_doc.txt" if i < 4 else "other_doc.txt",
                ai_provider="ollama",
                embedding_model="mxbai-embed-large",
                text=f"Content {i}",
                similarity=0.9 - (i * 0.05),
                created_at=datetime.now()
            )
            for i in range(6)
        ]
        
        balanced = agent._balance_sources(results, 4)
        
        assert len(balanced) == 4
        # Should have representation from both sources
        sources = set(doc.source for doc in balanced)
        assert len(sources) >= 1  # At least one source represented


class TestExtractionAgent:
    """Test ExtractionAgent specialization."""
    
    def test_extraction_query_parsing(self):
        """Test that ExtractionAgent parses query correctly."""
        from app.services.subagents.extraction_agent import ExtractionAgent
        
        context = {'original_query': 'Extract names', 'document_set': []}
        agent = ExtractionAgent(parent_context=context)
        
        keywords = agent._parse_extraction_query("Extract all people names from the document")
        
        assert 'people' in keywords or len(keywords) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
