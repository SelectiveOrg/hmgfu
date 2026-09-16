"""95.78 D1/D2 — the live session where two plain "yes" answers were dropped.

D1  turn 6 ended with "**Would you like me to rewrite the widget so it actually performs a fetch()
    request?**". The harness registers a proposal only from a first-person PROMISE ("I'll rewrite…"),
    so an offer in question form registered nothing. The user answered "yes" twice; both times
    plan_task was refused with "nothing is pending to confirm or refuse -- ask the user what they want
    done", which is the one instruction that guarantees the loop. Three refusals, two turns lost.
D2  the proposal the harness DOES synthesise takes a sentence of the model's prose as its step ("Since
    this requires fetching live data and designing the interface, I'll need to write the HTML…"). When
    the model then declared its real two steps, it was told a plan was already active, and
    update_plan(step=1) answered "step must be 0..0". A synthesised step is a placeholder for the work,
    not the work: the model's own declaration replaces it.
"""

from __future__ import annotations

from hmgfu.offers import register_offer
from hmgfu.plans import confirmation_without_pending, plan_action
from hmgfu.speech_act import offers_to_act

THE_REAL_OFFER = ("I cannot verify why you are seeing 18°C because that value does not appear in my "
                  "tool results. **Would you like me to rewrite the widget so it actually performs a "
                  "fetch() request to the Open-Meteo API using Valencia's coordinates?**")


class _Plans:
    def __init__(self):
        self.saved = None

    def save(self, sid, plan):
        self.saved = plan

    def get(self, sid):
        return self.saved

    def pending(self, sid):
        p = self.get(sid)
        return p if p and p.get("status") == "proposed" else None

    def resumable(self, sid):
        p = self.get(sid)
        return p if p and p.get("status") in ("approved", "active") else None

    def set_status(self, sid, status, reason=""):
        if self.saved:
            self.saved["status"] = status
        return self.saved


class _Engine:
    def __init__(self, message="yes"):
        self.session_plans = _Plans()
        self._turn_plan = None
        self._turn_proposed = False
        self._turn_session = "s1"
        self._turn_seq = 7
        self._turn_user_message = message
        self._turn_effects_allowed = True
        self._turn_prohibited = False
        self._turn_runbooks_shown = []
        self._turn_bandit = None
        self._turn_step_tools = []
        self.emitted = []

    def _emit(self, event):
        self.emitted.append(event)


def test_an_offer_in_question_form_is_an_offer():
    assert offers_to_act(THE_REAL_OFFER)
    assert offers_to_act("Shall I go ahead and build the widget?")
    assert offers_to_act("Queres que eu escreva o ficheiro?")


def test_a_question_that_offers_nothing_is_not_an_offer():
    assert not offers_to_act("Hello Teo! How are things going with you today?")
    assert not offers_to_act("The coordinates in that command are for Berlin, not Valencia.")
    assert not offers_to_act("What is the capital of Spain?")
    assert not offers_to_act("")


def test_the_offer_becomes_the_thing_a_yes_answers():
    eng = _Engine()
    assert register_offer(eng, "s1", THE_REAL_OFFER) is True
    pending = eng.session_plans.pending("s1")
    assert pending and pending["status"] == "proposed"
    assert "rewrite the widget" in (pending.get("proposed_as") or "").lower(), "the user's own reading is recorded"
    assert not confirmation_without_pending(eng, "s1"), "a yes now has an addressee"


def test_nothing_is_offered_twice():
    eng = _Engine()
    register_offer(eng, "s1", THE_REAL_OFFER)
    before = eng.session_plans.saved
    assert register_offer(eng, "s1", THE_REAL_OFFER) is False, "a pending offer is not replaced"
    assert eng.session_plans.saved is before


def test_the_models_own_steps_replace_the_placeholder():
    eng = _Engine(message="yes")
    register_offer(eng, "s1", THE_REAL_OFFER)
    plan = eng.session_plans.set_status("s1", "active")
    from hmgfu.session_plans import authorization_record
    plan["authorization"] = authorization_record("user_approval", "yes", 7)   # what begin_turn stamps on a yes
    eng._turn_plan = plan
    out = plan_action(eng, "plan_task", {"steps": [
        "Write the HTML, CSS, and JavaScript code for a sleek weather widget in a new file.",
        "Create the widget on the canvas from that file."]})
    assert out.get("ok") and not out.get("already_active"), out
    texts = [s["text"] for s in eng._turn_plan["steps"]]
    assert len(texts) == 2 and texts[0].startswith("Write the HTML"), texts
    assert eng._turn_plan.get("authorization"), "the approval the placeholder carried is kept"


def test_a_plan_the_model_declared_is_not_replaced():
    """The 67.11 guard still holds: only a placeholder gives way."""
    eng = _Engine(message="continue")
    plan_action(eng, "plan_task", {"steps": ["Write the file", "Create the widget"]})
    eng.session_plans.save("s1", dict(eng._turn_plan, status="active"))
    out = plan_action(eng, "plan_task", {"steps": ["Something else entirely"]})
    assert out.get("already_active"), out
    assert len(eng._turn_plan["steps"]) == 2


# --- end to end, through the real engine ---------------------------------------------------------

def _engine(tmp_path, script):
    from tests.test_v2_agent import make_agent
    engine, _ = make_agent(tmp_path, script)
    for k, v in {"grader_enabled": False, "workspace_dir": str(tmp_path), "plan_step_recall": False,
                 "thinking_mode": "off", "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(k, v)
    from hmgfu.tool_builtins import set_workspace
    set_workspace(str(tmp_path))
    return engine


def test_the_whole_exchange_no_longer_loops(tmp_path):
    """The live shape: the agent offers in question form, the user says yes once, and the work starts."""
    engine = _engine(tmp_path, [
        {"content": "The coordinates in that command are for Berlin. Would you like me to rewrite the "
                    "widget so it fetches live data for Valencia?", "tool_calls": []},
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"steps": [
            "Rewrite weather.html so it fetches live data.", "Create the widget from that file."]}}]},
        {"content": "Starting on it.", "tool_calls": []},
    ])
    sid = engine.sessions.create_session("offer")["id"]
    engine.agent_chat("why is it showing 18c?", session_id=sid)
    assert engine.session_plans.pending(sid) is not None, "the offer is what the yes will answer"

    r = engine.agent_chat("yes", session_id=sid)
    plan = engine.session_plans.get(sid)
    assert [s["text"] for s in plan["steps"]][0].startswith("Rewrite weather.html"), plan["steps"]
    assert len(plan["steps"]) == 2, plan["steps"]
    assert (plan.get("authorization") or {}).get("origin") == "user_approval", plan.get("authorization")
    refusals = [t for t in r["tool_trace"] if t["name"] == "plan_task" and t.get("failed")]
    assert not refusals, refusals
