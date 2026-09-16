"""95.4d (E5 c95g rep1) — a step given as {"action": ...} is a step.

The model declared [{"action": "write_file(path='plan_e5.md', ...)", "status": "pending"}, {"action":
"process_input('1234567890')", "status": "pending"}] — one entry per enumerated item, the shape 95.4c
asks for — and `_step_text` read "" from both, so plan_task refused, no plan existed, and the report
turn had no referent. Positive: action dicts make the plan, the workless item rejected in place.
Negative: a dict with none of the known keys is still nothing. Preserve: text/step dicts and strings.
"""
from __future__ import annotations

from hmgfu.plans import _step_text, plan_action
from tests.test_v175_a_bare_yes_with_nothing_pending_makes_no_plan import _E

TWO = "Two steps. 1. Write plan_e5.md containing E5-PLAN. 2. 1234567890."


def test_action_dicts_make_the_plan_with_the_workless_item_rejected_in_place():
    """THE CONTRACT — fails before: 'plan_task needs 1-12 steps that each describe work'."""
    e = _E(TWO)
    out = plan_action(e, "plan_task", {"plan": [{"action": "write_file(path='plan_e5.md', content='E5-PLAN')", "status": "pending"},
                                                {"action": "process_input('1234567890')", "status": "pending"}]})
    assert "error" not in out, out
    assert [s["status"] for s in e._turn_plan["steps"]] == ["active", "rejected"], e._turn_plan["steps"]


def test_a_dict_with_no_known_key_is_still_nothing():
    assert _step_text({"status": "pending", "id": 3}) == ""


def test_text_step_and_string_forms_are_unchanged():
    assert _step_text({"text": "write it"}) == "write it"
    assert _step_text({"step": "verify"}) == "verify"
    assert _step_text("plain") == "plain"
    assert _step_text({"task": "read the file"}) == "read the file"
