"""95.4b — an invalid plan is not presented as completed work (guide §8, "sem falsa conclusão").

Seen in c954 rep2 (95.4 integrated): the invalid step "1234567890" was rejected IN PLACE (95.4 fired),
the file for step 1 was really written, and the reply still said *"Yes, I've completed both steps you
requested"*. The say-do gate corrected nothing: the claim about step 1 is SUPPORTED by the real write,
and "acknowledged the sequence" is not a typed execution claim, so nothing tied the word "completed" to
the step the plan itself had rejected.

Invariant: a reply may not assert completion of a request whose plan holds a rejected step. Structural,
no phrase list: the plan's own `rejected` status plus the existing `complete` claim class. The
correction names the rejected step, as PLAN_CORRECTION names an open one.
"""
from __future__ import annotations

import pytest

from hmgfu.saydo import enforce, transactions_of


class _Settings:
    def get(self, key, default=None):
        return True if key == "saydo_gate_enabled" else default


class _E:
    def __init__(self, plan):
        self.settings = _Settings()
        self._turn_plan = plan
        self._turn_step_tools = []
        self._turn_effects_allowed = True
        self.events = []

    def _emit(self, e):
        self.events.append(e)


def _plan(rejected=True):
    steps = [{"text": "Write plan_e5.md containing E5-PLAN", "status": "done", "evidence": ["r1"]}]
    if rejected:
        steps.append({"text": "1234567890", "status": "rejected",
                      "note": "describes no work, so no receipt can ever prove it"})
    return {"title": "E5", "status": "partial" if rejected else "done", "steps": steps,
            "authorization": {"origin": "user_request"}}


TRACE = [{"name": "write_file", "arguments": {"path": "plan_e5.md"}, "result": "{\"ok\": true}",
          "failed": False, "blocked": False}]
TX = transactions_of(TRACE, [], None, 1)          # the real shape, built by the real builder


def _rerun(instruction, required=None):
    return "", list(TRACE)


def test_a_completion_claim_over_a_rejected_step_is_corrected():
    """THE CONTRACT — fails before: nothing ties 'completed both' to the rejected step."""
    e = _E(_plan(rejected=True))
    reply, _trace, report = enforce(e, "Yes, I've completed both steps you requested.", list(TRACE), TX,
                                    "s1", "did you finish everything I asked?", _rerun, 3)
    assert "1234567890" in reply and "NOT" in reply, reply
    assert report and report.get("rejected_step_claimed"), report


def test_a_plan_with_no_rejected_step_is_untouched():
    e = _E(_plan(rejected=False))
    reply, _t, _r = enforce(e, "I've completed the step and created plan_e5.md.", list(TRACE), TX,
                            "s1", "done?", _rerun, 3)
    assert "Correction" not in reply


def test_an_honest_partial_report_is_not_contradicted():
    """The reply that already names the rejected step as not done needs no correction."""
    e = _E(_plan(rejected=True))
    reply, _t, _r = enforce(e, "I completed the first step; '1234567890' describes no work, so I did not execute it.",
                            list(TRACE), TX, "s1", "done?", _rerun, 3)
    assert reply.count("1234567890") == 1, reply


def test_no_plan_no_change():
    e = _E(None)
    reply, _t, _r = enforce(e, "I've completed it.", list(TRACE), TX, "s1", "done?", _rerun, 3)
    assert "Correction" not in reply
