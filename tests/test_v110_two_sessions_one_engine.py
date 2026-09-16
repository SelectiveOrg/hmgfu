"""Phase 91.W2 — a correction must not inherit its antecedent from another session of the SAME engine.

The second independent analysis (`reports/codex_verify91V/ANALISE.md`) rejected my v106 "later session" test, and it
was right: `AgentEngine` holds ONE `self.facts` for every session, `SessionStore.create_session` only writes a row, and
there is no session in the referential resolution at all. My test built a NEW FactStore, which clears `_last_subject`,
so it proved isolation after recreating the store — not isolation between two sessions on one engine.

These tests use one store and alternate two session ids, the way the application does. The contract:

  * a correction resolves against the subject of the previous utterance OF ITS OWN SESSION;
  * a legitimate in-session correction keeps working, including after the other session has spoken in between;
  * a candidate resolved this way still goes through the ordinary validations.

No GPU and no model: the store is exercised directly, which is exactly the layer the analysis said was untested.
"""

from __future__ import annotations

from hmgfu.facts import FactStore

A, B = "session-a", "session-b"


def _store(tmp_path):
    return FactStore(str(tmp_path / "f.db"))


def _active(st):
    return {f["key"]: f["value"] for f in st.active()}


def test_a_correction_does_not_inherit_the_other_sessions_subject(tmp_path):
    """The defect the analysis predicted: B speaks about a colour, A then says "that's wrong" about ITS own city."""
    st = _store(tmp_path)
    st.apply_all("I live in Nacala.", "user_explicit", session=A)
    st.apply_all("My favourite colour is teal.", "user_explicit", session=B)
    st.apply_all("That's wrong, it's Lichinga.", "user_explicit", session=A)
    got = _active(st)
    assert got.get("identity.location") == "Lichinga", got
    assert got.get("pref.color") == "teal", got


def test_the_other_session_keeps_its_own_antecedent(tmp_path):
    """The mirror image: B's correction belongs to B's subject, not to A's."""
    st = _store(tmp_path)
    st.apply_all("I live in Nacala.", "user_explicit", session=A)
    st.apply_all("My favourite colour is teal.", "user_explicit", session=B)
    st.apply_all("No, it's amber.", "user_explicit", session=B)
    got = _active(st)
    assert got.get("pref.color") == "amber", got
    assert got.get("identity.location") == "Nacala", got


def test_a_session_with_no_previous_subject_writes_nothing(tmp_path):
    """A correction arriving first in a fresh session has no antecedent of its own — it must not borrow one."""
    st = _store(tmp_path)
    st.apply_all("I live in Nacala.", "user_explicit", session=A)
    st.apply_all("That's wrong, it's Lichinga.", "user_explicit", session=B)
    assert _active(st).get("identity.location") == "Nacala", _active(st)


def test_alternating_turns_keep_each_correction_in_its_own_thread(tmp_path):
    st = _store(tmp_path)
    st.apply_all("I live in Nacala.", "user_explicit", session=A)
    st.apply_all("My favourite colour is teal.", "user_explicit", session=B)
    st.apply_all("That's wrong, it's Lichinga.", "user_explicit", session=A)
    st.apply_all("No, it's amber.", "user_explicit", session=B)
    got = _active(st)
    assert got.get("identity.location") == "Lichinga" and got.get("pref.color") == "amber", got


def test_the_referential_candidate_still_faces_the_validations_across_sessions(tmp_path):
    st = _store(tmp_path)
    st.apply_all("My name is Amaro.", "user_explicit", session=A)
    st.apply_all("No, it's raining.", "user_explicit", session=A)
    assert _active(st).get("identity.name") == "Amaro", _active(st)


def test_without_a_session_the_previous_behaviour_is_unchanged(tmp_path):
    """Compatibility: every existing caller passes no session and must keep working exactly as before."""
    st = _store(tmp_path)
    st.apply_all("I live in Nacala.", "user_explicit")
    st.apply_all("That's wrong, it's Lichinga.", "user_explicit")
    assert _active(st).get("identity.location") == "Lichinga", _active(st)
