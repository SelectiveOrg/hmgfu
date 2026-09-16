"""Phase 92.E3 — the pendency table's invariants, enforced by the database rather than by convention.

`learning_cases` is not another ledger of truth: it records what was proposed, which question was
actually delivered, and which store revision an answer was given against. These tests cover the three
things the plan says must not be left to callers -- one active question per session, compare-and-swap
on the revision, and a legacy base that never gains the table while the protocol is off -- plus the
two sessions and the restart the transition table depends on.
"""

from __future__ import annotations

import sqlite3

import pytest

from hmgfu.learning_state import CaseConflict, LearningState


def _st(tmp_path, name="ls.db"):
    return LearningState(str(tmp_path / name))


def test_one_active_question_per_session_is_enforced_by_the_index(tmp_path):
    st = _st(tmp_path)
    st.open_case("s1", 1, {"q": "first"}, state="awaiting", question_turn_id="t1")
    with pytest.raises(CaseConflict):
        st.open_case("s1", 1, {"q": "second"}, state="awaiting", question_turn_id="t2")


def test_two_sessions_each_keep_their_own_question(tmp_path):
    st = _st(tmp_path)
    st.open_case("s1", 1, {"q": "one"}, state="awaiting", question_turn_id="t1")
    st.open_case("s2", 1, {"q": "two"}, state="awaiting", question_turn_id="t2")
    assert st.active_question("s1")["q"] == "one"
    assert st.active_question("s2")["q"] == "two"


def test_an_answer_against_a_moved_revision_fails_instead_of_overwriting(tmp_path):
    st = _st(tmp_path)
    cid = st.open_case("s1", 5, {"q": "x"}, state="awaiting", question_turn_id="t1")
    with pytest.raises(CaseConflict):
        st.transition(cid, expect_revision=4, to_state="committed")
    assert st.get(cid)["state"] == "awaiting"          # unchanged, not half-applied


def test_an_invalidated_case_is_never_resurrected(tmp_path):
    st = _st(tmp_path)
    cid = st.open_case("s1", 1, {"q": "x"}, state="awaiting", question_turn_id="t1")
    st.transition(cid, expect_revision=1, to_state="invalidated")
    with pytest.raises(CaseConflict):
        st.transition(cid, expect_revision=1, to_state="committed")


def test_a_question_not_delivered_is_not_reported_as_awaiting_an_answer(tmp_path):
    """A candidate stored without a visible question must not be able to consume a later yes."""
    st = _st(tmp_path)
    st.open_case("s1", 1, {"q": "x"}, state="awaiting")          # no question_turn_id
    assert st.active_question("s1")["question_delivered"] is False


def test_a_delivered_question_is_marked_as_such(tmp_path):
    st = _st(tmp_path)
    st.open_case("s1", 1, {"q": "x"}, state="awaiting", question_turn_id="t9")
    assert st.active_question("s1")["question_delivered"] is True


def test_a_restart_finds_the_question_still_pertinent(tmp_path):
    """The state survives the process; a new LearningState over the same file sees it."""
    st = _st(tmp_path)
    st.open_case("s1", 3, {"q": "still open"}, state="awaiting", question_turn_id="t1")
    st.close()
    again = _st(tmp_path)
    q = again.active_question("s1")
    assert q["q"] == "still open" and q["revision"] == 3


def test_the_protocol_is_absent_from_a_legacy_base_when_it_is_off(tmp_path):
    """Opening with create=False must not create the table on a base that never had it."""
    path = str(tmp_path / "legacy.db")
    sqlite3.connect(path).close()
    st = LearningState(path, create=False)
    assert st.active_question("s1") is None
    names = [r[0] for r in sqlite3.connect(path).execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "learning_cases" not in names


def test_it_can_be_created_lazily_after_the_mode_changes(tmp_path):
    """Turning the mode on later must work without rebuilding the engine."""
    path = str(tmp_path / "lazy.db")
    sqlite3.connect(path).close()
    st = LearningState(path, create=False)
    st.ensure()
    cid = st.open_case("s1", 1, {"q": "x"}, state="awaiting", question_turn_id="t1")
    assert st.get(cid)["state"] == "awaiting"


def test_a_shared_connection_is_not_committed_by_the_store(tmp_path):
    """The case and the revision it authorises must commit together, or not at all."""
    conn = sqlite3.connect(str(tmp_path / "shared.db"))
    st = LearningState(conn=conn)
    st.open_case("s1", 1, {"q": "x"}, state="awaiting", question_turn_id="t1")
    conn.rollback()                                   # the caller decided against the transaction
    assert st.active_question("s1") is None


def test_an_id_is_minted_by_the_store_not_supplied(tmp_path):
    st = _st(tmp_path)
    a = st.open_case("s1", 1, {"q": "x"})
    b = st.open_case("s2", 1, {"q": "y"})
    assert a != b and len(a) == 16
