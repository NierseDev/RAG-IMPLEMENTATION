"""
Web Search Tool for fallback when documents don't have the answer.

Features:
- DuckDuckGo search integration
- Attribution for trust
- Graceful fallback logic
- Result formatting
"""
from typing import Dict, Any, List, Optional
import logging
import asyncio
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Web search tool using DuckDuckGo for fallback when RAG doesn't have answers.
    """
    
    # DuckDuckGo Instant Answer API (free, no auth required)
    DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"
    
    # HTML API for web results (using duck.com HTML scraping)
    DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
    
    # Maximum results to return
    MAX_RESULTS = 5
    
    # Request timeout
    TIMEOUT = 10
    
    def __init__(self):
        """Initialize the web search tool."""
        self.client = httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True)
        logger.info("WebSearchTool initialized")
    
    async def execute(
        self,
        query: str,
        max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute web search and return results with attribution.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default: MAX_RESULTS)
            
        Returns:
            Dict with 'success', 'results', 'attribution', 'error' keys
        """
        try:
            max_results = max_results or self.MAX_RESULTS
            
            # Perform the search
            results = await self._search_duckduckgo(query, max_results)
            
            if not results:
                return {
                    'success': False,
                    'results': [],
                    'error': 'No search results found',
                    'attribution': None
                }
            
            # Add attribution metadata
            attribution = self._create_attribution(results)
            
            return {
                'success': True,
                'results': results,
                'attribution': attribution,
                'count': len(results)
            }
            
        except Exception as e:
            logger.error(f"Web search error: {e}", exc_info=True)
            return {
                'success': False,
                'results': [],
                'error': f"Web search failed: {str(e)}",
                'attribution': None
            }
    
    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Search DuckDuckGo and parse results.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            
        Returns:
            List of search result dicts
        """
        try:
            # Try Instant Answer API first (returns structured data)
            instant_results = await self._instant_answer_api(query)
            if instant_results:
                return instant_results[:max_results]
            
            # Fallback: Use HTML scraping (more results, less structured)
            html_results = await self._html_search(query, max_results)
            return html_results
            
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            raise
    
    async def _instant_answer_api(self, query: str) -> List[Dict[str, Any]]:
        """
        Use DuckDuckGo Instant Answer API.
        
        Returns structured instant answers, definitions, summaries.
        """
        try:
            params = {
                'q': query,
                'format': 'json',
                'no_html': 1,
                'skip_disambig': 1
            }
            
            response = await self.client.get(self.DUCKDUCKGO_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Abstract (main answer)
            if data.get('Abstract'):
                results.append({
                    'title': data.get('Heading', 'Instant Answer'),
                    'snippet': data['Abstract'],
                    'url': data.get('AbstractURL', ''),
                    'source': data.get('AbstractSource', 'DuckDuckGo'),
                    'type': 'instant_answer'
                })
            
            # Related topics
            for topic in data.get('RelatedTopics', [])[:3]:
                if isinstance(topic, dict) and 'Text' in topic:
                    results.append({
                        'title': topic.get('FirstURL', '').split('/')[-1].replace('_', ' '),
                        'snippet': topic['Text'],
                        'url': topic.get('FirstURL', ''),
                        'source': 'DuckDuckGo',
                        'type': 'related_topic'
                    })
            
            return results
            
        except Exception as e:
            logger.debug(f"Instant Answer API failed (expected): {e}")
            return []
    
    async def _html_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Fallback: Scrape DuckDuckGo HTML results.
        
        Note: This is a simplified implementation. In production, consider:
        1. Using a proper web scraping library (BeautifulSoup)
        2. Rotating user agents
        3. Implementing rate limiting
        4. Using a paid search API (SerpAPI, Bing API, etc.)
        """
        try:
            # For now, return a fallback message
            # In production, implement proper HTML scraping or use a paid API
            logger.warning("HTML scraping not fully implemented. Use a search API in production.")
            
            return [{
                'title': 'Web Search Unavailable',
                'snippet': f'Web search for "{query}" requires additional setup. Please configure a search API provider (SerpAPI, Bing, etc.) in production.',
                'url': 'https://duckduckgo.com/?q=' + query.replace(' ', '+'),
                'source': 'DuckDuckGo',
                'type': 'fallback'
            }]
            
        except Exception as e:
            logger.error(f"HTML search failed: {e}")
            return []
    
    def _create_attribution(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create attribution metadata for transparency and trust.
        
        Args:
            results: Search results
            
        Returns:
            Attribution dict with sources, timestamp, disclaimer
        """
        sources = list(set(r.get('source', 'Unknown') for r in results))
        urls = [r.get('url', '') for r in results if r.get('url')]
        
        return {
            'source_type': 'web_search',
            'search_engine': 'DuckDuckGo',
            'sources': sources,
            'urls': urls,
            'timestamp': datetime.utcnow().isoformat(),
            'disclaimer': 'Results from web search. Information may be outdated or inaccurate. Verify with authoritative sources.',
            'result_count': len(results)
        }
    
    def should_fallback_to_web(
        self,
        rag_confidence: float,
        rag_results_count: int,
        confidence_threshold: float = 0.5
    ) -> bool:
        """
        Determine if we should fallback to web search.
        
        Args:
            rag_confidence: Confidence score from RAG system (0.0-1.0)
            rag_results_count: Number of results from RAG
            confidence_threshold: Minimum confidence to skip web search
            
        Returns:
            True if should use web search, False otherwise
        """
        # Fallback conditions:
        # 1. No RAG results found
        if rag_results_count == 0:
            logger.info("Web fallback: No RAG results")
            return True
        
        # 2. Low confidence in RAG answer
        if rag_confidence < confidence_threshold:
            logger.info(f"Web fallback: Low RAG confidence ({rag_confidence:.2f})")
            return True
        
        # 3. Very few RAG results (might be insufficient)
        if rag_results_count < 2:
            logger.info(f"Web fallback: Insufficient RAG results ({rag_results_count})")
            return True
        
        return False
    
    async def format_for_agent(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Format search results as context for the agent.
        
        Args:
            search_results: List of search result dicts
            
        Returns:
            Formatted string for LLM context
        """
        if not search_results:
            return ""
        
        formatted = "## Web Search Results\n\n"
        
        for idx, result in enumerate(search_results, 1):
            formatted += f"### Result {idx}: {result.get('title', 'No title')}\n"
            formatted += f"**Source:** {result.get('source', 'Unknown')}\n"
            formatted += f"**URL:** {result.get('url', 'N/A')}\n"
            formatted += f"**Content:** {result.get('snippet', 'No content')}\n\n"
        
        formatted += "**Note:** These are web search results. Cite sources and verify information.\n"
        
        return formatted
    
    def get_tool_description(self) -> str:
        """Return a description of this tool for the agent."""
        return """
**Web Search Tool**

Search the web when the RAG knowledge base doesn't have sufficient information.

**Use when:**
- No relevant documents found in RAG database
- RAG confidence is low (<0.5)
- User asks about current events or recent information
- User asks about topics outside the knowledge base
- Need to verify or supplement RAG results

**Examples:**
- "What's the latest news on [topic]?"
- "Current price of [product]"
- "Recent developments in [field]"
- Questions about topics not in documents

**Output:**
- Search results with titles, snippets, URLs
- Attribution metadata (source, timestamp, disclaimer)
- Formatted context for answer generation

**Attribution:**
All web results include:
- Source attribution (search engine, websites)
- Timestamps
- Disclaimer about accuracy
- Direct URLs for verification
"""
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("WebSearchTool closed")


# Global instance
web_search_tool = WebSearchTool()
