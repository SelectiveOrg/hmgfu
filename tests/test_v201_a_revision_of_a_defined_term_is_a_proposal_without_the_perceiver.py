"""95.20 (L1 c95h rep3) — a correction of a term the ledger defines is a proposal even when the
perceiver returns none.

The protocol's only source of proposals was the nano's envelope. On rep3's correction turn the envelope
carried no proposal, the protocol passed through ("no pending case: nothing to confirm"), the ledger
stayed at revision 1, the say-do gate rightly corrected "I've updated my records", and the new session
answered the old value. Grounded in the ledger, not in a phrase list: an existing definition entity
named in the message + a definitional predicate + a meaning that differs. Positive: the empty envelope
still commits revision 2 with `prev`. Negative: a restatement proposes nothing; an undefined term
proposes nothing (the perceiver's job); "is" alone is not a definition. Preserve: an envelope that
carries proposals is used as it is.
"""
from __future__ import annotations

from hmgfu.learning_apply import DEFINITION_RELATION, ledger_grounded_proposals
from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
FIX = "Correction: ACME-7 means Adaptive Cache Manager, not Atlas Control Mesh."


class Q:
    def __init__(self, envelope=None):
        self.extraction = {"memory_update": envelope} if envelope is not None else {}


def _env(text, value):
    start = text.index(value)
    return {"feedback": "none", "scope": "memory", "ambiguity": "none", "target_case_id": None,
            "proposals": [{"kind": "domain_definition", "subject_ref": "ACME-7",   # no context_ref: the
                           "relation": DEFINITION_RELATION, "value": value,          # runs' own shape (local)
                           "evidence_refs": [f"turn:1#{start}-{start + len(value)}"]}]}


def _taught(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    out = run_learning_turn(engine, "s1", TEACH, Q(_env(TEACH, "Atlas Control Mesh")), turn_id="1")
    assert out["decision"]["action"] == "commit"
    return engine


def _current(engine):
    st = engine.facts.assertions
    return [(a["value"], a.get("status", "active")) for a in st.history() if a["relation"] == DEFINITION_RELATION]


def test_the_correction_commits_without_a_proposal_from_the_perceiver(tmp_path):
    """THE CONTRACT — fails before: pass_through, revision 1 stands."""
    engine = _taught(tmp_path)
    out = run_learning_turn(engine, "s1", FIX, Q({}), turn_id="2")
    assert out and out["decision"]["action"] == "commit", out and out["decision"]
    assert out["effects"] and out["effects"][0]["effects"][0]["prev"] == "Atlas Control Mesh", out["effects"]
    hist = _current(engine)
    assert ("Adaptive Cache Manager", "active") in hist and ("Atlas Control Mesh", "superseded") in hist, hist


def test_a_restatement_proposes_nothing(tmp_path):
    engine = _taught(tmp_path)
    assert ledger_grounded_proposals(engine.facts.assertions, "Yes, ACME-7 means Atlas Control Mesh.") == []


def test_an_undefined_term_and_a_bare_is_propose_nothing(tmp_path):
    engine = _taught(tmp_path)
    st = engine.facts.assertions
    assert ledger_grounded_proposals(st, "BETA-9 means Lyra Control Plane.") == []
    assert ledger_grounded_proposals(st, "ACME-7 is great, by the way.") == []


def test_an_envelope_with_proposals_is_used_as_it_is(tmp_path):
    engine = _taught(tmp_path)
    out = run_learning_turn(engine, "s1", FIX, Q(_env(FIX, "Adaptive Cache Manager")), turn_id="2")
    assert out["decision"]["action"] == "commit"
    assert len([v for v, s in _current(engine) if s == "active"]) == 1
