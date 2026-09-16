"""94.4 — the reply proposed a Python script; the "yes" activated a widget.

The demonstrated case, from session `5314a8a1` (2026-09-12), not the sticker/widget one:

  turn 3, delivered to the user:
      "…would you like me to write a small Python script using that API endpoint so you can run it
       locally to get real-time updates for Valencia? Shall I go ahead with this? (yes / no)"
  turn 4, the user: "yes"
  the plan that "yes" activated:
      {"title": "create_widget: Valencia Weather Forecast",
       "authorization": {"origin": "user_approval", "message": "yes", "turn_seq": 4}}

`saydo.enforce` builds the proposal from `_turn_unconfirmed_effects` — the tool calls the model
ATTEMPTED and that were blocked — and titles it from the first of them. The reply is what the user
reads; the blocked attempt is what gets recorded. When the model says one thing and reaches for
another, the user's "yes" lands on the reach.

The plan already stores `request` (the user's own words that produced it). What it never stored is
what was actually SHOWN. So `propose()` records that, and an approval is only an approval of a step
the delivered proposal can be recognised in.

The asymmetry is deliberate: when the two do not match, the cost of being wrong is one clarifying
question, and the cost of being wrong the other way is an unauthorised side effect. So a mismatch
asks.
"""
from __future__ import annotations

import pytest

from hmgfu.session_plans import begin_turn, propose

SHOWN_SCRIPT = ("I cannot execute curl directly. Would you like me to write a small Python script "
                "using that API endpoint so you can run it locally? Shall I go ahead? (yes / no)")
SHOWN_WIDGET = ("I can put a weather widget on your canvas for Valencia. "
                "Shall I go ahead and create the widget? (yes / no)")
STEP = "create_widget: Valencia Weather Forecast"


class _Store:
    def __init__(self):
        self.plan = None

    def save(self, session_id, plan):
        self.plan = dict(plan)

    def get(self, session_id):
        return self.plan

    def pending(self, session_id):
        return self.plan if (self.plan or {}).get("status") == "proposed" else None

    def resumable(self, session_id):
        return self.plan if (self.plan or {}).get("status") in ("active", "proposed") else None

    def set_status(self, session_id, status, reason=""):
        self.plan["status"] = status
        return dict(self.plan)


class _Engine:
    def __init__(self, user_message=""):
        self.session_plans = _Store()
        self._turn_plan = None
        self._turn_proposed = False
        self._turn_seq = 4
        self._turn_user_message = user_message
        self._turn_runbooks_shown = []
        self._turn_bandit = None
        self.receipts = None
        self.emitted = []

    def _emit(self, event):
        self.emitted.append(event)


def _proposed(shown):
    engine = _Engine("try this: curl https://api.open-meteo.com/...")
    propose(engine, "s1", STEP[:80], [STEP], shown=shown)
    return engine


# --- what the plan must carry -----------------------------------------------------------------------

def test_the_plan_records_what_was_actually_shown():
    engine = _proposed(SHOWN_SCRIPT)
    assert "Python script" in (engine.session_plans.get("s1") or {}).get("proposed_as", "")


# --- the demonstrated defect --------------------------------------------------------------------------

def test_yes_does_not_activate_a_step_the_proposal_never_mentioned():
    engine = _proposed(SHOWN_SCRIPT)
    block = begin_turn(engine, "s1", "yes")
    plan = engine.session_plans.get("s1")
    assert plan["status"] != "active", "a widget was authorised by a yes to a Python script"
    assert "authorization" not in plan


def test_and_it_asks_instead_of_silently_doing_nothing():
    engine = _proposed(SHOWN_SCRIPT)
    block = begin_turn(engine, "s1", "yes")
    assert block and "?" in block, block


# --- the control: when they match, yes still works exactly as before ------------------------------------

def test_yes_activates_a_step_the_proposal_did_describe():
    engine = _proposed(SHOWN_WIDGET)
    begin_turn(engine, "s1", "yes")
    plan = engine.session_plans.get("s1")
    assert plan["status"] == "active", "a matching proposal must still be approvable"
    assert plan["authorization"]["origin"] == "user_approval"


def test_no_still_declines_whatever_was_shown():
    engine = _proposed(SHOWN_SCRIPT)
    begin_turn(engine, "s1", "no")
    assert engine.session_plans.get("s1")["status"] == "abandoned"


def test_a_plan_without_a_shown_proposal_behaves_as_it_always_did():
    """Rule 11: plans persisted before this existed carry no `proposed_as` and must still approve."""
    engine = _Engine("do the thing")
    propose(engine, "s1", STEP[:80], [STEP])
    begin_turn(engine, "s1", "yes")
    assert engine.session_plans.get("s1")["status"] == "active"


@pytest.mark.parametrize("shown", [SHOWN_WIDGET, SHOWN_SCRIPT])
def test_the_check_never_invents_an_authorization(shown):
    """Whatever it decides, it must not mint an approval the user did not give."""
    engine = _proposed(shown)
    begin_turn(engine, "s1", "what were we talking about?")
    plan = engine.session_plans.get("s1")
    assert "authorization" not in plan and plan["status"] == "proposed"


# --- 94.4b: the mismatch is prevented, not merely detected --------------------------------------------
#
# Detecting it afterwards means guessing whether prose describes a tool call, and that guess bounced a
# legitimate yes in v46 (reply "A note." against step "create_widget: Unasked"). Naming the step in the
# question removes the mismatch instead: what is shown and what is stored agree by construction, and
# the user can see what they are agreeing to. The detector stays as the net for proposals that come
# from somewhere else.

def test_the_question_names_the_action_instead_of_saying_this():
    from hmgfu.saydo import _proposal_suffix
    asked = _proposal_suffix(["create_widget: Valencia Weather Forecast"])
    assert "create_widget: Valencia Weather Forecast" in asked
    assert "with this?" not in asked


def test_a_proposal_that_names_its_step_is_approvable():
    engine = _proposed("I can do that." + __import__("hmgfu.saydo", fromlist=["x"])
                       ._proposal_suffix([STEP]))
    begin_turn(engine, "s1", "yes")
    assert engine.session_plans.get("s1")["status"] == "active"


def test_several_steps_are_all_named():
    from hmgfu.saydo import _proposal_suffix
    asked = _proposal_suffix(["write_file: fetch.py", "bash: python fetch.py"])
    assert "write_file: fetch.py" in asked and "bash: python fetch.py" in asked


def test_no_steps_falls_back_to_the_old_wording():
    from hmgfu.saydo import PROPOSAL_SUFFIX, _proposal_suffix
    assert _proposal_suffix([]) == PROPOSAL_SUFFIX
