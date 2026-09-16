"""95.62b (T5 on v4, d95w19v4 rep1; a regression of 95.62 — an undue write) — a value holding its own subject or
a negation is a CLAIM, not a value: 95.62 does not turn such a retraction into a teaching.

"PXD-4 is not Packet Drop Daemon, whatever you may have heard." — the perceiver returned feedback "retract" with
the value "PXD-4 is not Packet Drop Daemon"; 95.62 saw an asserted clause and made it a teaching, and the SENTENCE
superseded the real definition (Packet Delay Detector). Positive: the definition stays and nothing is written.
Preserve: the L1 shape (a real replacement value) still supersedes (95.62).
"""
from __future__ import annotations

from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

TEACH = "In this project, PXD-4 means Packet Delay Detector."
ENV_TEACH = {"ambiguity": "none", "feedback": "none", "scope": "unclear",
             "proposals": [{"kind": "domain_definition", "value": "Packet Delay Detector", "subject_ref": "PXD-4",
                            "evidence_refs": ["turn:1#30-51"]}]}
DENY = "PXD-4 is not Packet Drop Daemon, whatever you may have heard."
ENV_DENY = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
            "proposals": [{"kind": "domain_definition", "value": "PXD-4 is not Packet Drop Daemon", "subject_ref": "PXD-4",
                           "evidence_refs": ["turn:2#0-6"]}]}
CORR = "Correction: PXD-4 means Packet Delay Detector, not Packet Drop Daemon."
ENV_CORR = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
            "proposals": [{"kind": "domain_definition", "value": "Packet Delay Detector", "subject_ref": "PXD-4",
                           "evidence_refs": ["turn:2#12-17"]}]}


class Q:
    def __init__(self, env):
        self.extraction = {"memory_update": env}


def _meanings(engine):
    return [a["value"] for a in engine.facts.assertions.active() if a.get("relation") == "definition.meaning"]


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    assert run_learning_turn(engine, "s1", TEACH, Q(ENV_TEACH), turn_id="1")["decision"]["action"] == "commit"
    assert _meanings(engine) == ["Packet Delay Detector"]
    return engine


def test_a_sentence_valued_retraction_writes_nothing(tmp_path):
    """THE CONTRACT — fails before: the sentence supersedes the definition."""
    engine = _engine(tmp_path)
    d = run_learning_turn(engine, "s1", DENY, Q(ENV_DENY), turn_id="2")["decision"]
    assert _meanings(engine) == ["Packet Delay Detector"], (d, _meanings(engine))
    assert d.get("operation") != "correct" and "PXD-4 is not" not in str(d), d


def test_a_real_replacement_still_supersedes(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    env0 = {**ENV_TEACH, "proposals": [{**ENV_TEACH["proposals"][0], "value": "Packet Drop Daemon", "evidence_refs": ["turn:1#30-48"]}]}
    assert run_learning_turn(engine, "s1", "In this project, PXD-4 means Packet Drop Daemon.", Q(env0), turn_id="1")["decision"]["action"] == "commit"
    d = run_learning_turn(engine, "s1", CORR, Q(ENV_CORR), turn_id="2")["decision"]
    assert d["action"] == "commit" and d.get("operation") != "retract", d
    assert _meanings(engine) == ["Packet Delay Detector"], _meanings(engine)
