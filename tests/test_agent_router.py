"""
Comprehensive tests for Agent Router (Sprint 4, Group 3).

Tests:
1. Query type classification
2. Tool selection logic
3. Fallback chains
4. Routing decisions
5. Edge cases and ambiguous queries
"""

import asyncio
import pytest
from app.services.agent_router import (
    AgentRouter,
    QueryType,
    ToolType,
    RoutingDecision,
    agent_router
)


class MockTool:
    """Mock tool for testing."""
    
    def __init__(self, name, should_succeed=True):
        self.name = name
        self.should_succeed = should_succeed
        self.called = False
    
    async def execute(self, query):
        self.called = True
        if self.should_succeed:
            return {'success': True, 'result': f'{self.name} executed for: {query}'}
        else:
            return {'success': False, 'error': f'{self.name} failed'}


class TestQueryAnalysis:
    """Test query type analysis and classification."""
    
    @pytest.fixture
    def router(self):
        return AgentRouter()
    
    def test_structured_query_detection(self, router):
        """Test detection of structured queries."""
        queries = [
            "How many documents are in the table?",
            "Count the rows in the database",
            "What's the sum of all values?",
            "Show me database statistics"
        ]
        
        for query in queries:
            query_type, confidence, reasoning = router.analyze_query(query)
            assert query_type == QueryType.STRUCTURED, f"Failed for: {query}"
            assert confidence >= 0.5, f"Confidence too low for: {query}"
            print(f"✓ Structured: {query} → {query_type.value} ({confidence:.2f})")
    
    def test_current_event_query_detection(self, router):
        """Test detection of current event queries."""
        queries = [
            "What's the latest news?",
            "Tell me about today's events",
            "What happened recently?",
        ]
        
        for query in queries:
            query_type, confidence, reasoning = router.analyze_query(query)
            assert query_type == QueryType.CURRENT_EVENT, f"Failed for: {query}"
            print(f"✓ Current Event: {query} → {query_type.value} ({confidence:.2f})")
    
    def test_entity_based_query_detection(self, router):
        """Test detection of entity-based queries."""
        queries = [
            "Who is John Smith?",
            "Which company is mentioned in this document?",
            "What documents are by specific author?",
            "Find information about XYZ organization"
        ]
        
        for query in queries:
            query_type, confidence, reasoning = router.analyze_query(query)
            assert query_type == QueryType.ENTITY_BASED, f"Failed for: {query}"
            print(f"✓ Entity-based: {query} → {query_type.value} ({confidence:.2f})")
    
    def test_document_analysis_query_detection(self, router):
        """Test detection of document analysis queries."""
        queries = [
            "Analyze the document structure",
            "Compare these two documents",
            "What are the pros and cons?"
        ]
        
        for query in queries:
            query_type, confidence, reasoning = router.analyze_query(query)
            assert query_type == QueryType.DOCUMENT_ANALYSIS, f"Failed for: {query}"
            print(f"✓ Analysis: {query} → {query_type.value} ({confidence:.2f})")
    
    def test_general_query_fallback(self, router):
        """Test that general queries get classified."""
        queries = [
            "What is machine learning?",
            "Tell me more information",
            "I want to learn"
        ]
        
        for query in queries:
            query_type, confidence, reasoning = router.analyze_query(query)
            # Should classify to some type (testing that analysis doesn't crash)
            assert query_type in QueryType
            print(f"✓ General: {query} → {query_type.value} ({confidence:.2f})")
    
    def test_confidence_scoring(self, router):
        """Test that confidence scores are reasonable."""
        # High confidence - clear keywords
        _, high_conf, _ = router.analyze_query("How many rows are in the database?")
        
        # Low confidence - ambiguous
        _, low_conf, _ = router.analyze_query("Tell me something")
        
        assert high_conf > low_conf, "High confidence should be > low confidence"
        assert 0.0 <= high_conf <= 1.0, "Confidence should be in [0, 1]"
        assert 0.0 <= low_conf <= 1.0, "Confidence should be in [0, 1]"
        print(f"✓ Confidence scoring: high={high_conf:.2f}, low={low_conf:.2f}")


class TestToolSelection:
    """Test tool selection logic."""
    
    @pytest.fixture
    def router(self):
        return AgentRouter()
    
    def test_structured_routes_to_sql(self, router):
        """Structured queries should route to SQL."""
        tool = router.select_tool(QueryType.STRUCTURED)
        assert tool == ToolType.SQL
        print(f"✓ STRUCTURED → {tool.value}")
    
    def test_current_event_routes_to_web_search(self, router):
        """Current event queries should route to web search."""
        tool = router.select_tool(QueryType.CURRENT_EVENT)
        assert tool == ToolType.WEB_SEARCH
        print(f"✓ CURRENT_EVENT → {tool.value}")
    
    def test_entity_routes_to_metadata_or_vector(self, router):
        """Entity queries should route to metadata or vector."""
        tool = router.select_tool(QueryType.ENTITY_BASED)
        assert tool in [ToolType.METADATA, ToolType.HYBRID, ToolType.VECTOR]
        print(f"✓ ENTITY_BASED → {tool.value}")
    
    def test_analysis_routes_to_vector(self, router):
        """Analysis queries should route to vector/hybrid."""
        tool = router.select_tool(QueryType.DOCUMENT_ANALYSIS)
        assert tool in [ToolType.VECTOR, ToolType.HYBRID]
        print(f"✓ DOCUMENT_ANALYSIS → {tool.value}")
    
    def test_general_routes_to_hybrid_or_vector(self, router):
        """General queries should route to hybrid or vector."""
        tool = router.select_tool(QueryType.GENERAL)
        assert tool in [ToolType.VECTOR, ToolType.HYBRID]
        print(f"✓ GENERAL → {tool.value}")
    
    def test_hybrid_search_disabled(self, router):
        """Test tool selection when hybrid is disabled."""
        tool = router.select_tool(QueryType.GENERAL, use_hybrid=False)
        assert tool == ToolType.VECTOR
        print(f"✓ GENERAL (no hybrid) → {tool.value}")


class TestFallbackChains:
    """Test fallback chain creation."""
    
    @pytest.fixture
    def router(self):
        return AgentRouter()
    
    def test_sql_fallback_chain(self, router):
        """SQL should have fallback chain."""
        # Fallback chains are only populated if tools are registered
        # Test that the method works without error
        chain = router.create_fallback_chain(ToolType.SQL, QueryType.STRUCTURED)
        assert isinstance(chain, list)  # Should return a list
        assert ToolType.SQL not in chain  # Primary not in fallbacks
        print(f"✓ SQL chain: {[t.value for t in chain]}")
    
    def test_web_search_fallback_chain(self, router):
        """Web search should have fallback chain."""
        chain = router.create_fallback_chain(ToolType.WEB_SEARCH, QueryType.CURRENT_EVENT)
        assert isinstance(chain, list)
        assert ToolType.WEB_SEARCH not in chain
        print(f"✓ Web search chain: {[t.value for t in chain]}")
    
    def test_vector_fallback_chain(self, router):
        """Vector should have fallback chain."""
        chain = router.create_fallback_chain(ToolType.VECTOR, QueryType.GENERAL)
        assert isinstance(chain, list)
        assert ToolType.VECTOR not in chain
        print(f"✓ Vector chain: {[t.value for t in chain]}")
    
    def test_fallback_chain_contains_only_available_tools(self, router):
        """Fallback chains should only contain registered tools."""
        router.register_tool(ToolType.VECTOR, MockTool("vector"))
        chain = router.create_fallback_chain(ToolType.SQL, QueryType.STRUCTURED)
        
        # Chain should only have registered tools (just VECTOR in this case)
        for tool in chain:
            assert tool in [ToolType.VECTOR]  # Only VECTOR registered
        print(f"✓ Fallback chain with limited tools: {[t.value for t in chain]}")
    
    def test_all_query_types_have_fallback_chains(self, router):
        """All query types should produce fallback chains."""
        for query_type in QueryType:
            tool = router.select_tool(query_type)
            chain = router.create_fallback_chain(tool, query_type)
            assert isinstance(chain, list)
            print(f"✓ {query_type.value} fallback chain: {len(chain)} tools")


class TestRoutingDecisions:
    """Test complete routing decisions."""
    
    @pytest.fixture
    def router(self):
        return AgentRouter()
    
    def test_routing_decision_creation(self, router):
        """Test creating a routing decision."""
        decision = router.route_query("How many documents are there?")
        
        assert decision.query_type == QueryType.STRUCTURED
        assert decision.primary_tool == ToolType.SQL
        assert decision.confidence >= 0.3
        assert len(decision.reasoning) > 0
        print(f"✓ Routing decision: {decision.query_type.value} → {decision.primary_tool.value}")
    
    def test_routing_decision_to_dict(self, router):
        """Test converting routing decision to dictionary."""
        decision = router.route_query("What happened today?")
        result = decision.to_dict()
        
        assert 'query_type' in result
        assert 'primary_tool' in result
        assert 'fallback_tools' in result
        assert 'confidence' in result
        assert 'reasoning' in result
        assert 'timestamp' in result
        print(f"✓ Routing decision dict: {result}")
    
    def test_routing_includes_metadata(self, router):
        """Test that routing includes proper metadata."""
        decision = router.route_query("Search for information", context={'use_hybrid': False})
        
        assert decision.confidence >= 0.0 and decision.confidence <= 1.0
        assert isinstance(decision.fallback_tools, list)
        print(f"✓ Routing metadata complete")
    
    def test_multiple_queries_have_different_routing(self, router):
        """Different queries should get different routing."""
        decision1 = router.route_query("Count all rows")
        decision2 = router.route_query("What's new today?")
        
        assert decision1.query_type != decision2.query_type
        assert decision1.primary_tool != decision2.primary_tool
        print(f"✓ Different queries get different routing")


class TestToolExecution:
    """Test tool execution with fallbacks."""
    
    @pytest.fixture
    def router(self):
        router = AgentRouter()
        # Register mock tools
        router.register_tool(ToolType.VECTOR, MockTool("vector", should_succeed=True))
        router.register_tool(ToolType.SQL, MockTool("sql", should_succeed=False))
        router.register_tool(ToolType.WEB_SEARCH, MockTool("web", should_succeed=True))
        return router
    
    @pytest.mark.asyncio
    async def test_tool_sequence_execution(self, router):
        """Test executing a sequence of tools."""
        tools = [ToolType.SQL, ToolType.VECTOR]
        result = await router.execute_tool_sequence(tools, "test query")
        
        assert result['success']
        assert result['tool_used'] == ToolType.VECTOR.value
        assert ToolType.SQL.value in result['tools_tried']
        assert ToolType.VECTOR.value in result['tools_tried']
        print(f"✓ Tool sequence execution: tried {result['tools_tried']}, used {result['tool_used']}")
    
    @pytest.mark.asyncio
    async def test_tool_fallback_on_failure(self, router):
        """Test fallback to next tool when primary fails."""
        tools = [ToolType.SQL, ToolType.VECTOR]  # SQL fails, should fall back to vector
        result = await router.execute_tool_sequence(tools, "test query")
        
        assert result['success']
        assert result['tool_used'] == ToolType.VECTOR.value
        print(f"✓ Fallback on failure: {result['tool_used']}")
    
    @pytest.mark.asyncio
    async def test_all_tools_failed(self, router):
        """Test handling when all registered tools fail."""
        # Create router with only failing SQL tool
        router2 = AgentRouter()
        router2.register_tool(ToolType.SQL, MockTool("sql", should_succeed=False))
        
        # Only try SQL - no fallbacks available
        result = await router2.execute_tool_sequence(
            [ToolType.SQL], 
            "test"
        )
        
        assert not result['success']
        assert result['error'] is not None
        assert ToolType.SQL.value in result['tools_tried']
        print(f"✓ All tools failed handling: {result['error']}")


class TestEdgeCases:
    """Test edge cases and ambiguous queries."""
    
    @pytest.fixture
    def router(self):
        return AgentRouter()
    
    def test_empty_query(self, router):
        """Test handling of empty query."""
        query_type, confidence, _ = router.analyze_query("")
        assert query_type in QueryType
        print(f"✓ Empty query handled: {query_type.value} ({confidence:.2f})")
    
    def test_very_long_query(self, router):
        """Test handling of very long query."""
        long_query = "What is " + "very " * 100 + "detailed information?"
        query_type, confidence, _ = router.analyze_query(long_query)
        assert query_type in QueryType
        print(f"✓ Long query handled: {query_type.value}")
    
    def test_mixed_keywords_query(self, router):
        """Test query with mixed keywords from multiple types."""
        # Query with both structured and event keywords
        query = "Count how many recent documents were added today"
        query_type, confidence, _ = router.analyze_query(query)
        assert query_type in QueryType
        print(f"✓ Mixed keywords: {query_type.value} ({confidence:.2f})")
    
    def test_case_insensitivity(self, router):
        """Test that query analysis is case insensitive."""
        query1 = "How Many Rows In Database?"
        query2 = "how many rows in database?"
        
        type1, conf1, _ = router.analyze_query(query1)
        type2, conf2, _ = router.analyze_query(query2)
        
        assert type1 == type2
        print(f"✓ Case insensitive analysis: {type1.value}")
    
    def test_special_characters_in_query(self, router):
        """Test handling special characters."""
        query = "How many #records $are& in (database)?"
        query_type, confidence, _ = router.analyze_query(query)
        assert query_type in QueryType
        print(f"✓ Special characters handled: {query_type.value}")


class TestToolRegistration:
    """Test tool registration and availability."""
    
    @pytest.fixture
    def router(self):
        return AgentRouter()
    
    def test_register_tool(self, router):
        """Test registering a tool."""
        tool = MockTool("test")
        router.register_tool(ToolType.SQL, tool)
        
        assert router.is_tool_available(ToolType.SQL)
        assert router.tools_registry[ToolType.SQL] == tool
        print(f"✓ Tool registered: {ToolType.SQL.value}")
    
    def test_tool_availability_check(self, router):
        """Test checking if tool is available."""
        router.register_tool(ToolType.SQL, MockTool("sql"))
        
        assert router.is_tool_available(ToolType.SQL)
        assert not router.is_tool_available(ToolType.WEB_SEARCH)
        print(f"✓ Tool availability check works")
    
    def test_get_tool_info(self, router):
        """Test getting tool information."""
        router.register_tool(ToolType.VECTOR, MockTool("vector"))
        router.register_tool(ToolType.SQL, MockTool("sql"))
        
        info = router.get_tool_info()
        
        assert 'registered_tools' in info
        assert 'query_types' in info
        assert 'tool_types' in info
        assert len(info['registered_tools']) == 2
        print(f"✓ Tool info retrieved: {len(info['registered_tools'])} tools registered")


def test_global_router_instance():
    """Test that global router instance is available."""
    assert agent_router is not None
    assert isinstance(agent_router, AgentRouter)
    print(f"✓ Global router instance available")


def test_routing_consistency():
    """Test that routing is consistent for same query."""
    router = AgentRouter()
    
    query = "How many documents are in the database?"
    decision1 = router.route_query(query)
    decision2 = router.route_query(query)
    
    assert decision1.query_type == decision2.query_type
    assert decision1.primary_tool == decision2.primary_tool
    assert decision1.confidence == decision2.confidence
    print(f"✓ Routing is consistent")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])
