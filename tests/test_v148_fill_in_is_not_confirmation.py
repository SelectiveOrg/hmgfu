"""93.P3 (F1) — "yes" cannot fill a blank, and a question must name what is missing.

The live chain closed, and the first thing it committed was this: `It is called Nimbus.` produced a
proposal whose subject was `"the name of the project/entity being discussed"`, the question was
`Could you confirm that?`, the user said "yes", and a definition was written for a placeholder. Every
link worked and the result is wrong, which is what the review predicted — a confirmation of an
interpretation and a request for missing information are different acts, and only the first can be
answered by a bare yes.

So a case records WHAT it still needs:

  * nothing missing — the proposal is complete and bound, and a bare yes confirms exactly it;
  * a subject that nothing binds — the case needs filling, its question says so, and a bare yes is
    not an answer to it at all: the turn goes to the model, where a real answer ("Nimbus is my
    project") can be read as the teaching it is.

The distinction is deterministic and uses what the evidence resolution already knows. No phrase list,
and no invented object so that something can be confirmed.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_answer import simple_feedback
from hmgfu.learning_evidence import missing_property, question_for

# the refs are what `attach_evidence` mints; a proposal without them has no evidence at all, which
# `missing_property` reports first and the last test here checks on purpose.
BOUND = {"kind": "domain_definition", "subject_ref": "ACME-7", "context_ref": "project terminology",
         "value": "Atlas Control Mesh", "evidence_refs": ["turn:1#0-5"]}
UNBOUND = dict(BOUND, subject_ref="the name of the project/entity being discussed")
MESSAGE = "In this project, ACME-7 means Atlas Control Mesh."


def _resolved(subject=None, context="project terminology"):
    return {"turn:1#0-5": {"exists": True, "origin": "user", "subject": subject, "context": context,
                           "modality": "assert", "revision": 0}}


def test_a_bound_proposal_needs_nothing():
    assert missing_property(BOUND, _resolved(subject="ACME-7")) is None


def test_an_unbound_subject_is_what_is_missing():
    assert missing_property(UNBOUND, _resolved(subject=None)) == "subject"


def test_an_unbound_context_is_what_is_missing():
    assert missing_property(BOUND, _resolved(subject="ACME-7", context=None)) == "context"


def test_a_proposal_with_no_evidence_at_all_needs_the_evidence():
    assert missing_property(BOUND, {}) == "evidence"
    assert missing_property({k: v for k, v in BOUND.items() if k != "evidence_refs"},
                            _resolved(subject="ACME-7")) == "evidence"


# --- the question says which of the two acts it is ------------------------------------------------

def test_a_complete_proposal_gets_a_question_that_states_the_interpretation():
    q = question_for(BOUND, None)
    assert "ACME-7" in q and "Atlas Control Mesh" in q
    assert q.endswith("?")


def test_a_missing_subject_gets_a_question_that_asks_for_it():
    q = question_for(UNBOUND, "subject")
    assert "Atlas Control Mesh" in q, "it must name what it has, to be answerable"
    assert "the name of the project/entity being discussed" not in q, "never echo the placeholder"
    assert q.endswith("?")


def test_the_question_never_invents_the_missing_thing():
    q = question_for(UNBOUND, "subject")
    assert "ACME-7" not in q


# --- and a bare yes cannot answer a fill-in question ----------------------------------------------

def _case(needs=None):
    return {"id": "c1", "session_id": "s1", "state": "awaiting", "question_delivered": True,
            "question": "…?", "needs": needs, "proposals": [BOUND if not needs else UNBOUND]}


def test_a_bare_yes_confirms_a_complete_proposal():
    assert simple_feedback("yes", _case()) == "confirm"


def test_a_bare_yes_does_not_answer_a_request_for_missing_information():
    """The reproduction: "yes" wrote a definition for a placeholder subject."""
    assert simple_feedback("yes", _case(needs="subject")) is None


def test_a_refusal_still_lands_even_when_something_is_missing():
    """"no" needs no missing piece: it declines whatever was proposed."""
    assert simple_feedback("no", _case(needs="subject")) == "reject"
