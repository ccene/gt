import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect

import ai
import db
from config import settings
from dice import roll
from emailer import send_all_save_points
from hub import campaign_of, combat_of, hub, session_characters

api = APIRouter(prefix="/api")

SESSION_STATES = ("lobby", "loading", "playing", "chapter_end", "ended")

DEFAULT_CAMPAIGN_MINUTES = 60  # a campaign defaults to 1 hour of play
MIN_CAMPAIGN_MINUTES = 15
MAX_CAMPAIGN_MINUTES = 8 * 60
MAX_STORY_PROMPT_CHARS = 2000
SNAPSHOT_EVENT_LIMIT = 200  # keep hub snapshots bounded (hub mirrors this)


def _check_access_token(x_access_token: str | None) -> None:
    """When ACCESS_TOKEN is configured, host-capable endpoints require it.

    Player-facing flows (join by session code, dice, chat) stay open — the
    6-char session code is their own boundary.
    """
    if not settings.access_token:
        return
    if not x_access_token or not secrets.compare_digest(x_access_token, settings.access_token):
        raise HTTPException(403, "invalid or missing access token")


def _require_session(session_id: int) -> dict:
    row = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not row:
        raise HTTPException(404, "session not found")
    return dict(row)


def _audit(session_id: int | None, actor: str, action: str, detail: dict | None = None) -> None:
    db.execute(
        "INSERT INTO audit_log (session_id, actor, action, detail) VALUES (?, ?, ?, ?)",
        (session_id, actor, action, db.dumps(detail or {})),
    )


def _session_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "state": row["state"],
        "chapter_index": row["chapter_index"],
        "save_point": db.loads(row["save_point"]),
        "campaign": campaign_of(row),
        "clients": hub.count(row["id"]),
    }


def _clamp_campaign_minutes(value) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = DEFAULT_CAMPAIGN_MINUTES
    return max(MIN_CAMPAIGN_MINUTES, min(MAX_CAMPAIGN_MINUTES, minutes))


def _check_admin(session: dict, x_admin_token: str | None) -> None:
    import passkeys

    if x_admin_token and (
        secrets.compare_digest(x_admin_token, session["admin_token"])
        or passkeys.is_valid_admin_session(x_admin_token)
    ):
        return
    raise HTTPException(403, "invalid admin token")


# --- players & characters ---

@api.post("/players")
def create_player(payload: dict):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "name is required")
    cur = db.execute("INSERT INTO players (name, email) VALUES (?, ?)", (name, str(payload.get("email", "")).strip()))
    _audit(None, name, "player.create", {"player_id": cur.lastrowid})
    return {"id": cur.lastrowid, "name": name, "email": payload.get("email", "")}


@api.get("/players")
def list_players():
    rows = db.query(
        "SELECT p.id, p.name, p.email, c.id AS character_id, c.name AS character_name, c.sheet"
        " FROM players p LEFT JOIN characters c ON c.player_id = p.id ORDER BY p.id"
    )
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "character": (
                {"id": r["character_id"], "name": r["character_name"], "sheet": db.loads(r["sheet"])}
                if r["character_id"]
                else None
            ),
        }
        for r in rows
    ]


@api.post("/players/{player_id}/character")
def submit_character(player_id: int, payload: dict):
    if not db.query_one("SELECT id FROM players WHERE id = ?", (player_id,)):
        raise HTTPException(404, "player not found")
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "character name is required")
    sheet = payload.get("sheet", {})
    if not isinstance(sheet, dict):
        raise HTTPException(422, "sheet must be an object")
    existing = db.query_one("SELECT id FROM characters WHERE player_id = ?", (player_id,))
    if existing:
        db.execute(
            "UPDATE characters SET name = ?, sheet = ?, updated_at = datetime('now') WHERE id = ?",
            (name, db.dumps(sheet), existing["id"]),
        )
        cid = existing["id"]
    else:
        cur = db.execute(
            "INSERT INTO characters (player_id, name, sheet) VALUES (?, ?, ?)",
            (player_id, name, db.dumps(sheet)),
        )
        cid = cur.lastrowid
    _audit(None, f"player:{player_id}", "character.submit", {"character_id": cid, "name": name})
    return {"id": cid, "player_id": player_id, "name": name, "sheet": sheet}


# --- stories ---

@api.post("/stories/generate")
async def generate_story(payload: dict, x_access_token: str | None = Header(default=None)):
    """Generate a campaign from the host's free-text input.

    length_hours drives the chapter count (~20 min per chapter); default 1 hour.
    Gated by ACCESS_TOKEN when configured: story generation spends AI budget.
    """
    _check_access_token(x_access_token)
    prompt = str(payload.get("prompt", "")).strip()
    if len(prompt) > MAX_STORY_PROMPT_CHARS:
        raise HTTPException(422, f"prompt too long (max {MAX_STORY_PROMPT_CHARS} chars)")
    genre = str(payload.get("genre", "classic fantasy"))
    tone = str(payload.get("tone", "heroic"))
    try:
        length_hours = float(payload.get("length_hours", 1.0))
    except (TypeError, ValueError):
        length_hours = 1.0
    result = await ai.generate_campaign(prompt, length_hours=length_hours, genre=genre, tone=tone)
    campaign = result["campaign"]
    title = str(campaign.get("title") or f"{genre} adventure ({tone})")
    content = {
        "provider": result["provider"],
        "length_hours": result["length_hours"],
        "campaign": campaign,
    }
    cur = db.execute(
        "INSERT INTO stories (title, source, content) VALUES (?, 'generated', ?)",
        (title, db.dumps(content)),
    )
    return {"id": cur.lastrowid, "title": title, "length_hours": result["length_hours"], "content": content}


@api.post("/stories/import")
def import_story(payload: dict, x_access_token: str | None = Header(default=None)):
    _check_access_token(x_access_token)
    title = str(payload.get("title", "")).strip()
    content = payload.get("content", {})
    if not title:
        raise HTTPException(422, "title is required")
    cur = db.execute(
        "INSERT INTO stories (title, source, content) VALUES (?, 'imported', ?)",
        (title, db.dumps(content)),
    )
    return {"id": cur.lastrowid, "title": title, "source": "imported"}


@api.get("/stories")
def list_stories():
    return [
        {"id": r["id"], "title": r["title"], "source": r["source"], "content": db.loads(r["content"])}
        for r in db.query("SELECT * FROM stories ORDER BY id")
    ]


# --- sessions ---

@api.post("/sessions")
def create_session(payload: dict, x_access_token: str | None = Header(default=None)):
    _check_access_token(x_access_token)
    code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))
    admin_token = secrets.token_urlsafe(32)
    story_id = payload.get("story_id")
    if story_id is not None:
        if not isinstance(story_id, int) or isinstance(story_id, bool):
            raise HTTPException(422, "story_id must be an integer or null")
        if not db.query_one("SELECT id FROM stories WHERE id = ?", (story_id,)):
            raise HTTPException(422, "story_id does not exist")
    campaign_minutes = _clamp_campaign_minutes(payload.get("campaign_minutes", DEFAULT_CAMPAIGN_MINUTES))
    cur = db.execute(
        "INSERT INTO sessions (code, admin_token, story_id, campaign_minutes) VALUES (?, ?, ?, ?)",
        (code, admin_token, story_id, campaign_minutes),
    )
    sid = cur.lastrowid
    assert isinstance(sid, int)
    _audit(
        sid,
        "host",
        "session.create",
        {"code": code, "story_id": story_id, "campaign_minutes": campaign_minutes},
    )
    return {"id": sid, "code": code, "admin_token": admin_token, **_session_public(_require_session(sid))}


@api.get("/sessions/{session_id}")
def get_session(session_id: int):
    return _session_public(_require_session(session_id))


@api.post("/sessions/join")
def join_session(payload: dict):
    code = str(payload.get("code", "")).strip().upper()
    row = db.query_one("SELECT * FROM sessions WHERE code = ?", (code,))
    if not row:
        raise HTTPException(404, "session not found")
    player_id = payload.get("player_id")
    if player_id is not None:
        if not isinstance(player_id, int) or isinstance(player_id, bool):
            raise HTTPException(422, "player_id must be an integer or null")
        if not db.query_one("SELECT id FROM players WHERE id = ?", (player_id,)):
            raise HTTPException(404, "player not found")
    player_token = secrets.token_urlsafe(24)
    # Record membership so snapshots, narration and save-point emails are
    # scoped to this session instead of every character ever created.
    db.execute(
        "INSERT INTO session_players (session_id, player_id, token) VALUES (?, ?, ?)",
        (row["id"], player_id, player_token),
    )
    _audit(row["id"], "player", "session.join", {"code": code, "player_id": player_id})
    return {
        "session_id": row["id"],
        "player_token": player_token,
        "state": row["state"],
        "snapshot": hub.snapshot(row["id"]),
    }


@api.post("/sessions/{session_id}/state")
async def set_state(session_id: int, payload: dict, x_admin_token: str | None = Header(default=None)):
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    new_state = str(payload.get("state", ""))
    if new_state not in SESSION_STATES:
        raise HTTPException(422, f"state must be one of {SESSION_STATES}")
    db.execute("UPDATE sessions SET state = ? WHERE id = ?", (new_state, session_id))
    if new_state == "playing" and not session["campaign_started_at"]:
        # The campaign clock starts when play begins.
        started = datetime.now(UTC)
        ends = started + timedelta(minutes=int(session["campaign_minutes"]))
        db.execute(
            "UPDATE sessions SET campaign_started_at = ?, campaign_ends_at = ? WHERE id = ?",
            (started.isoformat(), ends.isoformat(), session_id),
        )
        session = _require_session(session_id)
        await hub.log_event(session_id, "campaign", campaign_of(session))
    if new_state == "ended":
        emails = send_all_save_points(session_id)
        await hub.log_event(session_id, "session_ended", {"emails": emails})
    await hub.log_event(session_id, "state", {"state": new_state})
    _audit(session_id, "host", "session.state", {"state": new_state})
    return _session_public(_require_session(session_id))


@api.post("/sessions/{session_id}/campaign/extend")
async def extend_campaign(session_id: int, payload: dict, x_admin_token: str | None = Header(default=None)):
    """Host extends the running campaign (e.g. +30 min) — the default is 1 hour."""
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    try:
        minutes = int(payload.get("minutes", 30))
    except (TypeError, ValueError):
        raise HTTPException(422, "minutes must be an integer") from None
    minutes = max(5, min(MAX_CAMPAIGN_MINUTES, minutes))
    if session["campaign_ends_at"]:
        base = datetime.fromisoformat(session["campaign_ends_at"])
        if base.tzinfo is None:
            base = base.replace(tzinfo=UTC)
        ends = max(base, datetime.now(UTC)) + timedelta(minutes=minutes)
        db.execute("UPDATE sessions SET campaign_ends_at = ? WHERE id = ?", (ends.isoformat(), session_id))
    else:
        new_total = _clamp_campaign_minutes(int(session["campaign_minutes"]) + minutes)
        db.execute("UPDATE sessions SET campaign_minutes = ? WHERE id = ?", (new_total, session_id))
    session = _require_session(session_id)
    campaign = campaign_of(session)
    await hub.log_event(session_id, "campaign", campaign)
    _audit(session_id, "host", "campaign.extend", {"minutes": minutes})
    return campaign


@api.post("/sessions/{session_id}/chapter")
async def next_chapter(session_id: int, x_admin_token: str | None = Header(default=None)):
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    new_index = session["chapter_index"] + 1
    save_point = db.loads(session["save_point"])
    save_point["chapter_index"] = new_index
    save_point["label"] = f"Chapter {new_index + 1}"
    db.execute(
        "UPDATE sessions SET chapter_index = ?, save_point = ?, state = 'loading' WHERE id = ?",
        (new_index, db.dumps(save_point), session_id),
    )
    await hub.log_event(session_id, "chapter", {"chapter_index": new_index, "save_point": save_point})
    return _session_public(_require_session(session_id))


# --- dice & narration (real-time) ---

@api.post("/sessions/{session_id}/roll")
async def roll_dice(session_id: int, payload: dict):
    _require_session(session_id)
    try:
        result = roll(
            int(payload.get("count", 1)),
            int(payload.get("faces", 20)),
            int(payload.get("modifier", 0)),
            str(payload.get("mode", "normal")),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result["roller"] = str(payload.get("roller", "someone"))
    await hub.log_event(session_id, "dice", result)
    _audit(session_id, result["roller"], "dice.roll", result)
    return result


def _player_name_for_token(session_id: int, token: str | None) -> str | None:
    """Resolve a join token to the player's name (server-side attribution)."""
    if not token:
        return None
    row = db.query_one(
        "SELECT p.name FROM session_players sp JOIN players p ON p.id = sp.player_id"
        " WHERE sp.session_id = ? AND sp.token = ? AND sp.player_id IS NOT NULL",
        (session_id, token),
    )
    return row["name"] if row else None


@api.post("/sessions/{session_id}/chat")
async def chat_message(session_id: int, payload: dict, x_player_token: str | None = Header(default=None)):
    """Table chat over REST (the WS 'chat' frame does the same in real time).

    The sender is resolved from the join token, never from client input.
    """
    _require_session(session_id)
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(422, "text is required")
    name = _player_name_for_token(session_id, x_player_token)
    if name is None:
        raise HTTPException(403, "valid X-Player-Token required")
    event = {"from": name, "text": text[:500]}
    await hub.log_event(session_id, "chat", event)
    return event


@api.post("/sessions/{session_id}/recap")
async def recap(session_id: int):
    """"What happened so far" — summarizes the session log for players who lost the thread."""
    _require_session(session_id)
    rows = db.query(
        "SELECT kind, payload FROM session_events WHERE session_id = ? ORDER BY id", (session_id,)
    )
    lines = []
    for r in rows:
        if r["kind"] in ("narration", "notes", "chat", "recap"):
            p = db.loads(r["payload"])
            text = p.get("text") or p.get("summary") or (p.get("from", "") + ": " + p.get("text", ""))
            if text:
                lines.append(f"[{r['kind']}] {text}")
    result = await ai.recap_session("\n".join(lines))
    await hub.log_event(session_id, "recap", result)
    return result


@api.post("/sessions/{session_id}/narrate")
async def narrate(session_id: int, payload: dict):
    _require_session(session_id)
    scene = str(payload.get("scene", "The party stands at a crossroads."))
    chars = [str(c["name"]) for c in session_characters(session_id)]
    result = await ai.narrate_scene(scene, chars)
    await hub.log_event(session_id, "narration", result)
    return result


@api.post("/sessions/{session_id}/notes")
async def notes(session_id: int, payload: dict):
    _require_session(session_id)
    transcript = str(payload.get("transcript", ""))
    if not transcript.strip():
        raise HTTPException(422, "transcript is required")
    result = await ai.summarize_notes(transcript)
    await hub.log_event(session_id, "notes", result)
    return result


@api.post("/sessions/{session_id}/maps")
async def set_map(session_id: int, payload: dict, x_admin_token: str | None = Header(default=None)):
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    label = str(payload.get("label", ""))
    markers = payload.get("markers", [])
    if not isinstance(markers, list):
        raise HTTPException(422, "markers must be a list")
    for m in markers:
        if (
            not isinstance(m, dict)
            or not isinstance(m.get("x"), (int, float))
            or isinstance(m.get("x"), bool)
            or not isinstance(m.get("y"), (int, float))
            or isinstance(m.get("y"), bool)
            or not isinstance(m.get("label", ""), str)
        ):
            raise HTTPException(422, "each marker must be {x: number, y: number, label: string}")
    cur = db.execute(
        "INSERT INTO maps (session_id, label, markers) VALUES (?, ?, ?)",
        (session_id, label, db.dumps(markers)),
    )
    event = {"id": cur.lastrowid, "label": label, "markers": markers}
    await hub.log_event(session_id, "map", event)
    return event


# --- combat / initiative tracker (the #1 thing DMs ask for at a table) ---

CONDITIONS = (
    "blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated",
    "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained",
    "stunned", "unconscious", "exhausted", "concentrating",
)


def _combatant_from_payload(item: dict, turn_order: int) -> tuple:
    name = str(item.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "each combatant needs a name")
    try:
        hp = int(item.get("hp", item.get("max_hp", 10)))
        max_hp = int(item.get("max_hp", hp))
        initiative = int(item.get("initiative", 0))
        init_mod = int(item.get("init_mod", 0))
        ac = int(item["ac"]) if item.get("ac") is not None else None
    except (TypeError, ValueError):
        raise HTTPException(422, "hp/max_hp/initiative/init_mod/ac must be integers") from None
    conditions = [str(c) for c in item.get("conditions", []) if str(c) in CONDITIONS]
    is_enemy = 1 if item.get("is_enemy") else 0
    return (name, initiative, init_mod, max(0, hp), max(0, max_hp), ac, is_enemy, db.dumps(conditions), turn_order)


@api.post("/sessions/{session_id}/combat")
async def combat_start(session_id: int, payload: dict, x_admin_token: str | None = Header(default=None)):
    """Host sets up an encounter: list of combatants (heroes and/or enemies)."""
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    combatants = payload.get("combatants")
    if not isinstance(combatants, list) or not combatants:
        raise HTTPException(422, "combatants must be a non-empty list")
    if len(combatants) > 50:
        raise HTTPException(422, "at most 50 combatants per encounter")
    db.execute("DELETE FROM combatants WHERE session_id = ?", (session_id,))
    for i, item in enumerate(combatants):
        if not isinstance(item, dict):
            raise HTTPException(422, "each combatant must be an object")
        db.execute(
            "INSERT INTO combatants (session_id, name, initiative, init_mod, hp, max_hp, ac, is_enemy,"
            " conditions, turn_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, *_combatant_from_payload(item, i)),
        )
    db.execute(
        "INSERT OR REPLACE INTO combat_state (session_id, round, turn_index) VALUES (?, 1, 0)",
        (session_id,),
    )
    state = combat_of(session_id)
    await hub.log_event(session_id, "combat", state)
    _audit(session_id, "host", "combat.start", {"count": len(state["combatants"])})
    return state


@api.post("/sessions/{session_id}/combat/roll")
async def combat_roll_initiative(session_id: int, x_admin_token: str | None = Header(default=None)):
    """Roll d20 + init_mod for every combatant, sort descending, start round 1."""
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    rows = db.query("SELECT * FROM combatants WHERE session_id = ? ORDER BY id", (session_id,))
    if not rows:
        raise HTTPException(422, "no combatants — start combat first")
    ordered = []
    for r in rows:
        initiative = secrets.randbelow(20) + 1 + int(r["init_mod"])
        db.execute("UPDATE combatants SET initiative = ? WHERE id = ?", (initiative, r["id"]))
        ordered.append((initiative, r["id"]))
    ordered.sort(key=lambda t: (-t[0], t[1]))
    for order, (initiative, cid) in enumerate(ordered):
        db.execute("UPDATE combatants SET turn_order = ? WHERE id = ?", (order, cid))
    db.execute(
        "INSERT OR REPLACE INTO combat_state (session_id, round, turn_index) VALUES (?, 1, 0)",
        (session_id,),
    )
    state = combat_of(session_id)
    await hub.log_event(session_id, "combat", state)
    _audit(session_id, "host", "combat.roll", {"order": [c["name"] for c in state["combatants"]]})
    return state


@api.post("/sessions/{session_id}/combat/next")
async def combat_next_turn(session_id: int, x_admin_token: str | None = Header(default=None)):
    """Advance to the next combatant; wraps to a new round."""
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    state = combat_of(session_id)
    if not state["active"]:
        raise HTTPException(422, "no active combat")
    n = len(state["combatants"])
    turn_index = state["turn_index"] + 1
    round_no = state["round"]
    if turn_index >= n:
        turn_index = 0
        round_no += 1
    db.execute(
        "INSERT OR REPLACE INTO combat_state (session_id, round, turn_index) VALUES (?, ?, ?)",
        (session_id, round_no, turn_index),
    )
    state = combat_of(session_id)
    await hub.log_event(session_id, "combat", state)
    return state


@api.post("/sessions/{session_id}/combat/end")
async def combat_end(session_id: int, x_admin_token: str | None = Header(default=None)):
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    db.execute("DELETE FROM combatants WHERE session_id = ?", (session_id,))
    db.execute("DELETE FROM combat_state WHERE session_id = ?", (session_id,))
    state = {"active": False, "round": 0, "turn_index": 0, "combatants": []}
    await hub.log_event(session_id, "combat", state)
    _audit(session_id, "host", "combat.end", {})
    return state


@api.post("/sessions/{session_id}/combat/{combatant_id}")
async def combat_update(session_id: int, combatant_id: int, payload: dict):
    """Anyone may update a combatant: HP delta, conditions, initiative tweak."""
    _require_session(session_id)
    row = db.query_one("SELECT * FROM combatants WHERE id = ? AND session_id = ?", (combatant_id, session_id))
    if not row:
        raise HTTPException(404, "combatant not found")
    try:
        hp = row["hp"]
        if "hp_delta" in payload:
            hp = int(row["hp"]) + int(payload["hp_delta"])
        if "hp" in payload:
            hp = int(payload["hp"])
        hp = max(0, min(hp, int(row["max_hp"]) or hp))
        initiative = row["initiative"]
        if "initiative" in payload:
            initiative = int(payload["initiative"])
    except (TypeError, ValueError):
        raise HTTPException(422, "hp, hp_delta and initiative must be integers") from None
    conditions = db.loads(row["conditions"])
    if "conditions" in payload:
        if not isinstance(payload["conditions"], list):
            raise HTTPException(422, "conditions must be a list")
        conditions = [str(c) for c in payload["conditions"] if str(c) in CONDITIONS]
    if "condition_toggle" in payload:
        cond = str(payload["condition_toggle"])
        if cond in CONDITIONS:
            conditions = [c for c in conditions if c != cond] if cond in conditions else conditions + [cond]
    db.execute(
        "UPDATE combatants SET hp = ?, conditions = ?, initiative = ? WHERE id = ?",
        (hp, db.dumps(conditions), initiative, combatant_id),
    )
    state = combat_of(session_id)
    await hub.log_event(session_id, "combat", state)
    return state


# --- character sheet live updates (HP, conditions) ---

@api.post("/sessions/{session_id}/characters/{character_id}/update")
async def update_character(session_id: int, character_id: int, payload: dict):
    """Merge-patch a character sheet (hp, conditions, ...) and broadcast to the table."""
    _require_session(session_id)
    row = db.query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
    if not row:
        raise HTTPException(404, "character not found")
    sheet = db.loads(row["sheet"])
    for key in ("hp", "max_hp", "ac", "conditions", "spell_slots", "level", "class"):
        if key in payload:
            sheet[key] = payload[key]
    db.execute(
        "UPDATE characters SET sheet = ?, updated_at = datetime('now') WHERE id = ?",
        (db.dumps(sheet), character_id),
    )
    event = {"id": character_id, "name": row["name"], "sheet": sheet}
    await hub.log_event(session_id, "character", event)
    return event


@api.get("/sessions/{session_id}/events")
def list_events(session_id: int):
    _require_session(session_id)
    rows = db.query(
        "SELECT kind, payload, created_at FROM session_events WHERE session_id = ? ORDER BY id",
        (session_id,),
    )
    return [{"kind": r["kind"], "payload": db.loads(r["payload"]), "at": r["created_at"]} for r in rows]


@api.get("/ai/health")
def ai_health():
    return ai.health()


# --- audio (mic -> local Whisper STT) and vision (camera -> Pixtral EU) ---

@api.post("/sessions/{session_id}/transcribe")
async def transcribe(session_id: int, file: UploadFile):
    """Accept an audio chunk (webm/ogg), transcribe locally, store only the text."""
    _require_session(session_id)
    data = await file.read()
    if not data or len(data) > 25 * 1024 * 1024:
        raise HTTPException(422, "audio chunk missing or too large (25 MB max)")
    import asyncio

    import audio

    if not audio.available():
        raise HTTPException(503, "local Whisper (faster-whisper) not installed on host")
    result = await asyncio.to_thread(audio.transcribe, data)
    await hub.log_event(session_id, "transcript", result)
    return result


@api.post("/sessions/{session_id}/vision")
async def vision(session_id: int, payload: dict, x_admin_token: str | None = Header(default=None)):
    """Explicit host action: describe a camera frame. Broadcasts a 'vision active' notice."""
    session = _require_session(session_id)
    _check_admin(session, x_admin_token)
    import base64

    b64 = str(payload.get("image", ""))
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise HTTPException(422, "image must be base64 (optionally data-URL)") from exc
    if not image_bytes or len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(422, "image missing or too large (10 MB max)")
    await hub.log_event(session_id, "vision_active", {"note": "camera frame sent to EU vision model"})
    import vision

    result = await vision.describe_image(image_bytes, str(payload.get("prompt", "")))
    await hub.log_event(session_id, "vision", result)
    return result


# --- WebAuthn passkey (host admin) ---

def _passkey_origin(request: Request, x_access_token: str | None) -> str:
    """Validate the client-supplied Origin against the request's own Host.

    The WebAuthn RP ID is derived from the Origin, so a foreign Origin must
    never be trusted. When ACCESS_TOKEN is configured, these endpoints
    additionally require it (registration is what grants admin).
    """
    import passkeys

    _check_access_token(x_access_token)
    origin = request.headers.get("origin") or f"http://{request.headers.get('host', 'localhost')}"
    try:
        passkeys.validate_origin(origin, request.headers.get("host", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return origin


@api.post("/auth/passkey/register/options")
def passkey_register_options(request: Request, x_access_token: str | None = Header(default=None)):
    import passkeys

    return passkeys.registration_options(_passkey_origin(request, x_access_token))


@api.post("/auth/passkey/register/verify")
def passkey_register_verify(payload: dict, request: Request, x_access_token: str | None = Header(default=None)):
    import passkeys

    try:
        return passkeys.verify_registration(_passkey_origin(request, x_access_token), payload.get("credential", {}))
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@api.post("/auth/passkey/login/options")
def passkey_login_options(request: Request, x_access_token: str | None = Header(default=None)):
    import passkeys

    return passkeys.authentication_options(_passkey_origin(request, x_access_token))


@api.post("/auth/passkey/login/verify")
def passkey_login_verify(payload: dict, request: Request, x_access_token: str | None = Header(default=None)):
    import passkeys

    try:
        token = passkeys.verify_authentication(_passkey_origin(request, x_access_token), payload.get("credential", {}))
    except (ValueError, KeyError) as exc:
        raise HTTPException(401, str(exc)) from exc
    _audit(None, "host-passkey", "auth.passkey", {"token_issued": True})
    return {"admin_session_token": token}


# --- websocket ---

@api.websocket("/sessions/{session_id}/ws")
async def session_ws(websocket: WebSocket, session_id: int, token: str = ""):
    session = db.query_one("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if not session:
        await websocket.close(code=4404)
        return
    # The WS channel is authenticated with the join token issued at join time.
    player_name = _player_name_for_token(session_id, token) or "guest"
    if not token or not db.query_one(
        "SELECT token FROM session_players WHERE session_id = ? AND token = ?", (session_id, token)
    ):
        await websocket.close(code=4401)
        return
    await hub.connect(session_id, websocket)
    try:
        await websocket.send_json(hub.snapshot(session_id))
        while True:
            msg = await websocket.receive_json()
            kind = msg.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong", "clients": hub.count(session_id)})
            elif kind == "roll":
                try:
                    result = roll(
                        int(msg.get("count", 1)),
                        int(msg.get("faces", 20)),
                        int(msg.get("modifier", 0)),
                        str(msg.get("mode", "normal")),
                    )
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
                result["roller"] = player_name
                await hub.log_event(session_id, "dice", result)
            elif kind == "chat":
                text = str(msg.get("text", "")).strip()
                if text:
                    await hub.log_event(session_id, "chat", {"from": player_name, "text": text[:500]})
    except WebSocketDisconnect:
        await hub.disconnect(session_id, websocket)
