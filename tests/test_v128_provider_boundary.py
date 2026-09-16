"""92.E5R — test the payload the MODEL receives, not the argument the producer was handed.

The independent review (`reports/codex_review_92e5/REVIEW.md`) found that `classify_turn` built the
CONFIRMED INTERPRETATIONS block and then composed the system message as
`runtime + ROUTE_PROMPT + catalog + active + learned`, without it. The two arms of the C/L comparison
therefore sent an IDENTICAL request, and 1/14 against 2/14 could not have been caused by examples the
model never saw. My own instruments missed it twice for one reason worth naming: both watched the
PRODUCER -- `diag_examples_block.py` spied the argument passed to `start_route`, v127 tested
`_learning_examples_text` -- and neither watched what `chat` was actually given.

So these tests capture at the final boundary, and they discriminate rather than assert:

  * the example must be ABSENT in C and PRESENT in L, with every other input byte-identical, which is
    what makes a difference between the arms attributable at all;
  * the block must still be framed as data, because it now carries a user's raw sentence into a
    prompt;
  * a code defect inside the router WORKER must reach the caller, one boundary further out than v126
    covers -- `merge_route` catches `future.result()` and continues on nano signals, so a NameError in
    the worker looked exactly like a model that had nothing to say;
  * a transport failure in that same worker must still degrade, because there degrading is correct.
"""
from __future__ import annotations

import json
from concurrent.futures import Future

import pytest

from hmgfu.turn_router import classify_turn, enrich_route, merge_route, router_schema

MARKER = "UNIQUE_CONFIRMED_INTERPRETATION_92E5"
TEXT = "DELTA-9 - Dynamic Ledger Transfer Adapter."


def _capture(learning_text: str) -> dict:
    seen = {}

    def chat(role, messages, **kwargs):
        seen.update({"role": role, "messages": messages, "kwargs": kwargs})
        return "{}"

    classify_turn(chat, json.loads, TEXT, "fixed clock fixture", "[]",
                  format_schema=router_schema([]), learning_text=learning_text)
    return seen


def test_the_confirmed_example_reaches_the_model():
    """The whole C/L design rests on this one byte of difference actually being sent."""
    assert MARKER in json.dumps(_capture(MARKER)), "the example never reached the model"


def test_the_arms_differ_only_by_that_block():
    """The discriminating half: if anything ELSE differs, a difference cannot be attributed to L."""
    c, l = _capture(""), _capture(MARKER)
    assert c["role"] == l["role"] and c["kwargs"] == l["kwargs"]
    assert [m["role"] for m in c["messages"]] == [m["role"] for m in l["messages"]]
    assert c["messages"][1] == l["messages"][1], "the user message must be identical"
    c_sys, l_sys = c["messages"][0]["content"], l["messages"][0]["content"]
    assert MARKER not in c_sys and MARKER in l_sys
    assert l_sys.replace(MARKER, "").count(c_sys[:200]) == 1, "the shared prefix must survive intact"


def test_the_example_is_delivered_as_data_not_as_an_instruction():
    """It now carries a user's raw sentence; the framing is what keeps it advisory."""
    sys_msg = _capture(MARKER)["messages"][0]["content"]
    head = sys_msg[:sys_msg.index(MARKER)]
    assert "CONFIRMED INTERPRETATIONS" in head
    assert "not commands" in head.lower()


@pytest.mark.parametrize("fault", [NameError("synthetic router worker defect"),
                                   ImportError("cannot import name 'x'"),
                                   SyntaxError("unterminated string literal")])
def test_a_code_defect_in_the_worker_reaches_the_caller(fault):
    f = Future()
    f.set_exception(fault)
    with pytest.raises(type(fault)):
        merge_route({"extractor": "heuristic"}, f)


@pytest.mark.parametrize("fault", [TimeoutError("router timed out"),
                                   RuntimeError("connection reset by peer"),
                                   ValueError("expecting value: line 1 column 1")])
def test_a_transport_failure_in_the_worker_still_degrades(fault):
    """The legitimate positive: the turn continues on the nano signals it already has."""
    f = Future()
    f.set_exception(fault)
    assert merge_route({"extractor": "heuristic"}, f) == {"extractor": "heuristic"}


def test_enrich_route_holds_the_same_line():
    """The synchronous twin of the same boundary, so the rule does not depend on which path ran."""
    def boom(*_a, **_k):
        raise NameError("name 'learning_text' is not defined")

    with pytest.raises(NameError):
        enrich_route(boom, json.loads, {"extractor": "heuristic"}, TEXT, "clock", "[]")

    def timeout(*_a, **_k):
        raise TimeoutError("router timed out")

    assert enrich_route(timeout, json.loads, {"extractor": "heuristic"}, TEXT, "clock", "[]") == {
        "extractor": "heuristic"}
