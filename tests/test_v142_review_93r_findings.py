"""93.RR — the four findings of REVIEW_93R, each as the test that was missing.

All four were reproduced with pure probes before anything was changed:

  * **F1** `router_prompt` removed HH:MM:SS with a regex while `unix_seconds` kept ticking, so two
    fixed instants in the same minute still produced different blocks. The v140 test took two
    consecutive captures, which usually land in the same second and therefore never exercised the
    difference it was written to prevent — so the tests here use FIXED, deliberately separated
    instants and cross a minute and a day boundary on purpose.
  * **F3** the recall cache dropped `limit` from its key, so asking for more rows after a narrow
    search was answered as a repeat, with the narrow rows. Widening the evidence is exactly what a
    model should be able to do.
  * **F4** the policy judge tested containment, so a stored exception that ADDS "or whenever
    convenient" to what the user said passed. Presence is not equivalence: an extra disjunct changes
    the behaviour the user asked for.

F2 is an instrument defect in `diag_frozen_replay` and is covered by its own probe, not here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sequence_verdict import taught_policy  # noqa: E402

from hmgfu.recall_budget import RecallBudget  # noqa: E402
from hmgfu.runtime_context import RuntimeContext, router_prompt  # noqa: E402

STYLE = "short snippets"
ASKED = "unless the user asks for the full context"


def _at(hh: int, mm: int, ss: int, day: int = 11) -> RuntimeContext:
    """A context for one FIXED instant — every field consistent with it."""
    return RuntimeContext.at(f"2026-09-{day:02d}T{hh:02d}:{mm:02d}:{ss:02d}+00:00")


# --- F1: the router's clock -----------------------------------------------------------------------

def test_two_fixed_instants_in_the_same_minute_are_identical_for_the_router():
    """The case the old test could not see: seconds 01 and 45 of the same minute."""
    assert router_prompt(_at(12, 20, 1)) == router_prompt(_at(12, 20, 45))


def test_no_second_level_field_survives_into_the_router_context():
    block = router_prompt(_at(12, 20, 45))
    assert "12:20:45" not in block
    assert str(_at(12, 20, 45).unix_seconds) not in block, "unix_seconds keeps ticking every second"


def test_a_different_minute_is_a_different_context():
    """The discriminating half: coarsening must not blind the router to time passing."""
    assert router_prompt(_at(12, 20, 1)) != router_prompt(_at(12, 21, 1))


def test_a_day_boundary_is_crossed_deliberately():
    assert router_prompt(_at(23, 59, 30)) != router_prompt(_at(0, 0, 30, day=12))


def test_the_router_still_sees_the_date_and_the_hour():
    block = router_prompt(_at(12, 20, 45))
    assert "2026-09-11" in block and "12:20" in block


def test_the_answer_path_keeps_the_exact_second():
    """What is spoken to the user must stay exact; only the classifier is coarsened."""
    assert "12:20:45" in _at(12, 20, 45).prompt_block()


# --- F3: widening a search is not a repeat --------------------------------------------------------

def test_asking_for_more_rows_is_not_a_repeat():
    b = RecallBudget()
    b.record("memory_timeline", {"query": "dog", "limit": 1}, '{"rows": ["one"]}')
    assert b.seen("memory_timeline", {"query": "dog", "limit": 3}) is None


def test_asking_for_the_same_or_fewer_rows_is_a_repeat():
    """The stored answer already satisfies it, so it is reused rather than run again."""
    b = RecallBudget()
    b.record("memory_search", {"query": "dog", "limit": 5}, '{"results": ["a", "b"]}')
    assert b.seen("memory_search", {"query": "dog", "limit": 5}) is not None
    assert b.seen("memory_search", {"query": "dog", "limit": 2}) is not None


def test_a_widened_search_replaces_the_narrow_answer():
    b = RecallBudget()
    b.record("memory_timeline", {"query": "dog", "limit": 1}, '{"rows": ["one"]}')
    b.record("memory_timeline", {"query": "dog", "limit": 3}, '{"rows": ["one", "two", "three"]}')
    again = b.seen("memory_timeline", {"query": "dog", "limit": 3})
    assert again is not None and "three" in again


def test_a_failure_is_classified_by_the_shared_rule_not_by_a_key_name():
    """`blocked: true` is the safety layer working, and it is not an answer to remember either."""
    b = RecallBudget()
    b.record("memory_search", {"query": "dog"}, '{"blocked": true, "reason": "not authorised"}')
    assert b.seen("memory_search", {"query": "dog"}) is None


# --- F4: equivalence, not occurrence --------------------------------------------------------------

def _row(condition):
    return [{"kind": "response_style", "value": STYLE, "condition": condition}]


def test_the_exception_the_user_stated_is_accepted():
    assert taught_policy(_row(ASKED), expect_value=STYLE, expect_condition=ASKED)


@pytest.mark.parametrize("stored,why", [
    (ASKED + " or whenever convenient", "invented: an extra case the user never granted"),
    ("unless the user does not ask for the full context", "negated"),
    ("unless the user asks for anything", "widened"),
    ("unless the user asks for the full context in writing", "narrowed"),
    ("", "removed"),
])
def test_a_condition_that_is_not_the_one_stated_is_refused(stored, why):
    assert not taught_policy(_row(stored), expect_value=STYLE, expect_condition=ASKED), why


def test_punctuation_and_spacing_do_not_decide_equivalence():
    assert taught_policy(_row("  Unless the user asks for the full context.  "),
                         expect_value=STYLE, expect_condition=ASKED)


def test_an_unconditional_expectation_refuses_an_invented_exception():
    """Previously the helper did not look at the condition at all when none was expected."""
    assert not taught_policy(_row("whenever convenient"), expect_value=STYLE, expect_condition="")
    assert taught_policy(_row(""), expect_value=STYLE, expect_condition="")
