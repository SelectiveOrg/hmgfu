"""X7c (X7 on b9bedb4 rep2) — a request deferred to the user's confirmation proposes ITSELF when the
turn produced no proposal.

The reply said "Ficarei a aguardar pelo teu sinal. Assim que confirmares, criarei o ficheiro" (a future
tense the intent class does not know) with no tool offered, so nothing was proposed and "Afinal nao,
deixa estar" had nothing to abandon. Positive: the deferred request ends the turn with a proposed plan
naming the request and a question. Negative: a plain order proposes nothing here; a deferred request
whose turn already proposed a plan is not proposed twice.
"""
from __future__ import annotations

import pathlib

from hmgfu.saydo import enforce, transactions_of
from hmgfu.session_plans import begin_turn
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
V4 = "Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN, mas so depois de eu confirmar."


def _engine(tmp_path, msg):
    engine, _ = make_agent(pathlib.Path(tmp_path), [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = msg
    return engine


def test_the_deferred_request_proposes_itself_and_a_decline_abandons_it(tmp_path):
    """THE CONTRACT — fails before: no plan exists after the waiting reply."""
    e = _engine(tmp_path, V4)
    reply, _t, report = enforce(e, "Com certeza! Ficarei a aguardar pelo teu sinal.", [], TX, "s1", V4, lambda i, required=None: ("", []), 1)
    assert report.get("action") == "proposed_deferred" and "?" in reply[-160:], (report, reply)
    plan = e.session_plans.pending("s1")
    assert plan and plan.get("status") == "proposed" and "resumo.md" in (plan.get("title") or "")
    begin_turn(e, "s1", "Afinal nao, deixa estar.")
    assert e.session_plans.get("s1")["status"] == "abandoned"


def test_a_plain_order_and_an_already_proposed_turn_are_unchanged(tmp_path):
    e = _engine(tmp_path, "Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN.")
    _r, _t, report = enforce(e, "Feito? Nao, ainda nao.", [], TX, "s1", "Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN.", lambda i, required=None: ("", []), 1)
    assert (report or {}).get("action") != "proposed_deferred" and e.session_plans.pending("s1") is None
    (tmp_path / "b").mkdir(exist_ok=True)
    e2 = _engine(tmp_path / "b", V4)
    from hmgfu.session_plans import propose
    propose(e2, "s1", "already", ["already"])
    _r, _t, report = enforce(e2, "Aguardo.", [], TX, "s1", V4, lambda i, required=None: ("", []), 1)
    assert (report or {}).get("action") != "proposed_deferred" and e2.session_plans.pending("s1")["title"] == "already"
