"""95.11 — a store write is durable when it is made (guide §4 "guardar").

Found while building v170: `AssertionStore(conn=facts._db)` does not own its commits (`_owns=False`,
so `_commit()` is a no-op), and `learning_apply`'s definition write (`assertions.assert_`) therefore
relies on a LATER FactStore write to commit the shared connection. Until that happens, a second
connection to the same file — the graph's own — waits on SQLite's busy timeout (30 s in v170's first
run) or fails with "database is locked".

Invariant: the write that supersedes or creates an assertion is committed by the path that made it.
The fixture below is two connections on one file, exactly the shape the engine runs with (FactStore and
HMGGraph each open their own). The test measures the wait rather than asserting an implementation.
"""
from __future__ import annotations

import sqlite3
import time

import pytest

from hmgfu.learning_apply import DEFINITION_RELATION, apply_decision, definition_entity_key
from tests.test_v2_agent import make_agent


def _write_definition(engine, text="In this project, ACME-7 means Atlas Control Mesh."):
    return apply_decision({"action": "commit", "operation": "assert"},
                          [{"kind": "domain_definition", "subject_ref": "ACME-7", "value": "Atlas Control Mesh"}],
                          text=text, source="user_explicit", session="s1",
                          facts=engine.facts, assertions=engine.facts.assertions, directives=engine.directives)


def test_a_second_connection_can_write_right_after_a_definition_write(tmp_path):
    """THE CONTRACT — fails before: the graph's connection waits on the uncommitted definition."""
    engine, _ = make_agent(tmp_path, [])
    _write_definition(engine)
    other = sqlite3.connect(str(tmp_path / "agent.db"), timeout=2.0)   # the same file, a second connection
    t0 = time.perf_counter()
    try:
        other.execute("CREATE TABLE IF NOT EXISTS v183_probe (id INTEGER PRIMARY KEY)")
        other.execute("INSERT INTO v183_probe DEFAULT VALUES")
        other.commit()
        locked = False
    except sqlite3.OperationalError as exc:
        locked = "locked" in str(exc)
    elapsed = time.perf_counter() - t0
    assert not locked, "the definition write left the shared connection holding the file"
    assert elapsed < 1.0, elapsed


def test_the_definition_is_visible_from_the_second_connection(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    _write_definition(engine)
    other = sqlite3.connect(str(tmp_path / "agent.db"), timeout=2.0)
    rows = other.execute("SELECT value FROM assertions WHERE relation=? AND status='active'",
                         (DEFINITION_RELATION,)).fetchall()
    assert rows and rows[0][0] == "Atlas Control Mesh", rows


def test_the_canonical_path_was_already_durable(tmp_path):
    """PRESERVE — FactStore._apply_one commits its own transaction (82.2); it must keep doing so."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all("O meu projeto principal chama-se Nimbus.", "user", session="s1")
    other = sqlite3.connect(str(tmp_path / "agent.db"), timeout=2.0)
    assert other.execute("SELECT value FROM canonical_facts WHERE key='project.main'").fetchone()[0] == "Nimbus"
