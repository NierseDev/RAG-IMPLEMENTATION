import pytest

from app.core.config import settings
import app.services.llm as llm_module
from app.services.llm import LLMService
from app.services.llm_providers import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_is_selected_when_configured(monkeypatch):
    captured = {}

    class DummyProvider:
        async def generate(self, prompt, system=None, temperature=0.7, max_tokens=None):
            return "ok"

        async def check_availability(self):
            return True

    def fake_create_llm_provider(provider, **kwargs):
        captured["provider"] = provider
        captured["kwargs"] = kwargs
        return DummyProvider()

    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-openai-key")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr(settings, "openai_model", "gpt-4.1-mini")
    monkeypatch.setattr(llm_module, "create_llm_provider", fake_create_llm_provider)

    service = LLMService()

    assert captured["provider"] == "openai"
    assert captured["kwargs"]["api_key"] == "test-openai-key"
    assert captured["kwargs"]["base_url"] == "https://api.openai.com/v1"
    assert captured["kwargs"]["model"] == "gpt-4.1-mini"
    assert service.provider.__class__.__name__ == "DummyProvider"


def test_openai_provider_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(ValueError, match="OPENAI_API_KEY not set in environment"):
        LLMService()


@pytest.mark.asyncio
async def test_openai_provider_uses_max_completion_tokens(monkeypatch):
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]}
            )()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)

    provider = OpenAIProvider(
        api_key="key",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        max_output_tokens=256,
    )

    result = await provider.generate("hello", max_tokens=64)

    assert result == "ok"
    assert "max_completion_tokens" in captured
    assert captured["max_completion_tokens"] == 64
    assert "max_tokens" not in captured
