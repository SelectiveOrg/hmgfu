"""95.4c (E5 c95c rep1) — one step per enumerated item: a plan that DROPS an item is not accepted.

95.4 validates each step in the user's words when the message enumerates them one-to-one. Rep1's model
declared ONE step for the two enumerated items ("1234567890" silently omitted), so the one-to-one check
never applied, the plan finished `done` and the reply claimed both steps complete over a reduced
request — the shape 94.3b forbids. Structural: N enumerated items and fewer declared steps is a
refusal that says what to declare; the model re-declares one entry per item and 94.3b/95.4 reject the
workless one IN PLACE. Positive: fewer steps refused. Negative: one per item accepted, the workless
one rejected in place. Variant: more steps than items is not a dropped item. Preserve: no enumeration,
one step, plan made.
"""
from __future__ import annotations

from hmgfu.plans import plan_action
from tests.test_v175_a_bare_yes_with_nothing_pending_makes_no_plan import _E

TWO = "Two steps. 1. Write plan_e5.md containing E5-PLAN. 2. 1234567890."


def test_fewer_steps_than_enumerated_items_is_refused_with_the_rule():
    """THE CONTRACT — fails before: the one-step plan is accepted and finishes 'done'."""
    e = _E(TWO)
    out = plan_action(e, "plan_task", {"steps": ["Create the file plan_e5.md with the content E5-PLAN"]})
    assert "error" in out and "one step per item" in out["error"], out
    assert e._turn_plan is None


def test_one_step_per_item_is_accepted_and_the_workless_item_is_rejected_in_place():
    e = _E(TWO)
    out = plan_action(e, "plan_task", {"steps": ["Create the file plan_e5.md with the content E5-PLAN",
                                                 "Acknowledge the numeric sequence 1234567890"]})
    assert "error" not in out, out
    plan = e._turn_plan or {}
    assert [s["status"] for s in plan["steps"]] == ["active", "rejected"], plan["steps"]


def test_more_steps_than_items_is_not_a_dropped_item():
    e = _E(TWO)
    out = plan_action(e, "plan_task", {"steps": ["Create plan_e5.md", "Write E5-PLAN into it", "Verify the file"]})
    assert "error" not in out, out


def test_no_enumeration_one_step_still_plans():
    e = _E("please write plan_e5.md containing E5-PLAN")
    out = plan_action(e, "plan_task", {"steps": ["Write plan_e5.md containing E5-PLAN"]})
    assert "error" not in out and e._turn_plan is not None, out
