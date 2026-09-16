"""93.Q2 — "maybe" must not destroy the thing it declined to decide.

Found in the probe's own scratch databases, not in a unit test. After the three arms ran, the pendency
case rows read:

    rep 1  state awaiting   needs 'subject'  question "…what is it the name of?"  proposals [ … ]
    rep 2  state rejected   needs None       question None                        proposals []
    rep 3  state deferred   needs None       question None                        proposals []

`transition` merges the payload it is given, and `_persist` hands it every key on every turn —
including the ones the answering turn has nothing for. A bare "no" or "maybe" carries no proposal, no
question and no needs, so the merge overwrote all three with emptiness. The case survived; everything
that made it answerable did not.

It is the same lesson a third time (92.E4 `memory_update`, 93.R1 `condition`, 93.R4 `ambiguity`, and
93.P1 for a commit): **an optional field is an omitted field**. 93.P1 fixed it for `commit` alone —
"re-deriving the proposal from 'yes' … would overwrite the case with an empty list, erasing what it
had just committed" — and reject and defer were left writing the same emptiness.

`defer` is where it bites hardest, because deferring is precisely the state that says *decide later*:
"uncertainty is not agreement and is not a refusal". A deferred case that has forgotten its own
question cannot be answered later by anyone.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_state import LearningState, _persist

QUESTION = "I do not want to record 'Nimbus' against the wrong thing -- what is it the name of?"
PROPOSAL = {"kind": "domain_definition", "value": "Nimbus",
            "subject_ref": "the name of the project being discussed",
            "evidence_refs": ["turn:1#13-19"]}


def _case(tmp_path):
    state = LearningState(str(tmp_path / "cases.db"))
    case_id = state.open_case("s1", 0, {"proposals": [PROPOSAL], "question": QUESTION,
                                        "needs": "subject", "expression": "It is called Nimbus."},
                              state="awaiting", origin_turn_id="1")
    return state, case_id


def _answer(state, case_id, action):
    """What `_persist` does on a turn that answers with a bare word: no proposal of its own."""
    decision = {"action": action, "question": None, "reason": f"{action} by a bare answer"}
    snapshot = {"pending_case": {"id": case_id, "revision": 0, "state": "awaiting"}, "needs": None}
    _persist(state, decision, snapshot, [], "s1", 0, "2", "")
    return state.get(case_id)


@pytest.mark.parametrize("action,expected", [("reject", "rejected"), ("defer", "deferred")])
def test_the_case_still_holds_the_proposal_it_was_asking_about(tmp_path, action, expected):
    state, case_id = _case(tmp_path)
    case = _answer(state, case_id, action)
    assert case["state"] == expected
    assert case["proposals"] == [PROPOSAL], "the answer carried none; that is not the same as none"
    state.close()


@pytest.mark.parametrize("action", ["reject", "defer"])
def test_it_still_holds_the_question_and_what_the_question_asked_for(tmp_path, action):
    state, case_id = _case(tmp_path)
    case = _answer(state, case_id, action)
    assert case["question"] == QUESTION
    assert case["needs"] == "subject"
    state.close()


@pytest.mark.parametrize("action", ["reject", "defer"])
def test_the_words_the_user_actually_said_survive(tmp_path, action):
    """The expression is the evidence the preserved value points into; losing it loses the value."""
    state, case_id = _case(tmp_path)
    assert _answer(state, case_id, action)["expression"] == "It is called Nimbus."
    state.close()


@pytest.mark.parametrize("action", ["reject", "defer"])
def test_the_reason_is_this_turn_s_reason_not_the_old_one(tmp_path, action):
    """The discriminating half: preserving must not freeze the case. What this turn DID is new."""
    state, case_id = _case(tmp_path)
    assert _answer(state, case_id, action)["reason"] == f"{action} by a bare answer"
    state.close()


def test_a_turn_that_brings_a_new_proposal_replaces_the_old_one(tmp_path):
    """The other discriminating half: preservation is for what the turn is SILENT about."""
    state, case_id = _case(tmp_path)
    fresh = {"kind": "domain_definition", "value": "Stratus"}
    decision = {"action": "commit", "question": None, "reason": "a new teaching"}
    snapshot = {"pending_case": {"id": case_id, "revision": 0, "state": "awaiting"}, "needs": None}
    _persist(state, decision, snapshot, [fresh], "s1", 0, "2", "It is called Stratus.")
    case = state.get(case_id)
    assert case["proposals"] == [fresh] and case["expression"] == "It is called Stratus."
    state.close()
