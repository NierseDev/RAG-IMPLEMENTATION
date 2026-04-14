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
from html import unescape
from html.parser import HTMLParser
import httpx
import re
from urllib.parse import parse_qs, unquote, urlparse

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
    MAX_TITLE_CHARS = 120
    MAX_SNIPPET_CHARS = 240
    MAX_URL_CHARS = 200
    
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
            results = [self._compact_result(result) for result in results[:max_results]]
            
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
        """
        try:
            response = await self.client.get(
                self.DUCKDUCKGO_HTML_URL,
                params={'q': query},
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; CopilotCLI/1.0; +https://github.com)'
                }
            )
            response.raise_for_status()

            parser = _DuckDuckGoHTMLParser(max_results=max_results)
            parser.feed(response.text)
            results = parser.results[:max_results]

            if not results:
                logger.info("DuckDuckGo HTML search returned no parsed results")
                return []

            return results

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

    def _compact_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Trim web results so downstream prompts stay small."""
        title = self._truncate_text(str(result.get('title', '')), self.MAX_TITLE_CHARS)
        snippet = self._truncate_text(str(result.get('snippet', '')), self.MAX_SNIPPET_CHARS)
        url = self._truncate_text(str(result.get('url', '')), self.MAX_URL_CHARS)

        return {
            'title': title or 'DuckDuckGo result',
            'snippet': snippet,
            'url': url,
            'source': result.get('source', 'DuckDuckGo'),
            'type': result.get('type', 'web_result')
        }

    @staticmethod
    def _truncate_text(value: str, limit: int) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        if len(value) <= limit:
            return value
        return value[: limit - 3].rstrip() + "..."
    
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
        
        for idx, result in enumerate(search_results[:3], 1):
            formatted += f"### Result {idx}: {result.get('title', 'No title')}\n"
            formatted += f"**Source:** {result.get('source', 'Unknown')}\n"
            formatted += f"**URL:** {result.get('url', 'N/A')}\n"
            formatted += f"**Content:** {self._truncate_text(result.get('snippet', 'No content'), self.MAX_SNIPPET_CHARS)}\n\n"
        
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


class _DuckDuckGoHTMLParser(HTMLParser):
    """Parse DuckDuckGo HTML result cards into normalized result dictionaries."""

    def __init__(self, max_results: int):
        super().__init__()
        self.max_results = max_results
        self.results: List[Dict[str, Any]] = []
        self._current: Optional[Dict[str, Any]] = None
        self._current_depth = 0
        self._current_field: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]):
        attrs_map = {key: value or "" for key, value in attrs}
        class_name = attrs_map.get("class", "")

        if tag == "div" and "result" in class_name and "web-result" in class_name:
            if self._current is None and len(self.results) < self.max_results:
                self._current = {
                    "title": "",
                    "snippet": "",
                    "url": "",
                    "visible_url": "",
                    "source": "DuckDuckGo",
                    "type": "web_result"
                }
                self._current_depth = 1
            return

        if self._current is None:
            return

        if tag == "div":
            self._current_depth += 1
            self._current_field = None
            return

        if tag == "a":
            href = attrs_map.get("href", "")
            if "result__a" in class_name:
                self._current["url"] = self._normalize_url(href)
                self._current_field = "title"
            elif "result__url" in class_name:
                if not self._current.get("url"):
                    self._current["url"] = self._normalize_url(href)
                self._current_field = "visible_url"
            elif "result__snippet" in class_name:
                self._current_field = "snippet"
            else:
                self._current_field = None

    def handle_endtag(self, tag: str):
        if self._current is None:
            return

        if tag == "a":
            self._current_field = None
            return

        if tag == "div":
            self._current_depth -= 1
            if self._current_depth <= 0:
                self._finalize_current()

    def handle_data(self, data: str):
        if self._current is None or not self._current_field:
            return

        self._current.setdefault(self._current_field, "")
        self._current[self._current_field] += data

    def _finalize_current(self):
        title = self._clean_text(self._current.get("title", ""))
        snippet = self._clean_text(self._current.get("snippet", ""))
        url = self._clean_text(self._current.get("url", ""))
        visible_url = self._clean_text(self._current.get("visible_url", ""))

        if not url and visible_url:
            url = self._normalize_url(visible_url)

        if title or snippet or url:
            self.results.append({
                "title": title or url or "DuckDuckGo result",
                "snippet": snippet,
                "url": url,
                "source": self._current.get("source", "DuckDuckGo"),
                "type": self._current.get("type", "web_result")
            })

        self._current = None
        self._current_depth = 0
        self._current_field = None

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", unescape(value)).strip()

    @staticmethod
    def _normalize_url(href: str) -> str:
        if not href:
            return ""

        href = unescape(href).strip()
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        target = query.get("uddg", [None])[0]
        if target:
            return unquote(target)

        if href.startswith("//"):
            return f"https:{href}"

        return unquote(href)


# Global instance
web_search_tool = WebSearchTool()
