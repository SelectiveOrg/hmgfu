"""93.R3 — the router's clock carries seconds, and the seconds were deciding what gets learned.

The frozen replay settled a question three earlier measurements could not. Replaying the router's
captured request byte for byte gives an envelope in **8 of 8**: the model call is deterministic.
Rewriting only the clock line drops it to 5/8, and whole fresh turns to 2/8 — and a diff of the system
message across fresh turns of the same sentence shows the ONLY difference is one line, the runtime
clock, down to the second.

So the instability blamed on "a perception decision on a knife edge" is context sensitivity, and the
context is a timestamp whose seconds cannot matter to a classification. The router decides freshness
and whether the runtime clock answers the turn; minute resolution serves both.

What must not change is the ANSWER path: when the user asks the time, the value spoken comes from the
runtime block with its full precision, and phase 90 spent real effort on that. These tests hold both
ends — coarse for the classifier, exact for the answer.
"""
from __future__ import annotations

import re

from hmgfu.runtime_context import RuntimeContext, router_prompt, runtime_prompt

SECONDS = re.compile(r"\b[0-2]\d:[0-5]\d:([0-5]\d)\b")


def test_the_router_clock_has_no_seconds():
    block = router_prompt(RuntimeContext.capture())
    assert block, "the router still needs to know the time"
    assert not SECONDS.search(block), f"seconds reach the router: {block[:200]}"


def test_the_router_still_knows_the_date_and_the_hour():
    block = router_prompt(RuntimeContext.capture())
    now = RuntimeContext.capture().public()
    assert str(now.get("local_date")) in block
    assert str(now.get("local_time"))[:5] in block, "the hour and minute must survive"


def test_the_answer_path_keeps_full_precision():
    """The discriminating half: coarsening the classifier must not coarsen what is spoken."""
    assert SECONDS.search(runtime_prompt(RuntimeContext.capture()))


def test_two_captures_in_the_same_minute_are_identical_for_the_router():
    """The whole point: consecutive turns should send the SAME bytes, not differ by a second."""
    a, b = RuntimeContext.capture(), RuntimeContext.capture()
    if str(a.public().get("local_time"))[:5] != str(b.public().get("local_time"))[:5]:
        return                                  # a minute boundary fell between them; nothing to assert
    assert router_prompt(a) == router_prompt(b)
