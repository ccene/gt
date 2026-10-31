import json
import sqlite3
import threading
from pathlib import Path

from config import settings

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_init_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS characters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id INTEGER NOT NULL REFERENCES players(id),
  name TEXT NOT NULL,
  sheet TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS stories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'generated',
  content TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  admin_token TEXT NOT NULL,
  story_id INTEGER REFERENCES stories(id),
  state TEXT NOT NULL DEFAULT 'lobby',
  chapter_index INTEGER NOT NULL DEFAULT 0,
  save_point TEXT NOT NULL DEFAULT '{}',
  campaign_minutes INTEGER NOT NULL DEFAULT 60,
  campaign_started_at TEXT,
  campaign_ends_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS combatants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  name TEXT NOT NULL,
  initiative INTEGER NOT NULL DEFAULT 0,
  init_mod INTEGER NOT NULL DEFAULT 0,
  hp INTEGER NOT NULL DEFAULT 0,
  max_hp INTEGER NOT NULL DEFAULT 0,
  ac INTEGER,
  is_enemy INTEGER NOT NULL DEFAULT 0,
  conditions TEXT NOT NULL DEFAULT '[]',
  turn_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS session_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  kind TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS maps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  label TEXT NOT NULL DEFAULT '',
  markers TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS combat_state (
  session_id INTEGER PRIMARY KEY REFERENCES sessions(id),
  round INTEGER NOT NULL DEFAULT 1,
  turn_index INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS session_players (
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  player_id INTEGER REFERENCES players(id),
  token TEXT PRIMARY KEY,
  joined_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ai_cache (
  key TEXT PRIMARY KEY,
  response TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ai_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  month TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS webauthn_credentials (
  credential_id TEXT PRIMARY KEY,
  public_key TEXT NOT NULL,
  sign_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS webauthn_challenges (
  challenge TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_sessions (
  token TEXT PRIMARY KEY,
  credential_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER,
  actor TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


_init_lock = threading.Lock()

# Columns added after the initial schema shipped; applied idempotently so
# existing databases (e.g. data/app.db) pick them up without a manual migration.
_MIGRATIONS = {
    "sessions": {
        "campaign_minutes": "INTEGER NOT NULL DEFAULT 60",
        "campaign_started_at": "TEXT",
        "campaign_ends_at": "TEXT",
    },
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _MIGRATIONS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, decl in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def get_conn() -> sqlite3.Connection:
    global _conn
    conn = _conn
    if conn is None:
        with _init_lock:
            conn = _conn
            if conn is None:
                settings.ensure_dirs()
                path = settings.db_path
                conn = sqlite3.connect(str(path), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executescript(SCHEMA)
                _migrate(conn)
                _conn = conn
    return conn


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return get_conn().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with _lock:
        return get_conn().execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        cur = get_conn().execute(sql, params)
        get_conn().commit()
        return cur


def insert_event(session_id: int, kind: str, payload) -> dict:
    """Insert a session event and return its row atomically.

    The INSERT and the created_at SELECT happen under one lock so a concurrent
    writer can never make last_insert_rowid() point at someone else's row.
    """
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO session_events (session_id, kind, payload) VALUES (?, ?, ?)",
            (session_id, kind, dumps(payload)),
        )
        row = conn.execute(
            "SELECT id, created_at FROM session_events WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        conn.commit()
        return {"id": row["id"], "created_at": row["created_at"]}


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(text: str):
    return json.loads(text) if text else {}


def reset_for_tests(db_file: Path) -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
    settings.database_url = f"sqlite:///{db_file}"
