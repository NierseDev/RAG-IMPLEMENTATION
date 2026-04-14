import pytest

from app.core.config import settings
import app.services.llm as llm_module
from app.services.llm import LLMService


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
