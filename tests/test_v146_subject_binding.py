"""93.P2 (F3) — a proposal may not be the proof of itself.

The review's reproduction, repeated here: the message is `In this project, ACME-7 means Atlas Control
Mesh.`, the VALUE is genuinely in it, and the proposal claims `subject_ref=UNMENTIONED-ENTITY` and
`context_ref=UNVERIFIED-CONTEXT`. The whole chain returned **commit / "explicit and evidenced"**,
because `_span_of` reports `subject_present=True` whenever the offsets parse, and `resolve_evidence`
copies the subject and context FROM the proposal into the descriptor that `evidence_problem` then
checks AGAINST that same proposal. The value being locatable proves nothing about the subject.

Binding has to come from somewhere the proposal does not control. Three sources are legitimate and
none of them is a list of phrases:

  * the subject appears in the message the evidence cites — the ordinary case;
  * it matches something the stores already hold (an entity, or a canonical slot), which is what a
    grounded contextual reference looks like: the user says "the project" about a project already
    known;
  * it is the subject of the pending case being confirmed — "yes" inherits the subject of the
    question, and nothing else.

An unbound subject is not a refusal of contextual language; it is a refusal to promote a proposal
nothing supports. The last tests are the ones that keep this honest: a bound-by-store subject must
still pass, and a confirmation must still inherit.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_protocol import attach_evidence, decide, resolve_evidence

MESSAGE = "In this project, ACME-7 means Atlas Control Mesh."


def _envelope(**proposal):
    # 93.Q1: the context must be words the message really contains. "project terminology" was a
    # paraphrase that bound because it shared ONE word, which is how "Project Omega Delivery" bound to
    # a sentence about Project Alpha. The teaching says "this project", so that is the context.
    base = {"kind": "domain_definition", "subject_ref": "ACME-7", "context_ref": "this project",
            "value": "Atlas Control Mesh"}
    base.update(proposal)
    return {"feedback": "none", "scope": "memory", "ambiguity": "none", "proposals": [base]}


def _run(env, text=MESSAGE, known=None, pending=None):
    env = attach_evidence(env, text, "1")
    resolved = resolve_evidence(env, text, "1", 0, known_subjects=known)
    snapshot = {"session_id": "s1", "store_revision": 0, "pending_case": pending,
                "plan_pending": False, "attempts": 0, "proposed_question": "Could you confirm that?",
                "praise_only": False, "evidence": resolved}
    return decide(snapshot, env)


def test_a_subject_named_in_the_message_is_bound():
    assert _run(_envelope())["action"] == "commit"


def test_a_subject_the_message_never_mentions_is_not_bound():
    """The reproduction: an invented subject used to commit on the strength of the value alone."""
    out = _run(_envelope(subject_ref="UNMENTIONED-ENTITY"))
    assert out["action"] != "commit", out


def test_a_context_the_message_never_mentions_is_not_bound():
    out = _run(_envelope(context_ref="UNVERIFIED-CONTEXT"))
    assert out["action"] != "commit", out


def test_a_subject_the_stores_know_but_the_clause_never_names_is_still_not_bound():
    """93.Q1 replaces what this test used to assert, and the change is the point.

    Being in the stores made a subject bindable, so a value could be attached to an entity the
    sentence never spoke about — the review pinned "Atlas Control Mesh" on BETA-2 that way. A known
    entity is a candidate for RESOLUTION, never an authorisation, so the clause has to name it."""
    out = _run(_envelope(subject_ref="BETA-2"), known={"BETA-2"})
    assert out["action"] != "commit", out


def test_a_referring_expression_the_clause_does_name_is_bound():
    """And the legitimate half survives: what the clause says, binds."""
    text = "In the project, the tool is called Atlas Control Mesh."
    out = _run(_envelope(subject_ref="the tool", context_ref="the project"), text=text)
    assert out["action"] == "commit", out


def test_a_confirmation_inherits_the_subject_of_its_question():
    """"yes" carries no subject of its own; it inherits the one it was asked about, and no other."""
    pending = {"id": "c1", "session_id": "s1", "revision": 0, "state": "awaiting",
               "question_delivered": True,
               "question": "Is ACME-7 Atlas Control Mesh?",
               "proposals": [{"kind": "domain_definition", "subject_ref": "ACME-7",
                              "context_ref": "project terminology", "value": "Atlas Control Mesh"}]}
    env = {"feedback": "confirm", "scope": "memory", "ambiguity": "none", "target_case_id": "c1",
           "proposals": []}
    assert _run(env, text="yes", pending=pending)["action"] == "commit"


def test_the_value_still_has_to_be_in_the_message():
    """Binding the subject does not relax the value: both properties are checked, not traded."""
    out = _run(_envelope(value="Something Never Said"))
    assert out["action"] != "commit"


def test_an_unbound_subject_asks_rather_than_inventing():
    """The turn is not thrown away: what is missing is exactly what a question should name."""
    out = _run(_envelope(subject_ref="UNMENTIONED-ENTITY"))
    assert out["action"] in ("ask", "pass_through")
