"""93.R1 — negatives for the judge itself: an envelope is not learning, a call is not execution.

The independent review of 93.F showed the 5/5 was partly an instrument result. Two gates in
`diag_sequence_20260911.py` were permissive:

  * `teaching_left_a_trace` accepted *any* delta OR the mere presence of an envelope, so a proposal
    that was refused, or committed with the wrong value, or stored under the wrong target, passed;
  * `widget_created` looked for the tool's NAME in `r["_tools"]`, which `bench_say_do` fills from the
    whole trace — failed and blocked calls included. A call that raised still counted as a widget.

So the verdict now asks the stores what is there, and asks the trace whether the call actually
succeeded. These tests are the judge's own negatives: each one is a case the old gate passed and the
new one must fail, paired with the legitimate positive it must keep accepting.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sequence_verdict import taught_policy, tool_succeeded  # noqa: E402

POLICY = "short snippets"
UNLESS = "the user asks for the full context"
ROW = {"kind": "response_style", "value": POLICY, "condition": UNLESS}


# --- teaching: the store decides, not the envelope ------------------------------------------------

def test_a_persisted_policy_with_its_condition_counts():
    assert taught_policy([ROW], expect_value=POLICY, expect_condition=UNLESS)


def test_an_envelope_with_nothing_persisted_does_not_count():
    """The exact permissiveness: `bool(changes) or envelope` passed a refused proposal."""
    assert not taught_policy([], expect_value=POLICY, expect_condition=UNLESS)


def test_the_wrong_value_does_not_count():
    assert not taught_policy([dict(ROW, value="always answer in full")],
                             expect_value=POLICY, expect_condition=UNLESS)


def test_a_policy_that_lost_its_condition_does_not_count():
    """A policy stored without the exception is not the policy the user stated."""
    assert not taught_policy([dict(ROW, condition="")], expect_value=POLICY, expect_condition=UNLESS)


def test_the_wrong_target_does_not_count():
    assert not taught_policy([dict(ROW, kind="output_prefix")],
                             expect_value=POLICY, expect_condition=UNLESS)


def test_an_unconditional_expectation_ignores_the_condition():
    assert taught_policy([dict(ROW, condition="")], expect_value=POLICY, expect_condition="")


# --- execution: the call has to have worked -------------------------------------------------------

def test_a_successful_call_counts():
    assert tool_succeeded([{"name": "create_widget", "failed": False}], "create_widget")


def test_a_failed_call_does_not_count():
    """`_tools` lists every call, so the old gate counted this one."""
    assert not tool_succeeded([{"name": "create_widget", "failed": True,
                                "result": "unknown widget type"}], "create_widget")


def test_a_blocked_call_does_not_count():
    assert not tool_succeeded([{"name": "create_widget", "blocked": True}], "create_widget")


def test_a_failed_call_followed_by_a_successful_one_counts():
    """A retry that worked is execution; the judge must not punish the first attempt."""
    trace = [{"name": "create_widget", "failed": True},
             {"name": "create_widget", "failed": False}]
    assert tool_succeeded(trace, "create_widget")


def test_another_tool_succeeding_proves_nothing_about_this_one():
    assert not tool_succeeded([{"name": "write_file", "failed": False}], "create_widget")


def test_an_empty_trace_is_not_execution():
    assert not tool_succeeded([], "create_widget")
