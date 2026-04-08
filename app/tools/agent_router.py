"""
Agent Router for multi-tool and sub-agent coordination.

Routes between:
- RAG retrieval (vector search)
- SQL queries (structured data)
- Web search (external information)
- Sub-agents (specialized tasks)
"""
from typing import Dict, Any, Optional, List
from enum import Enum
import logging
from app.services.llm import llm_service

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Available tool types."""
    RAG = "rag"
    SQL = "sql"
    WEB_SEARCH = "web_search"
    SUBAGENT = "subagent"


class AgentRouter:
    """
    Routes queries to appropriate tools or sub-agents based on intent classification.
    """
    
    def __init__(self):
        """Initialize the agent router."""
        self.tools = {}
        logger.info("AgentRouter initialized")
    
    def register_tool(self, tool_type: ToolType, tool_instance: Any):
        """
        Register a tool with the router.
        
        Args:
            tool_type: Type of tool (from ToolType enum)
            tool_instance: Instance of the tool
        """
        self.tools[tool_type] = tool_instance
        logger.info(f"Registered tool: {tool_type.value}")
    
    async def route(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route a query to the appropriate tool(s).
        
        Args:
            query: User query
            context: Optional context from previous iterations
            
        Returns:
            Dict with routing decision and tool recommendations
        """
        try:
            # Classify the query intent
            classification = await self._classify_query(query, context)
            
            # Determine which tools to use
            tool_plan = self._plan_tool_usage(classification)
            
            return {
                'success': True,
                'classification': classification,
                'tool_plan': tool_plan,
                'requires_multi_tool': len(tool_plan) > 1
            }
            
        except Exception as e:
            logger.error(f"Router error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'tool_plan': [ToolType.RAG]  # Default fallback
            }
    
    async def _classify_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify query intent using LLM.
        
        Args:
            query: User query
            context: Optional context
            
        Returns:
            Classification dict with intent, confidence, reasoning
        """
        prompt = f"""Classify the user's query intent for tool routing.

Available Tools:
1. **RAG (Vector Search)** - Semantic search in uploaded documents
2. **SQL (Database Query)** - Structured queries about document statistics, metadata
3. **Web Search** - External information not in knowledge base
4. **Sub-Agent** - Complex, multi-step tasks requiring specialized reasoning

Query: {query}

Analyze the query and determine:
1. Primary tool(s) needed (RAG, SQL, Web Search, or Sub-Agent)
2. Whether multiple tools are needed (sequential or parallel)
3. Confidence in this classification (0.0-1.0)
4. Brief reasoning

Examples:
- "What is machine learning?" → RAG (search documents)
- "How many PDFs do we have?" → SQL (database statistics)
- "What's the weather today?" → Web Search (real-time info)
- "Compare document A and B, then summarize" → Sub-Agent (complex task)
- "Find documents about X and tell me which is newest" → RAG + SQL (multi-tool)

Respond in JSON format:
{{
    "primary_tool": "rag|sql|web_search|subagent",
    "secondary_tools": ["tool1", "tool2"] or [],
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation",
    "is_analytical": true|false,
    "is_real_time": true|false,
    "is_complex": true|false
}}"""

        response = await llm_service.generate_text(
            prompt=prompt,
            max_tokens=300,
            temperature=0.1
        )
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
        
        try:
            classification = json.loads(response.strip())
            return classification
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse classification JSON: {response}")
            # Default to RAG
            return {
                'primary_tool': 'rag',
                'secondary_tools': [],
                'confidence': 0.5,
                'reasoning': 'Fallback to RAG (JSON parse failed)',
                'is_analytical': False,
                'is_real_time': False,
                'is_complex': False
            }
    
    def _plan_tool_usage(
        self,
        classification: Dict[str, Any]
    ) -> List[ToolType]:
        """
        Plan which tools to use based on classification.
        
        Args:
            classification: Query classification
            
        Returns:
            List of ToolType in execution order
        """
        tools = []
        
        # Map string to ToolType enum
        tool_map = {
            'rag': ToolType.RAG,
            'sql': ToolType.SQL,
            'web_search': ToolType.WEB_SEARCH,
            'subagent': ToolType.SUBAGENT
        }
        
        # Add primary tool
        primary = classification.get('primary_tool', 'rag')
        if primary in tool_map:
            tools.append(tool_map[primary])
        
        # Add secondary tools
        for secondary in classification.get('secondary_tools', []):
            if secondary in tool_map and tool_map[secondary] not in tools:
                tools.append(tool_map[secondary])
        
        # If no tools determined, default to RAG
        if not tools:
            tools.append(ToolType.RAG)
        
        logger.info(f"Tool plan: {[t.value for t in tools]}")
        return tools
    
    def should_use_subagent(self, classification: Dict[str, Any]) -> bool:
        """
        Determine if a sub-agent should be used.
        
        Args:
            classification: Query classification
            
        Returns:
            True if sub-agent recommended
        """
        # Use sub-agent for:
        # 1. Complex multi-step tasks
        if classification.get('is_complex', False):
            return True
        
        # 2. Tasks requiring multiple tools in sequence
        if len(classification.get('secondary_tools', [])) > 1:
            return True
        
        # 3. Explicit sub-agent classification
        if classification.get('primary_tool') == 'subagent':
            return True
        
        return False
    
    async def execute_multi_tool_workflow(
        self,
        query: str,
        tool_plan: List[ToolType],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow using multiple tools.
        
        Args:
            query: User query
            tool_plan: List of tools to use in order
            context: Optional context
            
        Returns:
            Combined results from all tools
        """
        results = {
            'query': query,
            'tools_used': [],
            'tool_results': [],
            'combined_context': '',
            'success': True
        }
        
        for tool_type in tool_plan:
            try:
                if tool_type not in self.tools:
                    logger.warning(f"Tool {tool_type.value} not registered, skipping")
                    continue
                
                tool = self.tools[tool_type]
                
                # Execute tool
                logger.info(f"Executing tool: {tool_type.value}")
                
                if tool_type == ToolType.RAG:
                    # RAG tool execution would be handled by retrieval service
                    result = {'tool': 'rag', 'note': 'Handled by retrieval service'}
                
                elif tool_type == ToolType.SQL:
                    result = await tool.execute(query)
                
                elif tool_type == ToolType.WEB_SEARCH:
                    result = await tool.execute(query)
                
                elif tool_type == ToolType.SUBAGENT:
                    result = {'tool': 'subagent', 'note': 'Sub-agent delegation not yet implemented'}
                
                results['tools_used'].append(tool_type.value)
                results['tool_results'].append(result)
                
            except Exception as e:
                logger.error(f"Tool execution error ({tool_type.value}): {e}")
                results['tool_results'].append({
                    'tool': tool_type.value,
                    'error': str(e),
                    'success': False
                })
        
        # Combine results into context
        results['combined_context'] = self._combine_tool_results(results['tool_results'])
        
        return results
    
    def _combine_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """
        Combine results from multiple tools into unified context.
        
        Args:
            tool_results: List of results from different tools
            
        Returns:
            Combined context string
        """
        context_parts = []
        
        for result in tool_results:
            if not result.get('success', True):
                continue
            
            # Format based on tool type
            if 'interpretation' in result:  # SQL tool
                context_parts.append(f"**Database Analysis:**\n{result['interpretation']}")
            
            elif 'results' in result:  # Web search tool
                if result['results']:
                    context_parts.append("**Web Search Results:**")
                    for r in result['results'][:3]:
                        context_parts.append(f"- {r.get('title')}: {r.get('snippet')}")
            
            elif 'data' in result:  # Generic data result
                context_parts.append(f"**Tool Result:**\n{str(result['data'])[:500]}")
        
        return "\n\n".join(context_parts)
    
    def get_available_tools(self) -> List[str]:
        """Get list of registered tools."""
        return [tool_type.value for tool_type in self.tools.keys()]


# Global instance
agent_router = AgentRouter()
