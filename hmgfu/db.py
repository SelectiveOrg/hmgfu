"""One way to open the hmg-fu SQLite database (Phase 72.6d).

Every store (graph store, facts, assertions, receipts, session plans, directives) keeps its own connection to the same
file. With SQLite's defaults (rollback journal, 5 s busy timeout) one long write transaction on any connection makes a
concurrent INSERT on another fail with "database is locked" — seen killing a bench turn in `receipts.open`. This helper
is the single place where the connection policy lives:

* WAL journal: readers never block a writer and a writer never blocks readers (the -wal/-shm side files are covered by
  the `hmgfu.db-*` gitignore rule);
* 30 s busy timeout (connection + PRAGMA) so a concurrent writer waits instead of failing;
* `check_same_thread=False` because the API serves turns from a thread pool while stores guard themselves with RLocks.

`connect(path)` is drop-in for `sqlite3.connect(path, check_same_thread=False)`.
"""
from __future__ import annotations

import sqlite3

BUSY_TIMEOUT_S = 30.0


def connect(path: str, *, timeout: float = BUSY_TIMEOUT_S) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=timeout)
    try:
        conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        if path not in (":memory:", ""):
            conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass                                   # a read-only or exotic file still gets a working connection
    return conn


def journal_mode(conn: sqlite3.Connection) -> str:
    return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()


STORE_ATTRS = ("facts", "directives", "receipts", "session_plans", "sessions", "graph", "settings", "learned_params")


def commit_open_transactions(engine, where: str = "") -> list:
    """73.4 turn-boundary guard: every store connection an engine holds must be committed between turns. A write left
    open on one connection makes the next writer on another connection in the same thread wait for the busy timeout
    ('database is locked'). Commits and reports offenders so the leak is fixed at its site, never hidden."""
    import logging
    log = logging.getLogger("hmgfu.db")
    offenders = []
    seen = set()
    for attr in STORE_ATTRS:
        store = getattr(engine, attr, None)
        for name, obj in ((attr, store), (attr + ".assertions", getattr(store, "assertions", None))):
            conn = getattr(obj, "_db", None)
            if conn is None or id(conn) in seen:
                continue
            seen.add(id(conn))
            try:
                if conn.in_transaction:
                    conn.commit()
                    offenders.append(name)
            except Exception:
                pass
    if offenders:
        log.warning("open transaction committed at %s on: %s — fix the store that left it open", where or "turn boundary",
                    ", ".join(offenders))
    return offenders
