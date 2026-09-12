"""SQLite persistence for conversations, messages and interpreter trace events."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    meta TEXT NOT NULL DEFAULT '{}',
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, ts);
CREATE INDEX IF NOT EXISTS idx_trace_conv ON trace_events(conversation_id, id);
"""


def init_db(path: str) -> None:
    global _conn
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    with _lock:
        _conn.executescript(SCHEMA)
        _conn.commit()


def _c() -> sqlite3.Connection:
    assert _conn is not None, "db not initialised — call init_db() first"
    return _conn


def now() -> float:
    return time.time()


def new_conversation(title: str = "") -> dict:
    cid = uuid.uuid4().hex[:12]
    ts = now()
    with _lock:
        _c().execute(
            "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (cid, title or "New chat", ts, ts),
        )
        _c().commit()
    return get_conversation(cid)  # type: ignore[return-value]


def get_conversation(cid: str) -> dict | None:
    row = _c().execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    return dict(row) if row else None


def list_conversations() -> list[dict]:
    rows = _c().execute(
        "SELECT * FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def touch_conversation(cid: str, title: str | None = None) -> None:
    with _lock:
        if title is not None:
            _c().execute(
                "UPDATE conversations SET updated_at=?, title=? WHERE id=?",
                (now(), title, cid),
            )
        else:
            _c().execute(
                "UPDATE conversations SET updated_at=? WHERE id=?", (now(), cid)
            )
        _c().commit()


def delete_conversation(cid: str) -> None:
    with _lock:
        _c().execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
        _c().execute("DELETE FROM trace_events WHERE conversation_id=?", (cid,))
        _c().execute("DELETE FROM conversations WHERE id=?", (cid,))
        _c().commit()


def add_message(
    conversation_id: str, role: str, content: str, meta: dict | None = None
) -> dict:
    mid = uuid.uuid4().hex[:12]
    ts = now()
    with _lock:
        _c().execute(
            "INSERT INTO messages(id,conversation_id,role,content,meta,ts) "
            "VALUES(?,?,?,?,?,?)",
            (mid, conversation_id, role, content, json.dumps(meta or {}), ts),
        )
        _c().commit()
    return {"id": mid, "conversation_id": conversation_id, "role": role,
            "content": content, "meta": meta or {}, "ts": ts}


def list_messages(conversation_id: str) -> list[dict]:
    rows = _c().execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY ts ASC",
        (conversation_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["meta"] = json.loads(d.get("meta") or "{}")
        out.append(d)
    return out


def add_trace(conversation_id: str, run_id: str, seq: int, type_: str,
              payload: dict[str, Any]) -> None:
    with _lock:
        _c().execute(
            "INSERT INTO trace_events(conversation_id,run_id,seq,type,payload,ts) "
            "VALUES(?,?,?,?,?,?)",
            (conversation_id, run_id, seq, type_, json.dumps(payload, default=str),
             now()),
        )
        _c().commit()


def list_trace(conversation_id: str) -> list[dict]:
    rows = _c().execute(
        "SELECT * FROM trace_events WHERE conversation_id=? ORDER BY id ASC",
        (conversation_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.get("payload") or "{}")
        out.append(d)
    return out
