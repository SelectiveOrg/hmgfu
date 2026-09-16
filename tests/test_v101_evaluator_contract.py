"""Phase 91.S0 — the five counter-proofs the independent audit reproduced against the conversation evaluator, turned
into tests of that evaluator (`reports/codex_execution_audit_20260909/ANALISE_E_PLANO.md`, §3 "P1 de avaliação").

The old verdict was "does the value appear in the text", which cannot tell an affirmation from a denial, a current
claim from a remembered one, an answer from an abstention, or `Amaro` from `AmaroOther`. It also counted a value
sitting in the LEDGER as evidence DELIVERED to the reader, which then blamed the reader for a retrieval failure.

These tests exercise the pure `judge()` — no model, no database, no GPU — so the instrument is checked before any
number produced with it is believed.
"""

from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _runner():
    sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location("run_conversations", os.path.join(ROOT, "scripts", "run_conversations.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


R = _runner()


def test_counterproof_1_an_invented_answer_is_not_an_abstention():
    """`abstained` was computed and then ignored: any reply passed as long as it dodged a short forbidden list."""
    conv = {"abstain": True, "allowed": [], "forbidden_as_current": ["Zambeze"], "expected_ledger": {}}
    j = R.judge(conv, "Your sister is called Mirela.", injected="", ledger={})
    assert not j["answer_ok"] and j["verdict"].startswith("FAIL@reader")
    ok = R.judge(conv, "I don't have that in my records.", injected="", ledger={})
    assert ok["answer_ok"] and ok["verdict"] == "OK"


def test_counterproof_2_a_denial_is_not_an_answer():
    """"You do not work at Zenvira" contains the right value and means the opposite."""
    conv = {"allowed": ["Zenvira"], "forbidden_as_current": [], "expected_ledger": {}}
    ctx = "User identity: employer Zenvira"
    assert not R.judge(conv, "You do not work at Zenvira.", ctx, {})["answer_ok"]
    assert R.judge(conv, "You work at Zenvira.", ctx, {})["answer_ok"]


def test_counterproof_3_a_value_in_the_ledger_is_not_evidence_delivered():
    """The ledger was mixed into the delivered context, so an empty context was still blamed on the reader."""
    conv = {"allowed": ["Zenvira"], "forbidden_as_current": [], "expected_ledger": {"identity.company": "Zenvira"}}
    j = R.judge(conv, "I don't know.", injected="", ledger={"identity.company": "Zenvira"})
    assert j["delivered"] == [] and j["in_ledger"] == ["Zenvira"]
    assert j["verdict"].startswith("FAIL@retrieval"), j["verdict"]


def test_counterproof_4_naming_the_old_value_as_history_is_correct():
    """"You used to work at Lunavo; now you work at Zenvira" was failed for mentioning the superseded value."""
    conv = {"allowed": ["Zenvira"], "forbidden_as_current": ["Lunavo"], "expected_ledger": {}}
    ctx = "employer Zenvira"
    j = R.judge(conv, "You used to work at Lunavo; now you work at Zenvira.", ctx, {})
    assert j["stated_forbidden"] == [] and j["answer_ok"] and j["verdict"] == "OK"
    bad = R.judge(conv, "You work at Lunavo.", ctx, {})
    assert bad["stated_forbidden"] == ["Lunavo"] and not bad["answer_ok"]


def test_counterproof_5_a_longer_name_is_not_the_expected_value():
    """Prefix/substring matching passed `AmaroOther` for `Amaro`, in the reply and in the ledger check."""
    conv = {"allowed": ["Amaro"], "forbidden_as_current": [], "expected_ledger": {"family.brother_name": "Amaro"},
            "question": "what is my brother's name?"}
    j = R.judge(conv, "Your brother is AmaroOther.", "brother AmaroOther", {"family.brother_name": "AmaroOther"})
    assert j["write_ok"] == {"family.brother_name": False}
    assert j["stated_in_reply"] == [] and not j["answer_ok"]
    good = R.judge(conv, "Your brother is Amaro.", "brother Amaro", {"family.brother_name": "Amaro"})
    assert good["write_ok"] == {"family.brother_name": True} and good["verdict"] == "OK"


def test_the_four_outputs_stay_separate():
    """Write, delivery, interpretation and cost are different failures and must not be collapsed."""
    conv = {"allowed": ["Chire"], "forbidden_as_current": [], "expected_ledger": {"identity.company": "Chire"}}
    assert R.judge(conv, "You work at Chire.", "employer Chire", {"identity.company": "Chire"})["verdict"] == "OK"
    assert R.judge(conv, "You work at Chire.", "employer Chire", {})["verdict"].startswith("FAIL@write")
    assert R.judge(conv, "I don't know.", "employer Chire", {"identity.company": "Chire"})["verdict"].startswith("FAIL@reader")
