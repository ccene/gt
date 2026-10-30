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

    async def log_event(self, session_id: int, kind: str, payload: dict) -> None:
        db.execute(
            "INSERT INTO session_events (session_id, kind, payload) VALUES (?, ?, ?)",
            (session_id, kind, db.dumps(payload)),
        )
        row = db.query_one("SELECT created_at AS ts FROM session_events WHERE id = last_insert_rowid()")
        ts = row["ts"] if row else ""
        await self.broadcast(session_id, {"type": kind, "payload": payload, "ts": ts})


    def snapshot(self, session_id: int) -> dict:
        session = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not session:
            return {}
        events = db.query(
            "SELECT kind, payload, created_at FROM session_events WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        characters = db.query(
            "SELECT c.id, c.name, c.sheet, p.name AS player FROM characters c"
            " JOIN players p ON p.id = c.player_id ORDER BY c.id"
        )
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


# Module-level hub shared by the app.
hub = Hub()
