"""Phase 92.E3 — an evidence reference must resolve, and a conflict must block the commit.

Two gaps the self-recall review reproduced against the controller as first written
(`reports/codex_self_recall_92/probe.py`):

  * a proposal citing `evidence_refs=['assistant-reflection:invented-id']` was committed. Nothing
    checked that the reference EXISTS, what its ORIGIN is, or whether it even mentions the subject.
    A model that can name a reference could authorise its own writes.
  * a delivered, current pending case with `feedback=confirm` AND `ambiguity=contradictory` was
    committed, because the confirmation branch ran before the ambiguity guard. A classification of
    the feedback must not cancel an unresolved conflict signal.

The controller is PURE, so it cannot look a reference up: the caller resolves references and passes
what it found. That is the point — the controller refuses whatever the caller did not resolve, so an
unresolvable or invented id can never reach a store.

Every negative here is paired with the legitimate positive it must be distinguished from, so the
guard cannot pass by refusing everything.
"""

from __future__ import annotations

import pytest

from hmgfu.learning_protocol import decide, evidence_problem

USER_REF = "turn:7#12-40"
REFLECT_REF = "assistant-reflection:abc"

# what the caller resolved: origin, subject, context, modality, revision
RESOLVED = {
    USER_REF: {"exists": True, "origin": "user", "subject": "acme7", "context": "proj-1",
               "modality": "assert", "revision": 5},
    REFLECT_REF: {"exists": True, "origin": "assistant", "subject": "acme7", "context": "proj-1",
                  "modality": "assert", "revision": 5},
}


def prop(refs=(USER_REF,), **kw):
    base = {"kind": "domain_definition", "relation": "definition.meaning", "value": "Atlas Control Mesh",
            "subject_ref": "acme7", "context_ref": "proj-1", "evidence_refs": list(refs)}
    base.update(kw)
    return base


def env(proposals, feedback="none", ambiguity="none", scope="memory", target=None):
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
            "question_delivered": True, "targets": ["definition.meaning"], "question": "Did you mean X?",
            "proposals": [{"kind": "domain_definition", "relation": "definition.meaning", "value": "X"}]}   # 95.29: a yes commits the case's proposals, nothing else
    base.update(kw)
    return base


# --- the reference has to resolve, and to the right thing -----------------------------------------
@pytest.mark.parametrize("refs,resolved,why", [
    (["assistant-reflection:invented-id"], RESOLVED, "the reference does not resolve at all"),
    ([REFLECT_REF], RESOLVED, "an assistant reflection does not authorise a user fact"),
    ([USER_REF], {USER_REF: dict(RESOLVED[USER_REF], exists=False)}, "the reference does not exist"),
    ([USER_REF], {USER_REF: dict(RESOLVED[USER_REF], subject="other")}, "it is about another subject"),
    ([USER_REF], {USER_REF: dict(RESOLVED[USER_REF], context="proj-2")}, "it belongs to another context"),
    ([USER_REF], {USER_REF: dict(RESOLVED[USER_REF], modality="hypothesis")}, "it is not asserted"),
    ([USER_REF], {USER_REF: dict(RESOLVED[USER_REF], revision=4)}, "its revision has moved"),
    ([], RESOLVED, "no reference at all"),
])
def test_a_proposal_without_resolvable_supporting_evidence_is_not_committed(refs, resolved, why):
    d = decide(snap(evidence=resolved, store_revision=5), env([prop(refs)]))
    assert d.action != "commit", f"{why}: {d}"


def test_a_proposal_with_resolvable_user_evidence_is_committed():
    """The protection must not be vacuous."""
    assert decide(snap(), env([prop()])).action == "commit"


def test_a_reflection_alongside_user_evidence_is_still_acceptable():
    """A reflection may accompany the user's own words; it just cannot stand alone."""
    assert decide(snap(), env([prop([USER_REF, REFLECT_REF])])).action == "commit"


@pytest.mark.parametrize("resolved,ok", [
    ({USER_REF: dict(RESOLVED[USER_REF], origin="tool", source="memory_search")}, True),
    ({USER_REF: dict(RESOLVED[USER_REF], origin="tool")}, False),
])
def test_a_tool_observation_counts_only_when_it_names_its_source(resolved, ok):
    d = decide(snap(evidence=resolved), env([prop()]))
    assert (d.action == "commit") is ok


def test_evidence_problem_names_the_reason():
    assert evidence_problem(prop(["nope"]), RESOLVED) is not None
    assert evidence_problem(prop(), RESOLVED) is None


# --- an unresolved conflict blocks the commit, whatever the feedback says -------------------------
@pytest.mark.parametrize("ambiguity", ["contradictory", "target", "value", "unsupported"])
def test_a_confirmation_cannot_override_an_unresolved_conflict(ambiguity):
    d = decide(snap(pending_case=pending()), env([], feedback="confirm", ambiguity=ambiguity))
    assert d.action != "commit", f"ambiguity={ambiguity} was overridden by the confirmation"


def test_a_clean_confirmation_still_commits():
    d = decide(snap(pending_case=pending()), env([], feedback="confirm", ambiguity="none"))
    assert d.action == "commit"


def test_a_rejection_is_still_allowed_while_ambiguous():
    """Blocking the WRITE is the point; refusing to record a refusal would lose the user's no."""
    d = decide(snap(pending_case=pending()), env([], feedback="reject", ambiguity="contradictory"))
    assert d.action == "reject"


def test_an_ambiguous_correction_asks_rather_than_writing():
    d = decide(snap(pending_case=pending()), env([prop()], feedback="correct", ambiguity="value"))
    assert d.action == "ask"
