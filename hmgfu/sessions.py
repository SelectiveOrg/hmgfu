"""Sessions, conversation log, and per-session widgets (PA3 contract, simplified).

conversations.metadata JSON keys consumed by the frontend on history restore
(mirrors PA3's contract): tool_calls, thinking, memory_count, memory_items, grade.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import List, Optional

from . import config
from .models import create_id, now_iso

# Widget types the LLM (and the + menu) may create — must match the Canvas renderer.
WIDGET_TYPES = ("metric", "table", "weather", "plan", "diff", "note",
                "memory-hex", "memory-graph", "memory-trace", "layers", "canon", "dream", "grader",
                "timeline", "now", "app")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
    turn_seq INTEGER, metadata TEXT DEFAULT '{}', created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, created_at);
CREATE TABLE IF NOT EXISTS session_widgets (
    session_id TEXT, widget_id TEXT, type TEXT, title TEXT, props TEXT DEFAULT '{}',
    generated INTEGER DEFAULT 0, created_at TEXT,
    PRIMARY KEY (session_id, widget_id)
);
"""


class SessionStore:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        # migration-safe: group folders added in Phase 21
        cols = [r[1] for r in self._db.execute("PRAGMA table_info(sessions)")]
        if "grp" not in cols:
            self._db.execute("ALTER TABLE sessions ADD COLUMN grp TEXT DEFAULT ''")
        self._db.commit()

    # --- sessions ------------------------------------------------------------

    def create_session(self, title: str = "New session") -> dict:
        with self._lock:
            sid = create_id()
            now = now_iso()
            self._db.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (sid, title, now, now))
            self._db.commit()
            return {"id": sid, "title": title, "created_at": now, "updated_at": now}

    def ensure_session(self, session_id: Optional[str]) -> str:
        with self._lock:
            if session_id:
                row = self._db.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
                if row:
                    return session_id
            return self.create_session()["id"]

    def list_sessions(self) -> List[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT s.id, s.title, s.created_at, s.updated_at, s.grp, "
                "(SELECT COUNT(*) FROM conversations c WHERE c.session_id = s.id) "
                "FROM sessions s ORDER BY s.updated_at DESC"
            ).fetchall()
        return [{"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3],
                 "group": r[4] or "", "messages": r[5]} for r in rows]

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM sessions WHERE id=?",
                                    (session_id,)).fetchone() is not None

    def rename_session(self, session_id: str, title: str) -> None:
        with self._lock:
            self._db.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?",
                             (title[:80], now_iso(), session_id))
            self._db.commit()

    def set_group(self, session_id: str, group: str) -> None:
        with self._lock:
            self._db.execute("UPDATE sessions SET grp=? WHERE id=?",
                             ((group or "")[:60], session_id))
            self._db.commit()

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            self._db.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
            self._db.execute("DELETE FROM session_widgets WHERE session_id=?", (session_id,))
            try:                                  # 69.5: a deleted session takes its plan with it (same DB file)
                self._db.execute("DELETE FROM session_plans WHERE session_id=?", (session_id,))
            except sqlite3.OperationalError:
                pass                              # the plans table is created lazily by SessionPlanStore
            self._db.commit()

    # --- conversation log -------------------------------------------------------

    def save_message(self, session_id: str, role: str, content: str,
                     turn_seq: int, metadata: Optional[dict] = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (create_id(), session_id, role, content, turn_seq,
                 json.dumps(metadata or {}), now_iso()),
            )
            self._db.execute("UPDATE sessions SET updated_at=? WHERE id=?",
                             (now_iso(), session_id))
            # auto-title on the first user message
            row = self._db.execute("SELECT title FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row and row[0] == "New session" and role == "user":
                self._db.execute("UPDATE sessions SET title=? WHERE id=?",
                                 (content[:60], session_id))
            self._db.commit()

    def update_metadata(self, session_id: str, turn_seq: int, patch: dict, role: str = "assistant") -> bool:
        """73.2(a): merge `patch` into the stored metadata of one message (the async tail adds grade + timings)."""
        with self._lock:
            row = self._db.execute("SELECT id, metadata FROM conversations WHERE session_id=? AND turn_seq=? AND role=? "
                                   "ORDER BY rowid DESC LIMIT 1", (session_id, turn_seq, role)).fetchone()
            if not row:
                return False
            try:
                meta = json.loads(row[1] or "{}")
            except (json.JSONDecodeError, TypeError):
                meta = {}
            meta.update(patch or {})
            self._db.execute("UPDATE conversations SET metadata=? WHERE id=?", (json.dumps(meta), row[0]))
            self._db.commit()
            return True

    def history(self, session_id: str, limit: int = 200) -> List[dict]:
        with self._lock:
            # M-02: take the NEWEST `limit` rows (DESC + turn_seq tiebreak), then return them in
            # ascending display order — the old `ORDER BY created_at LIMIT` kept the OLDEST rows,
            # so long sessions reopened without their most recent turns.
            rows = self._db.execute(
                "SELECT role, content, turn_seq, metadata, created_at FROM conversations "
                "WHERE session_id=? ORDER BY created_at DESC, turn_seq DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            rows = list(reversed(rows))
        out = []
        for role, content, turn_seq, metadata, created in rows:
            try:
                meta = json.loads(metadata or "{}")
            except (json.JSONDecodeError, ValueError):
                meta = {}
            out.append({"role": role, "content": content, "turn_seq": turn_seq,
                        "metadata": meta, "created_at": created})
        return out

    def next_turn_seq(self, session_id: str) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(MAX(turn_seq), 0) FROM conversations WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return (row[0] or 0) + 1

    # --- widgets ----------------------------------------------------------------

    def upsert_widget(self, session_id: str, widget: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO session_widgets VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, widget["id"], widget["type"], widget.get("title", ""),
                 json.dumps(widget.get("props") or {}), 1 if widget.get("generated") else 0,
                 widget.get("created_at") or now_iso()),
            )
            self._db.commit()

    def remove_widget(self, session_id: str, widget_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM session_widgets WHERE session_id=? AND widget_id=?",
                             (session_id, widget_id))
            self._db.commit()

    def widgets(self, session_id: str) -> List[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT widget_id, type, title, props, generated, created_at "
                "FROM session_widgets WHERE session_id=? ORDER BY created_at", (session_id,),
            ).fetchall()
        out = []
        for wid, wtype, title, props, generated, created in rows:
            try:
                parsed = json.loads(props or "{}")
            except (json.JSONDecodeError, ValueError):
                parsed = {}
            out.append({"id": wid, "type": wtype, "title": title, "props": parsed,
                        "generated": bool(generated), "created_at": created})
        return out
