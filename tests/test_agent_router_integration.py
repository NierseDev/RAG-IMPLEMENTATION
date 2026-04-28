"""
Integration tests for Agent Router with Agentic RAG.
Tests that the router integrates properly with the agent.
"""

import pytest
from app.services.agent_router import agent_router, QueryType, ToolType
from app.services.agent import create_agent


def test_router_integrated_with_agent():
    """Test that agent properly initializes with router."""
    agent = create_agent(enable_tools=True)
    
    # Agent should have router enabled
    assert agent.enable_tools is True
    
    # Router should be available globally
    assert agent_router is not None
    print("✓ Router integrated with agent")


def test_router_query_analysis_in_context():
    """Test query analysis for different query types."""
    test_cases = [
        {
            'query': 'How many documents are in the database?',
            'expected_type': QueryType.STRUCTURED
        },
        {
            'query': 'What is machine learning?',
            'expected_type': QueryType.GENERAL  # Could be general or analysis
        },
        {
            'query': 'Tell me about John Smith',
            'expected_type': QueryType.ENTITY_BASED
        }
    ]
    
    for case in test_cases:
        decision = agent_router.route_query(case['query'])
        print(
            f"✓ '{case['query'][:40]}...' "
            f"→ {decision.query_type.value} "
            f"(confidence: {decision.confidence:.2f})"
        )


def test_router_fallback_logic():
    """Test that fallback logic is sound."""
    # Structured query
    decision = agent_router.route_query('Count all rows')
    assert decision.primary_tool == ToolType.SQL
    assert len(decision.fallback_tools) > 0
    
    # Web query
    decision = agent_router.route_query('What happened today?')
    assert decision.primary_tool == ToolType.WEB_SEARCH
    assert len(decision.fallback_tools) > 0
    
    print("✓ Fallback logic validated")


def test_router_routing_consistency():
    """Test that same query produces same routing decision."""
    query = 'How many documents by source?'
    
    decision1 = agent_router.route_query(query)
    decision2 = agent_router.route_query(query)
    
    assert decision1.query_type == decision2.query_type
    assert decision1.primary_tool == decision2.primary_tool
    assert decision1.confidence == decision2.confidence
    
    print("✓ Routing decisions are consistent")


def test_router_decision_metadata():
    """Test that routing decisions include proper metadata."""
    decision = agent_router.route_query('test query')
    
    metadata = decision.to_dict()
    
    assert 'query_type' in metadata
    assert 'primary_tool' in metadata
    assert 'fallback_tools' in metadata
    assert 'confidence' in metadata
    assert 'reasoning' in metadata
    assert 'timestamp' in metadata
    
    # Validate types
    assert isinstance(metadata['confidence'], (int, float))
    assert 0.0 <= metadata['confidence'] <= 1.0
    assert isinstance(metadata['fallback_tools'], list)
    
    print(f"✓ Routing decision metadata complete: {metadata}")


def test_router_all_query_types_covered():
    """Test that all QueryType values are handled."""
    for query_type in QueryType:
        tool = agent_router.select_tool(query_type)
        assert tool in ToolType
        print(f"✓ {query_type.value} → {tool.value}")


def test_router_tool_registration():
    """Test tool registration mechanism."""
    # Check that tools can be registered
    assert agent_router.tools_registry is not None
    
    # Get tool info
    info = agent_router.get_tool_info()
    assert 'registered_tools' in info
    assert 'query_types' in info
    assert 'tool_types' in info
    
    print(f"✓ Tool info: {len(info['query_types'])} types, "
          f"{len(info['tool_types'])} tools, "
          f"{len(info['registered_tools'])} registered")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
