"""95.6 — "sim/não/talvez" answer only the delivered pending question of that session (guide §5).

Reproduced live (S2 and X1 in the 94.7 pilot, L1 rep3 in 94.8c): a bare "yes" with nothing pending
made the model apologise for having nothing in progress — and then call `plan_task` with the apology
as the single step, so the session gained a PROPOSED plan whose title is *"Since there is no specific
task currently active in our conversation, please let..."*. The apology masked the real plan and the
ask that followed was answered as a task continuation.

Invariant: a confirmation resolves an identified pending item and nothing else; with nothing pending
it is a clarification, not authority to invent work. The store already has the two facts this needs:
`session_plans.approval_signal` (whether the text is a bare yes/no — the same matcher the approval
path uses) and `SessionPlanStore.pending` (whether anything awaits an answer). No new detector.
"""
from __future__ import annotations

import pytest

from hmgfu.plans import plan_action

APOLOGY = ("Since there is no specific task currently active in our conversation, please let me know "
           "what you would like me to do next")


class _Plans:
    def __init__(self, pending=None):
        self._pending = pending
        self.saved = []

    def pending(self, sid):
        return self._pending

    def resumable(self, sid):
        return None

    def proposed(self, sid):
        return self._pending

    def get(self, sid):
        return self._pending

    def save(self, sid, plan):
        self.saved.append(plan)

    def set_status(self, sid, status, reason=""):
        pass


class _E:
    def __init__(self, message, pending=None):
        self._turn_user_message = message
        self._turn_plan = None
        self._turn_step_tools = []
        self._turn_effects_allowed = True
        self._turn_session = "s1"
        self.session_plans = _Plans(pending)

    def _emit(self, event):
        pass


@pytest.mark.parametrize("text", ["yes", "sim", "ok", "no", "não", "go ahead"])
def test_a_bare_answer_with_nothing_pending_creates_no_plan(text):
    """THE CONTRACT — fails before: the apology becomes a proposed plan."""
    e = _E(text)
    out = plan_action(e, "plan_task", {"title": APOLOGY[:80], "steps": [APOLOGY], "status": "proposed"})
    assert out.get("error"), out
    assert e._turn_plan is None
    assert not e.session_plans.saved


def test_an_instruction_still_makes_a_plan():
    """NEGATIVE — a real request is not a bare answer."""
    e = _E("Write notes.md containing HELLO and then read it back to me.")
    out = plan_action(e, "plan_task", {"title": "notes", "steps": ["Write notes.md", "Read it back"]})
    assert out.get("ok"), out
    assert e._turn_plan is not None


def test_a_long_message_that_starts_with_yes_is_an_instruction():
    """VARIANT — 'yes, and also write notes.md ...' carries new work; approval_signal already says so."""
    e = _E("yes, and also write notes.md containing HELLO, then read it back to me please, thanks a lot")
    out = plan_action(e, "plan_task", {"title": "notes", "steps": ["Write notes.md", "Read it back"]})
    assert out.get("ok"), out


def test_the_refusal_says_what_to_do():
    """Rule 10: the tool result tells the model to ask, not to invent."""
    e = _E("yes")
    out = plan_action(e, "plan_task", {"title": "x", "steps": [APOLOGY]})
    assert "pending" in out.get("error", "").lower() or "ask" in out.get("error", "").lower(), out
