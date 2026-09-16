"""95.58 (N6 on v4, d95w16v4 rep1) — an unbound proposal is refused on its own; the bound denial beside it
is decided, so the turn asks and nothing is cleared.

"Kestrel is no longer the name of my main project." — the perceiver proposed a retraction with the subject
"main project name" (nowhere in the message) and no reference; the system could not bind it, the WHOLE
envelope was refused as unavailable, the ledger-grounded denial merged beside it (bound, negated) was
thrown away with it, nothing held project.main and the fact store cleared it (undue write; the turn must
ask). Positive: the protocol asks and project.main stays. Preserve: a retraction the message does not name
and the ledger does not see writes nothing and asks nothing (S3 on v3: a prohibition read as a
retraction); an envelope whose shape is wrong is still unavailable.
"""
from __future__ import annotations

from hmgfu.learning_evidence import validate_envelope
from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

N6 = "Kestrel is no longer the name of my main project."
ENV_N6 = {"ambiguity": "none", "feedback": "retract",
          "proposals": [{"kind": "domain_definition", "value": N6, "subject_ref": "main project name"}]}
S3 = "Do not store anything from this session. What is my cat called?"
ENV_S3 = {"ambiguity": "none", "feedback": "retract", "scope": "unclear",
          "proposals": [{"kind": "behavior_policy", "value": "Do not store anything from this session.",
                         "subject_ref": "session data retention"}]}


class Q:
    def __init__(self, envelope):
        self.extraction = {"memory_update": envelope}


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    return engine


def test_the_denial_beside_an_unbound_proposal_is_decided_and_the_turn_asks(tmp_path):
    """THE CONTRACT — fails before: protocol_unavailable, and the store then clears project.main."""
    engine = _engine(tmp_path)
    engine.facts.apply_all("My main project is called Kestrel.", "user_explicit", session="s0")
    out = run_learning_turn(engine, "s1", N6, Q(ENV_N6), turn_id="1")
    d = out["decision"]
    assert d["action"] == "ask" and d.get("blocked_all"), d
    assert [f["value"] for f in engine.facts.active() if f["key"] == "project.main"] == ["Kestrel"]
    held = [r for r in (d.get("blocked_proposals") or []) if r]
    assert "project.main" in held, held
    assert engine.facts.apply_all(N6, "user_explicit", session="s1", hold_keys=held) == []
    assert [f["value"] for f in engine.facts.active() if f["key"] == "project.main"] == ["Kestrel"]


def test_an_unnamed_retraction_writes_nothing_and_asks_nothing(tmp_path):
    engine = _engine(tmp_path)
    engine.facts.apply_all("My cat is called Mira.", "user_explicit", session="s0")
    out = run_learning_turn(engine, "s1", S3, Q(ENV_S3), turn_id="1")
    d = out["decision"]
    assert d["action"] == "pass_through" and not d.get("question"), d
    assert [f["value"] for f in engine.facts.active() if f["key"] == "pet.cat.name"] == ["Mira"]


def test_a_malformed_envelope_is_still_unavailable():
    assert validate_envelope({"feedback": "yes", "proposals": []}) is not None
    assert validate_envelope({"feedback": "none", "proposals": [{"kind": "personal_fact", "value": " "}]}) is not None
    assert validate_envelope({"feedback": "retract", "proposals": [{"kind": "personal_fact", "value": "x"}]}) is not None
