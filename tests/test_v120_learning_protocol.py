"""Phase 92.E3 — the enumerated transition table of the learning controller.

The plan fixes P as "invariantes/transicoes enumerados cumpridos / total enumerado, alvo 100%", and
every row of its §4.1 table appears here. The controller is pure, so each row is a literal input and
a literal expected decision: no database, no model, no tool, nothing to stub.

The point of a table like this is the rows that REFUSE. A protocol that says yes readily is easy; the
invariants worth testing are that a bare yes cannot approve a plan, that another session's pending
question cannot consume this session's answer, that a candidate stored without a visible question
earns nothing, that praise trains no facts, and that a moved revision loses rather than overwrites.
"""

from __future__ import annotations

import pytest

from hmgfu.learning_protocol import (MAX_ATTEMPTS_PER_CASE, MAX_PROPOSALS_PER_TURN, decide,
                                     next_state, receipt, validate_envelope)

PROP = {"kind": "personal_fact", "relation": "pet.dog.name", "value": "Green",
        "evidence_refs": ["turn:7#12-40"]}
# 92.E3: the controller now refuses evidence the CALLER could not resolve, so a fixture that claims a
# reference has to supply what resolving it found. The assertions below are unchanged.
RESOLVED = {"turn:7#12-40": {"exists": True, "origin": "user", "modality": "assert", "revision": 5}}


def env(feedback="none", scope="memory", proposals=(), ambiguity="none", target=None):
    return {"feedback": feedback, "scope": scope, "proposals": list(proposals),
            "ambiguity": ambiguity, "target_case_id": target}


def snap(**kw):
    base = {"session_id": "s1", "store_revision": 5, "pending_case": None, "plan_pending": False,
            "praise_only": False, "attempts": 0, "proposed_question": "Did you mean X?",
            "evidence": dict(RESOLVED)}
    base.update(kw)
    return base


def pending(**kw):
    base = {"id": "c1", "session_id": "s1", "state": "awaiting", "revision": 5,
            "question_delivered": True, "targets": ["pet.dog.name"], "question": "Did you mean X?",
            "proposals": [{"kind": "fact", "relation": "pet.dog.name", "value": "X"}]}   # 95.29: a yes commits the case's proposals, nothing else
    base.update(kw)
    return base


# --- the envelope is a contract, and absence is never agreement -----------------------------------
# 92.E4: absence changed meaning on purpose. A turn that simply TEACHES carries no feedback, and a
# model omitting the field is behaving correctly, so a MISSING feedback/scope now means "no feedback"
# -- which authorises nothing on its own. A field that is PRESENT but not a declared value is still
# refused: that is a contract violation rather than a silence.
@pytest.mark.parametrize("bad,why", [
    (dict(env(), scope="sideways"), "a scope outside the declared values"),
    (dict(env(), surprise=1), "unknown field"),
    (dict(env(feedback="yes")), "feedback outside the declared values"),
    (dict(env(proposals=[PROP] * (MAX_PROPOSALS_PER_TURN + 1))), "too many proposals"),
    (dict(env(proposals=[{"kind": "personal_fact", "evidence_refs": ["t"], "value": "  "}])), "no value"),
    ("not an object", "not an object"),
])
def test_an_invalid_envelope_is_unavailable_never_a_confirmation(bad, why):
    assert validate_envelope(bad) is not None, why
    assert decide(snap(), bad).action == "protocol_unavailable"


def test_an_unbound_proposal_is_refused_on_its_own_and_the_envelope_stands():
    """95.58: since 93.Q2 the system locates the span; a proposal it could not bind is an evidence
    problem of that proposal (nothing is written), never an unavailable envelope."""
    unbound = env(proposals=[{"kind": "personal_fact", "value": "x"}])
    assert validate_envelope(unbound) is None
    d = decide(snap(), unbound)
    assert d.action == "pass_through" and "no evidence reference" in d["reason"], d


def test_a_valid_envelope_passes_validation():
    assert validate_envelope(env(proposals=[PROP])) is None


def test_a_missing_feedback_means_no_feedback_not_an_unusable_envelope():
    """A teaching turn has nothing to feed back, and omitting the field is correct behaviour."""
    assert validate_envelope({"proposals": [PROP], "ambiguity": "none"}) is None


def test_an_absent_envelope_is_still_unavailable():
    """Absence of the field entirely is protocol_unavailable, never an invented confirmation."""
    assert decide(snap(), None).action == "protocol_unavailable"


# --- the rows of the table ------------------------------------------------------------------------
def test_an_explicit_evidenced_fact_is_stored_without_a_routine_question():
    d = decide(snap(), env(proposals=[PROP]))
    assert d.action == "commit" and d["handled_targets"] == ["pet.dog.name"]


def test_an_inference_is_not_stored_without_confirmation():
    d = decide(snap(), env(proposals=[dict(PROP, operation="infer")]))
    assert d.action == "ask" and d["blocked_proposals"] == ["pet.dog.name"]


@pytest.mark.parametrize("ambiguity", ["target", "relation", "value", "time", "contradictory"])
def test_ambiguity_asks_once_and_writes_nothing(ambiguity):
    d = decide(snap(), env(proposals=[PROP], ambiguity=ambiguity))
    assert d.action == "ask" and d["independent_writes"] == []


def test_a_yes_confirms_only_the_proposition_that_was_asked():
    d = decide(snap(pending_case=pending()), env(feedback="confirm", target="c1"))
    assert d.action == "commit" and d["handled_targets"] == ["pet.dog.name"]


def test_a_yes_to_a_question_never_delivered_confirms_nothing():
    d = decide(snap(pending_case=pending(question_delivered=False)), env(feedback="confirm"))
    assert d.action == "pass_through"


def test_a_yes_from_another_session_does_not_consume_this_answer():
    d = decide(snap(pending_case=pending(session_id="other")), env(feedback="confirm"))
    assert d.action == "pass_through"


def test_a_yes_naming_a_case_this_session_never_saw_is_unavailable():
    d = decide(snap(pending_case=pending()), env(feedback="confirm", target="c-other"))
    assert d.action == "protocol_unavailable"


def test_one_yes_cannot_approve_both_a_plan_and_a_memory_update():
    d = decide(snap(pending_case=pending(), plan_pending=True), env(feedback="confirm", scope="unclear"))
    assert d.action == "ask" and d["owner"] == "ambiguous"


def test_a_bare_yes_with_nothing_pending_leaves_the_plan_to_the_plan():
    d = decide(snap(plan_pending=True), env(feedback="confirm"))
    assert d.action == "pass_through" and d["owner"] == "plan"


def test_a_no_rejects_and_preserves_the_previous_state():
    assert decide(snap(pending_case=pending()), env(feedback="reject")).action == "reject"


def test_a_retraction_touches_only_the_identified_target():
    d = decide(snap(pending_case=pending()), env(feedback="retract"))
    assert d.action == "commit" and d["operation"] == "retract" and d["handled_targets"] == ["pet.dog.name"]


def test_a_correction_with_one_target_corrects_it():
    d = decide(snap(pending_case=pending()), env(feedback="correct", proposals=[PROP]))
    assert d.action == "commit" and d["operation"] == "correct"


def test_a_correction_with_several_targets_asks_instead_of_guessing():
    d = decide(snap(pending_case=pending()), env(feedback="correct", proposals=[PROP, dict(PROP, relation="x")]))
    assert d.action == "ask"


def test_maybe_defers_and_does_not_promote():
    assert decide(snap(pending_case=pending()), env(feedback="uncertain")).action == "defer"


def test_generic_praise_confirms_nothing():
    assert decide(snap(praise_only=True), env(proposals=[PROP])).action == "pass_through"


def test_a_complaint_with_one_effect_revokes_that_rule():
    d = decide(snap(complaint_targets=["output_prefix"]), env(feedback="complain", scope="behavior"))
    assert d.action == "commit" and d["operation"] == "revoke" and d["owner"] == "behavior"


def test_a_complaint_with_several_candidates_asks_rather_than_penalising_everything():
    d = decide(snap(complaint_targets=["output_prefix", "tool_rule:memory_search"]),
               env(feedback="complain", scope="behavior"))
    assert d.action == "ask"


def test_a_moved_revision_loses_instead_of_overwriting():
    d = decide(snap(pending_case=pending(revision=4)), env(feedback="confirm"))
    assert d.action == "invalidate"


def test_a_revoked_case_is_not_resurrected():
    d = decide(snap(pending_case=pending(state="invalidated")), env(feedback="confirm"))
    assert d.action == "invalidate"


def test_after_the_attempt_limit_the_gap_is_explained_not_asked_again():
    d = decide(snap(attempts=MAX_ATTEMPTS_PER_CASE), env(proposals=[PROP], ambiguity="value"))
    assert d.action == "pass_through"


def test_a_second_question_is_not_opened_while_one_is_pending():
    d = decide(snap(pending_case=pending()), env(proposals=[PROP], ambiguity="value"))
    assert d.action == "defer"


# --- lifecycle and receipts -----------------------------------------------------------------------
@pytest.mark.parametrize("start,action,expected", [
    ("proposed", "ask", "awaiting"), ("proposed", "commit", "committed"),
    ("proposed", "reject", "rejected"), ("proposed", "defer", "deferred"),
    ("awaiting", "commit", "committed"), ("awaiting", "reject", "rejected"),
    ("deferred", "ask", "awaiting"), ("awaiting", "invalidate", "invalidated"),
    ("committed", "invalidate", "invalidated"),
])
def test_the_case_lifecycle(start, action, expected):
    assert next_state(start, action) == expected


def test_received_is_not_committed():
    assert receipt("defer")["status"] == "received"
    assert receipt("ask")["status"] == "pending_clarification"
    r = receipt("commit", kind="domain_definition", target="acme7", revision=9, available=False)
    assert r["status"] == "committed" and r["available_for_reading"] is False


def test_an_unavailable_protocol_reports_itself_as_such():
    assert receipt("protocol_unavailable")["status"] == "unavailable"
