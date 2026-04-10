"""
Tool handlers for WorkflowOrchestrator integration with RAG system tools.

Implements ToolHandler interface for each available tool:
- VectorSearchHandler - Vector similarity search
- HybridSearchHandler - Vector + keyword hybrid search
- SQLHandler - Structured SQL queries
- WebSearchHandler - Web search fallback
- MetadataFilterHandler - Metadata-based filtering
"""

from typing import Dict, Any, Optional
import logging
from app.services.workflow_orchestrator import ToolHandler, ToolType

logger = logging.getLogger(__name__)


class VectorSearchHandler(ToolHandler):
    """Handler for vector similarity search."""
    
    def __init__(self, retrieval_service):
        """Initialize vector search handler."""
        self.retrieval_service = retrieval_service
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute vector search."""
        try:
            top_k = context.get('top_k', 10)
            min_similarity = context.get('min_similarity', 0.0)
            metadata_filters = context.get('metadata_filters')
            filter_logic = context.get('filter_logic', 'AND')
            
            results = await self.retrieval_service.retrieve(
                query=query,
                top_k=top_k,
                min_similarity=min_similarity,
                use_hybrid=False,
                metadata_filters=metadata_filters,
                filter_logic=filter_logic
            )
            
            return {
                'success': True,
                'results': [r.dict() if hasattr(r, 'dict') else r for r in results],
                'count': len(results),
                'method': 'vector'
            }
        except Exception as e:
            logger.exception("Vector search error")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }


class HybridSearchHandler(ToolHandler):
    """Handler for hybrid search (vector + keyword)."""
    
    def __init__(self, query_service):
        """Initialize hybrid search handler."""
        self.query_service = query_service
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hybrid search."""
        try:
            top_k = context.get('top_k', 10)
            min_similarity = context.get('min_similarity', 0.0)
            metadata_filters = context.get('metadata_filters')
            
            result = await self.query_service.search(
                query=query,
                metadata_filters=metadata_filters,
                top_k=top_k,
                use_hybrid=True,
                min_similarity=min_similarity
            )
            
            return {
                'success': True,
                'results': result.get('results', []),
                'count': len(result.get('results', [])),
                'method': 'hybrid',
                'breakdown': result.get('search_breakdown', {})
            }
        except Exception as e:
            logger.exception("Hybrid search error")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }


class SQLHandler(ToolHandler):
    """Handler for SQL queries."""
    
    def __init__(self, sql_tool):
        """Initialize SQL handler."""
        self.sql_tool = sql_tool
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute SQL query."""
        try:
            result = await self.sql_tool.query_from_text(query)
            
            return {
                'success': result.get('success', True),
                'results': result.get('results', []),
                'sql': result.get('sql'),
                'count': len(result.get('results', [])),
                'method': 'sql'
            }
        except Exception as e:
            logger.exception("SQL tool error")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }


class WebSearchHandler(ToolHandler):
    """Handler for web search."""
    
    def __init__(self, web_search_tool):
        """Initialize web search handler."""
        self.web_search_tool = web_search_tool
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web search."""
        try:
            max_results = context.get('max_results', 5)
            result = await self.web_search_tool.execute(query, max_results)
            
            return {
                'success': result.get('success', False),
                'results': result.get('results', []),
                'count': result.get('count', 0),
                'attribution': result.get('attribution'),
                'method': 'web_search'
            }
        except Exception as e:
            logger.exception("Web search error")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }


class MetadataFilterHandler(ToolHandler):
    """Handler for metadata-based filtering."""
    
    def __init__(self, retrieval_service, metadata_filter):
        """Initialize metadata filter handler."""
        self.retrieval_service = retrieval_service
        self.metadata_filter = metadata_filter
    
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute metadata-filtered search."""
        try:
            metadata_filters = context.get('metadata_filters')
            filter_logic = context.get('filter_logic', 'AND')
            top_k = context.get('top_k', 10)
            
            if not metadata_filters:
                return {
                    'success': False,
                    'error': 'No metadata filters provided',
                    'results': []
                }
            
            results = await self.retrieval_service.retrieve(
                query=query,
                top_k=top_k,
                metadata_filters=metadata_filters,
                filter_logic=filter_logic
            )
            
            return {
                'success': True,
                'results': [r.dict() if hasattr(r, 'dict') else r for r in results],
                'count': len(results),
                'method': 'metadata_filter',
                'filters': metadata_filters
            }
        except Exception as e:
            logger.exception("Metadata filter error")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }


def create_tool_handlers(
    retrieval_service=None,
    query_service=None,
    sql_tool=None,
    web_search_tool=None,
    metadata_filter=None
) -> Dict[ToolType, ToolHandler]:
    """
    Create tool handlers for orchestrator.
    
    Args:
        retrieval_service: Retrieval service instance
        query_service: Query service for hybrid search
        sql_tool: SQL tool instance
        web_search_tool: Web search tool instance
        metadata_filter: Metadata filter instance
        
    Returns:
        Dictionary mapping ToolType to ToolHandler instances
    """
    handlers = {}
    
    if retrieval_service:
        handlers[ToolType.VECTOR] = VectorSearchHandler(retrieval_service)
        logger.info("Vector search handler registered")
    
    if query_service:
        handlers[ToolType.HYBRID] = HybridSearchHandler(query_service)
        logger.info("Hybrid search handler registered")
    
    if sql_tool:
        handlers[ToolType.SQL] = SQLHandler(sql_tool)
        logger.info("SQL handler registered")
    
    if web_search_tool:
        handlers[ToolType.WEB_SEARCH] = WebSearchHandler(web_search_tool)
        logger.info("Web search handler registered")
    
    if retrieval_service and metadata_filter:
        handlers[ToolType.METADATA] = MetadataFilterHandler(retrieval_service, metadata_filter)
        logger.info("Metadata filter handler registered")
    
    return handlers
