"""95.38 (E6, c95w11d rep1) — a PT passive completion claim is a claim.

create_widget failed ("note widget needs props") and the reply said 'O widget "Painel E6" foi criado
com sucesso'; saydo returned no action. `_EXEC` knew the EN auxiliary passive ("has been created") and
the PT first person ("criei") but not the PT auxiliary passive, though the participles were already
claim verbs. Positive: "foi criado" / "foram criadas" / "está criado" are create claims and a failed
create_widget gets the correction. Negative: a PT sentence with the participle but no auxiliary and no
first person is not a claim ("um widget criado por si"); EN claims unchanged; a succeeded create is
not corrected.
"""
from __future__ import annotations

import pathlib

from hmgfu.saydo import CORRECTION, enforce, exec_claims, transactions_of
from tests.test_v2_agent import make_agent

MSG = "Cria um widget com o titulo Painel E6."
FAILED = [{"id": "t1_0", "name": "create_widget", "arguments": {"title": "Painel E6", "type": "note"},
           "result": "{\"error\": \"note widget needs props ['text']\"}", "failed": True, "blocked": False}]


def _engine(tmp_path):
    engine, _ = make_agent(pathlib.Path(tmp_path), [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = True
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = MSG
    return engine


def test_pt_auxiliary_passives_are_claims():
    """THE CONTRACT — fails before: 'foi criado' is no claim."""
    assert exec_claims('O widget "Painel E6" foi criado com sucesso.') == {"create"}
    assert exec_claims("As notas foram criadas e o link foi atualizado.") == {"create", "update"}
    assert exec_claims("O ficheiro está criado.") == {"create"}


def test_a_participle_without_an_auxiliary_and_en_claims_are_unchanged():
    assert exec_claims("Um widget criado por si aparece no painel.") == set()
    assert exec_claims("The widget has been created.") == {"create"} and exec_claims("Criei o widget.") == {"create"}


def test_a_failed_create_widget_claimed_done_in_pt_is_corrected(tmp_path):
    e = _engine(tmp_path)
    tx = transactions_of(FAILED, [], None, 0, episode=True)
    reply, _t, report = enforce(e, 'O widget "Painel E6" foi criado com sucesso. Pode usa-lo para notas.', FAILED, tx, "s1", MSG,
                                lambda i, required=None: ("", []), 1)
    assert report.get("action") == "corrected_claim" and reply.endswith(CORRECTION), (report, reply)


def test_a_succeeded_create_is_not_corrected(tmp_path):
    e = _engine(tmp_path)
    ok = [dict(FAILED[0], result="{\"id\": \"w1\"}", failed=False)]
    tx = transactions_of(ok, [], None, 0, episode=True)
    reply, _t, report = enforce(e, 'O widget "Painel E6" foi criado com sucesso.', ok, tx, "s1", MSG,
                                lambda i, required=None: ("", []), 1)
    assert (report or {}).get("action") != "corrected_claim" and not reply.endswith(CORRECTION)
