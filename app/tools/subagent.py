"""
Base Sub-Agent class for specialized task delegation.

Sub-agents are isolated agents with their own:
- Tool set
- Context management
- Reasoning loop
- Results aggregation
"""
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import logging
import time

logger = logging.getLogger(__name__)


class SubAgentTask:
    """Represents a task to be executed by a sub-agent."""
    
    def __init__(
        self,
        task_id: str,
        task_type: str,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.query = query
        self.context = context or {}
        self.created_at = time.time()
        self.status = 'pending'  # pending, running, completed, failed
        self.result = None
        self.error = None


class SubAgent(ABC):
    """
    Base class for all sub-agents.
    
    Sub-agents are specialized agents that handle specific types of tasks
    in isolation from the main agent.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        max_iterations: int = 3
    ):
        """
        Initialize a sub-agent.
        
        Args:
            name: Sub-agent name
            description: What this sub-agent does
            max_iterations: Maximum reasoning iterations
        """
        self.name = name
        self.description = description
        self.max_iterations = max_iterations
        self.tools = []
        self.tasks = []  # Task history
        logger.info(f"Sub-agent initialized: {name}")
    
    @abstractmethod
    async def execute(
        self,
        task: SubAgentTask
    ) -> Dict[str, Any]:
        """
        Execute a task. Must be implemented by subclasses.
        
        Args:
            task: SubAgentTask to execute
            
        Returns:
            Dict with 'success', 'result', 'reasoning', 'tools_used'
        """
        pass
    
    def can_handle(self, task_type: str) -> bool:
        """
        Check if this sub-agent can handle a task type.
        
        Args:
            task_type: Type of task
            
        Returns:
            True if can handle, False otherwise
        """
        return task_type in self.get_supported_task_types()
    
    @abstractmethod
    def get_supported_task_types(self) -> List[str]:
        """
        Return list of task types this sub-agent supports.
        
        Returns:
            List of task type strings
        """
        pass
    
    def register_tool(self, tool: Any):
        """
        Register a tool with this sub-agent.
        
        Args:
            tool: Tool instance
        """
        self.tools.append(tool)
        logger.info(f"Sub-agent {self.name} registered tool: {tool.__class__.__name__}")
    
    def get_context_summary(self, task: SubAgentTask) -> str:
        """
        Generate a context summary for the sub-agent's reasoning.
        
        Args:
            task: Current task
            
        Returns:
            Context string
        """
        context_parts = [
            f"**Sub-Agent:** {self.name}",
            f"**Task Type:** {task.task_type}",
            f"**Query:** {task.query}",
        ]
        
        if task.context:
            context_parts.append("**Additional Context:**")
            for key, value in task.context.items():
                context_parts.append(f"- {key}: {value}")
        
        return "\n".join(context_parts)
    
    def log_task_start(self, task: SubAgentTask):
        """Log when a task starts."""
        task.status = 'running'
        self.tasks.append(task)
        logger.info(f"Sub-agent {self.name} starting task: {task.task_id}")
    
    def log_task_complete(self, task: SubAgentTask, result: Dict[str, Any]):
        """Log when a task completes."""
        task.status = 'completed'
        task.result = result
        logger.info(f"Sub-agent {self.name} completed task: {task.task_id}")
    
    def log_task_failed(self, task: SubAgentTask, error: str):
        """Log when a task fails."""
        task.status = 'failed'
        task.error = error
        logger.error(f"Sub-agent {self.name} task failed: {task.task_id} - {error}")
    
    def get_task_history(self) -> List[Dict[str, Any]]:
        """
        Get history of all tasks executed by this sub-agent.
        
        Returns:
            List of task summaries
        """
        return [
            {
                'task_id': task.task_id,
                'task_type': task.task_type,
                'query': task.query,
                'status': task.status,
                'created_at': task.created_at,
                'result': task.result,
                'error': task.error
            }
            for task in self.tasks
        ]
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about this sub-agent.
        
        Returns:
            Dict with name, description, supported tasks, tools
        """
        return {
            'name': self.name,
            'description': self.description,
            'supported_task_types': self.get_supported_task_types(),
            'tools': [tool.__class__.__name__ for tool in self.tools],
            'max_iterations': self.max_iterations,
            'tasks_completed': len([t for t in self.tasks if t.status == 'completed']),
            'tasks_failed': len([t for t in self.tasks if t.status == 'failed'])
        }


class FullDocumentSubAgent(SubAgent):
    """
    Sub-agent for full-document analysis tasks.
    
    Use when:
    - User asks to analyze an entire document
    - Need to read and process complete documents
    - Task requires document-level context
    """
    
    def __init__(self):
        super().__init__(
            name="FullDocumentAgent",
            description="Analyzes entire documents with full context",
            max_iterations=2
        )
    
    def get_supported_task_types(self) -> List[str]:
        return [
            'full_document_analysis',
            'document_summary',
            'document_qa'
        ]
    
    async def execute(self, task: SubAgentTask) -> Dict[str, Any]:
        """Execute full document analysis task."""
        self.log_task_start(task)
        
        try:
            # TODO: Implement full document analysis logic
            # This would:
            # 1. Retrieve all chunks for the document
            # 2. Combine them in order
            # 3. Perform analysis with full context
            # 4. Return structured results
            
            result = {
                'success': True,
                'result': 'Full document analysis not yet implemented',
                'reasoning': 'This sub-agent will analyze entire documents',
                'tools_used': []
            }
            
            self.log_task_complete(task, result)
            return result
            
        except Exception as e:
            self.log_task_failed(task, str(e))
            return {
                'success': False,
                'error': str(e),
                'result': None,
                'reasoning': 'Task execution failed',
                'tools_used': []
            }


class ComparisonSubAgent(SubAgent):
    """
    Sub-agent for comparing multiple documents or data sources.
    
    Use when:
    - User asks to compare documents
    - Need side-by-side analysis
    - Contrast analysis required
    """
    
    def __init__(self):
        super().__init__(
            name="ComparisonAgent",
            description="Compares and contrasts multiple documents or data",
            max_iterations=3
        )
    
    def get_supported_task_types(self) -> List[str]:
        return [
            'document_comparison',
            'contrast_analysis',
            'difference_detection'
        ]
    
    async def execute(self, task: SubAgentTask) -> Dict[str, Any]:
        """Execute comparison task."""
        self.log_task_start(task)
        
        try:
            # TODO: Implement comparison logic
            result = {
                'success': True,
                'result': 'Comparison analysis not yet implemented',
                'reasoning': 'This sub-agent will compare multiple documents',
                'tools_used': []
            }
            
            self.log_task_complete(task, result)
            return result
            
        except Exception as e:
            self.log_task_failed(task, str(e))
            return {
                'success': False,
                'error': str(e),
                'result': None,
                'reasoning': 'Task execution failed',
                'tools_used': []
            }


class ExtractionSubAgent(SubAgent):
    """
    Sub-agent for structured data extraction tasks.
    
    Use when:
    - User wants to extract specific information
    - Need structured data output
    - Parsing and extraction required
    """
    
    def __init__(self):
        super().__init__(
            name="ExtractionAgent",
            description="Extracts structured information from documents",
            max_iterations=2
        )
    
    def get_supported_task_types(self) -> List[str]:
        return [
            'data_extraction',
            'entity_extraction',
            'structured_output'
        ]
    
    async def execute(self, task: SubAgentTask) -> Dict[str, Any]:
        """Execute extraction task."""
        self.log_task_start(task)
        
        try:
            # TODO: Implement extraction logic
            result = {
                'success': True,
                'result': 'Data extraction not yet implemented',
                'reasoning': 'This sub-agent will extract structured data',
                'tools_used': []
            }
            
            self.log_task_complete(task, result)
            return result
            
        except Exception as e:
            self.log_task_failed(task, str(e))
            return {
                'success': False,
                'error': str(e),
                'result': None,
                'reasoning': 'Task execution failed',
                'tools_used': []
            }


# Pre-initialized sub-agents
full_document_agent = FullDocumentSubAgent()
comparison_agent = ComparisonSubAgent()
extraction_agent = ExtractionSubAgent()

# Sub-agent registry
SUBAGENT_REGISTRY = {
    'full_document': full_document_agent,
    'comparison': comparison_agent,
    'extraction': extraction_agent
}
