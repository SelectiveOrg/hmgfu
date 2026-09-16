"""93.A — a "yes" answers the question that was actually asked, and only one thing can be asking.

From the real conversation of 2026-09-11: the user said *stop saying none*, the assistant turned that
into a plan proposal titled *make sure that doesn't happen again!*, and the user's *yes* approved the
PLAN. Nothing was learned, and the plan then outlived its purpose and blocked an unrelated request
sixteen turns later.

The protocol already refuses the mirror image of this — a bare yes cannot approve a plan, and another
session's pending question cannot consume this answer (v120). The missing half is on the plan side:
`begin_turn` runs before the learning turn, so when BOTH a plan proposal and a delivered learning
question are waiting, the plan silently takes the yes and the learning question is left to be
deferred. Two addressees for one word is exactly the ambiguity the guide says must be clarified
rather than resolved by guessing, so neither side may consume it.

The discriminating half matters as much: with only one thing pending, the yes must still work
normally, and with the protocol off there is no second addressee at all.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_state import LearningState
from hmgfu.session_plans import SessionPlanStore, begin_turn, propose


class _Engine:
    """The smallest engine `begin_turn` touches: a plan store, a settings getter and an emitter."""

    def __init__(self, tmp_path, mode="confirm"):
        self.db_path = str(tmp_path / "s.db")
        self.session_plans = SessionPlanStore(self.db_path)
        self.state = LearningState(self.db_path)
        self._turn_seq = 4
        self._turn_plan = None
        self._turn_step_tools = []
        self.events = []
        self.receipts = None
        self._mode = mode

    def _emit(self, event):
        self.events.append(event)


@pytest.fixture()
def engine(tmp_path):
    return _Engine(tmp_path)


def _ask(engine, session="s1"):
    """A learning question that was DELIVERED to the user and is still waiting."""
    return engine.state.open_case(session, 7, {"question": "Is Green your dog's name?",
                                               "proposals": [{"kind": "personal_fact"}]},
                                  state="awaiting", question_turn_id="3")


def test_a_bare_yes_with_two_pendings_activates_nothing(engine):
    propose(engine, "s1", "make sure that doesn't happen again!", ["memory_search: check"])
    _ask(engine)
    block = begin_turn(engine, "s1", "yes")
    assert engine.session_plans.pending("s1") is not None, "the plan must still be waiting"
    assert (engine.session_plans.resumable("s1") or {}).get("status") != "active"
    assert engine.state.active_question("s1") is not None, "the question must still be waiting"
    assert "which" in block.lower() or "clarif" in block.lower(), block


def test_the_ambiguity_block_names_both_candidates(engine):
    propose(engine, "s1", "make sure that doesn't happen again!", ["memory_search: check"])
    _ask(engine)
    block = begin_turn(engine, "s1", "yes")
    assert "make sure that doesn't happen again!" in block
    assert "Is Green your dog's name?" in block


def test_a_yes_with_only_a_plan_still_approves_it(engine):
    """The legitimate positive: no second addressee, no change in behaviour."""
    propose(engine, "s1", "build the timer", ["create_widget: timer"])
    block = begin_turn(engine, "s1", "yes")
    plan = engine.session_plans.resumable("s1")
    assert plan["status"] == "active" and "APPROVED" in block


def test_a_yes_with_only_a_learning_question_leaves_the_plan_alone(engine):
    _ask(engine)
    begin_turn(engine, "s1", "yes")
    assert engine.session_plans.pending("s1") is None
    assert engine.state.active_question("s1") is not None, "the protocol consumes it later in the turn"


def test_a_question_never_delivered_is_not_a_second_addressee(engine):
    """An undelivered question was never asked, so it cannot be what the user is answering."""
    propose(engine, "s1", "build the timer", ["create_widget: timer"])
    engine.state.open_case("s1", 7, {"question": "unsent"}, state="awaiting")
    block = begin_turn(engine, "s1", "yes")
    assert engine.session_plans.resumable("s1")["status"] == "active", block


def test_another_sessions_question_is_not_a_second_addressee(engine):
    propose(engine, "s1", "build the timer", ["create_widget: timer"])
    _ask(engine, session="OTHER")
    begin_turn(engine, "s1", "yes")
    assert engine.session_plans.resumable("s1")["status"] == "active"


def test_with_the_protocol_off_there_is_no_second_addressee(tmp_path):
    """A legacy base has no learning_cases table at all: the plan path must be untouched."""
    eng = _Engine(tmp_path, mode="off")
    eng.state._db.execute("DROP TABLE IF EXISTS learning_cases")
    eng.state._db.commit()
    eng.state._ready = False
    propose(eng, "s1", "build the timer", ["create_widget: timer"])
    begin_turn(eng, "s1", "yes")
    assert eng.session_plans.resumable("s1")["status"] == "active"


def test_a_no_with_two_pendings_also_asks_rather_than_declining_blindly(engine):
    propose(engine, "s1", "make sure that doesn't happen again!", ["memory_search: check"])
    _ask(engine)
    begin_turn(engine, "s1", "no")
    assert engine.session_plans.pending("s1") is not None, "a blind decline is a guess too"
