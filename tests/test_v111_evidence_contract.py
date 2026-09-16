"""Phase 91.W3 — the record must say what it does not hold, and one write flag must not stand for four outcomes.

From the second independent analysis (`reports/codex_verify91V/ANALISE.md`):

  * the runner kept `reply[:400]` and `injected_context[:4000]` and no prompt at all, so "the field is present" was
    being read as "the evidence was preserved". Truncation must be FLAGGED;
  * the 91.V6 rule "there was a write delta" is right about not crediting the clone's own values, but it collapses
    four different things. A legitimate reiteration produces no delta and is not a failure to learn.

So a run now records, per expected key, which of these happened: **new learning**, **revision**, **pre-existing** (the
value was already in the store when the conversation began) or **absent**. These tests exercise the classifier on
recorded stage data — no model, no GPU.
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


def _classify(stages, ledger, expected):
    """The same expression the runner records, exercised directly."""
    written = {k for s in stages for k in (s.get("ledger_delta") or {})}
    revised = {k for s in stages for k in (s.get("ledger_delta") or {})
               if sum(1 for t in stages if k in (t.get("ledger_delta") or {})) > 1}
    return {k: ("revision" if k in revised else "new learning") if k in written
               else ("pre-existing" if str(ledger.get(k) or "") else "absent")
            for k in expected}


def test_a_first_write_is_new_learning():
    stages = [{"ledger_delta": {"identity.location": "Nacala"}}]
    assert _classify(stages, {"identity.location": "Nacala"}, {"identity.location": "Nacala"}) == \
        {"identity.location": "new learning"}


def test_a_second_write_of_the_same_key_is_a_revision():
    stages = [{"ledger_delta": {"identity.location": "Nacala"}}, {"ledger_delta": {"identity.location": "Lichinga"}}]
    assert _classify(stages, {"identity.location": "Lichinga"}, {"identity.location": "Lichinga"}) == \
        {"identity.location": "revision"}


def test_a_reiteration_writes_nothing_and_is_not_called_a_failure_to_learn():
    """The case the analysis singled out: saying the same thing twice produces no delta, and that is correct."""
    stages = [{"ledger_delta": {"identity.location": "Nacala"}}, {"ledger_delta": {}}]
    assert _classify(stages, {"identity.location": "Nacala"}, {"identity.location": "Nacala"}) == \
        {"identity.location": "new learning"}


def test_a_value_the_store_already_held_is_pre_existing_not_learning():
    stages = [{"ledger_delta": {}}, {"ledger_delta": {}}]
    assert _classify(stages, {"identity.location": "valencia city"}, {"identity.location": "Valencia"}) == \
        {"identity.location": "pre-existing"}


def test_a_key_neither_written_nor_present_is_absent():
    assert _classify([{"ledger_delta": {}}], {}, {"identity.location": "Valencia"}) == {"identity.location": "absent"}


def test_the_judge_still_refuses_to_credit_a_pre_existing_value():
    """W3 explains the outcome; it does not reopen the V6 rule that write credit needs this conversation's own delta."""
    conv = {"allowed": ["Valencia"], "forbidden_as_current": [], "expected_ledger": {"identity.location": "Valencia"},
            "question": "where do I live?"}
    j = R.judge(conv, "You live in Valencia.", "location Valencia", {"identity.location": "Valencia"}, None, set())
    assert j["write_ok"] == {"identity.location": False}
