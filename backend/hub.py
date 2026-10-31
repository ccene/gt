import asyncio
import json
from typing import Any

from fastapi import WebSocket

import db


class Hub:
    """Tracks WebSocket connections per session and broadcasts events."""

    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(session_id, set()).add(ws)

    async def disconnect(self, session_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._conns.get(session_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    del self._conns[session_id]

    def count(self, session_id: int) -> int:
        return len(self._conns.get(session_id, ()))

    async def broadcast(self, session_id: int, event: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._conns.get(session_id, ()))
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns.get(session_id, set()).discard(ws)

    async def log_event(self, session_id: int, kind: str, payload: dict) -> dict:
        row = db.insert_event(session_id, kind, payload)
        event = {"type": kind, "payload": payload, "ts": row["created_at"]}
        await self.broadcast(session_id, event)
        return event


    def snapshot(self, session_id: int) -> dict:
        session = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not session:
            return {}
        # Cap the event history so long sessions don't grow snapshots forever.
        events = db.query(
            "SELECT kind, payload, created_at FROM session_events WHERE session_id = ?"
            " ORDER BY id DESC LIMIT 200",
            (session_id,),
        )
        events.reverse()
        characters = session_characters(session_id)
        maps = db.query(
            "SELECT id, label, markers FROM maps WHERE session_id = ? ORDER BY id", (session_id,)
        )
        return {
            "type": "snapshot",
            "session": {
                "id": session["id"],
                "code": session["code"],
                "state": session["state"],
                "chapter_index": session["chapter_index"],
                "save_point": db.loads(session["save_point"]),
            },
            "campaign": campaign_of(session),
            "story": story_of(session_id),
            "combat": combat_of(session_id),
            "characters": [
                {"id": c["id"], "name": c["name"], "player": c["player"], "sheet": db.loads(c["sheet"])}
                for c in characters
            ],
            "maps": [{"id": m["id"], "label": m["label"], "markers": db.loads(m["markers"])} for m in maps],
            "events": [
                {"kind": e["kind"], "payload": db.loads(e["payload"]), "at": e["created_at"]}
                for e in events
            ],
            "clients": self.count(session_id),
        }


def session_characters(session_id: int) -> list:
    """Characters visible in a session: its members' characters.

    A session with no recorded members (e.g. fresh lobby, legacy data) falls
    back to all characters so nothing disappears; once players join, the
    snapshot is scoped so sessions never leak each other's heroes.
    """
    return db.query(
        "SELECT c.id, c.name, c.sheet, p.name AS player FROM characters c"
        " JOIN players p ON p.id = c.player_id"
        " WHERE NOT EXISTS (SELECT 1 FROM session_players sp"
        "   WHERE sp.session_id = ? AND sp.player_id IS NOT NULL)"
        "    OR c.player_id IN (SELECT sp.player_id FROM session_players sp"
        "   WHERE sp.session_id = ? AND sp.player_id IS NOT NULL)"
        " ORDER BY c.id",
        (session_id, session_id),
    )


def campaign_of(session: Any) -> dict:
    return {
        "minutes": session["campaign_minutes"],
        "started_at": session["campaign_started_at"],
        "ends_at": session["campaign_ends_at"],
    }


def story_of(session_id: int) -> dict | None:
    row = db.query_one(
        "SELECT s.id, s.title, s.source, s.content FROM stories s"
        " JOIN sessions sess ON sess.story_id = s.id WHERE sess.id = ?",
        (session_id,),
    )
    if not row:
        return None
    return {"id": row["id"], "title": row["title"], "source": row["source"], "content": db.loads(row["content"])}


def combatant_public(row: Any) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "initiative": row["initiative"],
        "init_mod": row["init_mod"],
        "hp": row["hp"],
        "max_hp": row["max_hp"],
        "ac": row["ac"],
        "is_enemy": bool(row["is_enemy"]),
        "conditions": db.loads(row["conditions"]),
        "turn_order": row["turn_order"],
    }


def combat_of(session_id: int) -> dict:
    rows = db.query(
        "SELECT * FROM combatants WHERE session_id = ? ORDER BY turn_order, id", (session_id,)
    )
    if not rows:
        return {"active": False, "round": 0, "turn_index": 0, "combatants": []}
    state = db.query_one("SELECT round, turn_index FROM combat_state WHERE session_id = ?", (session_id,))
    return {
        "active": True,
        "round": state["round"] if state else 1,
        "turn_index": state["turn_index"] if state else 0,
        "combatants": [combatant_public(r) for r in rows],
    }


# Module-level hub shared by the app.
hub = Hub()
