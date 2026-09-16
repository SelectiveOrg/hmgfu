"""Phase 91.W1 — the judge is measured against a balanced labelled set, and must admit when it cannot decide.

The second independent analysis (`reports/codex_verify91V/ANALISE.md`) showed the 91.V4 judge reads FORMS rather than
meaning, with a transfer case in each direction:

    "I don't know for sure. Her name: Mirela."                            -> passed, while inventing a name
    "I don't know her name. Your sister is a person you have not named."  -> failed, while abstaining correctly

and it said explicitly that the fix must not be to add those phrasings to a regex. So this test does not check those
two strings: it measures the judge's ERROR RATE over `scripts/oracles/judge_labelled_v1.json` — right and wrong replies
across subject, time, abstention and paraphrase — and requires a third outcome, `inconclusive`, for replies a careful
reader cannot score either way.

The bar is stated before the change and applies to the whole set, not to the two cases that prompted it.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _runner():
    sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location("run_conversations", os.path.join(ROOT, "scripts", "run_conversations.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


R = _runner()
CASES = json.load(io.open(os.path.join(ROOT, "scripts", "oracles", "judge_labelled_v1.json"), encoding="utf-8"))["cases"]


def _outcome(case):
    """The judge's verdict on the reply alone, reduced to ok / fail / inconclusive."""
    conv = {"allowed": case.get("allowed", []), "forbidden_as_current": case.get("forbidden", []),
            "expected_ledger": {}, "question": case["question"], "abstain": case.get("abstain", False)}
    ctx = " ".join(case.get("allowed", [])) or "context"
    j = R.judge(conv, case["reply"], ctx, {})
    if j.get("inconclusive"):
        return "inconclusive"
    return "ok" if j["answer_ok"] else "fail"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_the_judge_agrees_with_the_label(case):
    assert _outcome(case) == case["label"], f"{case['id']} ({case['contract']}): {case['reply']!r}"


def test_the_judge_error_rate_is_reported_and_zero_on_this_set():
    """One number, so a later change cannot quietly trade one contract against another."""
    wrong = [(c["id"], c["contract"], c["label"], _outcome(c)) for c in CASES if _outcome(c) != c["label"]]
    assert not wrong, f"{len(wrong)}/{len(CASES)} judge errors: {wrong}"


def test_every_contract_has_both_a_right_and_a_wrong_reply():
    """A set that only contains failures would let a judge that rejects everything look perfect."""
    for contract in {c["contract"] for c in CASES} - {"inconclusive"}:
        labels = {c["label"] for c in CASES if c["contract"] == contract}
        assert {"ok", "fail"} <= labels, f"{contract} is not balanced: {labels}"
