"""94.3 — a plan that could never be finished, and the user had to ask why.

From the first real-memory conversation (`0ad8e72e`). The receipt for `plan_task` (`ad87f6a89b12`)
carries its arguments verbatim:

    {"steps": [1234567890, "I will first research current weather trends and visual styles for
     stickers.", 2345678901, ...]}

`_step_text` turns anything into a step: `str(1234567890).strip()[:120]` is `"1234567890"`, which is
truthy, so it survives the filter. Step 0 of that plan was the literal string `"1234567890"`.

Nothing can ever produce a receipt matching it, so `update_plan` refused three times with a correct
post-condition error — *"step 0 cannot be marked done — no receipt of this turn matches the requested
action. Do the work, then call update_plan."* The guard was right and the plan was a deadlock, which
is exactly what the user asked about at turn 6: *"why is the task plan not showing finalized?"*

A step names something to DO. The test for that is not a list of phrases: it is whether the text
contains a word at all. A bare number, an id, or punctuation describes no work.

Junk steps are dropped rather than rejecting the whole call, because the rest of the plan was real and
refusing it would cost a turn for nothing; what was dropped is reported in the tool result so the
model sees it (Rule 10). If nothing survives, the existing "1–12 steps" error stands.
"""
from __future__ import annotations

import pytest

from hmgfu.plans import _describes_work, _step_text


# --- the exact arguments that produced the deadlock ---------------------------------------------------

REAL_CALL = [1234567890,
             "I will first research current weather trends and visual styles for stickers.",
             2345678901,
             "Then I will design the sticker."]


def test_the_integers_from_the_real_call_are_not_steps():
    junk = [s for s in REAL_CALL if not _describes_work(_step_text(s))]
    assert junk == [1234567890, 2345678901]


def test_the_real_steps_survive():
    kept = [_step_text(s) for s in REAL_CALL if _describes_work(_step_text(s))]
    assert kept == ["I will first research current weather trends and visual styles for stickers.",
                    "Then I will design the sticker."]


# --- what does and does not describe work --------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "write the fetch script",
    "Then I will design the sticker.",
    "create_widget: Valencia Weather Forecast",
    "correr o script",                     # PT: a step is a step in any language
    "e-mail the summary",
])
def test_these_describe_work(text):
    assert _describes_work(text)


@pytest.mark.parametrize("text", [
    "1234567890",
    "2345678901",
    "42",
    "3.14",
    "",
    "   ",
    "---",
    "...",
    "#1",
])
def test_these_do_not(text):
    assert not _describes_work(text)


def test_a_single_letter_token_is_not_a_description():
    """One stray character is not a step; two letters is the smallest word worth calling one."""
    assert not _describes_work("x")
    assert _describes_work("go now")


# --- end to end through the tool, with the real arguments ---------------------------------------------

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


def _plan_task(steps):
    from hmgfu.plans import plan_action
    return plan_action(_Engine(), "plan_task", {"steps": steps})


def test_the_real_call_produces_a_workable_plan():
    """94.3b superseded 94.3's drop-and-report: every entry is KEPT so indices and receipt bindings
    survive, and the unworkable ones are marked rejected in place. The plan reports all four entries,
    two of them rejected, rather than quietly becoming a two-step plan."""
    out = _plan_task(REAL_CALL)
    assert out.get("ok") and out["steps"] == 4, out


def test_it_says_which_entries_it_rejected():
    out = _plan_task(REAL_CALL)
    assert out.get("rejected_steps") == ["1234567890", "2345678901"], out
    assert "rejected" in out["hint"]


def test_a_clean_plan_reports_nothing_rejected():
    out = _plan_task(["fetch the weather", "build the widget"])
    assert out.get("ok") and "rejected_steps" not in out


def test_a_plan_of_nothing_but_junk_is_refused():
    out = _plan_task([1234567890, 2345678901])
    assert "error" in out and "describe work" in out["error"]
