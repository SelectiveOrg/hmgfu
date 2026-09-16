"""95.29 (N6, 0/3 both arms) — a confirmation invents nothing: a denied value is not a value, and a
"yes" cannot supply one.

"My main project is not called Marlin anymore." → the perceiver proposed the denied value (or the
negation itself), the resolver read its clause as asserted, the protocol asked and kept the proposal,
and "yes" committed it. Positive: the denial is asked about with nothing written; "yes" writes nothing
and asks again; a real value then commits. Negative: a plain assertion still commits without a
question. Preserve: a denial the resolver already refused for another reason still passes through.
"""
from __future__ import annotations

from hmgfu.learning_apply import DEFINITION_RELATION
from hmgfu.learning_evidence import _modality_of
from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

DENY = "My main project is not called Marlin anymore."


class Q:
    def __init__(self, envelope=None):
        self.extraction = {"memory_update": envelope} if envelope is not None else {}


def _env(text, value, subject="main project", feedback="none"):
    start = text.index(value) if value in text else 0
    return {"feedback": feedback, "scope": "memory", "ambiguity": "none", "target_case_id": None,
            "proposals": [{"kind": "domain_definition", "subject_ref": subject, "relation": DEFINITION_RELATION,
                           "value": value, "evidence_refs": [f"turn:1#{start}-{start + len(value)}"]}]}


def _defs(engine):
    """Every value the ledger holds for the project, by either writer: the canonical slot a 'main project'
    subject takes (95.2) and the definition relation a bare term takes."""
    canon = [(f["value"], "active") for f in engine.facts.active() if f["key"] == "project.main"]
    return canon + [(a["value"], a.get("status", "active")) for a in engine.facts.assertions.history()
                    if a["relation"] == DEFINITION_RELATION]


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    return engine


def test_a_denied_value_is_negated_not_asserted():
    """THE CONTRACT (resolver) — fails before: the holding clause reads as assert."""
    assert _modality_of("Marlin", DENY) == "negated"
    assert _modality_of("not called Marlin anymore", DENY) == "negated"
    assert _modality_of("Orca", "My main project is called Orca now.") == "assert"


def test_the_denial_is_asked_about_and_yes_writes_nothing(tmp_path):
    """THE CONTRACT (protocol) — fails before: 'yes' commits the denied value."""
    engine = _engine(tmp_path)
    out = run_learning_turn(engine, "s1", DENY, Q(_env(DENY, "Marlin", subject="Marlin")), turn_id="1")   # the live case's shape
    assert out["decision"]["action"] == "ask" and "What is it now?" in (out["decision"].get("question") or ""), out["decision"]
    assert _defs(engine) == []
    yes = run_learning_turn(engine, "s1", "yes", Q({}), turn_id="2")
    assert yes["decision"]["action"] != "commit", yes["decision"]
    assert _defs(engine) == [], _defs(engine)
    now = "My main project is called Orca now."      # 93.Q1: the subject is bound in the message that supplies the value
    real = run_learning_turn(engine, "s1", now, Q(_env(now, "Orca")), turn_id="3")
    assert real["decision"]["action"] == "commit" and ("Orca", "active") in _defs(engine), (real["decision"], _defs(engine))


def test_a_plain_assertion_still_commits_without_a_question(tmp_path):
    engine = _engine(tmp_path)
    text = "My main project is called Orca."
    out = run_learning_turn(engine, "s1", text, Q(_env(text, "Orca")), turn_id="1")
    assert out["decision"]["action"] == "commit" and ("Orca", "active") in _defs(engine)


def test_a_denial_the_perceiver_calls_ambiguous_is_still_a_denial(tmp_path):
    """95.29b — fails before: the ambiguity ask runs first, builds 'Should I record that Marlin is Marlin?'
    from the proposal, keeps it committable, and 'yes' writes it (d95w9 rep1)."""
    engine = _engine(tmp_path)
    envelope = dict(_env(DENY, "Marlin", subject="Marlin"), ambiguity="value")
    out = run_learning_turn(engine, "s1", DENY, Q(envelope), turn_id="1")
    assert out["decision"]["action"] == "ask" and "What is it now?" in (out["decision"].get("question") or ""), out["decision"]
    assert _defs(engine) == []
    yes = run_learning_turn(engine, "s1", "yes", Q({}), turn_id="2")
    assert yes["decision"]["action"] != "commit" and _defs(engine) == [], (yes["decision"], _defs(engine))


def test_a_denial_is_a_denial_whatever_the_feedback_label(tmp_path):
    """95.29c — fails before: a retraction/correction label walks past the negation check into the
    ambiguity ask (d95w10 reps 2-3 delivered "Should I record that Marlin is Marlin?" again)."""
    for feedback in ("retract", "correct"):
        (tmp_path / feedback).mkdir()
        engine = _engine(tmp_path / feedback)
        envelope = dict(_env(DENY, "Marlin", subject="Marlin", feedback=feedback), ambiguity="value")
        out = run_learning_turn(engine, "s1", DENY, Q(envelope), turn_id="1")
        assert out["decision"]["action"] == "ask" and "What is it now?" in (out["decision"].get("question") or ""), (feedback, out["decision"])
        assert _defs(engine) == []
        yes = run_learning_turn(engine, "s1", "yes", Q({}), turn_id="2")
        assert yes["decision"]["action"] != "commit" and _defs(engine) == [], (feedback, yes["decision"], _defs(engine))
