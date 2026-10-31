import base64
import struct
import zlib


def _png_1px() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"\x00\xff\x00\x00")
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


PNG_1PX = base64.b64encode(_png_1px()).decode()


def test_transcribe_requires_whisper(client, session, monkeypatch):
    import audio

    monkeypatch.setattr(audio, "available", lambda: False)
    resp = client.post(
        f"/api/sessions/{session['id']}/transcribe",
        files={"file": ("chunk.webm", b"fake-audio", "audio/webm")},
    )
    assert resp.status_code == 503


def test_transcribe_happy_path_mocked(client, session, monkeypatch):
    import audio

    monkeypatch.setattr(audio, "available", lambda: True)
    monkeypatch.setattr(
        audio,
        "transcribe",
        lambda data: {
            "provider": "local-whisper",
            "language": "en",
            "duration_s": 2.0,
            "text": "we should check the left door",
        },
    )
    resp = client.post(
        f"/api/sessions/{session['id']}/transcribe",
        files={"file": ("chunk.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"].startswith("we should")
    events = client.get(f"/api/sessions/{session['id']}/events").json()
    assert events[-1]["kind"] == "transcript"


def test_transcribe_size_limit(client, session, monkeypatch):
    import audio

    monkeypatch.setattr(audio, "available", lambda: True)
    big = b"x" * (26 * 1024 * 1024)
    resp = client.post(
        f"/api/sessions/{session['id']}/transcribe",
        files={"file": ("big.webm", big, "audio/webm")},
    )
    assert resp.status_code == 422


def test_vision_requires_admin(client, session):
    resp = client.post(
        f"/api/sessions/{session['id']}/vision",
        json={"image": PNG_1PX},
    )
    assert resp.status_code == 403


def test_vision_bad_base64(client, session):
    resp = client.post(
        f"/api/sessions/{session['id']}/vision",
        json={"image": "!!!not-base64!!!"},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert resp.status_code == 422


def test_vision_fallback_without_key(client, session, monkeypatch):
    monkeypatch.setattr("vision.settings.mistral_api_key", "")
    resp = client.post(
        f"/api/sessions/{session['id']}/vision",
        json={"image": f"data:image/png;base64,{PNG_1PX}"},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "local-fallback"
    events = client.get(f"/api/sessions/{session['id']}/events").json()
    kinds = [e["kind"] for e in events]
    assert "vision_active" in kinds and "vision" in kinds


def test_vision_budget_capped(client, session, monkeypatch):
    import ai
    import db

    db.execute(
        "INSERT INTO ai_usage (month, model, input_tokens, output_tokens, cost_usd) VALUES (?, 'm', 0, 0, 999)",
        (ai._month_key(),),
    )
    monkeypatch.setattr("vision.settings.mistral_api_key", "test-key")
    resp = client.post(
        f"/api/sessions/{session['id']}/vision",
        json={"image": PNG_1PX},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert resp.status_code == 200
    assert resp.json()["provider"] == "budget-capped"


def test_audio_available_flag():
    import audio

    assert isinstance(audio.available(), bool)
