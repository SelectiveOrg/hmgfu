"""94.3b — dropping a bad step shifted every index after it, and let a REDUCED request finish as "done".

94.3 removed steps that describe no work. That was half right and half wrong, and the wrong half is
the dangerous one:

  * `receipts.consume(ids, step_index)` binds a receipt to a step INDEX. Dropping step 0 renumbers
    everything after it, so a receipt recorded against index 2 now certifies a different step.
  * `finalize_status` returns "done" when every SURVIVING step is done. Drop two of four and finish
    the other two, and the plan reports done — the user asked for four things and was told the task
    was complete.

So nothing is dropped. An entry that describes no work stays exactly where it is, marked `rejected`
with the reason, and the plan can never be "done" while one is there: the scope that was not executed
is declared, in the plan and in the pinned block the model reads.

On what "describes work" can and cannot prove — stated rather than implied: the letters rule catches
the demonstrated case (`1234567890`), and it does NOT catch lettered nonsense like "asdfgh qwerty".
That is not detectable lexically without a word list, and a word list is what this project refuses.
What protects the user there is the existing post-condition: such a step can never be marked done,
because no receipt will match it. The test below asserts that limit openly instead of pretending the
validator is cleverer than it is.
"""
from __future__ import annotations

import pytest

from hmgfu.plans import _describes_work, plan_action
from hmgfu.session_plans import finalize_status, pinned_block

MIXED = [1234567890,
         "I will first research current weather trends and visual styles for stickers.",
         2345678901,
         "Then I will design the sticker."]


class _Plans:
    def __init__(self):
        self.saved = None

    def save(self, sid, plan):
        self.saved = plan

    def get(self, sid):
        return self.saved

    def pending(self, sid):
        return None

    def resumable(self, sid):
        return None


class _Engine:
    def __init__(self):
        self.session_plans = _Plans()
        self._turn_plan = None
        self._turn_proposed = False
        self._turn_session = "s1"
        self._turn_seq = 3
        self._turn_user_message = "create a weather sticker for me"
        self._turn_effects_allowed = True
        self._turn_prohibited = False
        self._turn_runbooks_shown = []
        self._turn_bandit = None
        self.emitted = []

    def _emit(self, event):
        self.emitted.append(event)


def _planned(steps=MIXED):
    engine = _Engine()
    out = plan_action(engine, "plan_task", {"steps": steps})
    return engine, out


# --- indices survive ----------------------------------------------------------------------------------

def test_every_entry_keeps_its_position():
    engine, _ = _planned()
    texts = [s["text"] for s in engine._turn_plan["steps"]]
    assert texts[0] == "1234567890" and texts[2] == "2345678901"
    assert len(texts) == 4, "an entry was dropped and every later index moved with it"


def test_the_real_steps_are_still_at_the_indices_the_model_will_use():
    engine, _ = _planned()
    steps = engine._turn_plan["steps"]
    assert steps[1]["text"].startswith("I will first research")
    assert steps[3]["text"].startswith("Then I will design")


def test_the_entries_that_describe_no_work_are_marked_rejected_with_a_reason():
    engine, _ = _planned()
    steps = engine._turn_plan["steps"]
    assert steps[0]["status"] == "rejected" and steps[2]["status"] == "rejected"
    assert "no work" in (steps[0].get("note") or "").lower()


def test_the_valid_steps_are_workable():
    engine, _ = _planned()
    steps = engine._turn_plan["steps"]
    assert steps[1]["status"] == "active"
    assert steps[3]["status"] == "pending"


# --- the reduced request must never report done ---------------------------------------------------------

def test_a_plan_holding_a_rejected_step_can_never_be_done():
    engine, _ = _planned()
    for s in engine._turn_plan["steps"]:
        if s["status"] != "rejected":
            s["status"] = "done"
    assert finalize_status(engine._turn_plan) != "done"


def test_and_it_says_so_as_partial():
    engine, _ = _planned()
    for s in engine._turn_plan["steps"]:
        if s["status"] != "rejected":
            s["status"] = "done"
    assert finalize_status(engine._turn_plan) == "partial"


def test_the_pinned_block_declares_what_was_not_executed():
    engine, _ = _planned()
    block = pinned_block(engine._turn_plan)
    assert "rejected" in block.lower() or "not executed" in block.lower(), block


def test_a_clean_plan_still_reaches_done():
    """The control: rejecting must not make an honest plan uncompletable."""
    engine, _ = _planned(["fetch the weather", "build the widget"])
    for s in engine._turn_plan["steps"]:
        s["status"] = "done"
    assert finalize_status(engine._turn_plan) == "done"


# --- the model cannot mark a rejected entry done ----------------------------------------------------------

def test_update_plan_refuses_a_rejected_index():
    engine, _ = _planned()
    out = plan_action(engine, "update_plan", {"step": 0, "status": "done"})
    assert "error" in out and "rejected" in out["error"].lower(), out


# --- the limit, asserted rather than hidden ----------------------------------------------------------------

@pytest.mark.parametrize("text", ["asdfgh qwerty", "lorem ipsum dolor"])
def test_lettered_nonsense_is_NOT_caught_and_that_is_documented(text):
    """Not detectable without a word list, which this project refuses. The post-condition is what
    stops it: such a step can never be marked done, because no receipt will ever match it."""
    assert _describes_work(text), "if this ever changes, the docstring above must change with it"
