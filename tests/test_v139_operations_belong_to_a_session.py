"""93.R2 — "what I changed in this conversation" has to mean THIS conversation.

`record_operations` kept one list on the engine and `state_block(engine, session_id)` printed it
whatever session asked, so an operation performed in session A appeared in session B's block as
something the previous turn had changed there. The engine serves every session of the API; serialising
turns does not fix an attribution that carries no session at all. Reproduced without a model before
this was touched.

The semantics are made explicit rather than guessed, because both answers are defensible and they say
different things:

  * effects of THIS session are reported as what this conversation changed;
  * an effect from elsewhere is not hidden — a directive is global and still in force — but it is
    labelled as coming from another conversation, so the assistant cannot claim it as something it
    just did here.

The discriminating case is the last test: a turn that changed nothing in this session must say so,
even while another session's effect is visible.
"""
from __future__ import annotations

import pytest

from hmgfu.directives import DirectiveStore
from hmgfu.learning_state import LearningState
from hmgfu.operational_state import record_operations, state_block
from hmgfu.saydo import transactions_of
from hmgfu.session_plans import SessionPlanStore

REMOVAL = {"kind": "output_prefix", "cleared": True}


class _Engine:
    def __init__(self, tmp_path):
        path = str(tmp_path / "s.db")
        self.directives = DirectiveStore(path)
        self.session_plans = SessionPlanStore(path)
        self.state = LearningState(path)
        self._turn_seq = 4

    def _emit(self, _event):
        pass


@pytest.fixture()
def engine(tmp_path):
    return _Engine(tmp_path)


def test_the_session_that_acted_sees_its_own_operation(engine):
    record_operations(engine, transactions_of([], [], REMOVAL), session_id="A", turn_seq=4)
    assert "remove directive:output_prefix" in state_block(engine, "A")


def test_another_session_does_not_see_it_as_its_own(engine):
    """The reproduction: session A's removal appeared in B's block as B's previous turn."""
    record_operations(engine, transactions_of([], [], REMOVAL), session_id="A", turn_seq=4)
    block = state_block(engine, "B")
    assert "changed by the previous turn in this conversation: nothing" in block


def test_an_effect_from_elsewhere_is_shown_but_labelled(engine):
    """Not hidden: a directive removed elsewhere is still in force, and the origin is named."""
    record_operations(engine, transactions_of([], [], REMOVAL), session_id="A", turn_seq=4)
    block = state_block(engine, "B")
    assert "another conversation" in block.lower() and "output_prefix" in block


def test_the_label_says_which_session_and_turn(engine):
    record_operations(engine, transactions_of([], [], REMOVAL), session_id="A", turn_seq=7)
    assert "turn 7" in state_block(engine, "B")


def test_a_later_turn_of_the_same_session_replaces_the_earlier_one(engine):
    record_operations(engine, transactions_of([], [], REMOVAL), session_id="A", turn_seq=4)
    record_operations(engine, transactions_of([], [{"key": "pet.dog.name", "value": "Green"}], None),
                      session_id="A", turn_seq=5)
    block = state_block(engine, "A")
    assert "update fact:pet.dog.name" in block and "output_prefix" not in block.split("in force")[0]


def test_a_turn_that_changed_nothing_here_says_so_even_when_elsewhere_did(engine):
    """The discriminating case: silence about this session must not be filled from another one."""
    record_operations(engine, transactions_of([], [], REMOVAL), session_id="A", turn_seq=4)
    record_operations(engine, transactions_of([], [], None), session_id="B", turn_seq=1)
    block = state_block(engine, "B")
    assert "changed by the previous turn in this conversation: nothing" in block


def test_the_old_call_without_a_session_still_works(engine):
    """Compatibility: a caller that does not name a session gets the pre-93.R2 behaviour."""
    record_operations(engine, transactions_of([], [], REMOVAL))
    assert "output_prefix" in state_block(engine, "anything")
