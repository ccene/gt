def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_player_and_character_flow(client):
    p = client.post("/api/players", json={"name": "Aria", "email": "aria@example.com"}).json()
    assert p["id"] and p["name"] == "Aria"
    c = client.post(
        f"/api/players/{p['id']}/character",
        json={"name": "Aria the Bold", "sheet": {"hp": 30, "class": "Fighter", "level": 3}},
    ).json()
    assert c["sheet"]["hp"] == 30
    players = client.get("/api/players").json()
    assert players[0]["character"]["name"] == "Aria the Bold"


def test_character_requires_player(client):
    resp = client.post("/api/players/999/character", json={"name": "Ghost"})
    assert resp.status_code == 404


def test_character_requires_name(client):
    p = client.post("/api/players", json={"name": "Bob"}).json()
    resp = client.post(f"/api/players/{p['id']}/character", json={"sheet": {}})
    assert resp.status_code == 422


def test_character_upsert(client):
    p = client.post("/api/players", json={"name": "Cleo"}).json()
    client.post(f"/api/players/{p['id']}/character", json={"name": "Cleo", "sheet": {"hp": 10}})
    c2 = client.post(f"/api/players/{p['id']}/character", json={"name": "Cleo", "sheet": {"hp": 12}})
    assert c2.json()["sheet"]["hp"] == 12
    players = client.get("/api/players").json()
    assert len([x for x in players if x["character"]]) == 1


def test_session_lifecycle(client):
    s = client.post("/api/sessions", json={}).json()
    assert len(s["code"]) == 6 and s["state"] == "lobby"
    joined = client.post("/api/sessions/join", json={"code": s["code"]}).json()
    assert joined["session_id"] == s["id"]
    assert joined["snapshot"]["session"]["state"] == "lobby"
    # bad code
    assert client.post("/api/sessions/join", json={"code": "ZZZZZZ"}).status_code == 404
    # state transitions require admin token
    assert client.post(f"/api/sessions/{s['id']}/state", json={"state": "playing"}).status_code == 403
    r = client.post(
        f"/api/sessions/{s['id']}/state",
        json={"state": "playing"},
        headers={"X-Admin-Token": s["admin_token"]},
    )
    assert r.status_code == 200 and r.json()["state"] == "playing"
    # invalid state
    bad = client.post(
        f"/api/sessions/{s['id']}/state",
        json={"state": "flying"},
        headers={"X-Admin-Token": s["admin_token"]},
    )
    assert bad.status_code == 422


def test_chapter_advances_save_point(client, session):
    r = client.post(
        f"/api/sessions/{session['id']}/chapter", headers={"X-Admin-Token": session["admin_token"]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_index"] == 1
    assert body["save_point"]["label"] == "Chapter 2"
    assert body["state"] == "loading"


def test_roll_endpoint(client, session):
    r = client.post(
        f"/api/sessions/{session['id']}/roll",
        json={"count": 2, "faces": 6, "modifier": 1, "roller": "Aria"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rolls"]) == 2 and body["total"] == sum(body["rolls"]) + 1
    events = client.get(f"/api/sessions/{session['id']}/events").json()
    assert events[-1]["kind"] == "dice"


def test_roll_validation(client, session):
    resp = client.post(f"/api/sessions/{session['id']}/roll", json={"faces": 7})
    assert resp.status_code == 422


def test_narrate_fallback(client, session):
    r = client.post(f"/api/sessions/{session['id']}/narrate", json={"scene": "A dark cave"})
    assert r.status_code == 200
    assert r.json()["provider"] in ("mistral", "ollama", "local-fallback")


def test_notes_requires_transcript(client, session):
    assert client.post(f"/api/sessions/{session['id']}/notes", json={"transcript": " "}).status_code == 422
    r = client.post(f"/api/sessions/{session['id']}/notes", json={"transcript": "The party argued about the map."})
    assert r.status_code == 200


def test_end_session_writes_outbox(client, session, tmp_path):
    p = client.post("/api/players", json={"name": "Dana", "email": "dana@example.com"}).json()
    client.post(f"/api/players/{p['id']}/character", json={"name": "Dana", "sheet": {"hp": 20}})
    r = client.post(
        f"/api/sessions/{session['id']}/state",
        json={"state": "ended"},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert r.status_code == 200
    events = client.get(f"/api/sessions/{session['id']}/events").json()
    ended = [e for e in events if e["kind"] == "session_ended"]
    assert ended and ended[0]["payload"]["emails"][0]["via"] == "outbox"


def test_map_requires_admin(client, session):
    assert client.post(f"/api/sessions/{session['id']}/maps", json={"label": "dungeon"}).status_code == 403
    r = client.post(
        f"/api/sessions/{session['id']}/maps",
        json={"label": "dungeon", "markers": [{"x": 10, "y": 20, "label": "party"}]},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert r.status_code == 200 and r.json()["markers"][0]["label"] == "party"


def test_stories(client):
    imp = client.post("/api/stories/import", json={"title": "Curse of the Marsh", "content": {"chapters": []}})
    assert imp.status_code == 200
    gen = client.post("/api/stories/generate", json={"genre": "gothic horror", "tone": "dark"})
    assert gen.status_code == 200
    stories = client.get("/api/stories").json()
    assert len(stories) == 2


def test_ai_health(client):
    body = client.get("/api/ai/health").json()
    assert body["budget_usd"] == 25.0
    assert body["mistral_configured"] is False


def test_relative_db_path_resolves_to_repo_root(tmp_path, monkeypatch):
    import config as cfg

    monkeypatch.setattr(cfg.settings, "database_url", "sqlite:///./data/app.db")
    assert cfg.settings.db_path == (cfg.BASE_DIR / "data" / "app.db").resolve()
