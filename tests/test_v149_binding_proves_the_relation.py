"""93.Q1 (F1) — presence is not provenance: the value must be asserted OF that subject, there.

The independent review ran four controlled proposals through the real controller and three wrong ones
committed. Its table is this file. What `_bound` checked was whether the subject appeared ANYWHERE in
the message, or in the global set of known entities, and whether the context shared any four-letter
word — none of which shows that this value was said of this subject in this context.

The binding therefore travels with the clause that carries the value, using the clause machinery the
write path already uses. A known entity may RESOLVE a referring expression that is present in that
clause; it never authorises attaching a value to an entity the clause does not speak about. That is
the review's distinction between a candidate for resolution and an authorisation.

The positive control matters as much as the negatives: a correct proposal must still commit, and a
legitimate referring expression ("the project", about one already known) must still bind — otherwise
the guard has been bought with a permissiveness cut that nobody measured.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_protocol import attach_evidence, decide, resolve_evidence

ONE = "In Project Alpha, ACME-7 means Atlas Control Mesh."
TWO = "In Project Alpha, ACME-7 means Atlas Control Mesh. BETA-2 means Basic Event Transport."


def _run(text, *, subject, context, value, known=None):
    env = {"feedback": "none", "scope": "memory", "ambiguity": "none",
           "proposals": [{"kind": "domain_definition", "subject_ref": subject,
                          "context_ref": context, "value": value}]}
    env = attach_evidence(env, text, "1")
    resolved = resolve_evidence(env, text, "1", 0, known_subjects=known)
    snapshot = {"session_id": "s1", "store_revision": 0, "pending_case": None, "plan_pending": False,
                "attempts": 0, "proposed_question": "?", "praise_only": False, "evidence": resolved}
    return decide(snapshot, env)["action"]


# --- the positive control -------------------------------------------------------------------------

def test_the_correct_proposal_commits():
    assert _run(ONE, subject="ACME-7", context="Project Alpha", value="Atlas Control Mesh") == "commit"


def test_a_referring_expression_resolved_by_a_known_entity_still_binds():
    """"the project" is in the clause and names something the stores hold: a legitimate reference."""
    text = "In the project, ACME-7 means Atlas Control Mesh."
    assert _run(text, subject="ACME-7", context="the project", value="Atlas Control Mesh",
                known={"the project"}) == "commit"


# --- the three the review caught -------------------------------------------------------------------

def test_the_same_message_filed_under_another_project_is_refused():
    assert _run(ONE, subject="ACME-7", context="Project Omega",
                value="Atlas Control Mesh") != "commit"


def test_the_value_attributed_to_a_different_known_entity_is_refused():
    """Knowing BETA-2 exists makes it a candidate to resolve, never a licence to assign to it."""
    assert _run(ONE, subject="BETA-2", context="Project Alpha", value="Atlas Control Mesh",
                known={"BETA-2"}) != "commit"


def test_swapping_two_definitions_in_the_same_message_is_refused():
    """Both terms and both values are present; only the pairing is wrong, which is the whole point."""
    assert _run(TWO, subject="BETA-2", context="Project Alpha",
                value="Atlas Control Mesh") != "commit"


def test_the_other_pairing_in_that_same_message_still_commits():
    """The discriminating half: the message really does define both, and both must be learnable."""
    assert _run(TWO, subject="BETA-2", context="Project Alpha",
                value="Basic Event Transport") == "commit"


# --- the permissiveness that caused it -------------------------------------------------------------

def test_a_context_sharing_only_a_common_word_is_not_bound():
    assert _run(ONE, subject="ACME-7", context="Project Omega Delivery",
                value="Atlas Control Mesh") != "commit"


def test_a_subject_present_only_elsewhere_in_the_message_is_not_bound():
    text = "BETA-2 came up yesterday. In Project Alpha, ACME-7 means Atlas Control Mesh."
    assert _run(text, subject="BETA-2", context="Project Alpha", value="Atlas Control Mesh") != "commit"
