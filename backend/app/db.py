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

-- ---- Admin / governance / RAG (fitur publikasi) --------------------------
CREATE TABLE IF NOT EXISTS admin_policy (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT 'global',
    key TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'admin',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL DEFAULT '',
    mime TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    meta TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    rating TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    context TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'new',
    guidance_memory_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_conv ON feedback(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS rag_documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    pages INTEGER NOT NULL DEFAULT 0,
    chunks INTEGER NOT NULL DEFAULT 0,
    chars INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error TEXT NOT NULL DEFAULT '',
    embed_backend TEXT NOT NULL DEFAULT '',
    timings TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    page INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL,
    embedding TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON rag_chunks(doc_id, seq);

-- ---- Task management (halaman /tasks; task id = kode branch GitLab) --------
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,                 -- ASK-001 (dipakai di nama branch)
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    phase TEXT NOT NULL DEFAULT 'f0',
    status TEXT NOT NULL DEFAULT 'todo',
    priority TEXT NOT NULL DEFAULT 'medium',
    assignee TEXT NOT NULL DEFAULT '',
    estimate REAL NOT NULL DEFAULT 0,    -- estimasi hari kerja
    labels TEXT NOT NULL DEFAULT '[]',
    acceptance TEXT NOT NULL DEFAULT '[]',  -- [{text, done}]
    depends_on TEXT NOT NULL DEFAULT '[]',  -- ["ASK-002", …]
    evidence TEXT NOT NULL DEFAULT '[]',    -- file penanda implementasi
    source TEXT NOT NULL DEFAULT '',        -- rujukan slide / tab admin
    branch TEXT NOT NULL DEFAULT '',
    mr_url TEXT NOT NULL DEFAULT '',
    commits TEXT NOT NULL DEFAULT '[]',     -- [{sha, subject}]
    position INTEGER NOT NULL DEFAULT 0,    -- urutan dalam kolom
    seeded INTEGER NOT NULL DEFAULT 0,      -- 1 = berasal dari rencana RAG
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, position);
CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT 'dev',
    kind TEXT NOT NULL DEFAULT 'comment',   -- comment | activity
    body TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_comments ON task_comments(task_id, created_at);
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
        # Flatten payload so replayed events match the live SSE wire format
        # (the UI reads fields like `text`, `items`, `summary` top-level).
        payload = json.loads(d.pop("payload", None) or "{}")
        d.update(payload)
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Generic helpers for the feature modules (memory / artifacts / feedback /
# rag / governance). Kept tiny on purpose: modules own their SQL, db.py only
# owns the connection, the lock and commit semantics.
# ---------------------------------------------------------------------------

def execute(sql: str, params: tuple = ()) -> None:
    """Run a write statement (INSERT/UPDATE/DELETE) and commit."""
    with _lock:
        _c().execute(sql, params)
        _c().commit()


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    rows = _c().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    row = _c().execute(sql, params).fetchone()
    return dict(row) if row else None


def get_message(message_id: str) -> dict | None:
    return query_one("SELECT * FROM messages WHERE id=?", (message_id,))


def stats_counts() -> dict:
    """Dashboard counters for the admin overview."""
    def count(table: str) -> int:
        row = _c().execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        return int(row["n"]) if row else 0

    up = _c().execute(
        "SELECT COUNT(*) AS n FROM feedback WHERE rating='up'").fetchone()
    down = _c().execute(
        "SELECT COUNT(*) AS n FROM feedback WHERE rating='down'").fetchone()
    artifact_bytes = _c().execute(
        "SELECT COALESCE(SUM(size_bytes),0) AS n FROM artifacts").fetchone()
    rag_ready = _c().execute(
        "SELECT COUNT(*) AS n FROM rag_documents WHERE status='ready'").fetchone()
    tasks_done = _c().execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE status='done'").fetchone()
    return {
        "conversations": count("conversations"),
        "messages": count("messages"),
        "trace_events": count("trace_events"),
        "memories": count("memories"),
        "artifacts": count("artifacts"),
        "artifact_bytes": int(artifact_bytes["n"]) if artifact_bytes else 0,
        "feedback_total": int(up["n"] or 0) + int(down["n"] or 0),
        "feedback_up": int(up["n"] or 0),
        "feedback_down": int(down["n"] or 0),
        "rag_documents": count("rag_documents"),
        "rag_documents_ready": int(rag_ready["n"]) if rag_ready else 0,
        "tasks": count("tasks"),
        "tasks_done": int(tasks_done["n"]) if tasks_done else 0,
    }
