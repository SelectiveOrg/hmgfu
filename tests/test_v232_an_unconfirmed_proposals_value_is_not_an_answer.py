"""95.48 (T4 on b9bedb4 rep2) — an unconfirmed proposal's value is not an answer.

The protocol asked "Should I record that PXD-4 is Packet Drop Daemon?" and wrote nothing; the ask turn
fired asked_unknown and the reply still opened with "PXD-4 significa Packet Drop Daemon" -- the cited,
doubted, unconfirmed value published as the answer. Positive: a pending proposal's value about the
asked term is an offer, so the clause is re-asked once and, if it persists, dropped; the suffix asks.
Negative: with no pending case the same reply is untouched by this rule; a pending proposal about
another subject is not an offer.
"""
from __future__ import annotations

import pathlib

from hmgfu.learning_apply import DEFINITION_RELATION
from hmgfu.learning_state import LearningState, run_learning_turn
from hmgfu.saydo import UNKNOWN_SUFFIX, enforce, transactions_of
from hmgfu.unknowns import offered_for_unknown
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
CITE = "Segundo o Rui, PXD-4 quer dizer Packet Drop Daemon, mas ele costuma enganar-se nestas siglas."
ASK = "o que quer dizer PXD-4?"
REPLY = "PXD-4 significa **Packet Drop Daemon**. Trato essa informacao com a cautela necessaria!"


class Q:
    def __init__(self, envelope=None):
        self.extraction = {"memory_update": envelope} if envelope is not None else {}


def _engine(tmp_path):
    engine, _ = make_agent(pathlib.Path(tmp_path), [])
    engine.settings.set("grader_enabled", False)
    engine.settings.set("interactive_learning_mode", "confirm")
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    return engine


def _pend(engine):
    start = CITE.index("Packet Drop Daemon")
    env = {"feedback": "none", "scope": "memory", "ambiguity": "value", "target_case_id": None,
           "proposals": [{"kind": "domain_definition", "subject_ref": "PXD-4", "relation": DEFINITION_RELATION,
                          "value": "Packet Drop Daemon", "evidence_refs": [f"turn:1#{start}-{start + 18}"]}]}
    out = run_learning_turn(engine, "s1", CITE, Q(env), turn_id="1")
    assert out["decision"]["action"] == "ask", out["decision"]
    assert LearningState(conn=engine.facts._db).active_question("s1")


def test_a_pending_proposals_value_is_an_offer_and_is_not_published(tmp_path):
    """THE CONTRACT — fails before: the cited value is published beside the question."""
    e = _engine(tmp_path)
    _pend(e)
    e._turn_user_message = ASK
    assert offered_for_unknown(e, REPLY, "PXD-4", "s1") == "Packet Drop Daemon"
    reply, _t, report = enforce(e, REPLY, [], TX, "s1", ASK, lambda i, required=None: (REPLY, []), 2)
    assert "Packet Drop Daemon" not in reply and reply.endswith(UNKNOWN_SUFFIX.format(label="PXD-4")), reply


def test_without_a_pending_case_or_about_another_subject_nothing_is_offered(tmp_path):
    e = _engine(tmp_path)
    e._turn_user_message = ASK
    assert offered_for_unknown(e, REPLY, "PXD-4", "s1") is None
    e2 = _engine(tmp_path / "b") if (tmp_path / "b").mkdir(exist_ok=True) is None else None
    _pend(e2)
    assert offered_for_unknown(e2, "QTR-2 significa Packet Drop Daemon.", "QTR-2", "s1") is None
