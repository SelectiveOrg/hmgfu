"""93.P3 — a bare "yes" to an unambiguous pending question is recognised without asking the model.

Authorised in terms by the standing goal: *"O reconhecimento de uma resposta simples pode ser
determinístico quando a pendência é inequívoca; isso nunca autoriza uma escrita sem evidência nem uma
tarefa diferente."* And it is the only link left: v145 shows a confirmation envelope now writes the
preserved proposal end to end, while the live model keeps returning `memory_update: null` for "yes".

The recogniser adds no vocabulary of its own — it is `session_plans.approval_signal`, which already
decides yes/no deterministically for plan proposals and already refuses anything that is not a bare
answer. What it produces is a FEEDBACK, never a proposal: the write still comes from the preserved
proposal with its original evidence, so this cannot authorise a fact nobody stated.

The guards are the point, and each has a test: no delivered question means nothing is recognised; a
composite answer is not a bare answer and must reach the model instead; a plan proposal waiting at the
same time is the ambiguity 93.A already refuses; and an answer to a question in another session is not
this session's.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_answer import simple_feedback

DELIVERED = {"id": "c1", "session_id": "s1", "state": "awaiting", "question_delivered": True,
             "question": "Is ACME-7 Atlas Control Mesh?", "proposals": [{"kind": "domain_definition"}]}


@pytest.mark.parametrize("text,expected", [
    ("yes", "confirm"),
    ("Yes.", "confirm"),
    ("sim", "confirm"),
    ("yes please", "confirm"),
    ("no", "reject"),
    ("Não.", "reject"),
    ("maybe", "uncertain"),
    ("talvez", "uncertain"),
    ("not sure", "uncertain"),
])
def test_a_bare_answer_is_recognised(text, expected):
    assert simple_feedback(text, DELIVERED) == expected


@pytest.mark.parametrize("text", [
    "yes, and also create a timer widget for me",
    "no — instead, my dog is called Green",
    "yes to the first one and no to the second",
    "I think the answer is somewhere in the middle, depending on the project",
])
def test_a_composite_or_qualified_answer_is_not_recognised(text):
    """These have content of their own; deciding them deterministically would be guessing."""
    assert simple_feedback(text, DELIVERED) is None


def test_nothing_is_recognised_without_a_delivered_question():
    """A question the user never saw cannot be what a "yes" answers."""
    assert simple_feedback("yes", dict(DELIVERED, question_delivered=False)) is None
    assert simple_feedback("yes", None) is None


def test_a_case_that_is_not_awaiting_is_not_answered():
    assert simple_feedback("yes", dict(DELIVERED, state="committed")) is None


def test_a_teaching_sentence_is_not_an_answer():
    assert simple_feedback("In this project, ACME-7 means Atlas Control Mesh.", DELIVERED) is None


def test_praise_is_not_a_confirmation():
    """Praise trains nothing — the protocol's own rule, and it must not arrive through this door."""
    assert simple_feedback("that was a great answer, thank you!", DELIVERED) is None


def test_the_recogniser_never_produces_a_proposal():
    """It reports how the user answered. What gets written is the proposal already on the case."""
    assert simple_feedback("yes", DELIVERED) in ("confirm", "reject", "uncertain")
