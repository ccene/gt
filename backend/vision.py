"""Optional camera vision via Mistral Pixtral (EU endpoint only).

Frames are sent only on an explicit host action, carry no metadata beyond the
image, and are discarded after the call. A visible 'vision active' event is
broadcast to all clients so players know the camera is in use.
"""

import base64

import httpx

import ai
from config import settings

TIMEOUT = httpx.Timeout(60.0, connect=5.0)


DEFAULT_PROMPT = "Describe what is on the game table: maps, miniatures, dice, papers. Be concise."


async def describe_image(image_bytes: bytes, prompt: str = DEFAULT_PROMPT) -> dict:
    if not settings.mistral_api_key:
        return {
            "provider": "local-fallback",
            "description": "Vision requires MISTRAL_API_KEY (Pixtral, EU endpoint). Offline mode: vision disabled.",
        }
    if ai.budget_remaining() <= 0:
        return {
            "provider": "budget-capped",
            "description": "Monthly budget cap reached; vision paused until next month.",
        }
    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": settings.mistral_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
    }
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
        ai._record_usage(
            settings.mistral_vision_model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
        return {"provider": "mistral-pixtral", "description": text}
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return {"provider": "error", "description": f"vision call failed: {type(exc).__name__}"}
