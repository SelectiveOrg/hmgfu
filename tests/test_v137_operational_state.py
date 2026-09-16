"""93.D — the assistant's picture of its own state must be read from the state, or say it cannot be.

Three moments from the real conversation of 2026-09-11 are the specification here: the assistant
removed the `output_prefix` directive and then said no directive had changed; it defended a plan
whose status it never checked; and it said it had updated its records on a turn that recorded
nothing. Each is the same failure — describing itself from the reply it was composing instead of from
what the stores hold.

The tests guard the three rules, not the wording: every line comes from a store read now, an
unreadable source says so rather than reading as "nothing", and the block authorises nothing.
"""
from __future__ import annotations

import pytest

from hmgfu.directives import DirectiveStore
from hmgfu.learning_state import LearningState
from hmgfu.operational_state import NO_ACCESS, record_operations, state_block
from hmgfu.saydo import transactions_of
from hmgfu.session_plans import SessionPlanStore, propose


class _Engine:
    def __init__(self, tmp_path):
        path = str(tmp_path / "s.db")
        self.directives = DirectiveStore(path)
        self.session_plans = SessionPlanStore(path)
        self.state = LearningState(path)
        self._turn_seq = 2
        self._turn_plan = None
        self._turn_step_tools = []
        self.receipts = None

    def _emit(self, _event):
        pass


@pytest.fixture()
def engine(tmp_path):
    return _Engine(tmp_path)


def test_an_empty_state_says_nothing_at_all(engine):
    assert state_block(engine, "s1") == ""


def test_an_active_directive_is_named_with_its_condition(engine):
    engine.directives.apply("keep it short unless I ask for more", "user_explicit",
                            detected={"kind": "response_style", "value": "short",
                                      "condition": "the user asks for the full context"})
    block = state_block(engine, "s1")
    assert "response_style" in block and "short" in block
    assert "unless the user asks for the full context" in block


def test_a_proposed_plan_says_it_is_waiting_for_the_user(engine):
    propose(engine, "s1", "build the timer", ["create_widget: timer"])
    block = state_block(engine, "s1")
    assert "PROPOSED" in block and "build the timer" in block


def test_a_pending_question_names_its_addressee(engine):
    """The line that would have prevented a plan from eating the learning question's yes."""
    engine.state.open_case("s1", 3, {"question": "Is Green your dog's name?"},
                           state="awaiting", question_turn_id="2")
    block = state_block(engine, "s1")
    assert "Is Green your dog's name?" in block
    assert "answers THAT" in block


def test_what_the_previous_turn_changed_comes_from_the_transactions(engine):
    """The exact failure: 'I have removed the directive' followed by 'no directive changed'."""
    record_operations(engine, transactions_of([], [], {"kind": "output_prefix", "cleared": True}))
    block = state_block(engine, "s1")
    assert "remove directive:output_prefix" in block


def test_a_turn_that_changed_nothing_says_so_rather_than_listing_something(engine):
    record_operations(engine, transactions_of([], [], None))
    engine.directives.apply("x", "user_explicit", detected={"kind": "response_style", "value": "short"})
    # 93.R2 reworded this line to name the conversation it speaks about
    assert "in this conversation: nothing" in state_block(engine, "s1")


def test_an_unreadable_source_says_unavailable_instead_of_none(engine):
    """Silence would read as 'nothing there', which is a different claim and often a false one."""
    class _Broken:
        def active(self):
            raise RuntimeError("store is gone")

    engine.directives = _Broken()
    engine.state.open_case("s1", 3, {"question": "q?"}, state="awaiting", question_turn_id="2")
    assert NO_ACCESS in state_block(engine, "s1")


def test_the_block_says_it_authorises_nothing(engine):
    propose(engine, "s1", "build the timer", ["create_widget: timer"])
    assert "authorises nothing" in state_block(engine, "s1")


def test_the_state_is_read_now_not_remembered(engine):
    """A stale snapshot outliving the effect that invalidated it is the whole failure mode."""
    engine.directives.apply("always start with Ready:", "user_explicit",
                            detected={"kind": "output_prefix", "value": "Ready:", "instruction": "i"})
    assert "output_prefix" in state_block(engine, "s1")
    engine.directives.apply("stop that", "user_explicit",
                            detected={"kind": "output_prefix", "clear": True})
    assert "output_prefix" not in state_block(engine, "s1")
