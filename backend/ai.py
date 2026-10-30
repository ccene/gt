import hashlib
import json
import time
from datetime import UTC, datetime

import httpx

import db
from config import settings

# Approximate USD per 1M tokens (input, output) used for budget accounting.
PRICES = {
    "mistral-small-latest": (0.15, 0.60),
    "mistral-large-latest": (0.50, 1.50),
    "pixtral-large-latest": (0.50, 1.50),
    "mistral-embed": (0.10, 0.0),
}

TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class BudgetExceeded(Exception):
    pass


def _month_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def month_spend_usd() -> float:
    row = db.query_one(
        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM ai_usage WHERE month = ?",
        (_month_key(),),
    )
    return float(row["total"]) if row else 0.0


def budget_remaining() -> float:
    return max(0.0, settings.mistral_monthly_budget_usd - month_spend_usd())


def _record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    in_p, out_p = PRICES.get(model, (0.5, 1.5))
    cost = (input_tokens * in_p + output_tokens * out_p) / 1_000_000
    db.execute(
        "INSERT INTO ai_usage (month, model, input_tokens, output_tokens, cost_usd)"
        " VALUES (?, ?, ?, ?, ?)",
        (_month_key(), model, input_tokens, output_tokens, cost),
    )


def _cache_key(kind: str, payload: dict) -> str:
    return hashlib.sha256(f"{kind}:{json.dumps(payload, sort_keys=True)}".encode()).hexdigest()


def _cache_get(key: str):
    row = db.query_one("SELECT response FROM ai_cache WHERE key = ?", (key,))
    return json.loads(row["response"]) if row else None


def _cache_put(key: str, value: dict) -> None:
    db.execute("INSERT OR REPLACE INTO ai_cache (key, response) VALUES (?, ?)", (key, db.dumps(value)))


def _fallback(kind: str, payload: dict) -> dict:
    prompt = str(payload.get("prompt", ""))
    if kind == "chat":
        return {
            "provider": "local-fallback",
            "text": (
                "The torchlight flickers across the table. (Local fallback narration — "
                "no AI provider configured.)"
            ),
            "prompt_preview": prompt[:120],
        }
    if kind == "vision":
        return {
            "provider": "local-fallback",
            "description": "Vision unavailable offline.",
            "prompt_preview": prompt[:120],
        }
    return {"provider": "local-fallback", "result": None, "prompt_preview": prompt[:120]}


async def _mistral_chat(model: str, messages: list[dict], use_cache: bool = True) -> dict | None:
    if not settings.mistral_api_key:
        return None
    if budget_remaining() <= 0:
        raise BudgetExceeded("monthly Mistral budget cap reached; using local fallback")
    payload = {"model": model, "messages": messages}
    key = _cache_key("mistral-chat", payload)
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            cached = dict(cached)
            cached["cached"] = True
            return cached
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{settings.mistral_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.mistral_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        _record_usage(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        result = {"provider": "mistral", "model": model, "text": text}
        _cache_put(key, result)
        return result
    except (httpx.HTTPError, KeyError, ValueError, BudgetExceeded):
        return None


async def _ollama_chat(messages: list[dict]) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={"model": settings.ollama_model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
        return {"provider": "ollama", "model": settings.ollama_model, "text": data["message"]["content"]}
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def chat(messages: list[dict], model: str | None = None, use_cache: bool = True) -> dict:
    """DM narration / notes. Mistral first, Ollama local, then deterministic fallback."""
    model = model or settings.mistral_model
    try:
        result = await _mistral_chat(model, messages, use_cache=use_cache)
        if result is not None:
            return result
    except BudgetExceeded:
        pass
    result = await _ollama_chat(messages)
    if result is not None:
        return result
    return _fallback("chat", {"prompt": messages[-1].get("content", "") if messages else ""})


async def chat_large(messages: list[dict]) -> dict:
    """Story generation / shaping — uses the large model, never in the play loop."""
    try:
        result = await _mistral_chat(settings.mistral_large_model, messages, use_cache=True)
        if result is not None:
            return result
    except BudgetExceeded:
        pass
    result = await _ollama_chat(messages)
    if result is not None:
        return result
    return _fallback("chat", {"prompt": messages[-1].get("content", "") if messages else ""})


async def narrate_scene(scene: str, characters: list[str]) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "You are the dungeon master's narrator for a tabletop RPG. "
                "Write 2-4 vivid sentences of scene narration, present tense. "
                "No dice mechanics, no meta commentary."
            ),
        },
        {"role": "user", "content": f"Scene: {scene}\nHeroes present: {', '.join(characters) or 'unknown'}"},
    ]
    return await chat(messages)


async def summarize_notes(transcript: str) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "Summarize the table conversation into short bullet notes "
                "and a one-line 'next step' suggestion."
            ),
        },
        {"role": "user", "content": transcript[:8000]},
    ]
    return await chat(messages)


def health() -> dict:
    return {
        "mistral_configured": bool(settings.mistral_api_key),
        "ollama_base_url": settings.ollama_base_url,
        "month_spend_usd": round(month_spend_usd(), 6),
        "budget_usd": settings.mistral_monthly_budget_usd,
        "budget_remaining_usd": round(budget_remaining(), 6),
    }


_last_tick = 0.0


def time_now() -> float:
    return time.time()
