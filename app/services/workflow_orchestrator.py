"""
Multi-Tool Workflow Orchestration for Agentic RAG (Sprint 4, Group 3, Task 2).

Orchestrates intelligent execution of multiple tools in sequences, with:
- Sequential and parallel execution modes
- Conditional tool execution based on previous results
- Automatic retry with exponential backoff
- Comprehensive timeout and error handling
- Execution history tracking and metrics collection
- Fallback chains for robustness

Workflow Model:
    Input Query
    ↓
    [Route via AgentRouter]
    ↓
    [Primary Tool] → Success? → Return Result
        ↓ Failure
    [Fallback 1] → Success? → Return Result
        ↓ Failure
    [Fallback 2] → Success? → Return Result
        ↓ Failure
    [Error Handler] → Return Graceful Degradation
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Coroutine, Tuple
import logging
import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Available tool types for orchestration."""
    VECTOR = "vector"
    HYBRID = "hybrid"
    SQL = "sql"
    WEB_SEARCH = "web_search"
    METADATA = "metadata"


class ExecutionMode(Enum):
    """Execution modes for tool sequences."""
    SEQUENTIAL = "sequential"  # Execute tools one-by-one, stop on success
    PARALLEL = "parallel"  # Execute all tools concurrently, gather results
    CONDITIONAL = "conditional"  # Execute based on conditions


class ToolStatus(Enum):
    """Status of tool execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    max_retries: int = 2
    backoff_factor: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 30.0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


@dataclass
class ToolExecution:
    """Single tool execution result."""
    tool_type: ToolType
    status: ToolStatus = ToolStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    total_duration: float = 0.0
    
    def duration(self) -> float:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tool_type': self.tool_type.value,
            'status': self.status.value,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'result': self.result,
            'error': self.error,
            'attempts': self.attempts,
            'duration': self.duration()
        }


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""
    workflow_name: str
    execution_mode: ExecutionMode
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    success: bool = False
    primary_result: Optional[Dict[str, Any]] = None
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    executions: List[ToolExecution] = field(default_factory=list)
    execution_history: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    def total_duration(self) -> float:
        """Total workflow duration."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return time.time() - self.started_at
    
    def successful_executions(self) -> List[ToolExecution]:
        """Get list of successful executions."""
        return [e for e in self.executions if e.status == ToolStatus.SUCCESS]
    
    def failed_executions(self) -> List[ToolExecution]:
        """Get list of failed executions."""
        return [e for e in self.executions if e.status == ToolStatus.FAILED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'workflow_name': self.workflow_name,
            'execution_mode': self.execution_mode.value,
            'success': self.success,
            'duration': self.total_duration(),
            'primary_result': self.primary_result,
            'all_results': self.all_results,
            'executions': [e.to_dict() for e in self.executions],
            'error': self.error,
            'history': self.execution_history
        }


class Workflow:
    """Defines a sequence of tools to execute with configuration."""
    
    def __init__(
        self,
        name: str,
        tools: List[ToolType],
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        timeout: Optional[float] = None,
        retry_config: Optional[RetryConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        condition_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ):
        """
        Initialize workflow.
        
        Args:
            name: Workflow name for identification
            tools: List of tools to execute
            mode: Execution mode (sequential/parallel/conditional)
            timeout: Timeout in seconds for entire workflow
            retry_config: Retry configuration
            context: Initial context to pass between tools
            condition_fn: Function to determine if workflow should proceed
        """
        self.name = name
        self.tools = tools
        self.mode = mode
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.context = context or {}
        self.condition_fn = condition_fn
    
    def should_proceed(self) -> bool:
        """Check if workflow should proceed."""
        if self.condition_fn:
            return self.condition_fn(self.context)
        return True


class ToolHandler(ABC):
    """Abstract base class for tool handlers."""
    
    @abstractmethod
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool.
        
        Args:
            query: Input query
            context: Execution context
            
        Returns:
            Result dictionary with success, result, and metadata
        """
        pass


class WorkflowOrchestrator:
    """
    Orchestrates intelligent execution of multiple tools with advanced features:
    - Sequential, parallel, and conditional execution
    - Automatic retry with exponential backoff
    - Timeout management
    - Error recovery with fallbacks
    - Execution history and metrics tracking
    - Context passing between tools
    """
    
    def __init__(self, default_timeout: float = 30.0):
        """
        Initialize orchestrator.
        
        Args:
            default_timeout: Default timeout for tool execution in seconds
        """
        self.default_timeout = default_timeout
        self.tools: Dict[ToolType, ToolHandler] = {}
        self.execution_history: List[WorkflowResult] = []
        self.metrics: Dict[str, Any] = {
            'total_workflows': 0,
            'successful_workflows': 0,
            'failed_workflows': 0,
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_duration': 0.0,
            'average_duration': 0.0,
            'total_retries': 0
        }
        logger.info("WorkflowOrchestrator initialized")
    
    def add_tool(self, tool_type: ToolType, handler: ToolHandler) -> None:
        """
        Register a tool handler.
        
        Args:
            tool_type: Type of tool
            handler: Handler instance
        """
        self.tools[tool_type] = handler
        logger.info(f"Tool registered: {tool_type.value}")
    
    def remove_tool(self, tool_type: ToolType) -> None:
        """Remove a tool handler."""
        if tool_type in self.tools:
            del self.tools[tool_type]
            logger.info(f"Tool removed: {tool_type.value}")
    
    async def execute_sequential(
        self,
        workflow: Workflow,
        query: str
    ) -> WorkflowResult:
        """
        Execute tools sequentially, stopping on first success.
        
        Args:
            workflow: Workflow definition
            query: Input query
            
        Returns:
            WorkflowResult with execution details
        """
        result = WorkflowResult(
            workflow_name=workflow.name,
            execution_mode=ExecutionMode.SEQUENTIAL
        )
        
        # Check condition
        if not workflow.should_proceed():
            result.execution_history.append("Workflow condition not met, skipping")
            logger.info(f"Workflow {workflow.name} skipped due to condition")
            return result
        
        start_time = time.time()
        context = workflow.context.copy()
        
        try:
            for tool_type in workflow.tools:
                if not self._tool_available(tool_type):
                    msg = f"Tool {tool_type.value} not registered"
                    result.execution_history.append(msg)
                    logger.warning(msg)
                    continue
                
                # Execute with retry
                execution = await self._execute_with_retry(
                    tool_type=tool_type,
                    query=query,
                    context=context,
                    retry_config=workflow.retry_config,
                    timeout=workflow.timeout or self.default_timeout
                )
                
                result.executions.append(execution)
                context['last_result'] = execution.result
                
                if execution.status == ToolStatus.SUCCESS:
                    result.success = True
                    result.primary_result = execution.result
                    result.all_results.append(execution.result)
                    result.execution_history.append(
                        f"Tool {tool_type.value} succeeded (attempt {execution.attempts})"
                    )
                    logger.info(f"Workflow {workflow.name} succeeded with {tool_type.value}")
                    break
                else:
                    result.execution_history.append(
                        f"Tool {tool_type.value} failed: {execution.error}"
                    )
                    logger.warning(
                        f"Tool {tool_type.value} failed: {execution.error}"
                    )
            
            if not result.success and result.executions:
                result.error = "All tools failed"
                logger.error(f"Workflow {workflow.name} failed: all tools exhausted")
        
        except Exception as e:
            result.error = str(e)
            logger.exception(f"Workflow {workflow.name} error: {e}")
        
        finally:
            result.completed_at = time.time()
            self.execution_history.append(result)
            self._update_metrics(result)
        
        return result
    
    async def execute_parallel(
        self,
        workflow: Workflow,
        query: str
    ) -> WorkflowResult:
        """
        Execute multiple tools in parallel, gathering all results.
        
        Args:
            workflow: Workflow definition
            query: Input query
            
        Returns:
            WorkflowResult with all execution results
        """
        result = WorkflowResult(
            workflow_name=workflow.name,
            execution_mode=ExecutionMode.PARALLEL
        )
        
        if not workflow.should_proceed():
            result.execution_history.append("Workflow condition not met, skipping")
            return result
        
        context = workflow.context.copy()
        
        try:
            # Create tasks for all tools
            tasks = []
            for tool_type in workflow.tools:
                if not self._tool_available(tool_type):
                    result.execution_history.append(f"Tool {tool_type.value} not registered")
                    continue
                
                task = self._execute_with_retry(
                    tool_type=tool_type,
                    query=query,
                    context=context,
                    retry_config=workflow.retry_config,
                    timeout=workflow.timeout or self.default_timeout
                )
                tasks.append(task)
            
            # Execute all tasks concurrently
            if tasks:
                executions = await asyncio.gather(*tasks, return_exceptions=True)
                
                for execution in executions:
                    if isinstance(execution, Exception):
                        result.execution_history.append(f"Task error: {str(execution)}")
                        logger.exception("Parallel execution error")
                        continue
                    
                    result.executions.append(execution)
                    
                    if execution.status == ToolStatus.SUCCESS:
                        result.success = True
                        result.all_results.append(execution.result)
                        result.execution_history.append(
                            f"Tool {execution.tool_type.value} succeeded"
                        )
                    else:
                        result.execution_history.append(
                            f"Tool {execution.tool_type.value} failed: {execution.error}"
                        )
                
                # Set primary result from first successful execution
                if result.all_results:
                    result.primary_result = result.all_results[0]
                    logger.info(f"Workflow {workflow.name} completed with {len(result.all_results)} results")
        
        except Exception as e:
            result.error = str(e)
            logger.exception(f"Workflow {workflow.name} error: {e}")
        
        finally:
            result.completed_at = time.time()
            self.execution_history.append(result)
            self._update_metrics(result)
        
        return result
    
    async def execute_with_fallback(
        self,
        primary_tool: ToolType,
        fallback_tools: List[ToolType],
        query: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retry_config: Optional[RetryConfig] = None
    ) -> WorkflowResult:
        """
        Execute primary tool with fallback chain.
        
        Args:
            primary_tool: Primary tool to attempt first
            fallback_tools: List of fallback tools in order
            query: Input query
            context: Execution context
            timeout: Timeout for each tool
            retry_config: Retry configuration
            
        Returns:
            WorkflowResult with execution details
        """
        tools = [primary_tool] + fallback_tools
        workflow = Workflow(
            name=f"fallback_chain_{primary_tool.value}",
            tools=tools,
            mode=ExecutionMode.SEQUENTIAL,
            timeout=timeout,
            retry_config=retry_config,
            context=context
        )
        
        return await self.execute_sequential(workflow, query)
    
    async def execute_with_retry(
        self,
        tool_type: ToolType,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
        timeout: Optional[float] = None
    ) -> ToolExecution:
        """
        Execute a single tool with retry logic.
        
        Args:
            tool_type: Tool to execute
            query: Input query
            context: Execution context
            max_retries: Maximum retry attempts
            timeout: Timeout for execution
            
        Returns:
            ToolExecution with result
        """
        retry_config = RetryConfig(max_retries=max_retries)
        return await self._execute_with_retry(
            tool_type=tool_type,
            query=query,
            context=context or {},
            retry_config=retry_config,
            timeout=timeout or self.default_timeout
        )
    
    async def _execute_with_retry(
        self,
        tool_type: ToolType,
        query: str,
        context: Dict[str, Any],
        retry_config: RetryConfig,
        timeout: float
    ) -> ToolExecution:
        """Internal method to execute tool with retry logic."""
        execution = ToolExecution(tool_type=tool_type)
        execution.started_at = time.time()
        
        for attempt in range(retry_config.max_retries + 1):
            execution.attempts = attempt + 1
            execution.status = ToolStatus.RUNNING
            
            try:
                handler = self.tools.get(tool_type)
                if not handler:
                    execution.error = f"Tool {tool_type.value} not registered"
                    execution.status = ToolStatus.FAILED
                    execution.completed_at = time.time()
                    logger.error(execution.error)
                    break
                
                # Execute with timeout
                try:
                    result = await asyncio.wait_for(
                        handler.execute(query, context),
                        timeout=timeout
                    )
                    
                    if isinstance(result, dict):
                        if result.get('success', True):
                            execution.result = result
                            execution.status = ToolStatus.SUCCESS
                            execution.completed_at = time.time()
                            logger.info(f"Tool {tool_type.value} succeeded on attempt {attempt + 1}")
                            self.metrics['total_retries'] += attempt
                            break
                        else:
                            execution.error = result.get('error', 'Tool returned failure')
                            # If last attempt, mark as failed
                            if attempt >= retry_config.max_retries:
                                execution.status = ToolStatus.FAILED
                                execution.completed_at = time.time()
                                break
                    else:
                        execution.result = {'result': result}
                        execution.status = ToolStatus.SUCCESS
                        execution.completed_at = time.time()
                        self.metrics['total_retries'] += attempt
                        break
                
                except asyncio.TimeoutError:
                    execution.error = f"Execution timeout after {timeout}s"
                    execution.completed_at = time.time()
                    logger.warning(f"Tool {tool_type.value} timeout on attempt {attempt + 1}")
                    
                    if attempt >= retry_config.max_retries:
                        execution.status = ToolStatus.TIMEOUT
                        break
                    
                    # Retry on timeout
                    delay = retry_config.get_delay(attempt)
                    logger.info(f"Retrying {tool_type.value} after {delay}s")
                    await asyncio.sleep(delay)
            
            except Exception as e:
                execution.error = str(e)
                execution.completed_at = time.time()
                logger.exception(f"Tool {tool_type.value} error on attempt {attempt + 1}")
                
                if attempt >= retry_config.max_retries:
                    execution.status = ToolStatus.FAILED
                    break
                
                # Retry on error
                delay = retry_config.get_delay(attempt)
                logger.info(f"Retrying {tool_type.value} after {delay}s")
                await asyncio.sleep(delay)
        
        # Ensure status is set to FAILED if still RUNNING
        if execution.status == ToolStatus.RUNNING:
            execution.status = ToolStatus.FAILED
            if not execution.completed_at:
                execution.completed_at = time.time()
        
        if execution.completed_at and execution.started_at:
            execution.total_duration = execution.completed_at - execution.started_at
        
        return execution
    
    def _tool_available(self, tool_type: ToolType) -> bool:
        """Check if tool is registered."""
        return tool_type in self.tools
    
    def _update_metrics(self, result: WorkflowResult) -> None:
        """Update execution metrics."""
        self.metrics['total_workflows'] += 1
        self.metrics['total_duration'] += result.total_duration()
        self.metrics['total_executions'] += len(result.executions)
        
        if result.success:
            self.metrics['successful_workflows'] += 1
        else:
            self.metrics['failed_workflows'] += 1
        
        for execution in result.executions:
            if execution.status == ToolStatus.SUCCESS:
                self.metrics['successful_executions'] += 1
            elif execution.status == ToolStatus.FAILED or execution.status == ToolStatus.TIMEOUT:
                self.metrics['failed_executions'] += 1
        
        if self.metrics['total_workflows'] > 0:
            self.metrics['average_duration'] = (
                self.metrics['total_duration'] / self.metrics['total_workflows']
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics."""
        return {
            **self.metrics,
            'success_rate': (
                self.metrics['successful_executions'] / self.metrics['total_executions']
                if self.metrics['total_executions'] > 0 else 0.0
            ),
            'workflow_success_rate': (
                self.metrics['successful_workflows'] / self.metrics['total_workflows']
                if self.metrics['total_workflows'] > 0 else 0.0
            )
        }
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get execution history."""
        return [result.to_dict() for result in self.execution_history]
    
    def clear_history(self) -> None:
        """Clear execution history."""
        self.execution_history.clear()
        logger.info("Execution history cleared")
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        self.metrics = {
            'total_workflows': 0,
            'successful_workflows': 0,
            'failed_workflows': 0,
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_duration': 0.0,
            'average_duration': 0.0,
            'total_retries': 0
        }
        logger.info("Metrics reset")


# Global orchestrator instance
orchestrator = WorkflowOrchestrator(default_timeout=30.0)
