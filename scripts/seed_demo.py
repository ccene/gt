"""Seed the database with mock data for a demo run.

Usage: python3 scripts/seed_demo.py
Then: ./scripts/run.sh  and open http://<host>:8000

If backend dependencies are missing, this script re-runs itself with the
project virtualenv (.venv) when it exists, or tells you to run setup.sh.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"

try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    if VENV_PY.exists():
        os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve())])
    sys.exit(
        "Backend dependencies are not installed for the system Python.\n"
        "Run ./scripts/setup.sh first (it creates .venv), then re-run this script."
    )

sys.path.insert(0, str(ROOT / "backend"))

import ai  # noqa: E402
import db  # noqa: E402
import routers  # noqa: E402,F401
from config import settings  # noqa: E402

PLAYERS = [
    ("Aria", "aria@example.com", {"name": "Aria the Bold", "sheet": {"class": "Fighter", "level": 3, "hp": 32, "max_hp": 32, "ac": 17, "weapon": "Longsword +1"}}),
    ("Bram", "bram@example.com", {"name": "Bram Quickfingers", "sheet": {"class": "Rogue", "level": 3, "hp": 21, "max_hp": 21, "ac": 14, "weapon": "Shortbow"}}),
    ("Cleo", "cleo@example.com", {"name": "Cleo Dawnwhisper", "sheet": {"class": "Cleric", "level": 3, "hp": 26, "max_hp": 26, "ac": 16, "weapon": "Mace"}}),
    ("Dana", "dana@example.com", {"name": "Dana Emberheart", "sheet": {"class": "Sorcerer", "level": 3, "hp": 19, "max_hp": 19, "ac": 12, "weapon": "Quarterstaff"}}),
]

STORY = {
    "title": "The Sunken Crypt of Morvaine",
    "source": "imported",
    "content": {
        "title": "The Sunken Crypt of Morvaine",
        "logline": "Four heroes descend into a flooded crypt to stop a cult from raising the Hollow King.",
        "chapters": [
            {"title": "The Drowned Gate", "summary": "Cross the flooded causeway; fight off sahuagin scouts."},
            {"title": "Hall of Whispers", "summary": "Puzzle room; the walls tell lies. Find the true path."},
            {"title": "The Hollow King", "summary": "Boss fight in the ritual chamber."},
        ],
    },
}

MAPS = [
    {"label": "Causeway of Morvaine", "markers": [{"x": 20, "y": 80, "label": "party"}, {"x": 60, "y": 60, "label": "sahuagin"}]},
    {"label": "Hall of Whispers", "markers": [{"x": 30, "y": 70, "label": "party"}, {"x": 75, "y": 30, "label": "riddle door"}]},
    {"label": "Ritual Chamber", "markers": [{"x": 50, "y": 50, "label": "Hollow King"}, {"x": 40, "y": 70, "label": "party"}]},
]


def main() -> None:
    settings.ensure_dirs()
    db.get_conn()  # init schema

    player_ids = []
    for name, email, char in PLAYERS:
        cur = db.execute("INSERT INTO players (name, email) VALUES (?, ?)", (name, email))
        pid = cur.lastrowid
        db.execute(
            "INSERT INTO characters (player_id, name, sheet) VALUES (?, ?, ?)",
            (pid, char["name"], db.dumps(char["sheet"])),
        )
        player_ids.append(pid)

    cur = db.execute(
        "INSERT INTO stories (title, source, content) VALUES (?, ?, ?)",
        (STORY["title"], STORY["source"], db.dumps(STORY["content"])),
    )
    story_id = cur.lastrowid

    cur = db.execute(
        "INSERT INTO sessions (code, admin_token, story_id, state, chapter_index, save_point)"
        " VALUES ('DEMO42', 'demo-admin-token', ?, 'playing', 0, ?)",
        (story_id, db.dumps({"label": "Chapter 1", "chapter_index": 0, "notes": "Arrived at the drowned gate. The water is black and cold."})),
    )
    sid = cur.lastrowid

    for m in MAPS:
        db.execute("INSERT INTO maps (session_id, label, markers) VALUES (?, ?, ?)", (sid, m["label"], db.dumps(m["markers"])))

    # a few scripted events so the table view has content
    import dice

    r1 = dice.roll(1, 20, 4)
    r1["roller"] = "Aria"
    db.execute("INSERT INTO session_events (session_id, kind, payload) VALUES (?, 'dice', ?)", (sid, db.dumps(r1)))
    r2 = dice.roll(2, 6, 2)
    r2["roller"] = "Bram"
    db.execute("INSERT INTO session_events (session_id, kind, payload) VALUES (?, 'dice', ?)", (sid, db.dumps(r2)))
    db.execute(
        "INSERT INTO session_events (session_id, kind, payload) VALUES (?, 'narration', ?)",
        (sid, db.dumps(asyncio.run(ai.narrate_scene("The drowned gate of Morvaine. Black water laps at the broken causeway.", [p[0] for p in PLAYERS])))),
    )
    db.execute(
        "INSERT INTO session_events (session_id, kind, payload) VALUES (?, 'chat', ?)",
        (sid, db.dumps({"from": "Cleo", "text": "I check the water for undead. Nothing stirs… yet."})),
    )
    db.execute(
        "INSERT INTO audit_log (session_id, actor, action, detail) VALUES (?, 'host', 'demo.seed', ?)",
        (sid, db.dumps({"players": len(PLAYERS)})),
    )

    print("Demo data seeded.")
    print(f"  session id : {sid}")
    print("  join code  : DEMO42")
    print("  admin token: demo-admin-token")
    print("  players    : " + ", ".join(p[0] for p in PLAYERS))
    print(f"  story      : {STORY['title']} (id {story_id})")
    print(f"  maps       : {len(MAPS)}")
    print("\nRun ./scripts/run.sh and open http://localhost:8000 — join with code DEMO42")


if __name__ == "__main__":
    main()
