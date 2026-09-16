"""Assertions, entities and justifications — Fu-R objects C and R on top of the episodic store (Phase 72.2).

C (assertion): (entity_id, relation, value, polarity, modality, valid_from, valid_to, recorded_at, source episode/span,
status). Bitemporal: `valid_*` is when it holds in the world, `recorded_at` when the system learned it. A new value for
the same entity+relation SUPERSEDES the old one (valid_to = now) — the old one stays queryable at its own time.
R (justification): (conclusion, premises AND, type) — several justifications for one conclusion are OR. `supported()`
evaluates the positive, acyclic fragment: a conclusion holds while at least one justification has all its premises
active (or while it has no justification at all — a directly asserted fact).
Entities: the user ("user"), pets/people by (kind, name); two dogs are two entities, never two values in one slot.
"""
from __future__ import annotations

import json
import sqlite3
import re
import threading
import uuid
from typing import List, Optional

from . import config
from .db import connect as db_connect
from .models import now_iso

USER = "user"


SPAN_MAX = 4000        # 82.3: the whole chat message is the span; offsets are into the ORIGINAL text


def locate_value(text: str, value: str) -> tuple:
    """82.3: exact offsets of `value` in `text` (case-insensitive, first occurrence) or (None, None) when it is not
    verbatim there — never a guess."""
    if not text or not value:
        return (None, None)
    i = text.lower().find(value.strip().lower())
    return (i, i + len(value.strip())) if i >= 0 else (None, None)


class AssertionStore:
    def __init__(self, db_path: Optional[str] = None, conn=None):
        """82.2 (Codex A2): when `conn` is given the store WRITES ON THE CALLER'S CONNECTION and never commits — the
        caller (FactStore) owns the transaction, so a canonical row and its assertion are one durable revision."""
        self._lock = threading.RLock()
        self._owns = conn is None
        self._db = conn if conn is not None else db_connect(db_path or config.DB_PATH)
        # 82.5: SQLite's lower() folds ASCII only — "Élio" never equalled Python's "élio"; one fold for both sides
        self._db.create_function("ulower", 1, lambda s: (s or "").strip().lower())
        self._db.execute("CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, kind TEXT, name TEXT, aliases TEXT, created_at TEXT)")
        self._db.execute("CREATE TABLE IF NOT EXISTS assertions (id TEXT PRIMARY KEY, entity_id TEXT, relation TEXT, value TEXT, "
                         "polarity TEXT, modality TEXT, valid_from TEXT, valid_to TEXT, recorded_at TEXT, source_episode TEXT, "
                         "source_span TEXT, status TEXT)")
        for col in ("span_start INTEGER", "span_end INTEGER"):          # 82.3 additive migration: exact offsets of the value
            try:
                self._db.execute(f"ALTER TABLE assertions ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        self._db.execute("CREATE TABLE IF NOT EXISTS justifications (id TEXT PRIMARY KEY, conclusion TEXT, premises TEXT, "
                         "type TEXT, status TEXT, created_at TEXT)")
        self._db.execute("INSERT OR IGNORE INTO entities VALUES ('user', 'user', 'user', '[]', ?)", (now_iso(),))
        self._commit()

    # ---------------------------------------------------------------- entities
    def _commit(self) -> None:
        if self._owns:
            self._db.commit()

    def commit(self) -> None:
        """95.11: commit a revision this store finished ALONE (a definition assert/retract). On a shared
        connection `_commit()` is a deliberate no-op (82.2: one canonical revision, one transaction);
        the path that ends without a canonical write must still make its revision durable."""
        with self._lock:
            self._db.commit()

    def upsert_entity(self, kind: str, name: str) -> str:
        key = (name or "").strip().lower()
        with self._lock:
            row = self._db.execute("SELECT id FROM entities WHERE kind=? AND lower(name)=?", (kind, key)).fetchone()
            if row:
                return row[0]
            eid = f"{kind}:{uuid.uuid4().hex[:8]}"
            self._db.execute("INSERT INTO entities VALUES (?,?,?,?,?)", (eid, kind, name.strip(), "[]", now_iso()))
            self._commit()
            return eid

    def render_definition_lines(self, relation: str, limit: int = 12) -> List[str]:
        """92.E5R: ACTIVE definitions as canonical lines for the reply context.

        Written and never read is not learned: the matrix diagnostic taught `ACME-7`, stored it, and
        a new session answered "I'm not certain what ACME-7 refers to" -- `retrieve` and
        `context_render` never touch this store, and `read_definition` had no product call site.
        The entity name carries `<context>::<term>` (learning_state.definition_entity_key), so the
        line can say WHERE the term applies, and it is labelled as a definition the user confirmed so
        it can never be read as something the assistant inferred (provenance). Superseded meanings
        are excluded: a correction wins here too."""
        names = {e["id"]: e.get("name") or "" for e in self.entities("definition")}
        out = []
        for row in self.active():
            if row.get("relation") != relation:
                continue
            ctx, _, term = str(names.get(row.get("entity_id")) or "").partition("::")
            if not term:
                continue
            where = f" ({ctx})" if ctx and ctx != "local" else ""
            # the identity key folds case on purpose; the user's own spelling survives in the span
            span = row.get("source_span") or ""
            shown = next((m.group(0) for m in re.finditer(re.escape(term), span, re.IGNORECASE)), term)
            out.append(f"{shown}{where} means {row.get('value')} [definition confirmed by the user]")
        return out[:limit]

    def entities(self, kind: Optional[str] = None) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, kind, name FROM entities" + (" WHERE kind=?" if kind else ""),
                                    (kind,) if kind else ()).fetchall()
        return [{"id": i, "kind": k, "name": n} for i, k, n in rows]

    # ---------------------------------------------------------------- assertions
    def assert_(self, entity_id: str, relation: str, value: str, polarity: str = "pos", modality: str = "assert",
                valid_from: Optional[str] = None, source_episode: Optional[str] = None, source_span: str = "",
                span_start: Optional[int] = None, span_end: Optional[int] = None) -> str:
        """82.3: `source_span` is the WHOLE message (up to SPAN_MAX) and `span_start/end` the exact offsets of the value
        inside it (None when the value is not verbatim in the text — a mapped or normalised value)."""
        now = now_iso()
        with self._lock:
            cur = self._db.execute("SELECT id, value FROM assertions WHERE entity_id=? AND relation=? AND status='active' AND polarity='pos'",
                                   (entity_id, relation)).fetchall()
            ends_at = valid_from if valid_from and valid_from <= now else now   # 87.3: the old value stopped holding when the new one began
            for aid, old in cur:
                if old.strip().lower() == (value or "").strip().lower():
                    return aid                                       # restated: no new record
                self._db.execute("UPDATE assertions SET status='superseded', valid_to=? WHERE id=?", (ends_at, aid))
            aid = uuid.uuid4().hex[:12]
            self._db.execute("INSERT INTO assertions (id, entity_id, relation, value, polarity, modality, valid_from, valid_to, "
                             "recorded_at, source_episode, source_span, status, span_start, span_end) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (aid, entity_id, relation, value, polarity, modality, valid_from, None, now,
                              source_episode, (source_span or "")[:SPAN_MAX], "active", span_start, span_end))
            self._commit()
            return aid

    def link_episode(self, relation: str, value: str, episode: str) -> int:
        """82.3 (A4): attach the ingested point id to the assertion(s) for (relation, value) that have none yet — the
        assertion written THIS turn; a superseded predecessor keeps its own episode."""
        with self._lock:
            n = self._db.execute("UPDATE assertions SET source_episode=? WHERE relation=? AND ulower(value)=? AND source_episode IS NULL",
                                 (episode, relation, (value or "").strip().lower())).rowcount
            self._commit()
        return n

    def supersede_value(self, relation: str, value: str) -> int:
        """77.3: a canonical write REPLACED `value` in `relation` (a correction without plurality — 'my cat is Luna' then
        'my cat is Sol'): the old value's assertion is superseded wherever it lives (another pet entity included), so the
        assertion view never shows two current values where the canonical view shows one."""
        now = now_iso()
        with self._lock:
            n = self._db.execute("UPDATE assertions SET status='superseded', valid_to=? WHERE relation=? AND ulower(value)=? "
                                 "AND status='active' AND polarity='pos'", (now, relation, (value or "").strip().lower())).rowcount
            self._commit()
        return n

    def retract(self, entity_id: Optional[str], relation: Optional[str] = None, value: Optional[str] = None,
                relation_prefix: Optional[str] = None) -> int:
        """Retire matching active assertions (any of entity/relation/value may be None = wildcard). 82.1 (Codex A1):
        `relation_prefix` scopes a value retraction to one slot FAMILY ("pet.") so a named negation never reaches another
        entity's relation that happens to hold the same value."""
        now = now_iso()
        where, params = ["status='active'"], []
        if entity_id:
            where.append("entity_id=?"); params.append(entity_id)
        if relation:
            where.append("relation=?"); params.append(relation)
        if relation_prefix:
            where.append("relation LIKE ?"); params.append(relation_prefix.replace("%", "") + "%")
        if value:
            where.append("ulower(value)=?"); params.append(value.strip().lower())
        with self._lock:
            n = self._db.execute("UPDATE assertions SET status='retracted', valid_to=? WHERE " + " AND ".join(where),
                                 (now, *params)).rowcount
            self._commit()
        return n

    def _rows(self, where: str, params: tuple) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, entity_id, relation, value, polarity, modality, valid_from, valid_to, recorded_at, "
                                    "source_episode, source_span, status, span_start, span_end FROM assertions " + where, params).fetchall()
        keys = ("id", "entity_id", "relation", "value", "polarity", "modality", "valid_from", "valid_to", "recorded_at",
                "source_episode", "source_span", "status", "span_start", "span_end")
        return [dict(zip(keys, r)) for r in rows]

    def active(self, at: Optional[str] = None, entity_id: Optional[str] = None, known_at: Optional[str] = None) -> List[dict]:
        """Assertions that HOLD at `at` (default: now) — VALID time ("when did it happen"). 82.2: `known_at` adds the KNOWN
        time ("when did we learn it"): only assertions recorded at or before `known_at` are visible, so a fact valid since
        2020 but recorded today holds at 2021 and was not known at 2021. Query-time validity, not global demotion (Codex 68 §2.4)."""
        rows = self._rows("WHERE status IN ('active','superseded') AND polarity='pos'" + (" AND entity_id=?" if entity_id else ""),
                          (entity_id,) if entity_id else ())
        if at is None and known_at is None:
            return [r for r in rows if r["status"] == "active"]
        at = at or now_iso()
        out = []
        for r in rows:
            if known_at is not None and r["recorded_at"] > known_at:
                continue
            starts = r["valid_from"] or r["recorded_at"]
            ends = r["valid_to"]
            if starts <= at and (ends is None or ends > at):
                out.append(r)
        return out

    def history(self, entity_id: Optional[str] = None, relation: Optional[str] = None) -> List[dict]:
        where, params = [], []
        if entity_id:
            where.append("entity_id=?"); params.append(entity_id)
        if relation:
            where.append("relation=?"); params.append(relation)
        return self._rows(("WHERE " + " AND ".join(where) if where else "") + " ORDER BY recorded_at", tuple(params))

    # ---------------------------------------------------------------- justifications (AND/OR, positive, acyclic)
    def justify(self, conclusion: str, premises: List[str], kind: str = "support") -> str:
        jid = uuid.uuid4().hex[:12]
        with self._lock:
            self._db.execute("INSERT INTO justifications VALUES (?,?,?,?,?,?)",
                             (jid, conclusion, json.dumps(list(premises)), kind, "active", now_iso()))
            self._commit()
        return jid

    def supported(self, assertion_id: str, _depth: int = 0) -> bool:
        if _depth > 12:
            return False
        with self._lock:
            row = self._db.execute("SELECT status FROM assertions WHERE id=?", (assertion_id,)).fetchone()
            just = self._db.execute("SELECT premises FROM justifications WHERE conclusion=? AND status='active' AND type='support'",
                                    (assertion_id,)).fetchall()
        if not row or row[0] != "active":
            return False
        if not just:
            return True                                              # directly asserted
        for (prem,) in just:
            ids = json.loads(prem or "[]")
            if all(self.supported(p, _depth + 1) for p in ids):
                return True
        return False
