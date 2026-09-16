"""Phase 92.E1 — the evaluator is itself tested before it is trusted.

The plan's rule: "Zero erro nos negativos de seguranca antes de aceitar o instrumento." An instrument
that flags everything would pass a negatives-only check, so the labelled set carries positives too,
and both directions are asserted here.

The judge's learning half reads only RECORDED evidence -- the reply, the tools that actually ran, and
whether this turn wrote -- and never asks the product's own classifier for a verdict on itself.
"""

from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from run_conversations import learning_verdict  # noqa: E402

CASES = json.load(io.open(os.path.join(ROOT, "scripts", "oracles", "judge_learning_v1.json"),
                          encoding="utf-8"))["cases"]
SAFETY = ("claimed_update_without_write", "claimed_search_without_tool", "question_suggests_wrong_value")


def _run(c):
    return learning_verdict(c, c["reply"], "", {}, c.get("tools") or [],
                            {"k"} if c.get("wrote") else set())


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_each_labelled_case_is_judged_as_labelled(case):
    got = _run(case)
    for field, want in case["expect"].items():
        assert got[field] is want, f"{case['id']} ({case['class']}): {field} was {got[field]}"


def test_zero_error_on_the_safety_negatives():
    """The gate the plan puts on the instrument itself, counted over the whole set."""
    wrong = []
    for c in CASES:
        got, want = _run(c), c["expect"]
        for f in SAFETY:
            if f in want and got[f] is not want[f]:
                wrong.append((c["id"], f))
    assert not wrong, f"safety-negative errors: {wrong}"


def test_the_instrument_is_not_vacuous():
    """A judge that flagged everything would pass a negatives-only check, so the clean cases matter."""
    flagged = [c["id"] for c in CASES if _run(c)["safety_negative"]]
    clean = [c["id"] for c in CASES if c["class"] == "clean"]
    assert flagged, "no case is flagged at all: the instrument detects nothing"
    assert not (set(flagged) & set(clean)), f"clean cases flagged: {set(flagged) & set(clean)}"
