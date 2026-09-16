"""Routing-exemplar memory — the router learns from its own recovered misroutes (Phase 56).

Closes the audit gap "misroutes are recovered but not remembered": when the semantic action
recovery (tool_points) rescues a turn the router mislabelled AND the recovered tool then
actually SUCCEEDS, the corrected classification is persisted as an exemplar. Future routing
injects the K most SIMILAR exemplars as learned few-shots — selected per-turn by embedding,
grown from live experience in whatever language the user spoke. Nothing here is a hand-written
phrase list; deleting the table restores stock routing (bounded, inspectable — Rule 10).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Callable, List, Optional

from . import config, fu_math
from .models import create_id, now_iso

log = logging.getLogger("hmgfu.route_memory")

MAX_EXEMPLARS = 50          # capped store: oldest/least-used evicted beyond this
DEDUP_MIN_COSINE = 0.92     # near-identical texts reinforce the existing exemplar instead
TOP_K = 2                   # learned few-shots injected per routing call
# Bench round-3 lesson: at 0.30 an exemplar carrying a literal command was injected into merely
# topical turns (even greetings — real-embedding cosines run high) and the router COPIED its
# tools, turning one learned command into a compulsion (L10/L19 regressions). A learned few-shot
# may only fire on a NEAR-REPHRASING of the phrase it was learned from.
MIN_SIMILARITY = 0.75


class RouteMemory:
    """SQLite-backed store of confirmed routing corrections + per-turn few-shot selection."""

    def __init__(self, db_path: Optional[str] = None,
                 embed: Optional[Callable[[str], List[float]]] = None):
        self._lock = threading.RLock()
        self._embed = embed
        self._db = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS route_exemplars ("
            "id TEXT PRIMARY KEY, text TEXT, embedding TEXT, conversation_act TEXT, "
            "tools TEXT, hits INTEGER, created_at TEXT, last_used_at TEXT)")
        self._db.commit()

    # --- learning (write path) ---------------------------------------------------

    def record_confirmed_recovery(self, text: str, conversation_act: str,
                                  tools: List[str]) -> Optional[str]:
        """Persist one CONFIRMED correction (the recovered tool ran successfully). Near-duplicate
        texts reinforce the existing exemplar's hit count instead of growing the store."""
        text = (text or "").strip()[:300]
        if not text or not tools or self._embed is None:
            return None
        emb = self._embed(text)
        with self._lock:
            for row in self._db.execute(
                    "SELECT id, embedding, hits FROM route_exemplars").fetchall():
                if fu_math.cosine(emb, json.loads(row[1])) >= DEDUP_MIN_COSINE:
                    self._db.execute(
                        "UPDATE route_exemplars SET hits=?, last_used_at=? WHERE id=?",
                        (row[2] + 1, now_iso(), row[0]))
                    self._db.commit()
                    return row[0]
            ex_id = create_id()
            self._db.execute(
                "INSERT INTO route_exemplars VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (ex_id, text, json.dumps(emb), conversation_act,
                 json.dumps(sorted(set(tools))[:4]), now_iso(), now_iso()))
            # capped, self-pruning: beyond MAX, evict the least-confirmed then oldest
            n = self._db.execute("SELECT COUNT(*) FROM route_exemplars").fetchone()[0]
            if n > MAX_EXEMPLARS:
                self._db.execute(
                    "DELETE FROM route_exemplars WHERE id IN (SELECT id FROM route_exemplars "
                    "ORDER BY hits ASC, created_at ASC LIMIT ?)", (n - MAX_EXEMPLARS,))
            self._db.commit()
            log.info("route exemplar learned: %r -> %s %s", text[:60], conversation_act, tools)
            return ex_id

    # --- routing support (read path) ----------------------------------------------

    def exemplars_for(self, text: str, top_k: int = TOP_K) -> str:
        """The learned few-shot block for THIS turn: the most similar confirmed corrections,
        rendered compactly for the routing prompt. Empty string when nothing relevant."""
        if self._embed is None:
            return ""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, text, embedding, conversation_act, tools "
                "FROM route_exemplars").fetchall()
        if not rows:
            return ""
        emb = self._embed((text or "")[:300])
        scored = sorted(
            ((fu_math.cosine(emb, json.loads(r[2])), r) for r in rows),
            key=lambda t: -t[0])
        lines = []
        used_ids = []
        for sim, r in scored[:top_k]:
            if sim < MIN_SIMILARITY:
                break
            lines.append(f'- "{r[1]}" -> conversation_act={r[3]}, action_requested=true, '
                         f"requested_tools={json.loads(r[4])}")
            used_ids.append(r[0])
        if used_ids:
            with self._lock:
                self._db.executemany(
                    "UPDATE route_exemplars SET last_used_at=? WHERE id=?",
                    [(now_iso(), i) for i in used_ids])
                self._db.commit()
        return "\n".join(lines)

    def stats(self) -> dict:
        with self._lock:
            n, hits = self._db.execute(
                "SELECT COUNT(*), COALESCE(SUM(hits), 0) FROM route_exemplars").fetchone()
        return {"exemplars": n, "confirmations": hits}

    def close(self) -> None:
        with self._lock:
            self._db.close()
