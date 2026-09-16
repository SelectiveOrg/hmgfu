"""93.X — "forget about ACME-7" wrote nothing, four times, while the reply said it had.

From the manual session, against the stores rather than the replies:

    05:05:51  "no, ACME-7 is no longer our primary project, our primary projec is HMG"
              -> project.main = HMG                                    (the only one that wrote)
    05:11:13  "please forget about ACME-7 focus only on HMG"           -> NOTHING
    05:23:22  "i'm no longer working on ACME-7 (Atlas Control Mesh)"   -> NOTHING
    05:44:18  "ACME-7 is no longer my project please forget"           -> NOTHING

Each of those three was answered with *"I will no longer reference ACME-7"*, *"I have noted that"*,
*"I have updated my records"*. The definition assertion stayed `active` throughout and kept being
retrieved, so ACME-7 came back as a current project in the next broad question every time.

The cause is not the wording and not the model. `retract` is in the schema's feedback enum, and
`apply_decision` implements it (`assertions.retract`). But `decide` handles it only INSIDE the
`if pending:` branch, so it can fire only as the answer to a question the system itself asked. A user
who simply says it has no pending case, falls to `pass_through("no pending case: nothing to
confirm")`, and nothing is written. Declared, implemented, unreachable — the same shape as the
`memory_update`, `condition` and `ambiguity` defects before it.

The distinction the table was missing: `confirm` / `reject` / `resume_case` are ANSWERS and are
meaningless without a pending question. `correct` and `retract` are STATEMENTS — a user may make them
out of nowhere, and they carry their own target. A bare "yes" must still approve nothing.

A retraction also names no value, which is why it could never have survived the evidence rules as
they stood: they locate the VALUE in the message. For a retraction the thing that must be found is
the SUBJECT — what to forget — under the same binding discipline as 93.Q1.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_protocol import decide

ASKED = "please forget about ACME-7 focus only on HMG"


def _snapshot(**kw):
    base = {"session_id": "s1", "store_revision": 0, "pending_case": None, "plan_pending": False,
            "attempts": 0, "proposed_question": "?", "praise_only": False, "evidence": {}}
    base.update(kw)
    return base


def _env(feedback, proposals, **kw):
    env = {"feedback": feedback, "scope": "memory", "ambiguity": "none", "proposals": proposals}
    env.update(kw)
    return env


def _bound_evidence(ref="turn:1#19-25"):
    """What `resolve_evidence` produces for a subject the user really did name, here."""
    return {ref: {"exists": True, "origin": "user", "subject": "ACME-7", "context": None,
                  "modality": "assert", "revision": 0}}


RETRACTION = [{"kind": "domain_definition", "subject_ref": "ACME-7",
               "evidence_refs": ["turn:1#19-25"]}]


# --- the defect ------------------------------------------------------------------------------------

def test_a_user_can_retract_without_being_asked_first():
    """The whole finding: no pending case, and it still has to take effect."""
    got = decide(_snapshot(evidence=_bound_evidence()), _env("retract", RETRACTION))
    assert got["action"] == "commit", got["reason"]
    assert got.get("operation") == "retract"


def test_the_retraction_names_what_it_retracts():
    got = decide(_snapshot(evidence=_bound_evidence()), _env("retract", RETRACTION))
    assert "ACME-7" in str(got.get("handled_targets"))


def test_a_retraction_needs_no_value_because_it_removes_rather_than_sets():
    """`validate_envelope` demands a value of every proposal; a retraction has none to give."""
    assert "value" not in RETRACTION[0]
    got = decide(_snapshot(evidence=_bound_evidence()), _env("retract", RETRACTION))
    assert got["action"] == "commit", got["reason"]


# --- the guards that must NOT be loosened by fixing it ----------------------------------------------

@pytest.mark.parametrize("feedback", ["confirm", "reject", "resume_case"])
def test_an_answer_with_nothing_pending_still_approves_nothing(feedback):
    """A bare yes/no is an ANSWER. Without a question it means nothing, and that stays true."""
    got = decide(_snapshot(), _env(feedback, []))
    assert got["action"] == "pass_through"


def test_a_bare_yes_still_cannot_approve_a_waiting_plan():
    got = decide(_snapshot(plan_pending=True), _env("confirm", []))
    assert got["action"] == "pass_through" and got.get("owner") == "plan"


def test_a_retraction_of_something_the_message_never_named_is_refused():
    """93.Q1 is not suspended: an unbound subject authorises nothing, here as anywhere else."""
    unbound = {"turn:1#0-5": {"exists": True, "origin": "user", "subject": None, "context": None,
                              "modality": "assert", "revision": 0}}
    got = decide(_snapshot(evidence=unbound),
                 _env("retract", [{"kind": "domain_definition", "subject_ref": "BETA-2",
                                   "evidence_refs": ["turn:1#0-5"]}]))
    assert got["action"] != "commit"


def test_a_retraction_with_no_evidence_at_all_is_refused():
    got = decide(_snapshot(), _env("retract", [{"kind": "domain_definition",
                                                "subject_ref": "ACME-7"}]))
    assert got["action"] != "commit"


def test_an_open_conflict_still_blocks_the_retraction():
    """A retraction writes, so the conflict rule governs it like every other write."""
    got = decide(_snapshot(evidence=_bound_evidence()),
                 _env("retract", RETRACTION, ambiguity="target"))
    assert got["action"] != "commit"


def test_a_retraction_answering_a_real_question_still_works():
    """The path that already existed must survive: retract inside a pending case."""
    pending = {"id": "c1", "session_id": "s1", "state": "awaiting", "revision": 0,
               "question_delivered": True, "targets": ["ACME-7"]}
    got = decide(_snapshot(pending_case=pending, evidence=_bound_evidence()),
                 _env("retract", []))
    assert got["action"] == "commit" and got.get("operation") == "retract"
