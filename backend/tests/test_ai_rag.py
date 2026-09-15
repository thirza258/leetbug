from types import SimpleNamespace

import httpx
import pytest

from app import llm, rag
from app.config import settings


def test_openrouter_request_and_patch_extraction(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_base_url", "https://openrouter.ai/api/v1")
    client_class = httpx.Client
    def respond(request):
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.url.path == "/api/v1/chat/completions"
        assert b"hidden" not in request.content
        return httpx.Response(200, json={"choices": [{"message": {"content": "```python\ndef solve(data): return 1\n```"}}], "usage": {"total_tokens": 80}})
    monkeypatch.setattr(llm.httpx, "Client", lambda **kwargs: client_class(transport=httpx.MockTransport(respond)))
    result, tokens = llm.patch_code(SimpleNamespace(title="Sum", requirements=["Sum all inputs"]), "python", "source", "Fix the range")
    assert result == "def solve(data): return 1" and tokens == 80


def test_ollama_endpoint_and_provider_failure(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ai_base_url", "http://ollama:11434/v1")
    client_class = httpx.Client
    def respond(request):
        assert request.url.host == "ollama"
        return httpx.Response(503, text="model unavailable")
    monkeypatch.setattr(llm.httpx, "Client", lambda **kwargs: client_class(transport=httpx.MockTransport(respond)))
    with pytest.raises(llm.AIUnavailable):
        llm.complete([{"role": "user", "content": "Fix code"}])


def test_grounded_fallback_works_without_chroma_or_model(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "disabled")
    def unavailable():
        raise ConnectionError("offline")
    monkeypatch.setattr(rag, "collection", unavailable)
    problem = SimpleNamespace(title="Rollback", summary="Preserve a wallet balance on transaction failure", tags=["transactions"], hints=["Validate before changing balances."])
    result = rag.generate_hint(problem, "python", 1)
    assert result["text"] == problem.hints[0]
    assert result["retrieval"] == "bundled-docs"
    assert result["sources"] and all(row["url"].startswith("https://docs.python.org/") for row in result["sources"])


def test_vector_embedding_is_normalized_and_stable():
    embedding = rag.local_embedding("transaction rollback preserves account balances")
    assert len(embedding) == 384
    assert sum(value * value for value in embedding) == pytest.approx(1)
    assert embedding == rag.local_embedding("transaction rollback preserves account balances")

