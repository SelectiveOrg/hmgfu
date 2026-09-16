"""95.70 (T4 on v6, 0/3 — an undue write through 95.67) — "X swears/claims/jura/garante que" and the citation frame
"Segundo X, / According to X," are reported speech for the modality contract.

"O meu colega jura que MRD-2 quer dizer Manual Reset Dial, mas tenho as minhas duvidas." — the perceiver proposed
nothing, 95.67 proposed the stated definition, and the clause's modality read "assert" (the reported class knew
says/said/tells/told/diz/disse/afirma, not "jura"; the frame "Segundo X," was no citation), so the doubted citation
was COMMITTED and the answer repeated it. Positive: the clause is "cite" (EN, PT; the frame too), so the protocol
asks and writes nothing. Preserve: "diz que" still cites; a first-person "eu digo que" and a plain assertion still
assert; "In this project, MRD-2 means ..." still commits.
"""
from __future__ import annotations

from hmgfu.learning_state import run_learning_turn
from hmgfu.utterance import sentence_modalities
from tests.test_v2_agent import make_agent

T4 = "O meu colega jura que MRD-2 quer dizer Manual Reset Dial, mas tenho as minhas duvidas."
EMPTY = {"ambiguity": "none", "feedback": "none", "scope": "unclear"}


class Q:
    def __init__(self, env):
        self.extraction = {"memory_update": env}


def _first(t):
    return sentence_modalities(t)[0]["modality"]


def test_the_governors_and_the_frame_are_citations():
    """THE CONTRACT — fails before: 'jura que' and 'Segundo o Rui,' read as assertions."""
    assert _first(T4) == "cite"
    assert _first("My colleague swears MRD-2 means Manual Reset Dial, but I have my doubts.") == "cite"
    assert _first("Segundo o Rui, PXD-4 quer dizer Packet Drop Daemon, mas ele costuma enganar-se.") == "cite"
    assert _first("According to Rui, PXD-4 means Packet Drop Daemon.") == "cite"
    assert _first("O Rui garante que ACME-7 e Atlas Control Mesh.") == "cite"


def test_the_cited_definition_is_asked_not_written(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    d = run_learning_turn(engine, "s1", T4, Q(EMPTY), turn_id="1")["decision"]
    assert d["action"] == "ask", d
    assert [a for a in engine.facts.assertions.active() if a.get("relation") == "definition.meaning"] == []


def test_the_assertions_still_assert():
    assert _first("O meu colega diz que o projeto dele e o Atlas.") == "cite"
    assert _first("Eu digo que o meu projeto e o Ibis.") == "assert"
    assert _first("In this project, MRD-2 means Modular Rate Divider.") == "assert"
    assert _first("Segundo o plano, amanha entrego o relatorio.") == "cite"
