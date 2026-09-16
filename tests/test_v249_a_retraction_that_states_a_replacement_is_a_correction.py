"""95.62 (L1 on the chains, c95w18 rep2) — a retraction that STATES a replacement is a correction.

"Correction: ACME-7 means Adaptive Cache Manager, not Atlas Control Mesh." — the perceiver labelled the
turn feedback "retract" with a proposal carrying the new value; the protocol trusted the label, bound the
subject, committed a retraction: the old value was cleared and the new one never written, and the next
session answered the old value. Positive: with that envelope the new value supersedes the old.
Preserve: a bare retraction ("forget what ACME-7 means") still retracts.
"""
from __future__ import annotations

from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
CORR = "Correction: ACME-7 means Adaptive Cache Manager, not Atlas Control Mesh."
ENV_TEACH = {"ambiguity": "none", "feedback": "none", "scope": "unclear",
             "proposals": [{"kind": "domain_definition", "value": "Atlas Control Mesh", "subject_ref": "ACME-7",
                            "evidence_refs": ["turn:1#30-48"]}]}
ENV_RETRACT = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
               "proposals": [{"kind": "domain_definition", "value": "Adaptive Cache Manager", "subject_ref": "ACME-7",
                              "evidence_refs": ["turn:2#12-18"]}]}
FORGET = "Forget what ACME-7 means, drop it."
ENV_FORGET = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
              "proposals": [{"kind": "domain_definition", "value": "", "subject_ref": "ACME-7"}]}


class Q:
    def __init__(self, env):
        self.extraction = {"memory_update": env}


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    assert run_learning_turn(engine, "s1", TEACH, Q(ENV_TEACH), turn_id="1")["decision"]["action"] == "commit"
    assert _meanings(engine) == ["Atlas Control Mesh"]
    return engine


def _meanings(engine):
    return [a["value"] for a in engine.facts.assertions.active() if a.get("relation") == "definition.meaning"]


def test_the_stated_replacement_supersedes(tmp_path):
    """THE CONTRACT — fails before: the label 'retract' clears the old value and writes nothing."""
    engine = _engine(tmp_path)
    d = run_learning_turn(engine, "s1", CORR, Q(ENV_RETRACT), turn_id="2")["decision"]
    assert d["action"] == "commit" and d.get("operation") != "retract", d
    assert _meanings(engine) == ["Adaptive Cache Manager"], _meanings(engine)


def test_a_bare_retraction_still_retracts(tmp_path):
    engine = _engine(tmp_path)
    d = run_learning_turn(engine, "s1", FORGET, Q(ENV_FORGET), turn_id="2")["decision"]
    assert d["action"] == "commit" and d.get("operation") == "retract", d
    assert _meanings(engine) == [], _meanings(engine)
