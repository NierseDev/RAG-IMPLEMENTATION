import pytest

from app.tools.web_search_tool import WebSearchTool, _DuckDuckGoHTMLParser


def test_duckduckgo_html_parser_uses_visible_url_when_href_is_missing():
    html = """
    <div class="result web-result">
      <a class="result__a" href="">Example Title</a>
      <a class="result__url" href="/l/?uddg=https%3A%2F%2Fexample.com%2Farticle">
        example.com/article
      </a>
      <a class="result__snippet">Example snippet text.</a>
    </div>
    """

    parser = _DuckDuckGoHTMLParser(max_results=3)
    parser.feed(html)

    assert len(parser.results) == 1
    assert parser.results[0]["title"] == "Example Title"
    assert parser.results[0]["snippet"] == "Example snippet text."
    assert parser.results[0]["url"] == "https://example.com/article"


@pytest.mark.asyncio
async def test_execute_returns_failure_when_search_returns_no_results():
    tool = WebSearchTool()

    async def fake_search(query: str, max_results: int):
        return []

    try:
        tool._search_duckduckgo = fake_search  # type: ignore[method-assign]

        result = await tool.execute("nothing found", max_results=2)

        assert result["success"] is False
        assert result["results"] == []
        assert result["error"] == "No search results found"
    finally:
        await tool.close()
