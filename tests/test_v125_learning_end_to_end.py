"""Phase 92.E4 — the protocol running inside a real AgentEngine turn.

Everything before this was the contract in isolation. Here the engine builds the snapshot, the
resolver goes and looks at the actual message, the controller decides, the adapters write, and a
receipt comes back — with a FAKE model, so what is measured is the wiring and not the 12B's wording.

Two properties matter more than the happy path:

  * with the mode OFF the turn must be what it is today, table included. That is arm S, and if S
    differed from the current system every later comparison would measure the wrong thing.
  * an evidence reference is resolved against the real message. A span that does not exist, or one
    sitting inside a denial, does not authorise anything — the modality comes from the same
    `utterance` contract that governs every other write in this codebase.
"""

from __future__ import annotations

import sqlite3

import pytest

from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent


class Q:
    """The QueryPoint fields the entry actually reads."""

    def __init__(self, envelope=None):
        self.extraction = {"memory_update": envelope} if envelope is not None else {}


def _env(text, start, end, turn_id="1", **kw):
    base = {"feedback": "none", "scope": "memory", "ambiguity": "none", "target_case_id": None,
            "proposals": [{"kind": "domain_definition", "subject_ref": "ACME-7",
                           "context_ref": "proj-1", "relation": "definition.meaning",
                           "value": text[start:end],
                           "evidence_refs": [f"turn:{turn_id}#{start}-{end}"]}]}
    base.update(kw)
    return base


def _engine(tmp_path, mode):
    engine, fake = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", mode)
    return engine


# 93.P2: the context must now be BOUND by something outside the proposal, so the teaching names
# the project it is about. The old fixture said `context_ref="proj-1"` about a sentence that
# mentioned no project at all -- which is the invented context the review reproduced, and it is
# refused now. What this file tests (commit -> assertion -> a new session reads it) is unchanged.
TEACH = "In proj-1, ACME-7 means Atlas Control Mesh"
SPAN = (TEACH.index("Atlas"), len(TEACH))   # computed, not guessed


def test_off_is_todays_system_and_creates_no_table(tmp_path):
    engine = _engine(tmp_path, "off")
    assert run_learning_turn(engine, "s1", TEACH, Q(_env(TEACH, *SPAN)), turn_id="1") is None
    names = [r[0] for r in engine.facts._db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "learning_cases" not in names


def test_a_resolvable_teaching_is_committed_and_receipted(tmp_path):
    engine = _engine(tmp_path, "confirm")
    out = run_learning_turn(engine, "s1", TEACH, Q(_env(TEACH, *SPAN)), turn_id="1")
    assert out["decision"]["action"] == "commit"
    assert out["receipt"]["status"] == "committed" and out["receipt"]["available_for_reading"]
    assert out["effects"] and out["effects"][0]["applied"]


def test_the_committed_definition_is_readable_in_a_new_session(tmp_path):
    """Persistence across sessions is the point of the exercise, not a side effect."""
    from hmgfu.learning_state import read_definition
    engine = _engine(tmp_path, "confirm")
    run_learning_turn(engine, "s1", TEACH, Q(_env(TEACH, *SPAN)), turn_id="1")
    got = read_definition(engine.facts.assertions, "proj-1", "ACME-7")
    assert got and got["value"] == "Atlas Control Mesh"


# 92.E4: the controller now DISCARDS any reference the model supplies and locates the value itself,
# so "a bogus ref is refused" no longer tests anything -- the bogus ref never reaches the resolver.
# The invariant that actually protects the ledger is the one below: a value that is not in the
# message cannot be written, however the proposal is dressed up.
@pytest.mark.parametrize("value,why", [
    ("Something The User Never Said", "the value appears nowhere in the message"),
    ("Atlas Control Mesh of Wherever", "only part of it appears; the span must be the whole value"),
])
def test_a_value_absent_from_the_message_writes_nothing(tmp_path, value, why):
    engine = _engine(tmp_path, "confirm")
    env = _env(TEACH, *SPAN)
    env["proposals"][0]["value"] = value
    out = run_learning_turn(engine, "s1", TEACH, Q(env), turn_id="1")
    assert out["decision"]["action"] != "commit", why
    assert out["effects"] == [], why


def test_a_reference_the_model_supplied_is_ignored_and_relocated(tmp_path):
    """A cited span could exist, be asserted, and still not be the value. So it is not trusted."""
    from hmgfu.learning_state import read_definition
    engine = _engine(tmp_path, "confirm")
    env = _env(TEACH, *SPAN)
    env["proposals"][0]["evidence_refs"] = ["turn:1#0-6"]      # points at "ACME-7", not at the value
    out = run_learning_turn(engine, "s1", TEACH, Q(env), turn_id="1")
    assert out["decision"]["action"] == "commit"
    assert read_definition(engine.facts.assertions, "proj-1", "ACME-7")["value"] == "Atlas Control Mesh"


def test_a_span_inside_a_denial_does_not_authorise(tmp_path):
    """Modality is read by the same contract that governs every other write here."""
    text = "I never said that ACME-7 means Atlas Control Mesh"
    engine = _engine(tmp_path, "confirm")
    out = run_learning_turn(engine, "s1", text, Q(_env(text, text.index("ACME-7"), len(text))), turn_id="1")
    assert out["decision"]["action"] != "commit"
    assert out["effects"] == []


def test_a_missing_envelope_is_unavailable_never_a_confirmation(tmp_path):
    engine = _engine(tmp_path, "confirm")
    out = run_learning_turn(engine, "s1", "hello", Q(None), turn_id="1")
    assert out["decision"]["action"] == "protocol_unavailable"
    assert out["receipt"]["status"] == "unavailable" and out["effects"] == []


def test_an_unresolved_conflict_asks_and_writes_nothing(tmp_path):
    engine = _engine(tmp_path, "confirm")
    out = run_learning_turn(engine, "s1", TEACH,
                            Q(_env(TEACH, *SPAN, ambiguity="contradictory")), turn_id="1")
    assert out["decision"]["action"] == "ask" and out["effects"] == []
    assert out["receipt"]["status"] == "pending_clarification"


def test_a_maybe_defers_without_writing(tmp_path):
    engine = _engine(tmp_path, "confirm")
    out = run_learning_turn(engine, "s1", TEACH,
                            Q(_env(TEACH, *SPAN, feedback="uncertain")), turn_id="1")
    assert out["decision"]["action"] == "defer" and out["effects"] == []


def test_a_receipt_never_claims_more_than_happened(tmp_path):
    """`received` is not `committed`: the distinction the audit asked for."""
    engine = _engine(tmp_path, "confirm")
    out = run_learning_turn(engine, "s1", TEACH,
                            Q(_env(TEACH, *SPAN, feedback="uncertain")), turn_id="1")
    assert out["receipt"]["status"] == "received"
    assert "revision" not in out["receipt"]


def test_the_mode_is_visible_in_the_result(tmp_path):
    engine = _engine(tmp_path, "adapt")
    out = run_learning_turn(engine, "s1", TEACH, Q(_env(TEACH, *SPAN)), turn_id="1")
    assert out["mode"] == "adapt"
