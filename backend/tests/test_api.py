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


# --- campaign / story generation from host input ---

def test_generate_story_from_host_prompt_defaults_to_one_hour(client):
    r = client.post(
        "/api/stories/generate",
        json={"prompt": "A crew of sky-pirates raids a cloud castle", "length_hours": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["length_hours"] == 1.0
    campaign = body["content"]["campaign"]
    assert campaign["title"]
    # ~20 min per chapter -> a 1-hour campaign gets 3 chapters
    assert len(campaign["chapters"]) == 3
    assert "provider" in body["content"]


def test_generate_story_length_drives_chapter_count(client):
    r = client.post("/api/stories/generate", json={"prompt": "heist at the gem museum", "length_hours": 2})
    assert r.status_code == 200
    assert len(r.json()["content"]["campaign"]["chapters"]) == 6


def test_generate_story_clamps_length(client):
    r = client.post("/api/stories/generate", json={"prompt": "x", "length_hours": 99})
    assert r.json()["length_hours"] == 8.0
    r = client.post("/api/stories/generate", json={"prompt": "x", "length_hours": 0.01})
    assert r.json()["length_hours"] == 0.25


def test_session_campaign_defaults_to_60_minutes(client):
    s = client.post("/api/sessions", json={}).json()
    assert s["campaign"]["minutes"] == 60
    assert s["campaign"]["started_at"] is None


def test_session_campaign_custom_length_and_story(client):
    story = client.post("/api/stories/generate", json={"prompt": "vampire ball", "length_hours": 1}).json()
    s = client.post("/api/sessions", json={"story_id": story["id"], "campaign_minutes": 90}).json()
    assert s["campaign"]["minutes"] == 90
    assert client.post("/api/sessions", json={"story_id": 9999}).status_code == 422


def test_campaign_clock_starts_on_playing_and_extend_adds_time(client, session):
    token = session["admin_token"]
    sid = session["id"]
    r = client.post(f"/api/sessions/{sid}/state", json={"state": "playing"}, headers={"X-Admin-Token": token})
    camp = r.json()["campaign"]
    assert camp["started_at"] and camp["ends_at"]
    # extend without token -> 403
    assert client.post(f"/api/sessions/{sid}/campaign/extend", json={"minutes": 30}).status_code == 403
    r = client.post(
        f"/api/sessions/{sid}/campaign/extend", json={"minutes": 30}, headers={"X-Admin-Token": token}
    )
    assert r.status_code == 200
    from datetime import datetime

    ends = datetime.fromisoformat(r.json()["ends_at"])
    started = datetime.fromisoformat(camp["started_at"])
    # 60 min default + 30 min extension = 90 min total
    assert abs((ends - started).total_seconds() - 90 * 60) < 5


def test_extend_before_start_bumps_minutes(client, session):
    r = client.post(
        f"/api/sessions/{session['id']}/campaign/extend",
        json={"minutes": 45},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert r.json()["minutes"] == 105


def test_snapshot_includes_campaign_story_combat(client, session):
    story = client.post("/api/stories/generate", json={"prompt": "dragon heist"}).json()
    client.post("/api/sessions", json={"story_id": story["id"], "campaign_minutes": 60})
    s = client.post("/api/sessions", json={"story_id": story["id"], "campaign_minutes": 60}).json()
    joined = client.post("/api/sessions/join", json={"code": s["code"]}).json()
    snap = joined["snapshot"]
    assert snap["campaign"]["minutes"] == 60
    assert snap["story"]["id"] == story["id"]
    assert snap["story"]["content"]["campaign"]["title"]
    assert snap["combat"]["active"] is False


# --- combat / initiative ---

def _start_combat(client, session):
    return client.post(
        f"/api/sessions/{session['id']}/combat",
        json={
            "combatants": [
                {"name": "Aria", "hp": 30, "max_hp": 30, "ac": 16, "init_mod": 2},
                {"name": "Goblin", "hp": 7, "max_hp": 7, "is_enemy": True, "ac": 13, "init_mod": 1},
                {"name": "Goblin 2", "hp": 7, "max_hp": 7, "is_enemy": True, "init_mod": 1},
            ]
        },
        headers={"X-Admin-Token": session["admin_token"]},
    )


def test_combat_requires_admin_and_combatants(client, session):
    assert client.post(f"/api/sessions/{session['id']}/combat", json={"combatants": []}).status_code == 403
    r = client.post(
        f"/api/sessions/{session['id']}/combat",
        json={"combatants": []},
        headers={"X-Admin-Token": session["admin_token"]},
    )
    assert r.status_code == 422


def test_combat_start_roll_next_flow(client, session):
    sid = session["id"]
    token = session["admin_token"]
    r = _start_combat(client, session)
    assert r.status_code == 200
    state = r.json()
    assert state["active"] and len(state["combatants"]) == 3

    r = client.post(f"/api/sessions/{sid}/combat/roll", headers={"X-Admin-Token": token})
    state = r.json()
    inits = [c["initiative"] for c in state["combatants"]]
    assert inits == sorted(inits, reverse=True)  # sorted descending
    assert all(2 <= i <= 22 for i in inits)  # d20 + init_mod
    assert state["round"] == 1 and state["turn_index"] == 0

    r = client.post(f"/api/sessions/{sid}/combat/next", headers={"X-Admin-Token": token})
    assert r.json()["turn_index"] == 1
    client.post(f"/api/sessions/{sid}/combat/next", headers={"X-Admin-Token": token})
    r = client.post(f"/api/sessions/{sid}/combat/next", headers={"X-Admin-Token": token})
    assert r.json()["turn_index"] == 0 and r.json()["round"] == 2


def test_combat_update_hp_and_conditions(client, session):
    sid = session["id"]
    state = _start_combat(client, session).json()
    goblin = next(c for c in state["combatants"] if c["name"] == "Goblin")
    r = client.post(f"/api/sessions/{sid}/combat/{goblin['id']}", json={"hp_delta": -3, "condition_toggle": "poisoned"})
    assert r.status_code == 200
    updated = next(c for c in r.json()["combatants"] if c["id"] == goblin["id"])
    assert updated["hp"] == 4 and "poisoned" in updated["conditions"]
    # clamp at 0 and max_hp
    r = client.post(f"/api/sessions/{sid}/combat/{goblin['id']}", json={"hp_delta": -99})
    assert next(c for c in r.json()["combatants"] if c["id"] == goblin["id"])["hp"] == 0
    # toggle off
    r = client.post(f"/api/sessions/{sid}/combat/{goblin['id']}", json={"condition_toggle": "poisoned"})
    assert "poisoned" not in next(c for c in r.json()["combatants"] if c["id"] == goblin["id"])["conditions"]
    assert client.post(f"/api/sessions/{sid}/combat/999", json={"hp": 1}).status_code == 404


def test_combat_end_clears(client, session):
    sid = session["id"]
    token = session["admin_token"]
    _start_combat(client, session)
    r = client.post(f"/api/sessions/{sid}/combat/end", headers={"X-Admin-Token": token})
    assert r.json()["active"] is False
    joined = client.post("/api/sessions/join", json={"code": session["code"]}).json()
    assert joined["snapshot"]["combat"]["active"] is False


# --- live character sheet updates, chat, recap, adv/dis rolls ---

def test_character_update_broadcast_fields(client, session):
    p = client.post("/api/players", json={"name": "Aria"}).json()
    c = client.post(f"/api/players/{p['id']}/character", json={"name": "Aria the Bold", "sheet": {"hp": 30}}).json()
    r = client.post(
        f"/api/sessions/{session['id']}/characters/{c['id']}/update",
        json={"hp": 24, "conditions": ["concentrating"]},
    )
    assert r.status_code == 200
    assert r.json()["sheet"]["hp"] == 24 and r.json()["sheet"]["conditions"] == ["concentrating"]
    assert client.post(f"/api/sessions/{session['id']}/characters/999/update", json={"hp": 1}).status_code == 404


def test_chat_rest_and_recap(client, session):
    sid = session["id"]
    p = client.post("/api/players", json={"name": "Aria"}).json()
    token = client.post("/api/sessions/join", json={"code": session["code"], "player_id": p["id"]}).json()[
        "player_token"
    ]
    hdrs = {"X-Player-Token": token}
    r = client.post(f"/api/sessions/{sid}/chat", json={"from": "SPOOF", "text": "I check the door"}, headers=hdrs)
    assert r.status_code == 200
    assert r.json()["text"] == "I check the door"
    assert r.json()["from"] == "Aria"  # sender resolved from token, not the payload
    # no/invalid token -> 403; empty text -> 422
    assert client.post(f"/api/sessions/{sid}/chat", json={"text": "hi"}).status_code == 403
    bad = client.post(f"/api/sessions/{sid}/chat", json={"text": "hi"}, headers={"X-Player-Token": "bad"})
    assert bad.status_code == 403
    assert client.post(f"/api/sessions/{sid}/chat", json={"text": "  "}, headers=hdrs).status_code == 422
    r = client.post(f"/api/sessions/{sid}/narrate", json={"scene": "A cold wind blows through the hall."})
    assert r.status_code == 200
    r = client.post(f"/api/sessions/{sid}/recap")
    assert r.status_code == 200 and isinstance(r.json()["text"], str) and r.json()["text"]


def test_roll_advantage_disadvantage(client, session):
    r = client.post(
        f"/api/sessions/{session['id']}/roll",
        json={"faces": 20, "modifier": 5, "mode": "adv", "roller": "Aria"},
    )
    body = r.json()
    assert body["mode"] == "adv" and len(body["rolls"]) == 2
    assert body["total"] == max(body["rolls"]) + 5 and body["kept"] == max(body["rolls"])
    r = client.post(f"/api/sessions/{session['id']}/roll", json={"faces": 20, "mode": "dis"})
    assert r.json()["total"] == min(r.json()["rolls"])
    # adv on non-d20 falls back to a normal roll
    r = client.post(f"/api/sessions/{session['id']}/roll", json={"faces": 6, "mode": "adv"})
    assert r.json()["mode"] == "normal" and len(r.json()["rolls"]) == 1
    # invalid mode rejected
    assert client.post(f"/api/sessions/{session['id']}/roll", json={"mode": "lucky"}).status_code == 422
