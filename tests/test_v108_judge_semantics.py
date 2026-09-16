"""Phase 91.V4 — the judge must enforce a contract of subject, time, abstention and value, not pattern presence.

The independent verification (`reports/codex_verify_phase91/VERIFICACAO.md`) showed four replies that the 91.S0 judge
still marked OK. They are reproduced here as tests of the judge itself, together with the legitimate replies that must
keep passing — because the failure mode of a stricter judge is to reject correct answers, and that would be worse than
the leak it fixes.

    "I don't know for sure. Your sister is called Mirela."  -> an invention wrapped in doubt is not an abstention
    "Your sister works at Zenvira."                         -> a third party's employer is not the user's
    ledger "Zenvira Other" for expected "Zenvira"           -> a different value is not the value
    "You used to work at Zenvira."                          -> history alone does not answer a present-tense question

On the value comparison: the four existing oracles state in their own `_doc` that `expected_ledger` is a PREFIX match,
and two of them depend on it ("Kia" for a stored "Kia Sportage"; a shortened URL). So the fix is not to redefine what
those files already declare — it is to make EXACT the default for everything else, and to require a file to say when
it means prefix.
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
CONV = {"allowed": ["Zenvira"], "forbidden_as_current": [], "expected_ledger": {"identity.company": "Zenvira"},
        "question": "where do I work?"}
ABST = {"abstain": True, "allowed": [], "forbidden_as_current": ["Gurué"], "expected_ledger": {}}


def test_an_invention_wrapped_in_doubt_is_not_an_abstention():
    j = R.judge(ABST, "I don't know for sure. Your sister is called Mirela.", "", {})
    assert not j["answer_ok"] and j["verdict"].startswith("FAIL@reader"), j
    ok = R.judge(ABST, "I don't have that in my records.", "", {})
    assert ok["answer_ok"] and ok["verdict"] == "OK", ok


def test_a_third_partys_answer_does_not_answer_for_the_user():
    j = R.judge(CONV, "Your sister works at Zenvira.", "Your employer is Zenvira.", {"identity.company": "Zenvira"})
    assert not j["answer_ok"], j
    ok = R.judge(CONV, "You work at Zenvira.", "Your employer is Zenvira.", {"identity.company": "Zenvira"})
    assert ok["answer_ok"] and ok["verdict"] == "OK", ok


def test_a_different_stored_value_is_not_the_expected_one():
    j = R.judge(CONV, "You work at Zenvira.", "Your employer is Zenvira.", {"identity.company": "Zenvira Other"})
    assert j["write_ok"] == {"identity.company": False}, j
    assert j["verdict"].startswith("FAIL@write"), j


def test_a_declared_prefix_oracle_still_accepts_a_longer_stored_value():
    """conv_v1 and the learn sets declare prefix matching in their own _doc, and two expectations depend on it."""
    conv = dict(CONV, value_match="prefix")
    j = R.judge(conv, "You work at Zenvira.", "Your employer is Zenvira.", {"identity.company": "Zenvira Logistics"})
    assert j["write_ok"] == {"identity.company": True}, j


def test_history_alone_does_not_answer_a_present_tense_question():
    j = R.judge(CONV, "You used to work at Zenvira.", "Your current employer is Zenvira.", {"identity.company": "Zenvira"})
    assert not j["answer_ok"], j
    ok = R.judge(CONV, "You used to work at Lunavo; now you work at Zenvira.", "Your employer is Zenvira.",
                 {"identity.company": "Zenvira"})
    assert ok["answer_ok"], ok


def test_the_earlier_counterproofs_still_hold():
    """91.S0's five must not be undone by 91.V4's four."""
    assert not R.judge(CONV, "You do not work at Zenvira.", "employer Zenvira", {"identity.company": "Zenvira"})["answer_ok"]
    j = R.judge(CONV, "I don't know.", "", {"identity.company": "Zenvira"})
    assert j["delivered"] == [] and j["verdict"].startswith("FAIL@retrieval"), j
    hist = R.judge({"allowed": ["Zenvira"], "forbidden_as_current": ["Lunavo"], "expected_ledger": {}},
                   "You used to work at Lunavo; now you work at Zenvira.", "employer Zenvira", {})
    assert hist["stated_forbidden"] == [] and hist["answer_ok"], hist


def test_a_value_already_in_the_cloned_memory_is_not_credited_to_the_conversation():
    """91.V6 — the benches clone the live memory, so a pre-existing value satisfied an expectation the conversation
    never taught (l12 passed on a city the clone already held while every stage delta was empty). Write credit now
    requires the key to appear in THIS run's own deltas."""
    conv = dict(CONV, question="where do I live?", expected_ledger={"identity.location": "Valencia"})
    ledger = {"identity.location": "Valencia"}
    assert R.judge(conv, "You live in Valencia.", "location Valencia", ledger, None, set())["write_ok"] == {"identity.location": False}
    assert R.judge(conv, "You live in Valencia.", "location Valencia", ledger, None, {"identity.location"})["write_ok"] == {"identity.location": True}
    assert R.judge(conv, "You live in Valencia.", "location Valencia", ledger)["write_ok"] == {"identity.location": True}
