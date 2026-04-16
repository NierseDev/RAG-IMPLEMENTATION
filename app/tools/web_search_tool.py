"""
Web Search Tool for fallback when documents don't have the answer.

Features:
- Tavily search integration with DuckDuckGo fallback
- Attribution for trust
- Graceful fallback logic
- Explicit context-block formatting for agent prompts
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import httpx
import re
from urllib.parse import parse_qs, unquote, urlparse
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Web search tool using Tavily first, DuckDuckGo as fallback.
    """

    TAVILY_API_URL = settings.tavily_base_url

    # DuckDuckGo Instant Answer API (free, no auth required)
    DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"

    # HTML API for web results (using duck.com HTML scraping)
    DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"

    # Maximum results to return
    MAX_RESULTS = 5
    MAX_TAVILY_CREDITS_PER_QUERY = 3
    MAX_SEARCH_VARIANTS = 3
    MAX_TITLE_CHARS = 120
    MAX_SNIPPET_CHARS = 240
    MAX_URL_CHARS = 200
    MAX_CONTEXT_BLOCK_CHARS = 500
    
    # Request timeout
    TIMEOUT = 10

    def __init__(self, api_key: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        """Initialize the web search tool."""
        self.api_key = api_key or settings.tavily_api_key
        self.client = client or httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True)
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
            max_results = min(max_results or self.MAX_RESULTS, self.MAX_RESULTS)
            search_variants = self._build_search_variants(query)
            search_engine = "Tavily" if self.api_key else "DuckDuckGo"
            fallback_used = False
            results: List[Dict[str, Any]] = []
            raw_results: List[Dict[str, Any]] = []
            searched_queries: List[str] = []
            credits_used = 0

            if self.api_key:
                for search_query in search_variants[: self.MAX_TAVILY_CREDITS_PER_QUERY]:
                    searched_queries.append(search_query)
                    credits_used += 1
                    pass_results = await self._search_tavily(search_query, max_results)
                    for item in pass_results:
                        enriched = dict(item)
                        enriched["search_query"] = search_query
                        enriched["search_engine"] = "Tavily"
                        raw_results.append(enriched)

                results = self._merge_results(raw_results)

            if not results:
                fallback_used = True
                search_engine = "DuckDuckGo"
                raw_results = []
                for search_query in search_variants[: self.MAX_SEARCH_VARIANTS]:
                    searched_queries.append(search_query)
                    pass_results = await self._search_duckduckgo(search_query, max_results)
                    for item in pass_results:
                        enriched = dict(item)
                        enriched["search_query"] = search_query
                        enriched["search_engine"] = "DuckDuckGo"
                        raw_results.append(enriched)
                results = self._merge_results(raw_results)

            results = [self._compact_result(result) for result in results[:max_results]]
            
            if not results:
                return {
                    'success': False,
                    'results': [],
                    'error': 'No search results found',
                    'attribution': None
                }
            
            # Add attribution metadata
            attribution = self._create_attribution(
                results,
                search_engine=search_engine,
                fallback_used=fallback_used,
                searched_queries=searched_queries[: self.MAX_TAVILY_CREDITS_PER_QUERY],
                credits_used=credits_used
            )
            
            return {
                'success': True,
                'results': results,
                'attribution': attribution,
                'count': len(results),
                'search_engine': search_engine,
                'context': self.format_for_agent(results, attribution=attribution)
            }
            
        except Exception as e:
            logger.error(f"Web search error: {e}", exc_info=True)
            return {
                'success': False,
                'results': [],
                'error': f"Web search failed: {str(e)}",
                'attribution': None
            }

    async def _search_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Tavily and normalize results."""
        if not self.api_key:
            logger.info("Tavily fallback disabled: TAVILY_API_KEY not set")
            return []

        try:
            response = await self.client.post(
                self.TAVILY_API_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": settings.tavily_search_depth,
                    "max_results": min(max_results, settings.tavily_max_results),
                    "include_answer": settings.tavily_include_answer,
                    "include_raw_content": settings.tavily_include_raw_content,
                    "include_images": False,
                    "include_domains": [],
                    "exclude_domains": []
                }
            )
            response.raise_for_status()
            data = response.json()

            results = [self._normalize_tavily_result(item) for item in data.get("results", [])]
            return [item for item in results if item.get("snippet") or item.get("title") or item.get("url")]
        except Exception as e:
            logger.warning(f"Tavily search failed, falling back to DuckDuckGo: {e}")
            return []

    def _build_search_variants(self, query: str) -> List[str]:
        """Build a few focused search queries without exceeding the Tavily budget."""
        normalized = self._sanitize_query(query)
        key_terms = self._condense_query_terms(normalized)
        variants = [normalized]

        if key_terms and key_terms not in variants:
            variants.append(key_terms)

        if len(variants) < self.MAX_SEARCH_VARIANTS:
            if self._looks_time_sensitive(normalized):
                tail = "latest"
            else:
                tail = "overview"

            focused = f"{key_terms or normalized} {tail}".strip()
            if focused not in variants:
                variants.append(focused)

        return variants[: self.MAX_SEARCH_VARIANTS]

    def _condense_query_terms(self, query: str) -> str:
        stopwords = {
            "a", "an", "and", "are", "for", "from", "how", "in", "is", "it", "of",
            "on", "or", "the", "to", "was", "what", "when", "where", "which", "who",
            "why", "with", "does", "do", "can", "could", "should", "would"
        }
        modifiers = {
            "latest", "recent", "current", "today", "new", "news", "update", "updates",
            "overview", "summary", "guide", "howto", "how-to", "official", "best"
        }
        tokens = re.findall(r"[a-z0-9][a-z0-9+\-_.:/]*", query.lower())
        condensed: List[str] = []
        seen = set()
        for token in tokens:
            if token in stopwords or token in modifiers or token in seen or len(token) < 3:
                continue
            condensed.append(token)
            seen.add(token)
            if len(condensed) >= 8:
                break
        return " ".join(condensed).strip()

    def _looks_time_sensitive(self, query: str) -> bool:
        lowered = query.lower()
        return any(token in lowered for token in [
            "latest", "recent", "current", "today", "this week", "this month", "2025", "2026"
        ])

    def _sanitize_query(self, query: str) -> str:
        return re.sub(r"\s+", " ", unescape(str(query))).strip()

    def _merge_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge and dedupe search results across multiple passes."""
        merged: Dict[str, Dict[str, Any]] = {}
        for item in results:
            key = self._result_key(item)
            if not key:
                continue

            existing = merged.get(key)
            if not existing:
                merged[key] = dict(item)
                merged[key]["search_queries"] = [item.get("search_query")] if item.get("search_query") else []
                merged[key]["search_engines"] = [item.get("search_engine")] if item.get("search_engine") else []
                continue

            existing_score = existing.get("score") or 0.0
            item_score = item.get("score") or 0.0
            if item_score > existing_score:
                existing.update({k: v for k, v in item.items() if v not in [None, ""]})

            for field, target in (("search_query", "search_queries"), ("search_engine", "search_engines")):
                value = item.get(field)
                if value and value not in existing.setdefault(target, []):
                    existing[target].append(value)

        ordered = sorted(
            merged.values(),
            key=lambda item: (
                item.get("score") is None,
                -(item.get("score") or 0.0),
                item.get("title", ""),
                item.get("url", "")
            )
        )
        return ordered

    def _result_key(self, result: Dict[str, Any]) -> str:
        url = self._truncate_text(str(result.get("url", "")).lower(), self.MAX_URL_CHARS)
        if url:
            return f"url:{url}"

        title = self._truncate_text(str(result.get("title", "")).lower(), 80)
        snippet = self._truncate_text(str(result.get("snippet", "")).lower(), 120)
        if title or snippet:
            return f"text:{title}|{snippet}"
        return ""

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

    def _normalize_tavily_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Tavily result payloads to the shared agent-facing shape."""
        content = result.get("content") or result.get("raw_content") or result.get("snippet") or ""
        return {
            "title": self._sanitize_text(result.get("title", ""), self.MAX_TITLE_CHARS),
            "snippet": self._sanitize_text(content, self.MAX_SNIPPET_CHARS),
            "url": self._truncate_text(str(result.get("url", "")), self.MAX_URL_CHARS),
            "source": result.get("source", "Tavily"),
            "type": "tavily_result",
            "score": result.get("score")
        }
    
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
    
    def _create_attribution(
        self,
        results: List[Dict[str, Any]],
        search_engine: str,
        fallback_used: bool = False,
        searched_queries: Optional[List[str]] = None,
        credits_used: int = 0
    ) -> Dict[str, Any]:
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
            'search_engine': search_engine,
            'fallback_used': fallback_used,
            'sources': sources,
            'urls': urls,
            'searched_queries': searched_queries or [],
            'credits_used': credits_used,
            'timestamp': datetime.utcnow().isoformat(),
            'disclaimer': 'Results from web search. Information may be outdated or inaccurate. Verify with authoritative sources.',
            'result_count': len(results)
        }

    def _compact_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Trim web results so downstream prompts stay small."""
        title = self._sanitize_text(result.get('title', ''), self.MAX_TITLE_CHARS)
        snippet = self._sanitize_text(result.get('snippet', ''), self.MAX_SNIPPET_CHARS)
        url = self._truncate_text(str(result.get('url', '')), self.MAX_URL_CHARS)

        return {
            'title': title or 'DuckDuckGo result',
            'snippet': snippet,
            'url': url,
            'source': result.get('source', 'DuckDuckGo'),
            'type': result.get('type', 'web_result'),
            'search_query': result.get('search_query'),
            'search_engine': result.get('search_engine')
        }

    def build_context_block(self, result: Dict[str, Any], index: int) -> str:
        """Build an explicit context block for the agent prompt."""
        title = self._sanitize_text(result.get("title", "Web result"), self.MAX_TITLE_CHARS)
        snippet = self._sanitize_text(result.get("snippet", "No snippet available"), self.MAX_SNIPPET_CHARS)
        url = self._truncate_text(str(result.get("url", "N/A")), self.MAX_URL_CHARS)
        source = result.get("source", "Unknown")
        score = result.get("score")

        lines = [
            f"=== Web Result {index} ===",
            f"title: {title}",
            f"source: {source}",
            f"url: {url}",
        ]
        search_query = result.get("search_query")
        if search_query:
            lines.append(f"query: {self._sanitize_text(search_query, 120)}")
        if score is not None:
            lines.append(f"score: {score}")
        lines.append(f"snippet: {snippet}")
        lines.append(f"=== End Web Result {index} ===")

        block = "\n".join(lines)
        if len(block) <= self.MAX_CONTEXT_BLOCK_CHARS:
            return block
        return block[: self.MAX_CONTEXT_BLOCK_CHARS - 3].rstrip() + "..."

    @staticmethod
    def _truncate_text(value: str, limit: int) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        if len(value) <= limit:
            return value
        return value[: limit - 3].rstrip() + "..."

    def _sanitize_text(self, value: Any, limit: int) -> str:
        """Normalize web text and strip markdown emphasis before prompting the model."""
        text = unescape(str(value))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."
    
    def should_fallback_to_web(
        self,
        rag_confidence: float,
        rag_results_count: int,
        confidence_threshold: float = 0.5
    ) -> bool:
        """
        Determine if we should fallback to web search.
        
        Args:
            rag_confidence: Confidence score from RAG system (kept for compatibility)
            rag_results_count: Number of results from RAG
            confidence_threshold: Minimum confidence to skip web search (unused)
            
        Returns:
            True if should use web search, False otherwise
        """
        if rag_results_count == 0:
            logger.info("Web fallback: No RAG results")
            return True

        return False
    
    def format_for_agent(
        self,
        search_results: List[Dict[str, Any]],
        attribution: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format search results as context for the agent.
        
        Args:
            search_results: List of search result dicts
            
        Returns:
            Formatted string for LLM context
        """
        if not search_results:
            return ""
        
        formatted = ["Web Search Results"]
        if attribution:
            formatted.append(
                f"search_engine: {attribution.get('search_engine', 'Unknown')} | "
                f"fallback_used: {attribution.get('fallback_used', False)} | "
                f"credits_used: {attribution.get('credits_used', 0)}"
            )
            queries = attribution.get("searched_queries") or []
            if queries:
                formatted.append("queries: " + "; ".join(queries[:self.MAX_SEARCH_VARIANTS]))

        for idx, result in enumerate(search_results[: self.MAX_RESULTS], 1):
            formatted.append(self.build_context_block(result, idx))

        formatted.append("Note: These are web search results. Cite sources and verify information.")
        return "\n\n".join(formatted)
    
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
- Explicit context blocks for answer generation

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
