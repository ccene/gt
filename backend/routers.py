import secrets

from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect

import ai
import db
from dice import roll
from emailer import send_all_save_points
from hub import hub

api = APIRouter(prefix="/api")

SESSION_STATES = ("lobby", "loading", "playing", "chapter_end", "ended")


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
        "clients": hub.count(row["id"]),
    }


def _check_admin(session: dict, x_admin_token: str | None) -> None:
    if x_admin_token and secrets.compare_digest(x_admin_token, session["admin_token"]):
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
async def generate_story(payload: dict):
    genre = str(payload.get("genre", "classic fantasy"))
    tone = str(payload.get("tone", "heroic"))
    result = await ai.chat_large(
        [
            {
                "role": "system",
                "content": (
                    "You are a storyteller. Output a JSON object with keys: "
                    "title, logline, chapters (list of {title, summary}). 3 chapters."
                ),
            },
            {"role": "user", "content": f"Write a 3-chapter D&D adventure outline. Genre: {genre}. Tone: {tone}."},
        ]
    )
    cur = db.execute(
        "INSERT INTO stories (title, source, content) VALUES (?, 'generated', ?)",
        (f"{genre} adventure ({tone})", db.dumps(result)),
    )
    return {"id": cur.lastrowid, "title": f"{genre} adventure ({tone})", "content": result}


@api.post("/stories/import")
def import_story(payload: dict):
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
def create_session(payload: dict):
    code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))
    admin_token = secrets.token_urlsafe(32)
    story_id = payload.get("story_id")
    cur = db.execute(
        "INSERT INTO sessions (code, admin_token, story_id) VALUES (?, ?, ?)",
        (code, admin_token, story_id),
    )
    sid = cur.lastrowid
    assert isinstance(sid, int)
    _audit(sid, "host", "session.create", {"code": code, "story_id": story_id})
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
    player_token = secrets.token_urlsafe(24)
    _audit(row["id"], "player", "session.join", {"code": code})
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
    if new_state == "ended":
        emails = send_all_save_points(session_id)
        await hub.log_event(session_id, "session_ended", {"emails": emails})
    await hub.log_event(session_id, "state", {"state": new_state})
    _audit(session_id, "host", "session.state", {"state": new_state})
    return _session_public(_require_session(session_id))


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
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result["roller"] = str(payload.get("roller", "someone"))
    await hub.log_event(session_id, "dice", result)
    _audit(session_id, result["roller"], "dice.roll", result)
    return result


@api.post("/sessions/{session_id}/narrate")
async def narrate(session_id: int, payload: dict):
    _require_session(session_id)
    scene = str(payload.get("scene", "The party stands at a crossroads."))
    chars = [str(c["name"]) for c in db.query("SELECT name FROM characters")]
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
    cur = db.execute(
        "INSERT INTO maps (session_id, label, markers) VALUES (?, ?, ?)",
        (session_id, label, db.dumps(markers)),
    )
    event = {"id": cur.lastrowid, "label": label, "markers": markers}
    await hub.log_event(session_id, "map", event)
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


# --- websocket ---

@api.websocket("/sessions/{session_id}/ws")
async def session_ws(websocket: WebSocket, session_id: int):
    session = db.query_one("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if not session:
        await websocket.close(code=4404)
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
                    result = roll(int(msg.get("count", 1)), int(msg.get("faces", 20)), int(msg.get("modifier", 0)))
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
                result["roller"] = str(msg.get("roller", "someone"))
                await hub.log_event(session_id, "dice", result)
            elif kind == "chat":
                await hub.log_event(
                    session_id,
                    "chat",
                    {"from": str(msg.get("from", "?")), "text": str(msg.get("text", ""))[:500]},
                )
    except WebSocketDisconnect:
        await hub.disconnect(session_id, websocket)
