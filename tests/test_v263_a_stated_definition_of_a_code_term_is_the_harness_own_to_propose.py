"""95.67 (T4 on v4, d95w20v4 rep3) — a stated definition of a code-like term is the harness's own to propose.

"Segundo o Rui, PXD-4 quer dizer Packet Drop Daemon, mas ele costuma enganar-se nestas siglas." — the perceiver
proposed NOTHING this time (six earlier runs: a proposal with ambiguity "unsupported", so the protocol asked), no
case was pending, and at "o que quer dizer PXD-4?" the model stated the doubted citation while the unknown rule
had no pending value to drop. Positive: with no perceiver proposal the harness proposes the stated definition; a
citation makes it "unsupported" and the protocol asks; the pending value is then an offer the unknown rule drops.
Preserve: a plain assertion with no perceiver proposal is a teaching and commits; a message with no code term
proposes nothing; a term without a definitional predicate proposes nothing.
"""
from __future__ import annotations

from hmgfu.learning_apply import stated_definitions
from hmgfu.learning_state import run_learning_turn
from hmgfu.unknowns import offered_for_unknown, unknown_asked
from tests.test_v2_agent import make_agent

T4 = "Segundo o Rui, PXD-4 quer dizer Packet Drop Daemon, mas ele costuma enganar-se nestas siglas."
EMPTY = {"ambiguity": "unsupported", "feedback": "none", "scope": "unclear"}
TEACH = "In this project, KLM-9 means Kernel Lock Monitor."


class Q:
    def __init__(self, env):
        self.extraction = {"memory_update": env}


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    return engine


def test_the_cited_definition_is_proposed_and_asked_and_its_value_is_an_offer(tmp_path):
    """THE CONTRACT — fails before: stated_definitions does not exist; 'nothing proposed' and no pending case."""
    props = stated_definitions(T4)
    assert [(p["subject_ref"], p["value"]) for p in props] == [("PXD-4", "Packet Drop Daemon")], props
    engine = _engine(tmp_path)
    d = run_learning_turn(engine, "s1", T4, Q(EMPTY), turn_id="1")["decision"]
    assert d["action"] == "ask", d
    assert [a for a in engine.facts.assertions.active() if a.get("relation") == "definition.meaning"] == []
    label = unknown_asked(engine, "o que quer dizer PXD-4?")
    assert label == "PXD-4"
    assert offered_for_unknown(engine, "No contexto do Rui, PXD-4 significa Packet Drop Daemon.", label, "s1") == "Packet Drop Daemon"


def test_a_plain_teaching_commits_and_the_non_definitions_propose_nothing(tmp_path):
    engine = _engine(tmp_path)
    d = run_learning_turn(engine, "s1", TEACH, Q({"ambiguity": "none", "feedback": "none", "scope": "unclear"}), turn_id="1")["decision"]
    assert d["action"] == "commit", d
    assert [a["value"] for a in engine.facts.assertions.active() if a.get("relation") == "definition.meaning"] == ["Kernel Lock Monitor"]
    assert stated_definitions("O meu projeto chama-se Ibis e a minha gata Nina.") == []
    assert stated_definitions("PXD-4 is the one Rui keeps mentioning.") == []
