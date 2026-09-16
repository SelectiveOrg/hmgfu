"""93.Q2 — the router was told to expect a yes/no to a question that asked for a name.

With the three-arm probe in place, the elliptical arm reported `taught=protocol_unavailable,
envelope is not an object` 3/3: the router emitted no `memory_update` at all for `my current project`.
Before calling that a limit of the model, the deterministic side was checked, and it was wrong.

`question_for` asks two different questions. When the proposal is complete it asks for a
confirmation — *"Should I record that X is Y?"* — and a bare yes/no answers it. When a property is
MISSING it asks the user to supply it — *"I do not want to record 'Nimbus' against the wrong thing —
what is it the name of?"* — and a yes cannot answer that at all; 93.P3 established exactly that.

But the only guidance the router ever received was written for the first kind:

    A bare yes/no/maybe this turn ANSWERS THAT QUESTION — report it as feedback
    (confirm / reject / uncertain), not as a new fact.

So the system asked for a name and told its own classifier to expect a yes. The reply that supplies
the name is neither feedback nor a free-standing new fact, and nothing told it what that is.

The case already records `needs`, so this adds no new state: the question's own kind travels with it.
The negative matters as much — a CONFIRMATION question must keep inviting a yes/no and must NOT
invite a proposal, or every confirmation turn becomes a fresh teaching.
"""
from __future__ import annotations

import json

from hmgfu.turn_router import classify_turn, router_schema

FILL_IN = "I do not want to record 'Nimbus' against the wrong thing -- what is it the name of?"
CONFIRM = "Should I record that Nimbus is the name of my current project?"


def _system(pending: str = "", needs: str = "") -> str:
    seen = {}

    def chat(role, messages, **kwargs):
        seen["sys"] = messages[0]["content"]
        return "{}"

    classify_turn(chat, json.loads, "my current project", "clock", "[]",
                  format_schema=router_schema([], learning=True),
                  pending_question=pending, pending_needs=needs)
    return seen["sys"]


def test_a_fill_in_question_says_the_reply_supplies_the_missing_piece():
    block = _system(FILL_IN, "subject").lower()
    assert "supplies" in block or "names" in block


def test_a_fill_in_question_says_where_the_value_comes_from():
    """Not feedback and not a fresh fact: it finishes something already under discussion, so the
    value must come from the question rather than be invented here.

    Phrased as the invariant rather than as a word: the wording itself was chosen by measuring four
    candidates against the real router, so a test naming one of them would have to be rewritten every
    time a measurement changed the wording, which is how a test stops meaning anything."""
    block = _system(FILL_IN, "subject").lower()
    assert "from the question" in block and "not emit feedback" in block


def test_a_confirmation_question_still_asks_for_a_bare_answer():
    block = _system(CONFIRM).lower()
    assert "yes" in block and "feedback" in block


def test_a_confirmation_question_does_not_invite_a_new_proposal():
    """The discriminating half: inviting a proposal here would turn every 'yes' into a teaching."""
    assert "supplies" not in _system(CONFIRM).lower()


def test_the_fill_in_guidance_needs_a_question_to_attach_to():
    assert "supplies" not in _system("", "subject").lower()


def test_a_missing_context_asks_for_a_context_not_for_a_subject():
    block = _system("Where does 'Nimbus' apply?", "context").lower()
    assert "context" in block


def test_the_case_carries_which_kind_of_question_it_asked(tmp_path):
    """`needs` is already recorded when the case is opened; nothing new is stored for this."""
    from hmgfu.learning_perception import pending_needs, pending_question
    from hmgfu.learning_state import LearningState, deliver_question

    state = LearningState(str(tmp_path / "cases.db"))
    case_id = state.open_case("s1", 0, {"question": FILL_IN, "needs": "subject",
                                        "proposals": [{"kind": "domain_definition",
                                                       "value": "Nimbus"}]}, state="awaiting")
    deliver_question(state, case_id, turn_id="7", reply=FILL_IN)

    class _Facts:
        pass

    class _Engine:
        facts = _Facts()

    _Engine.facts._db = state._db
    assert pending_question(_Engine, "s1") == FILL_IN
    assert pending_needs(_Engine, "s1") == "subject"
    assert pending_needs(_Engine, "another-session") == ""
    state.close()
