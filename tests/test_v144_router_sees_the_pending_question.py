"""93.R4 — a bare "yes" only means something if the classifier knows what was asked.

The live chain gets as far as asking: with `ambiguity` required, an ambiguous teaching raises a
grounded question 3/3 and the reply carries it. The next turn then dies — "yes", "no" and "maybe" all
produce `protocol_unavailable`, because the router returns `memory_update: null` for them.

Which is a reasonable thing for it to do. A bare "yes" teaches nothing on its own; its whole meaning
is the question it answers, and the router was never shown that a question was outstanding. The
pending question reaches the CHAT model through the 93.D state block, but the router composes its own
context — runtime, prompt, catalog, directives, exemplars, confirmed interpretations — and the
question was in none of them.

So it is passed the same way the active directives are, and the tests hold both directions: present
when a question is genuinely outstanding, absent otherwise, so the model is never invited to read
agreement into a turn that answers nothing.
"""
from __future__ import annotations

import json

from hmgfu.turn_router import classify_turn, router_schema

QUESTION = "Which project is 'it' in this sentence?"


def _system(pending: str = "") -> str:
    seen = {}

    def chat(role, messages, **kwargs):
        seen["sys"] = messages[0]["content"]
        return "{}"

    classify_turn(chat, json.loads, "yes", "clock", "[]",
                  format_schema=router_schema([], learning=True), pending_question=pending)
    return seen["sys"]


def test_an_outstanding_question_reaches_the_router():
    assert QUESTION in _system(QUESTION)


def test_it_says_a_bare_answer_belongs_to_that_question():
    block = _system(QUESTION)
    lower = block.lower()
    assert "yes" in lower and "answers" in lower


def test_nothing_is_added_when_no_question_is_outstanding():
    """The discriminating half: without a pending question the router must not read agreement in."""
    assert QUESTION not in _system("")
    assert "outstanding" not in _system("").lower()


def test_the_question_is_marked_as_context_not_as_an_instruction():
    """It tells the router how to READ this turn; it is not something to execute or to assert."""
    head = _system(QUESTION)
    assert "QUESTION YOU ASKED" in head or "asked the user" in head


def test_the_sensitizer_offers_it_only_when_one_is_delivered_and_unanswered(tmp_path):
    from hmgfu.learning_state import LearningState
    from hmgfu.sensitizer import Sensitizer

    class _Facts:
        def __init__(self, db):
            self._db = db

    class _Settings:
        def get(self, key):
            return "confirm" if key == "interactive_learning_mode" else None

    class _Engine:
        def __init__(self, db):
            self.facts = _Facts(db)
            self.settings = _Settings()

    st = LearningState(str(tmp_path / "s.db"))
    sens = Sensitizer(client=None, enabled=False)
    sens.bind_learning_examples(_Engine(st._db))

    assert sens._pending_question_text("s1") == ""              # nothing pending
    case = st.open_case("s1", 3, {"question": QUESTION}, state="awaiting")
    assert sens._pending_question_text("s1") == "", "a question never delivered was never asked"
    st._db.execute("UPDATE learning_cases SET question_turn_id='4' WHERE id=?", (case,))
    st._db.commit()
    assert QUESTION in sens._pending_question_text("s1")
    assert sens._pending_question_text("OTHER") == "", "another session's question is not this one's"
