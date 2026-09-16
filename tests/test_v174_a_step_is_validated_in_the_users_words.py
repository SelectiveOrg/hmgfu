"""95.4 — an invalid step is not rewritten as completed work (guide §8).

Reproduced live: X3 3/3 and E5 4/6 across both arms. Asked "Two steps. 1. Write plan_e5.md containing
E5-PLAN. 2. 1234567890.", the planner passed `plan_task` the steps ["Create plan_e5.md ...",
"Acknowledge and process the numeric sequence 1234567890"]. The second is the model's PARAPHRASE of
an item that describes no work, and it passes `_describes_work` because the paraphrase does; the plan
sits `active`, and the reply says "I've completed both steps". 94.3b's rejection is correct and is
bypassed upstream, before it ever sees the item.

Invariant: a plan step is validated in the USER's words, not the model's. Structural rule, no phrase
list: when the user's message enumerates its items ("1. ... 2. ..."), each candidate step corresponds
to the user's item at the same position, and it is THAT item which must describe work. A message with
no enumeration keeps today's behaviour exactly. `_describes_work` is reused, not re-grown.
"""
from __future__ import annotations

import pytest

from hmgfu.plans import enumerated_items, plan_action

ASK = "Two steps. 1. Write plan_e5.md containing E5-PLAN. 2. 1234567890."


class _E:
    """The engine surface plan_action reads: the turn's user message and the plan slot."""
    def __init__(self, message):
        self._turn_user_message = message
        self._turn_plan = None
        self._turn_step_tools = []
        self._turn_effects_allowed = True
        self.session_plans = None
        self._turn_session = "s1"

    def _emit(self, event):
        pass


def test_the_users_enumeration_is_read_back():
    assert enumerated_items(ASK) == ["Write plan_e5.md containing E5-PLAN.", "1234567890."]
    assert enumerated_items("Do two things: first write a file, then read it.") == []


def test_a_paraphrased_no_work_item_is_rejected_in_place():
    """THE CONTRACT — fails before: the paraphrase describes work, the user's item does not."""
    e = _E(ASK)
    out = plan_action(e, "plan_task", {"title": "E5", "steps": [
        "Create plan_e5.md with the content E5-PLAN",
        "Acknowledge and process the numeric sequence 1234567890"]})
    assert out.get("ok"), out
    statuses = [s["status"] for s in e._turn_plan["steps"]]
    assert statuses == ["active", "rejected"], statuses
    assert out.get("rejected_steps"), out


def test_a_genuine_two_step_enumeration_is_untouched():
    """NEGATIVE — both user items describe work; nothing is rejected."""
    e = _E("Two steps. 1. Write plan.md containing PLAN. 2. Then read it back to me.")
    out = plan_action(e, "plan_task", {"title": "ok", "steps": ["Write plan.md", "Read plan.md back"]})
    assert [s["status"] for s in e._turn_plan["steps"]] == ["active", "pending"], out


def test_without_an_enumeration_the_model_steps_are_validated_as_before():
    """PRESERVE — no user enumeration: today's rule, on the candidates themselves."""
    e = _E("Please set up the project notes for me.")
    out = plan_action(e, "plan_task", {"title": "notes", "steps": ["Write notes.md", "1234567890"]})
    assert [s["status"] for s in e._turn_plan["steps"]] == ["active", "rejected"], out


def test_a_mismatched_count_falls_back_to_the_candidates():
    """VARIANT — the model made three steps of the user's two: no positional mapping, old rule."""
    e = _E(ASK)
    out = plan_action(e, "plan_task", {"title": "E5", "steps": [
        "Create plan_e5.md", "Write E5-PLAN into it", "Acknowledge the sequence 1234567890"]})
    assert out.get("ok"), out
    assert all(s["status"] != "rejected" for s in e._turn_plan["steps"])   # as before the change


def test_pt_enumeration_is_read_too():
    assert enumerated_items("Dois passos. 1) Escreve o plano.md com PLANO. 2) 1234567890.") == [
        "Escreve o plano.md com PLANO.", "1234567890."]
