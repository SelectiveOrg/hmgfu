"""93.Q2 (F2) — an elliptical answer, and the control that tells it from a complete new statement.

The independent review of 93.P names the attribution problem exactly. The probe's "named answer" was

    Nimbus is the name of my current project.

— a complete statement that teaches perfectly well with no question before it. So the 3/3 shows, at
most, learning after that statement; it never isolates *use of the pending case*. What would isolate
it is a legitimate elliptical answer, `my current project`, whose meaning depends on the value
`Nimbus` preserved on the pending case.

Reproduced before anything was changed: that answer reached `protocol_unavailable — a proposal
carries no evidence reference`. `attach_evidence` looks for the value in THIS message, and the value
is in the previous one. The pendency could ask a question it could never accept an answer to.

So a delivered pending case becomes a second place evidence may live, and the two halves travel
together with their provenance intact: the VALUE keeps a reference into the turn that stated it, the
SUBJECT must still be bound in the message that supplies it under 93.Q1's rule. Every guard that made
the pending case trustworthy is the guard on this: the case is this session's, its question was
really delivered, and the value must really be in what the user said.

The negatives are the point. Without the pendency the same elliptical answer must NOT teach — that is
the control the review asked for, and it is what separates "answered the question" from "made a
complete statement".
"""
from __future__ import annotations

import pytest

from hmgfu.learning_protocol import answering_case, attach_evidence, decide, resolve_evidence

ASKED = "It is called Nimbus."                 # the turn that stated the value, and bound nothing
ELLIPTICAL = "my current project"              # meaningless without the value the case preserved
COMPLETE = "Nimbus is the name of my current project."


def _pending(**kw):
    case = {"id": "c1", "session_id": "s1", "state": "awaiting", "revision": 0,
            "question_delivered": True, "question_turn_id": "1", "origin_turn_id": "1",
            "needs": "subject", "expression": ASKED,
            "proposals": [{"kind": "domain_definition", "value": "Nimbus"}]}
    case.update(kw)
    return case


def _run(text, proposal, *, pending=None, session="s1", turn="2"):
    env = {"feedback": "none", "scope": "memory", "ambiguity": "none", "proposals": [dict(proposal)]}
    # exactly what the controller does: the case is filtered by session BEFORE it may evidence
    # anything, so another session's pendency never answers this one.
    answering = answering_case(pending, session)
    env = attach_evidence(env, text, turn, pending=answering)
    resolved = resolve_evidence(env, text, turn, 0, pending=answering)
    snapshot = {"session_id": session, "store_revision": 0, "pending_case": pending,
                "plan_pending": False, "attempts": 1 if pending else 0, "proposed_question": "?",
                "needs": (pending or {}).get("needs"), "praise_only": False, "evidence": resolved}
    return decide(snapshot, env), env


ELLIPSIS = {"kind": "domain_definition", "subject_ref": ELLIPTICAL, "value": "Nimbus"}


# --- the answer that needs the pendency ------------------------------------------------------------

def test_the_elliptical_answer_fills_the_blank_the_question_left():
    decision, _ = _run(ELLIPTICAL, ELLIPSIS, pending=_pending())
    assert decision["action"] == "commit", decision["reason"]


def test_the_value_keeps_a_reference_to_the_turn_that_stated_it():
    """Provenance: the subject comes from this message, the value from the turn that said it."""
    _, env = _run(ELLIPTICAL, ELLIPSIS, pending=_pending())
    refs = env["proposals"][0].get("evidence_refs") or []
    assert refs and all(ref.startswith("turn:1#") for ref in refs), refs


# --- the control: without the pendency, the same words teach nothing --------------------------------

def test_the_same_elliptical_answer_with_no_pending_case_does_not_teach():
    decision, _ = _run(ELLIPTICAL, ELLIPSIS, pending=None)
    assert decision["action"] != "commit"


def test_a_question_that_was_never_delivered_authorises_nothing():
    decision, _ = _run(ELLIPTICAL, ELLIPSIS,
                       pending=_pending(question_delivered=False, question_turn_id=None))
    assert decision["action"] != "commit"


def test_another_sessions_pending_case_does_not_answer_this_one():
    decision, _ = _run(ELLIPTICAL, ELLIPSIS, pending=_pending(session_id="other"))
    assert decision["action"] != "commit"


# --- the complete statement stays what it was ------------------------------------------------------

def test_a_complete_new_statement_still_teaches_without_any_pending_case():
    decision, _ = _run(COMPLETE, {"kind": "domain_definition", "subject_ref": "Nimbus",
                                  "value": "the name of my current project"})
    assert decision["action"] == "commit", decision["reason"]


# --- what the pendency is NOT a licence for ---------------------------------------------------------

def test_a_value_the_pending_case_never_carried_is_not_evidenced_by_it():
    """The case preserves what the user said, not whatever the model would like to write now."""
    decision, _ = _run(ELLIPTICAL, {"kind": "domain_definition", "subject_ref": ELLIPTICAL,
                                    "value": "Stratus"}, pending=_pending())
    assert decision["action"] != "commit"


def test_the_subject_must_still_be_bound_in_the_message_that_supplies_it():
    """93.Q1 is not suspended by a pending case: an unspoken entity earns nothing."""
    decision, _ = _run(ELLIPTICAL, {"kind": "domain_definition", "subject_ref": "BETA-2",
                                    "value": "Nimbus"}, pending=_pending())
    assert decision["action"] != "commit"


@pytest.mark.parametrize("said", ["I deny that it is called Nimbus.",
                                  "If it is called Nimbus, tell me."])
def test_the_modality_of_the_preserved_words_is_read_again_not_assumed(said):
    """A value the user denied or supposed stays denied or supposed, however the answer is phrased.

    The modality comes from the clause in the CASE's own utterance, by the same contract that governs
    the current message — the pendency preserves what was said, not permission to call it a fact."""
    decision, _ = _run(ELLIPTICAL, ELLIPSIS, pending=_pending(expression=said))
    assert decision["action"] != "commit"


@pytest.mark.parametrize("text", ["forget it", "what were we talking about?"])
def test_a_reply_that_supplies_nothing_does_not_become_a_subject(text):
    """The filler is the subject the MODEL proposed and the message bound, not the message itself."""
    decision, _ = _run(text, {"kind": "domain_definition", "subject_ref": ELLIPTICAL,
                              "value": "Nimbus"}, pending=_pending())
    assert decision["action"] != "commit"
