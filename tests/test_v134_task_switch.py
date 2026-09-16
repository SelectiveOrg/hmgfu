"""93.B — an obsolete plan must not hold the user's next request hostage.

The last three turns of the real conversation of 2026-09-11: the user asked, in plain words, for a
timer widget. `plan_task` answered `already_active`; two `create_widget` calls were blocked as
"outside the approved plan's scope (memory_search)"; `update_plan` then failed for want of a receipt
that could never exist, because the action it was reporting had been blocked. The plan being defended
was the one generated sixteen turns earlier out of the assistant's own promise — and the prefix it
was about had already been removed.

Two defects, both reproducible without a model:

  * `authorization()` returns `approved_plan` whenever a plan record exists, so `plan_scope` narrows
    the turn even when the USER has just asked for the effect directly. A plan the user approved for
    one purpose cannot shrink what they may ask for next.
  * `plan_task` refuses to start anything while a plan is active. That rule exists so the model cannot
    re-plan its way around its own work, and it must stay for the model — but not against the user.

What must NOT change is the authority boundary itself: a turn with no request and no plan authorises
nothing, and an explicit prohibition still wins over everything. Those are the discriminating tests
here, not afterthoughts.
"""
from __future__ import annotations

import pytest

from hmgfu.authority import decide


class _Tools:
    schemas = {"create_widget": {"x-effect": "write"}, "memory_search": {"x-effect": "read"},
               "write_file": {"x-effect": "write"}}


class _Engine:
    def __init__(self, **kw):
        self.tools = _Tools()
        self._turn_plan = None
        self._turn_effects_allowed = False
        self._turn_prohibited = False
        self._turn_user_message = ""
        for k, v in kw.items():
            setattr(self, k, v)


STALE_PLAN = {"title": "make sure that doesn't happen again!",
              "steps": [{"text": "memory_search: the prefix directive", "status": "active"}],
              "authorization": {"origin": "user_approval", "turn_seq": 3}}


def test_the_users_own_request_is_not_narrowed_by_an_unrelated_plan():
    """The reproduction: 'create a timer widget' while a memory_search plan is active."""
    eng = _Engine(_turn_plan=STALE_PLAN, _turn_effects_allowed=True,
                  _turn_user_message="create a timer widget please")
    d = decide(eng, "create_widget", {"title": "timer"})
    assert d.allowed, d.reason
    assert d.origin == "user_request", "it is the user's request that authorises it, not the plan"


def test_the_plan_still_scopes_what_the_MODEL_does_on_its_own():
    """The discriminating half: with no request this turn, the plan's scope still binds."""
    eng = _Engine(_turn_plan=STALE_PLAN, _turn_effects_allowed=False)
    d = decide(eng, "create_widget", {"title": "timer"})
    assert not d.allowed and d.origin == "approved_plan"


def test_a_prohibition_still_wins_over_the_users_own_request():
    eng = _Engine(_turn_plan=STALE_PLAN, _turn_effects_allowed=False, _turn_prohibited=True)
    assert not decide(eng, "create_widget", {"title": "timer"}).allowed


def test_no_plan_and_no_request_still_authorises_nothing():
    assert not decide(_Engine(), "create_widget", {"title": "timer"}).allowed


def test_a_tool_inside_the_plan_scope_is_unaffected():
    eng = _Engine(_turn_plan=STALE_PLAN)
    assert decide(eng, "memory_search", {"query": "prefix"}).allowed


# --- plan_task and an explicit new task -----------------------------------------------------------

class _Store:
    def __init__(self):
        self.saved = []
        self.plan = dict(STALE_PLAN, status="active")

    def resumable(self, _sid):
        return self.plan

    def save(self, _sid, plan):
        self.saved.append(plan)

    def set_status(self, _sid, status, reason=""):
        self.plan = dict(self.plan, status=status, reason=reason)
        return self.plan

    def pending(self, _sid):
        return None


def _engine_with_store(**kw):
    eng = _Engine(**kw)
    eng.session_plans = _Store()
    eng._turn_session = "s1"
    eng._turn_seq = 16
    eng.events = []
    eng._emit = eng.events.append
    return eng


def test_the_user_asking_for_a_new_task_is_not_answered_with_already_active():
    from hmgfu.plans import plan_action

    eng = _engine_with_store(_turn_plan=STALE_PLAN, _turn_effects_allowed=True,
                             _turn_user_message="now create a timer widget for me")
    out = plan_action(eng, "plan_task", {"title": "timer widget",
                                         "steps": ["create_widget: a 20 minute timer"]})
    assert not out.get("already_active"), out
    assert eng._turn_plan["title"] == "timer widget"


def test_the_superseded_plan_is_recorded_not_silently_dropped():
    from hmgfu.plans import plan_action

    eng = _engine_with_store(_turn_plan=STALE_PLAN, _turn_effects_allowed=True,
                             _turn_user_message="now create a timer widget for me")
    plan_action(eng, "plan_task", {"title": "timer widget", "steps": ["create_widget: a timer"]})
    assert eng.session_plans.plan["status"] == "superseded"
    assert eng.session_plans.plan.get("reason"), "a supersession says why and when"


def test_the_model_replanning_on_its_own_is_still_refused():
    """The rule that must survive: no request this turn, so the active plan continues."""
    from hmgfu.plans import plan_action

    eng = _engine_with_store(_turn_plan=STALE_PLAN, _turn_effects_allowed=False,
                             _turn_user_message="(the assistant talking to itself)")
    out = plan_action(eng, "plan_task", {"title": "something else", "steps": ["write_file: x"]})
    assert out.get("already_active") is True
