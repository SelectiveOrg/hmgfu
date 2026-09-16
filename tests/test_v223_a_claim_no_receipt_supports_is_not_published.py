"""95.41 (E6, c95w11e rep1) — a claim no receipt supports is not published; the correction stands alone.

With 95.38 the PT passive claim was detected and saydo appended the CORRECTION, yet the published reply
still read 'Sim, o widget "Painel E6" foi criado ... Ele está disponível no seu canvas' above it — a
self-contradiction the judge rightly reads as a claim. Positive: the claiming sentences leave the reply
and the CORRECTION follows what remains. Negative: a supported claim is kept whole; a sentence with no
claim verb is kept; a reply that is nothing but the claim becomes the correction alone.
"""
from __future__ import annotations

import pathlib

from hmgfu.saydo import CORRECTION, enforce, transactions_of, without_unsupported_claims
from tests.test_v2_agent import make_agent

MSG = "o widget ficou criado?"
FAILED = [{"id": "t1_0", "name": "create_widget", "arguments": {"title": "Painel E6", "type": "note"},
           "result": "{\"error\": \"note widget needs props ['text']\"}", "failed": True, "blocked": False}]
CLAIM = 'Sim, o widget "Painel E6" foi criado como um widget do tipo nota. Se quiser que eu adicione conteudo, e so dizer!'


def _engine(tmp_path):
    engine, _ = make_agent(pathlib.Path(tmp_path), [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = True
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = MSG
    return engine


def test_the_unsupported_claim_leaves_and_the_correction_stands(tmp_path):
    """THE CONTRACT — fails before: the claim is published above the correction."""
    e = _engine(tmp_path)
    tx = transactions_of(FAILED, [], None, 0, episode=True)
    reply, _t, report = enforce(e, CLAIM, FAILED, tx, "s1", MSG, lambda i, required=None: ("", []), 1)
    assert report.get("action") == "corrected_claim"
    assert "foi criado" not in reply and "Sim," not in reply and "adicione conteudo" in reply, reply
    assert reply.endswith(CORRECTION)


def test_the_helper_keeps_what_claims_nothing_and_drops_only_the_named_classes():
    assert without_unsupported_claims(CLAIM, ["create"]) == "Se quiser que eu adicione conteudo, e so dizer!"
    assert without_unsupported_claims(CLAIM, ["remove"]) == CLAIM
    assert without_unsupported_claims("The widget has been created.", ["create"]) == ""


def test_a_supported_claim_is_kept_whole(tmp_path):
    e = _engine(tmp_path)
    ok = [dict(FAILED[0], result="{\"id\": \"w1\"}", failed=False)]
    tx = transactions_of(ok, [], None, 0, episode=True)
    reply, _t, report = enforce(e, CLAIM, ok, tx, "s1", MSG, lambda i, required=None: ("", []), 1)
    assert reply.startswith(CLAIM) and (report or {}).get("action") != "corrected_claim"
