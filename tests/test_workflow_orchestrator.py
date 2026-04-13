"""
Comprehensive tests for WorkflowOrchestrator (Sprint 4, Group 3, Task 2).

Tests cover:
- Sequential execution
- Parallel execution
- Conditional execution
- Fallback chains
- Retry logic with exponential backoff
- Timeout handling
- Error recovery
- Metrics collection
- Real-world scenarios
"""

import pytest
import asyncio
import time
from typing import Dict, Any
from app.services.workflow_orchestrator import (
    WorkflowOrchestrator,
    Workflow,
    ToolHandler,
    ToolType,
    ExecutionMode,
    ToolStatus,
    RetryConfig,
    ToolExecution,
    WorkflowResult
)


# Mock tool handlers for testing
class MockSuccessHandler(ToolHandler):
    """Mock handler that always succeeds."""
    
    def __init__(self, delay: float = 0.1):
        self.delay = delay
        self.call_count = 0
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        self.call_count += 1
        await asyncio.sleep(self.delay)
        return {
            'success': True,
            'result': f'Result from {query}',
            'call_count': self.call_count
        }


class MockFailureHandler(ToolHandler):
    """Mock handler that always fails."""
    
    def __init__(self):
        self.call_count = 0
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        self.call_count += 1
        await asyncio.sleep(0.01)
        return {
            'success': False,
            'error': 'Tool failed',
            'call_count': self.call_count
        }


class MockRetryHandler(ToolHandler):
    """Mock handler that fails N times then succeeds."""
    
    def __init__(self, fail_count: int = 2):
        self.fail_count = fail_count
        self.call_count = 0
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        self.call_count += 1
        await asyncio.sleep(0.01)
        
        if self.call_count <= self.fail_count:
            return {
                'success': False,
                'error': f'Attempt {self.call_count} failed'
            }
        return {
            'success': True,
            'result': f'Succeeded after {self.call_count} attempts'
        }


class MockTimeoutHandler(ToolHandler):
    """Mock handler that times out."""
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(10)  # Sleep longer than timeout
        return {'success': True}


# Fixtures
@pytest.fixture
def orchestrator():
    """Create a fresh orchestrator for each test."""
    return WorkflowOrchestrator(default_timeout=5.0)


@pytest.fixture
def mock_handlers():
    """Create mock handlers for testing."""
    return {
        'success': MockSuccessHandler(delay=0.05),
        'failure': MockFailureHandler(),
        'retry': MockRetryHandler(fail_count=2),
        'timeout': MockTimeoutHandler()
    }


# Tests for Sequential Execution
class TestSequentialExecution:
    """Tests for sequential tool execution."""
    
    @pytest.mark.asyncio
    async def test_sequential_success_first_tool(self, orchestrator, mock_handlers):
        """Test sequential execution succeeds with first tool."""
        # Register handlers
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['success'])
        
        # Create workflow
        workflow = Workflow(
            name="test_sequential_success",
            tools=[ToolType.VECTOR, ToolType.HYBRID]
        )
        
        # Execute
        result = await orchestrator.execute_sequential(workflow, "test query")
        
        # Verify
        assert result.success
        assert result.primary_result is not None
        assert len(result.executions) == 1  # Should stop after first success
        assert result.executions[0].status == ToolStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_sequential_fallback_to_second_tool(self, orchestrator, mock_handlers):
        """Test sequential execution falls back to second tool."""
        # Register handlers
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['failure'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['success'])
        
        # Create workflow
        workflow = Workflow(
            name="test_sequential_fallback",
            tools=[ToolType.VECTOR, ToolType.HYBRID]
        )
        
        # Execute
        result = await orchestrator.execute_sequential(workflow, "test query")
        
        # Verify
        assert result.success
        assert len(result.executions) == 2
        assert result.executions[0].status == ToolStatus.FAILED
        assert result.executions[1].status == ToolStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_sequential_all_tools_fail(self, orchestrator, mock_handlers):
        """Test sequential execution when all tools fail."""
        # Register handlers
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['failure'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['failure'])
        
        # Create workflow
        workflow = Workflow(
            name="test_sequential_all_fail",
            tools=[ToolType.VECTOR, ToolType.HYBRID]
        )
        
        # Execute
        result = await orchestrator.execute_sequential(workflow, "test query")
        
        # Verify
        assert not result.success
        assert result.error is not None
        assert len(result.executions) == 2
        assert all(e.status == ToolStatus.FAILED for e in result.executions)


# Tests for Parallel Execution
class TestParallelExecution:
    """Tests for parallel tool execution."""
    
    @pytest.mark.asyncio
    async def test_parallel_all_success(self, orchestrator, mock_handlers):
        """Test parallel execution with all tools succeeding."""
        # Register handlers
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['success'])
        orchestrator.add_tool(ToolType.SQL, MockSuccessHandler())
        
        # Create workflow
        workflow = Workflow(
            name="test_parallel_all_success",
            tools=[ToolType.VECTOR, ToolType.HYBRID, ToolType.SQL],
            mode=ExecutionMode.PARALLEL
        )
        
        # Execute
        result = await orchestrator.execute_parallel(workflow, "test query")
        
        # Verify
        assert result.success
        assert len(result.all_results) == 3
        assert all(e.status == ToolStatus.SUCCESS for e in result.executions)
    
    @pytest.mark.asyncio
    async def test_parallel_mixed_success_failure(self, orchestrator, mock_handlers):
        """Test parallel execution with mixed results."""
        # Register handlers
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['failure'])
        orchestrator.add_tool(ToolType.SQL, mock_handlers['success'])
        
        # Create workflow
        workflow = Workflow(
            name="test_parallel_mixed",
            tools=[ToolType.VECTOR, ToolType.HYBRID, ToolType.SQL],
            mode=ExecutionMode.PARALLEL
        )
        
        # Execute
        result = await orchestrator.execute_parallel(workflow, "test query")
        
        # Verify
        assert result.success  # Has at least one success
        assert len(result.all_results) == 2  # 2 successes
        assert len(result.executions) == 3
    
    @pytest.mark.asyncio
    async def test_parallel_execution_speed(self, orchestrator, mock_handlers):
        """Test that parallel execution returns all results concurrently."""
        orchestrator.add_tool(ToolType.VECTOR, MockSuccessHandler(delay=0.05))
        orchestrator.add_tool(ToolType.HYBRID, MockSuccessHandler(delay=0.05))
        orchestrator.add_tool(ToolType.SQL, MockSuccessHandler(delay=0.05))
        
        # Parallel execution - gather all results
        workflow_par = Workflow(
            name="test_parallel",
            tools=[ToolType.VECTOR, ToolType.HYBRID, ToolType.SQL],
            mode=ExecutionMode.PARALLEL
        )
        result_par = await orchestrator.execute_parallel(workflow_par, "test")
        
        # Sequential execution - stop on first success
        workflow_seq = Workflow(
            name="test_sequential",
            tools=[ToolType.VECTOR, ToolType.HYBRID, ToolType.SQL],
            mode=ExecutionMode.SEQUENTIAL
        )
        result_seq = await orchestrator.execute_sequential(workflow_seq, "test")
        
        # Verify key differences:
        # Parallel executes all tools and returns all results
        assert len(result_par.all_results) == 3
        assert len(result_par.executions) == 3
        
        # Sequential stops after first success
        assert len(result_seq.all_results) == 1
        assert len(result_seq.executions) == 1


# Tests for Retry Logic
class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self, orchestrator, mock_handlers):
        """Test retry logic recovers after failures."""
        handler = MockRetryHandler(fail_count=1)
        orchestrator.add_tool(ToolType.VECTOR, handler)
        
        # Execute with retry
        execution = await orchestrator.execute_with_retry(
            tool_type=ToolType.VECTOR,
            query="test query",
            max_retries=2
        )
        
        # Verify
        assert execution.status == ToolStatus.SUCCESS
        assert execution.attempts == 2  # Failed once, succeeded on retry
        assert handler.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts(self, orchestrator, mock_handlers):
        """Test retry stops after max attempts."""
        handler = MockRetryHandler(fail_count=10)  # Will always fail
        orchestrator.add_tool(ToolType.VECTOR, handler)
        
        # Execute with limited retries
        execution = await orchestrator.execute_with_retry(
            tool_type=ToolType.VECTOR,
            query="test query",
            max_retries=2
        )
        
        # Verify
        assert execution.status == ToolStatus.FAILED
        assert execution.attempts == 3  # Initial + 2 retries
        assert handler.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_config_backoff(self, orchestrator):
        """Test retry config calculates backoff correctly."""
        config = RetryConfig(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            max_delay=10.0
        )
        
        # Verify backoff calculation
        assert config.get_delay(0) == 1.0
        assert config.get_delay(1) == 2.0
        assert config.get_delay(2) == 4.0
        assert config.get_delay(3) == 8.0
        assert config.get_delay(4) == 10.0  # Capped at max_delay
    
    @pytest.mark.asyncio
    async def test_workflow_retry_config(self, orchestrator, mock_handlers):
        """Test workflow with custom retry config."""
        handler = MockRetryHandler(fail_count=1)
        orchestrator.add_tool(ToolType.VECTOR, handler)
        
        retry_config = RetryConfig(max_retries=2, backoff_factor=1.0)
        workflow = Workflow(
            name="test_retry_workflow",
            tools=[ToolType.VECTOR],
            retry_config=retry_config
        )
        
        # Execute
        result = await orchestrator.execute_sequential(workflow, "test query")
        
        # Verify
        assert result.success
        assert result.executions[0].attempts == 2


# Tests for Timeout Handling
class TestTimeoutHandling:
    """Tests for timeout handling."""
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, orchestrator):
        """Test timeout is enforced."""
        orchestrator.add_tool(ToolType.VECTOR, MockTimeoutHandler())
        
        # Execute with short timeout
        execution = await orchestrator.execute_with_retry(
            tool_type=ToolType.VECTOR,
            query="test",
            timeout=0.1
        )
        
        # Verify
        assert execution.status == ToolStatus.TIMEOUT
        assert execution.error is not None
        assert 'timeout' in execution.error.lower()
    
    @pytest.mark.asyncio
    async def test_workflow_timeout(self, orchestrator):
        """Test workflow timeout configuration."""
        orchestrator.add_tool(ToolType.VECTOR, MockTimeoutHandler())
        
        workflow = Workflow(
            name="test_timeout_workflow",
            tools=[ToolType.VECTOR],
            timeout=0.1
        )
        
        result = await orchestrator.execute_sequential(workflow, "test")
        
        # Verify
        assert not result.success
        assert len(result.executions) > 0


# Tests for Fallback Chains
class TestFallbackChains:
    """Tests for fallback chain execution."""
    
    @pytest.mark.asyncio
    async def test_fallback_chain_primary_succeeds(self, orchestrator, mock_handlers):
        """Test fallback chain when primary succeeds."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['success'])
        orchestrator.add_tool(ToolType.SQL, mock_handlers['success'])
        
        # Execute fallback chain
        result = await orchestrator.execute_with_fallback(
            primary_tool=ToolType.VECTOR,
            fallback_tools=[ToolType.HYBRID, ToolType.SQL],
            query="test query"
        )
        
        # Verify - only primary should execute
        assert result.success
        assert len(result.executions) == 1
        assert result.executions[0].tool_type == ToolType.VECTOR
    
    @pytest.mark.asyncio
    async def test_fallback_chain_uses_fallbacks(self, orchestrator, mock_handlers):
        """Test fallback chain uses fallbacks when primary fails."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['failure'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['failure'])
        orchestrator.add_tool(ToolType.SQL, mock_handlers['success'])
        
        # Execute fallback chain
        result = await orchestrator.execute_with_fallback(
            primary_tool=ToolType.VECTOR,
            fallback_tools=[ToolType.HYBRID, ToolType.SQL],
            query="test query"
        )
        
        # Verify - should go through all until success
        assert result.success
        assert len(result.executions) == 3
        assert result.executions[2].status == ToolStatus.SUCCESS


# Tests for Metrics Collection
class TestMetricsCollection:
    """Tests for execution metrics tracking."""
    
    @pytest.mark.asyncio
    async def test_metrics_initialization(self, orchestrator):
        """Test metrics are initialized correctly."""
        metrics = orchestrator.get_metrics()
        
        assert metrics['total_workflows'] == 0
        assert metrics['successful_workflows'] == 0
        assert metrics['failed_workflows'] == 0
        assert metrics['total_executions'] == 0
    
    @pytest.mark.asyncio
    async def test_metrics_updated_on_success(self, orchestrator, mock_handlers):
        """Test metrics updated on workflow success."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        
        workflow = Workflow(name="test", tools=[ToolType.VECTOR])
        result = await orchestrator.execute_sequential(workflow, "test")
        
        metrics = orchestrator.get_metrics()
        
        assert metrics['total_workflows'] == 1
        assert metrics['successful_workflows'] == 1
        assert metrics['total_executions'] == 1
        assert metrics['successful_executions'] == 1
        assert metrics['workflow_success_rate'] == 1.0
    
    @pytest.mark.asyncio
    async def test_metrics_updated_on_failure(self, orchestrator, mock_handlers):
        """Test metrics updated on workflow failure."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['failure'])
        
        workflow = Workflow(name="test", tools=[ToolType.VECTOR])
        result = await orchestrator.execute_sequential(workflow, "test")
        
        metrics = orchestrator.get_metrics()
        
        assert metrics['total_workflows'] == 1
        assert metrics['failed_workflows'] == 1
        assert metrics['workflow_success_rate'] == 0.0
    
    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, orchestrator, mock_handlers):
        """Test metrics aggregate correctly."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['failure'])
        
        # Run multiple workflows
        workflow1 = Workflow(name="test1", tools=[ToolType.VECTOR])
        await orchestrator.execute_sequential(workflow1, "query1")
        
        workflow2 = Workflow(name="test2", tools=[ToolType.HYBRID])
        await orchestrator.execute_sequential(workflow2, "query2")
        
        metrics = orchestrator.get_metrics()
        
        assert metrics['total_workflows'] == 2
        assert metrics['successful_workflows'] == 1
        assert metrics['failed_workflows'] == 1
        assert metrics['workflow_success_rate'] == 0.5


# Tests for Conditional Execution
class TestConditionalExecution:
    """Tests for conditional workflow execution."""
    
    @pytest.mark.asyncio
    async def test_conditional_execution_proceeds(self, orchestrator, mock_handlers):
        """Test workflow proceeds when condition is true."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        
        workflow = Workflow(
            name="test_condition_true",
            tools=[ToolType.VECTOR],
            condition_fn=lambda ctx: True
        )
        
        result = await orchestrator.execute_sequential(workflow, "test")
        
        assert result.success
        assert len(result.executions) > 0
    
    @pytest.mark.asyncio
    async def test_conditional_execution_skips(self, orchestrator, mock_handlers):
        """Test workflow skips when condition is false."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        
        workflow = Workflow(
            name="test_condition_false",
            tools=[ToolType.VECTOR],
            condition_fn=lambda ctx: False
        )
        
        result = await orchestrator.execute_sequential(workflow, "test")
        
        assert not result.success
        assert len(result.executions) == 0


# Tests for History and Reset
class TestHistoryAndReset:
    """Tests for history tracking and reset."""
    
    @pytest.mark.asyncio
    async def test_execution_history_tracking(self, orchestrator, mock_handlers):
        """Test execution history is tracked."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        
        workflow = Workflow(name="test", tools=[ToolType.VECTOR])
        await orchestrator.execute_sequential(workflow, "test1")
        await orchestrator.execute_sequential(workflow, "test2")
        
        history = orchestrator.get_execution_history()
        
        assert len(history) == 2
        assert history[0]['success']
        assert history[1]['success']
    
    @pytest.mark.asyncio
    async def test_metrics_reset(self, orchestrator, mock_handlers):
        """Test metrics can be reset."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        
        workflow = Workflow(name="test", tools=[ToolType.VECTOR])
        await orchestrator.execute_sequential(workflow, "test")
        
        metrics = orchestrator.get_metrics()
        assert metrics['total_workflows'] > 0
        
        # Reset
        orchestrator.reset_metrics()
        
        metrics = orchestrator.get_metrics()
        assert metrics['total_workflows'] == 0


# Real-world scenario tests
class TestRealWorldScenarios:
    """Tests for realistic usage patterns."""
    
    @pytest.mark.asyncio
    async def test_primary_fallback_web_search_scenario(self, orchestrator, mock_handlers):
        """Test: Try vector search, fallback to web search."""
        # Vector search fails, web search succeeds
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['failure'])
        orchestrator.add_tool(ToolType.WEB_SEARCH, mock_handlers['success'])
        
        workflow = Workflow(
            name="smart_search",
            tools=[ToolType.VECTOR, ToolType.WEB_SEARCH]
        )
        
        result = await orchestrator.execute_sequential(workflow, "latest news")
        
        assert result.success
        assert len(result.executions) == 2
        assert result.executions[1].status == ToolStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_hybrid_approach_multiple_tools(self, orchestrator, mock_handlers):
        """Test: Try multiple tools in parallel for best results."""
        orchestrator.add_tool(ToolType.VECTOR, mock_handlers['success'])
        orchestrator.add_tool(ToolType.HYBRID, mock_handlers['success'])
        orchestrator.add_tool(ToolType.SQL, mock_handlers['success'])
        
        workflow = Workflow(
            name="comprehensive_search",
            tools=[ToolType.VECTOR, ToolType.HYBRID, ToolType.SQL],
            mode=ExecutionMode.PARALLEL
        )
        
        result = await orchestrator.execute_parallel(workflow, "comprehensive query")
        
        assert result.success
        assert len(result.all_results) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
