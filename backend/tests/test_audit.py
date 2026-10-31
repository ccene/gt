"""Audit regression tests — one per issue found in the full-project audit.

Each test encodes the *expected* (fixed) behavior. They were written first and
confirmed failing before the fixes landed.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


def _join(client, code, player_id=None):
    payload = {"code": code}
    if player_id is not None:
        payload["player_id"] = player_id
    return client.post("/api/sessions/join", json=payload)


def _mk_player_with_character(client, name, char_name="Char", hp=10):
    p = client.post("/api/players", json={"name": name, "email": f"{name.lower()}@example.com"}).json()
    c = client.post(
        f"/api/players/{p['id']}/character", json={"name": char_name, "sheet": {"hp": hp}}
    ).json()
    return p, c


# --- a1: ACCESS_TOKEN must gate host-capable endpoints when configured ---

def test_access_token_gates_host_endpoints(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "access_token", "lan-secret")
    assert client.post("/api/sessions", json={}).status_code == 403
    assert client.post("/api/stories/generate", json={"prompt": "x"}).status_code == 403
    assert client.post("/api/auth/passkey/register/options").status_code == 403
    # wrong token rejected, right token accepted
    assert client.post("/api/sessions", json={}, headers={"X-Access-Token": "nope"}).status_code == 403
    r = client.post("/api/sessions", json={}, headers={"X-Access-Token": "lan-secret"})
    assert r.status_code == 200
    r = client.post(
        "/api/stories/generate", json={"prompt": "x"}, headers={"X-Access-Token": "lan-secret"}
    )
    assert r.status_code == 200


def test_access_token_empty_means_open(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "access_token", "")
    assert client.post("/api/sessions", json={}).status_code == 200


# --- a2: player_token must be validated; WS requires it; membership recorded ---

def test_ws_requires_valid_player_token(client, session):
    from starlette.websockets import WebSocketDisconnect

    sid = session["id"]
    token = _join(client, session["code"]).json()["player_token"]
    with pytest.raises(WebSocketDisconnect):  # no token -> rejected
        with client.websocket_connect(f"/api/sessions/{sid}/ws"):
            pass
    with pytest.raises(WebSocketDisconnect):  # bad token -> rejected
        with client.websocket_connect(f"/api/sessions/{sid}/ws?token=wrong"):
            pass
    with client.websocket_connect(f"/api/sessions/{sid}/ws?token={token}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"


def test_ws_chat_resolves_sender_from_token(client, session):
    sid = session["id"]
    p, _c = _mk_player_with_character(client, "Aria", "Aria the Bold")
    token = _join(client, session["code"], player_id=p["id"]).json()["player_token"]
    with client.websocket_connect(f"/api/sessions/{sid}/ws?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "from": "EVIL-SPOOF", "text": "hi"})
        ev = ws.receive_json()
        assert ev["type"] == "chat"
        assert ev["payload"]["from"] == "Aria"  # server-side attribution, not client-supplied


def test_join_records_membership(client, session):
    import db

    p, _c = _mk_player_with_character(client, "Bram")
    r = _join(client, session["code"], player_id=p["id"])
    assert r.status_code == 200
    row = db.query_one(
        "SELECT player_id FROM session_players WHERE session_id = ? AND player_id = ?",
        (session["id"], p["id"]),
    )
    assert row is not None


# --- a3: characters must be scoped to session members ---

def test_snapshot_scoped_to_session_members(client):
    s1 = client.post("/api/sessions", json={}).json()
    p1, _c1 = _mk_player_with_character(client, "Aria", "AriaC")
    _join(client, s1["code"], player_id=p1["id"])

    s2 = client.post("/api/sessions", json={}).json()
    p2, _c2 = _mk_player_with_character(client, "Bob", "BobC")
    snap2 = _join(client, s2["code"], player_id=p2["id"]).json()["snapshot"]
    names = [c["name"] for c in snap2["characters"]]
    assert "BobC" in names
    assert "AriaC" not in names  # no cross-session leak


def test_save_point_emails_scoped_to_members(client):
    import emailer

    s1 = client.post("/api/sessions", json={}).json()
    p1, _c1 = _mk_player_with_character(client, "Aria", "AriaC")
    _join(client, s1["code"], player_id=p1["id"])

    s2 = client.post("/api/sessions", json={}).json()
    p2, _c2 = _mk_player_with_character(client, "Bob", "BobC")
    _join(client, s2["code"], player_id=p2["id"])

    results = emailer.send_all_save_points(s2["id"])
    chars = [r["character"] for r in results]
    assert "BobC" in chars
    assert "AriaC" not in chars


# --- a4: passkey endpoints must validate Origin against the request Host ---

def test_passkey_rejects_foreign_origin(client):
    # TestClient sends Host: testserver; an Origin for another host must be refused
    r = client.post(
        "/api/auth/passkey/register/options",
        headers={"origin": "https://evil.example", "host": "testserver"},
    )
    assert r.status_code == 400
    r = client.post(
        "/api/auth/passkey/login/options",
        headers={"origin": "https://evil.example", "host": "testserver"},
    )
    assert r.status_code == 400
    # matching origin is fine
    r = client.post(
        "/api/auth/passkey/register/options",
        headers={"origin": "http://testserver", "host": "testserver"},
    )
    assert r.status_code == 200


# --- a5: prompt length cap on story generation ---

def test_generate_story_prompt_is_capped(client):
    r = client.post("/api/stories/generate", json={"prompt": "x" * 5000})
    assert r.status_code == 422
    r = client.post("/api/stories/generate", json={"prompt": "short idea"})
    assert r.status_code == 200


# --- a6: malformed payloads must be 422, never 500 ---

def test_combat_update_rejects_non_numeric(client, session):
    sid = session["id"]
    token = session["admin_token"]
    client.post(
        f"/api/sessions/{sid}/combat",
        json={"combatants": [{"name": "Goblin", "hp": 7, "max_hp": 7}]},
        headers={"X-Admin-Token": token},
    )
    import db

    cid = db.query_one("SELECT id FROM combatants WHERE session_id = ?", (sid,))["id"]
    r = client.post(f"/api/sessions/{sid}/combat/{cid}", json={"hp_delta": "abc"})
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
    r = client.post(f"/api/sessions/{sid}/combat/{cid}", json={"initiative": None})
    assert r.status_code == 422


def test_create_session_rejects_non_int_story_id(client):
    assert client.post("/api/sessions", json={"story_id": [1]}).status_code == 422
    assert client.post("/api/sessions", json={"story_id": {"x": 1}}).status_code == 422


def test_set_map_validates_markers(client, session):
    token = session["admin_token"]
    sid = session["id"]
    assert client.post(f"/api/sessions/{sid}/maps", json={"label": "x", "markers": "nope"},
                       headers={"X-Admin-Token": token}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/maps", json={"label": "x", "markers": [{"x": "a", "y": 1, "label": "p"}]},
                       headers={"X-Admin-Token": token}).status_code == 422
    r = client.post(f"/api/sessions/{sid}/maps", json={"label": "x", "markers": [{"x": 1, "y": 2, "label": "p"}]},
                    headers={"X-Admin-Token": token})
    assert r.status_code == 200


# --- a7: log_event broadcast ts must belong to its own row (no race) ---

def test_log_event_ts_matches_own_row(client, session, monkeypatch):
    import db
    import hub

    orig_query_one = db.query_one

    def sneaky_query_one(sql, params=()):
        # simulate another writer slipping in between the INSERT and the
        # last_insert_rowid() SELECT (the race window in the old code)
        if "last_insert_rowid" in sql:
            db.execute(
                "INSERT INTO session_events (session_id, kind, payload) VALUES (?, 'other', '{}')",
                (session["id"],),
            )
        return orig_query_one(sql, params)

    monkeypatch.setattr(db, "query_one", sneaky_query_one)
    event = asyncio.run(hub.hub.log_event(session["id"], "dice", {"total": 42}))
    own = db.query_one(
        "SELECT created_at FROM session_events WHERE session_id = ? AND kind = 'dice'", (session["id"],)
    )["created_at"]
    assert event["ts"] == own


# --- a8: snapshot must cap the event history ---

def test_snapshot_caps_events(client, session):
    import db

    for i in range(300):
        db.execute(
            "INSERT INTO session_events (session_id, kind, payload) VALUES (?, 'chat', ?)",
            (session["id"], db.dumps({"n": i})),
        )
    snap = _join(client, session["code"]).json()["snapshot"]
    assert len(snap["events"]) == 200
    assert snap["events"][-1]["payload"]["n"] == 299  # keeps the newest


# --- a9: transcription must never write audio to disk ---

def test_transcribe_never_writes_audio_to_disk(client, session, monkeypatch):
    import io
    import tempfile

    import audio

    monkeypatch.setattr(audio, "available", lambda: True)

    class FakeSegment:
        text = " hello table "

    class FakeInfo:
        language = "en"
        duration = 1.0

    class FakeModel:
        def transcribe(self, audio_in, vad_filter=False):
            assert isinstance(audio_in, io.BytesIO), f"audio must stay in memory, got {type(audio_in)}"
            return iter([FakeSegment()]), FakeInfo()

    monkeypatch.setattr(audio, "_load_model", lambda: FakeModel())

    def no_tmp_file(*args, **kwargs):
        raise AssertionError("transcribe wrote audio to a temp file on disk")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", no_tmp_file)
    result = audio.transcribe(b"fake-audio-bytes")
    assert result["text"] == "hello table"


# --- a10: seed_demo must be idempotent and seed a complete demo session ---

def test_seed_demo_is_idempotent_and_complete(tmp_path):
    db_file = tmp_path / "seed.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_file}"}
    for i in range(2):
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seed_demo.py")],
            env=env, capture_output=True, text=True, cwd=str(ROOT),
            timeout=120,
        )
        assert r.returncode == 0, f"seed run {i + 1} failed:\n{r.stderr[-2000:]}"

    sys.path.insert(0, str(ROOT / "backend"))
    import db
    from config import settings

    db.reset_for_tests(db_file)
    settings.ensure_dirs()
    db.get_conn()
    sess = db.query_one("SELECT * FROM sessions WHERE code = 'DEMO42'")
    assert sess is not None
    # demo session is 'playing' -> campaign clock must be running
    assert sess["campaign_started_at"] and sess["campaign_ends_at"]
    assert sess["campaign_minutes"] == 60
    # membership recorded for the 4 demo players
    members = db.query("SELECT player_id FROM session_players WHERE session_id = ?", (sess["id"],))
    assert len(members) == 4
    # story content is campaign-shaped so the story panel renders it
    story = db.query_one("SELECT content FROM stories WHERE id = ?", (sess["story_id"],))
    content = db.loads(story["content"])
    assert "campaign" in content and len(content["campaign"]["chapters"]) == 3
    db.reset_for_tests(db_file)
