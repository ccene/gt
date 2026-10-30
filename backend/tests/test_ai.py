import pytest

import ai
import db


@pytest.mark.asyncio
async def test_fallback_when_no_providers(client):
    result = await ai.chat([{"role": "user", "content": "hello"}])
    assert result["provider"] == "local-fallback"
    assert result["text"]


@pytest.mark.asyncio
async def test_budget_cap_forces_fallback(client, monkeypatch):
    db.execute(
        "INSERT INTO ai_usage (month, model, input_tokens, output_tokens, cost_usd) VALUES (?, 'm', 0, 0, 999)",
        (ai._month_key(),),
    )
    monkeypatch.setattr(ai.settings, "mistral_api_key", "test-key")
    result = await ai.chat([{"role": "user", "content": "hello"}])
    assert result["provider"] in ("local-fallback", "ollama")
    assert ai.budget_remaining() == 0.0


@pytest.mark.asyncio
async def test_mistral_called_and_cached(client, monkeypatch):
    calls = []

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{"message": {"content": "Once upon a time..."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(url)
            assert headers["Authorization"] == "Bearer test-key"
            return FakeResp()

    fake_httpx = type(
        "H",
        (),
        {"AsyncClient": FakeClient, "Timeout": ai.httpx.Timeout, "HTTPError": ai.httpx.HTTPError},
    )
    monkeypatch.setattr(ai, "httpx", fake_httpx)
    monkeypatch.setattr(ai.settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(ai.settings, "ollama_base_url", "http://127.0.0.1:1")

    msgs = [{"role": "user", "content": "tell me a story"}]
    r1 = await ai.chat(msgs)
    assert r1["provider"] == "mistral" and r1["text"] == "Once upon a time..."
    r2 = await ai.chat(msgs)
    assert r2.get("cached") is True
    assert len(calls) == 1  # second call served from cache
    spend = ai.month_spend_usd()
    assert spend > 0


@pytest.mark.asyncio
async def test_narrate_scene_fallback_shape(client):
    result = await ai.narrate_scene("A tavern", ["Aria"])
    assert "text" in result and "provider" in result
