"""93.R4 — a question only counts once it has actually reached the user.

With `ambiguity` required, the protocol now raises a grounded question on an ambiguous teaching (3/3
live, where it was 0/3). The chain still could not close: `_persist` opened the case WITHOUT a
`question_turn_id`, so `question_delivered` stayed false forever, and the next turn's "yes" earned
nothing — correctly, by the rule that a candidate without a DELIVERED question earns nothing.

Nothing delivered the question either. So two things join up here, and the order matters: the reply
must carry the question, and only then is the case marked as having asked it. Marking delivery
without delivering would be the same lie in the other direction — a case that believes it asked
something the user never saw, ready to accept a "yes" to a question nobody heard.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_state import LearningState, deliver_question

QUESTION = "Which project is 'it' in this sentence?"


@pytest.fixture()
def state(tmp_path):
    return LearningState(str(tmp_path / "s.db"))


def _awaiting(state, session="s1"):
    return state.open_case(session, 3, {"question": QUESTION, "proposals": [{"kind": "personal_fact"}]},
                           state="awaiting")


def test_a_fresh_case_has_not_asked_anything(state):
    _awaiting(state)
    assert state.active_question("s1")["question_delivered"] is False


def test_delivering_marks_the_case_with_the_turn_that_asked(state):
    case_id = _awaiting(state)
    assert deliver_question(state, case_id, turn_id="7") is True
    case = state.active_question("s1")
    assert case["question_delivered"] is True and case["question_turn_id"] == "7"


def test_the_reply_must_carry_the_question_for_it_to_count(state):
    """The discriminating half: marking delivery without delivering is the same lie reversed."""
    case_id = _awaiting(state)
    assert deliver_question(state, case_id, turn_id="7", reply="Sure, noted.") is False
    assert state.active_question("s1")["question_delivered"] is False


def test_a_reply_that_contains_the_question_counts(state):
    case_id = _awaiting(state)
    assert deliver_question(state, case_id, turn_id="7",
                            reply=f"I want to get this right. {QUESTION}") is True
    assert state.active_question("s1")["question_delivered"] is True


def test_delivery_does_not_change_the_state_or_the_revision(state):
    """It records that the question was asked — it decides nothing and approves nothing."""
    case_id = _awaiting(state)
    before = state.active_question("s1")
    deliver_question(state, case_id, turn_id="7")
    after = state.active_question("s1")
    assert after["state"] == before["state"] == "awaiting"
    assert after["revision"] == before["revision"]


def test_delivering_twice_keeps_the_first_turn(state):
    """The turn that ASKED is the one that matters; a later echo does not move it."""
    case_id = _awaiting(state)
    deliver_question(state, case_id, turn_id="7")
    deliver_question(state, case_id, turn_id="9")
    assert state.active_question("s1")["question_turn_id"] == "7"


def test_an_unknown_case_is_not_delivered(state):
    assert deliver_question(state, "no-such-case", turn_id="7") is False


def test_no_case_id_is_not_an_error(state):
    """The turn did not ask anything; there is nothing to mark and nothing to complain about."""
    assert deliver_question(state, "", turn_id="7") is False
