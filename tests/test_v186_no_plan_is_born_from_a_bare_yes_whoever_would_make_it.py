"""95.6b — no plan is born from a bare "yes" with nothing pending, whichever producer would make it.

95.6 (v175) gated `plan_task`. E8 in c95b (rep2, rep3) showed the second producer: on the bare "yes"
the model apologised and promised ("I will get started once you tell me…"), and the say-do gate's
promise path turned that promise into a PROPOSED plan whose step was the apology — the plan 95.6 had
just refused to let the model create. Same rule, one predicate (`confirmation_without_pending`, next
to `approval_signal`), honoured by every producer: plan_task, the promise path, the blocked-attempt path.

Positive: the promise on a bare "yes" makes no plan and the reply is delivered as the clarification it
is. Variant: a blocked attempt on that turn makes no plan either. Negative: the same promise on an
instruction still becomes a proposal. Preserve: with a proposal pending, "yes" still approves it.
"""
from __future__ import annotations

import pytest

from hmgfu.saydo import PROPOSAL_SUFFIX, enforce, transactions_of
from hmgfu.plans import confirmation_without_pending
from hmgfu.session_plans import SessionPlanStore


class _Settings:
    def get(self, key, default=None):
        return True if key == "saydo_gate_enabled" else default


class _E:
    def __init__(self, tmp_path, message, unconfirmed=None):
        self.settings = _Settings()
        self.session_plans = SessionPlanStore(str(tmp_path / "plans.db"))
        self._turn_user_message = message
        self._turn_plan = None
        self._turn_step_tools = []
        self._turn_effects_allowed = False
        self._turn_unconfirmed_effects = unconfirmed or []
        self.events = []

    def _emit(self, e):
        self.events.append(e)


PROMISE = ("I apologize for the oversight. Please let me know what specific task you would like me to "
           "work on, and I will get started right away.")
TX = transactions_of([], [], None, 0)


def _rerun(instruction, required=None):
    return "", []


@pytest.mark.parametrize("text", ["yes", "Yes.", "no", "sim", "ok go ahead"])
def test_a_promise_on_a_bare_answer_with_nothing_pending_makes_no_plan(tmp_path, text):
    """THE CONTRACT — fails before: the promise path proposes a plan whose step is the apology."""
    e = _E(tmp_path, text)
    reply, _t, report = enforce(e, PROMISE, [], TX, "s1", text, _rerun, 2)
    assert e.session_plans.get("s1") is None, e.session_plans.get("s1")
    assert PROPOSAL_SUFFIX not in reply
    assert report and report.get("action") == "clarification", report


def test_a_blocked_attempt_on_a_bare_answer_with_nothing_pending_makes_no_plan(tmp_path):
    e = _E(tmp_path, "yes", unconfirmed=[{"name": "write_file", "arguments": {"path": "notes.txt"}}])
    reply, _t, _r = enforce(e, "I'll write notes.txt for you.", [], TX, "s1", "yes", _rerun, 2)
    assert e.session_plans.get("s1") is None
    assert PROPOSAL_SUFFIX not in reply


def test_the_same_promise_on_an_instruction_is_still_proposed(tmp_path):
    e = _E(tmp_path, "please tidy the notes folder")
    reply, _t, report = enforce(e, "I will tidy the notes folder for you.", [], TX, "s1",
                                "please tidy the notes folder", _rerun, 2)
    assert e.session_plans.pending("s1") is not None
    assert report.get("action") == "proposed" and reply.endswith(PROPOSAL_SUFFIX)


def test_with_a_proposal_pending_yes_is_still_an_approval(tmp_path):
    e = _E(tmp_path, "yes")
    e.session_plans.save("s1", {"title": "Tidy", "status": "proposed", "steps": [{"text": "tidy", "status": "pending"}]})
    assert confirmation_without_pending(e, "s1") is False


def test_a_long_message_that_starts_with_yes_is_an_instruction(tmp_path):
    e = _E(tmp_path, "yes, and after that write a summary of the folder into summary.md for me please")
    assert confirmation_without_pending(e, "s1") is False
