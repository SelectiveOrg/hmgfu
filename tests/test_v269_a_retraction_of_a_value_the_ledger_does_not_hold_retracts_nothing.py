"""95.62c (T5 on v6, 2/3 — an undue write) — a retraction whose message denies a VALUE the ledger does not hold for the
subject retracts nothing.

"MRD-2 has never once meant Manual Reset Dial, no matter who says so." — the ledger held Modular Rate Divider; the
perceiver returned feedback "retract" with an empty value and the subject MRD-2; 93.X's retraction by subject
dropped the real definition, and the new session then answered with generic guesses. Positive: the denial of a
value that is not the stored one leaves the definition in place and writes nothing. Preserve: a bare retraction
("forget what MRD-2 means") still retracts; a denial of the STORED value follows the path it followed before.
"""
from __future__ import annotations

from hmgfu.learning_apply import denied_definition, held_definition
from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

TEACH = "In this project, MRD-2 means Modular Rate Divider."
ENV_TEACH = {"ambiguity": "none", "feedback": "none", "scope": "unclear",
             "proposals": [{"kind": "domain_definition", "value": "Modular Rate Divider", "subject_ref": "MRD-2",
                            "evidence_refs": ["turn:1#28-48"]}]}
DENY = "MRD-2 has never once meant Manual Reset Dial, no matter who says so."
ENV_DENY = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
            "proposals": [{"kind": "domain_definition", "value": "", "subject_ref": "MRD-2", "evidence_refs": ["turn:2#0-5"]}]}
FORGET = "Forget what MRD-2 means, drop it."
ENV_FORGET = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
              "proposals": [{"kind": "domain_definition", "value": "", "subject_ref": "MRD-2"}]}


class Q:
    def __init__(self, env):
        self.extraction = {"memory_update": env}


def _meanings(engine):
    return [a["value"] for a in engine.facts.assertions.active() if a.get("relation") == "definition.meaning"]


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    assert run_learning_turn(engine, "s1", TEACH, Q(ENV_TEACH), turn_id="1")["decision"]["action"] == "commit"
    assert _meanings(engine) == ["Modular Rate Divider"]
    return engine


def test_the_denial_of_another_value_leaves_the_definition(tmp_path):
    """THE CONTRACT — fails before: the retraction by subject drops Modular Rate Divider."""
    assert denied_definition(DENY) == ("MRD-2", "Manual Reset Dial")
    assert denied_definition("MRD-2 nunca significou Manual Reset Dial.") == ("MRD-2", "Manual Reset Dial")
    engine = _engine(tmp_path)
    assert held_definition(engine.facts.assertions, "MRD-2") == "Modular Rate Divider"
    d = run_learning_turn(engine, "s1", DENY, Q(ENV_DENY), turn_id="2")["decision"]
    assert d.get("operation") != "retract" and _meanings(engine) == ["Modular Rate Divider"], (d, _meanings(engine))


def test_a_bare_retraction_still_retracts_and_the_stored_value_denied_still_does(tmp_path):
    engine = _engine(tmp_path)
    d = run_learning_turn(engine, "s1", FORGET, Q(ENV_FORGET), turn_id="2")["decision"]
    assert d["action"] == "commit" and d.get("operation") == "retract" and _meanings(engine) == [], d
    (tmp_path / "b").mkdir()
    engine2 = _engine(tmp_path / "b")
    env = {**ENV_DENY, "proposals": [{"kind": "domain_definition", "value": "", "subject_ref": "MRD-2", "evidence_refs": ["turn:2#0-5"]}]}
    d2 = run_learning_turn(engine2, "s1", "MRD-2 has never meant Modular Rate Divider, drop that.", Q(env), turn_id="2")["decision"]
    assert d2["action"] == "commit" and d2.get("operation") == "retract", d2
