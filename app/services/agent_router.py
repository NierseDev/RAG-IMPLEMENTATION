"""
Intelligent Tool Router for Agentic RAG System (Sprint 4, Group 3).

Analyzes queries and routes them to the optimal tools:
- Vector retrieval for semantic search
- SQL queries for structured data
- Web search for current/external information
- Metadata filters for entity-based retrieval

Features:
- Query type classification with confidence scoring
- Intelligent tool selection with fallback chains
- Extensible routing logic for new tools
- Comprehensive logging for debugging
- Integration with metadata filters and hybrid search
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Query classification types for routing decisions."""
    STRUCTURED = "structured"  # SQL queries - table, database, rows, count, sum
    CURRENT_EVENT = "current_event"  # Web search - today, latest, current, news
    ENTITY_BASED = "entity_based"  # Metadata + vector - specific entities
    DOCUMENT_ANALYSIS = "document_analysis"  # Vector with full context - analyze, summarize, compare
    GENERAL = "general"  # Default - vector + hybrid search


class ToolType(Enum):
    """Available tools for query execution."""
    VECTOR = "vector"  # Vector similarity search
    HYBRID = "hybrid"  # Vector + keyword hybrid search
    SQL = "sql"  # Structured data queries
    WEB_SEARCH = "web_search"  # Web search fallback
    METADATA = "metadata"  # Metadata filtering


class RoutingDecision:
    """Encapsulates a routing decision with confidence and reasoning."""
    
    def __init__(
        self,
        query_type: QueryType,
        primary_tool: ToolType,
        fallback_tools: Optional[List[ToolType]] = None,
        confidence: float = 0.5,
        reasoning: str = ""
    ):
        self.query_type = query_type
        self.primary_tool = primary_tool
        self.fallback_tools = fallback_tools or []
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        self.reasoning = reasoning
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert routing decision to dictionary for response inclusion."""
        return {
            'query_type': self.query_type.value,
            'primary_tool': self.primary_tool.value,
            'fallback_tools': [t.value for t in self.fallback_tools],
            'confidence': round(self.confidence, 2),
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat()
        }


class AgentRouter:
    """
    Intelligent router that analyzes queries and selects appropriate tools.
    
    Decision logic:
    1. Analyze query for keywords and patterns
    2. Classify into QueryType with confidence score
    3. Select primary tool based on type
    4. Build fallback chain for robustness
    5. Return routing decision with metadata
    """
    
    # Query analysis keywords
    STRUCTURED_KEYWORDS = {
        'table', 'database', 'rows', 'count', 'sum', 'total', 'how many',
        'statistical', 'aggregate', 'statistics', 'report', 'data analysis',
        'query', 'column', 'schema'
    }
    
    CURRENT_EVENT_KEYWORDS = {
        'today', 'now', 'latest', 'current', 'news', 'recent', 'breaking',
        'just happened', 'just released', 'just announced', 'this week',
        'today\'s', 'tomorrow', 'yesterday', 'tonight', 'live', 'update'
    }
    
    ENTITY_KEYWORDS = {
        'who', 'which', 'specific', 'particular', 'named', 'called',
        'from', 'by', 'author', 'company', 'person', 'organization',
        'entity', 'tell me about'
    }
    
    ANALYSIS_KEYWORDS = {
        'analyze', 'summarize', 'summary', 'compare', 'contrast', 'difference',
        'advantage', 'disadvantage', 'evaluate', 'assessment', 'review', 'critical',
        'pros and cons', 'strengths', 'weaknesses', 'implications'
    }
    
    def __init__(self):
        """Initialize the agent router."""
        self.tools_registry: Dict[ToolType, Any] = {}
        logger.info("AgentRouter initialized")
    
    def register_tool(self, tool_type: ToolType, tool_instance: Any) -> None:
        """
        Register a tool with the router.
        
        Args:
            tool_type: Type of tool
            tool_instance: Tool instance or callable
        """
        self.tools_registry[tool_type] = tool_instance
        logger.info(f"Tool registered: {tool_type.value}")
    
    def is_tool_available(self, tool_type: ToolType) -> bool:
        """Check if a tool is registered."""
        return tool_type in self.tools_registry
    
    def analyze_query(self, question: str) -> Tuple[QueryType, float, str]:
        """
        Analyze query to determine type and classify with confidence score.
        
        Args:
            question: User's query
            
        Returns:
            Tuple of (QueryType, confidence_score, analysis_reasoning)
        """
        question_lower = question.lower()
        
        # Calculate keyword matches for each type
        structured_score = self._calculate_match_score(
            question_lower, self.STRUCTURED_KEYWORDS
        )
        current_score = self._calculate_match_score(
            question_lower, self.CURRENT_EVENT_KEYWORDS
        )
        entity_score = self._calculate_match_score(
            question_lower, self.ENTITY_KEYWORDS
        )
        analysis_score = self._calculate_match_score(
            question_lower, self.ANALYSIS_KEYWORDS
        )
        
        # Determine dominant type with confidence
        scores = {
            QueryType.STRUCTURED: structured_score,
            QueryType.CURRENT_EVENT: current_score,
            QueryType.ENTITY_BASED: entity_score,
            QueryType.DOCUMENT_ANALYSIS: analysis_score,
        }
        
        # Find type with highest score
        query_type = max(scores, key=scores.get)
        max_score = scores[query_type]
        
        # Calculate confidence: normalized score with base confidence
        if max_score > 0:
            # Confidence based on how dominant this type's score is
            total_score = sum(scores.values())
            dominance = max_score / total_score if total_score > 0 else 0
            confidence = 0.5 + (dominance * 0.5)  # Range [0.5, 1.0]
        else:
            # No keywords matched - default to general with lower confidence
            query_type = QueryType.GENERAL
            confidence = 0.3
        
        # Generate reasoning
        reasoning = self._generate_analysis_reasoning(
            question_lower, query_type, scores
        )
        
        logger.info(
            f"Query analysis: type={query_type.value}, "
            f"confidence={confidence:.2f}, scores={scores}"
        )
        
        return query_type, confidence, reasoning
    
    def select_tool(
        self,
        query_type: QueryType,
        use_hybrid: bool = True
    ) -> ToolType:
        """
        Select primary tool based on query type.
        
        Args:
            query_type: Type of query
            use_hybrid: Whether to use hybrid search (default: True)
            
        Returns:
            Primary ToolType to use
        """
        mapping = {
            QueryType.STRUCTURED: ToolType.SQL,
            QueryType.CURRENT_EVENT: ToolType.WEB_SEARCH,
            QueryType.ENTITY_BASED: ToolType.METADATA if self.is_tool_available(ToolType.METADATA) else ToolType.HYBRID if use_hybrid else ToolType.VECTOR,
            QueryType.DOCUMENT_ANALYSIS: ToolType.HYBRID if use_hybrid else ToolType.VECTOR,
            QueryType.GENERAL: ToolType.HYBRID if use_hybrid else ToolType.VECTOR,
        }
        
        tool = mapping.get(query_type, ToolType.VECTOR)
        logger.info(f"Tool selected: {tool.value} for query type {query_type.value}")
        return tool
    
    def create_fallback_chain(
        self,
        primary_tool: ToolType,
        query_type: QueryType
    ) -> List[ToolType]:
        """
        Create fallback chain for robustness.
        
        Each tool has a chain of fallbacks to try if primary fails.
        
        Args:
            primary_tool: Primary tool to use
            query_type: Query type (for context)
            
        Returns:
            List of tools in fallback order
        """
        fallback_chains = {
            ToolType.SQL: [
                ToolType.VECTOR,
                ToolType.HYBRID,
                ToolType.WEB_SEARCH
            ],
            ToolType.WEB_SEARCH: [
                ToolType.HYBRID,
                ToolType.VECTOR,
                ToolType.SQL
            ],
            ToolType.METADATA: [
                ToolType.HYBRID,
                ToolType.VECTOR,
                ToolType.WEB_SEARCH
            ],
            ToolType.HYBRID: [
                ToolType.VECTOR,
                ToolType.WEB_SEARCH,
                ToolType.SQL
            ],
            ToolType.VECTOR: [
                ToolType.HYBRID,
                ToolType.WEB_SEARCH,
                ToolType.SQL
            ],
        }
        
        chain = fallback_chains.get(primary_tool, [ToolType.VECTOR])
        
        # Filter out unavailable tools and primary tool itself
        available_fallbacks = [
            t for t in chain
            if t != primary_tool and self.is_tool_available(t)
        ]
        
        logger.info(
            f"Fallback chain for {primary_tool.value}: "
            f"{[t.value for t in available_fallbacks]}"
        )
        
        return available_fallbacks
    
    def route_query(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Route a query to appropriate tool(s) with full decision context.
        
        Args:
            question: User's query
            context: Optional context (metadata filters, user preferences, etc.)
            
        Returns:
            RoutingDecision with tool selection and reasoning
        """
        context = context or {}
        
        # Analyze query
        query_type, confidence, analysis_reason = self.analyze_query(question)
        
        # Select primary tool
        use_hybrid = context.get('use_hybrid', True)
        primary_tool = self.select_tool(query_type, use_hybrid)
        
        # Create fallback chain
        fallback_tools = self.create_fallback_chain(primary_tool, query_type)
        
        # Build detailed reasoning
        reasoning = f"{analysis_reason}\n\nSelected: {primary_tool.value}"
        if fallback_tools:
            reasoning += f" (fallbacks: {', '.join(t.value for t in fallback_tools[:2])})"
        
        decision = RoutingDecision(
            query_type=query_type,
            primary_tool=primary_tool,
            fallback_tools=fallback_tools,
            confidence=confidence,
            reasoning=reasoning
        )
        
        logger.info(f"Routing decision: {decision.to_dict()}")
        
        return decision
    
    async def execute_tool_sequence(
        self,
        tools: List[ToolType],
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute tools in sequence with fallback handling.
        
        Args:
            tools: List of tools to try in order
            question: User's query
            context: Optional context for tool execution
            
        Returns:
            Dict with execution results and status
        """
        context = context or {}
        results = {
            'success': False,
            'tool_used': None,
            'tools_tried': [],
            'results': None,
            'error': None,
            'execution_time': 0
        }
        
        import time
        start_time = time.time()
        
        for tool_type in tools:
            try:
                results['tools_tried'].append(tool_type.value)
                logger.info(f"Executing tool: {tool_type.value}")
                
                # Get tool instance
                tool = self.tools_registry.get(tool_type)
                if not tool:
                    logger.warning(f"Tool {tool_type.value} not registered")
                    continue
                
                # Execute tool
                result = await self._execute_tool(tool, tool_type, question, context)
                
                if result and result.get('success'):
                    results['success'] = True
                    results['tool_used'] = tool_type.value
                    results['results'] = result
                    results['execution_time'] = time.time() - start_time
                    logger.info(f"Tool {tool_type.value} succeeded")
                    return results
                else:
                    logger.warning(f"Tool {tool_type.value} failed, trying next fallback")
                    continue
                    
            except Exception as e:
                logger.error(f"Error executing {tool_type.value}: {e}", exc_info=True)
                continue
        
        results['execution_time'] = time.time() - start_time
        results['error'] = f"All tools failed. Tried: {', '.join(results['tools_tried'])}"
        logger.error(f"All tool execution attempts failed for query: {question}")
        
        return results
    
    async def _execute_tool(
        self,
        tool: Any,
        tool_type: ToolType,
        question: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a specific tool.
        
        Args:
            tool: Tool instance
            tool_type: Type of tool
            question: User query
            context: Execution context
            
        Returns:
            Tool result dictionary
        """
        try:
            # Handle different tool types
            if tool_type == ToolType.SQL:
                if hasattr(tool, 'execute'):
                    return await tool.execute(question)
                else:
                    logger.warning(f"Tool {tool_type.value} doesn't have execute method")
                    return {'success': False}
            
            elif tool_type == ToolType.WEB_SEARCH:
                if hasattr(tool, 'execute'):
                    return await tool.execute(question)
                else:
                    logger.warning(f"Tool {tool_type.value} doesn't have execute method")
                    return {'success': False}
            
            elif tool_type in [ToolType.VECTOR, ToolType.HYBRID, ToolType.METADATA]:
                # Retrieval tools are handled differently via retrieval service
                return {
                    'success': True,
                    'tool': tool_type.value,
                    'message': 'Handled by retrieval service'
                }
            
            else:
                logger.warning(f"Unknown tool type: {tool_type.value}")
                return {'success': False}
                
        except Exception as e:
            logger.error(f"Tool execution error ({tool_type.value}): {e}")
            return {'success': False, 'error': str(e)}
    
    # Private helper methods
    
    def _calculate_match_score(
        self,
        text: str,
        keywords: set
    ) -> float:
        """
        Calculate how well text matches a set of keywords.
        
        Args:
            text: Text to analyze
            keywords: Set of keywords to match
            
        Returns:
            Match score [0, 1]
        """
        if not keywords:
            return 0.0
        
        matches = 0
        for keyword in keywords:
            if keyword in text:
                matches += 1
        
        # Normalize: score = (matches / total_keywords) capped at 1.0
        score = min(matches / len(keywords), 1.0)
        return score
    
    def _generate_analysis_reasoning(
        self,
        question_lower: str,
        detected_type: QueryType,
        all_scores: Dict[QueryType, float]
    ) -> str:
        """
        Generate human-readable reasoning for query analysis.
        
        Args:
            question_lower: Lowercased question
            detected_type: Detected query type
            all_scores: Scores for all types
            
        Returns:
            Reasoning string
        """
        reason_parts = []
        
        # Explain what was detected
        if detected_type == QueryType.STRUCTURED:
            reason_parts.append("Detected structured/analytical query (keywords: table, count, aggregate, etc.)")
        elif detected_type == QueryType.CURRENT_EVENT:
            reason_parts.append("Detected time-sensitive/current event query (keywords: today, latest, news, etc.)")
        elif detected_type == QueryType.ENTITY_BASED:
            reason_parts.append("Detected entity-specific query (keywords: who, which, specific, named, etc.)")
        elif detected_type == QueryType.DOCUMENT_ANALYSIS:
            reason_parts.append("Detected analysis/comparison query (keywords: analyze, summarize, compare, etc.)")
        else:
            reason_parts.append("Detected general knowledge query")
        
        return " ".join(reason_parts)
    
    def get_tool_info(self) -> Dict[str, Any]:
        """Get information about registered tools."""
        return {
            'registered_tools': [
                {
                    'type': tool_type.value,
                    'available': True,
                    'instance': str(tool)[:100]
                }
                for tool_type, tool in self.tools_registry.items()
            ],
            'query_types': [qt.value for qt in QueryType],
            'tool_types': [tt.value for tt in ToolType]
        }


# Global router instance
agent_router = AgentRouter()
