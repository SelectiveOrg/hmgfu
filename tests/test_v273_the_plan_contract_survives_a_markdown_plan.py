"""95.75 — what the live session with gemma4:26b (61915ec3, 16/09 14:11) did to the plan contract.

P1  the model sent its plan as markdown, `plan_task({"plan": "[x] 0. Research…\\n[>] 2. Save…"})`.
    The argument-name and container drift were tolerated, the step TEXT was not: the steps were stored
    as "[x] 0. Research…". The model's own markers became part of the label, its declared statuses were
    silently dropped, and from then on the model and the system held different state — which is why the
    later turns narrate "[X] 0. …" in prose instead of calling update_plan.
P4  `update_plan(step_index=1, status="in_progress")` left step 0 active as well: the stored plan ends
    with two active steps. At most one step is active.
P5  after the user's new request superseded the plan and a new one was PROPOSED, update_plan answered
    "no active plan — call plan_task first". The plan is not missing; it is awaiting the user's yes.
P7  the post-condition refusal read as a permission problem: the model replied "the system blocked me…
    so I can proceed legally" and asked for a yes the user had already given. It is about EVIDENCE.
"""

from __future__ import annotations

from hmgfu.plans import plan_action


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
    def __init__(self, message="build me a weather widget"):
        self.session_plans = _Plans()
        self._turn_plan = None
        self._turn_proposed = False
        self._turn_session = "s1"
        self._turn_seq = 2
        self._turn_user_message = message
        self._turn_effects_allowed = True
        self._turn_prohibited = False
        self._turn_runbooks_shown = []
        self._turn_bandit = None
        self._turn_step_tools = []
        self.emitted = []

    def _emit(self, event):
        self.emitted.append(event)


THE_REAL_CALL = {"plan": "[x] 0. Research current weather data and design the HTML/JS structure for a weather widget.\n"
                         "[x] 1. Create the HTML, CSS, and JavaScript code for the Weather widget.\n"
                         "[>] 2. Save the weather widget as a new HTML file in the workspace.\n"
                         "[ ] 3. Verify the file exists and present it to the user."}


def test_a_markdown_plan_keeps_the_work_and_drops_the_markers():
    eng = _Engine()
    out = plan_action(eng, "plan_task", dict(THE_REAL_CALL))
    assert out.get("ok") and out["steps"] == 4, out
    texts = [s["text"] for s in eng._turn_plan["steps"]]
    assert not any(t.startswith("[") or t[:2].rstrip(".").isdigit() for t in texts), texts
    assert texts[0].startswith("Research current weather data"), texts[0]
    assert texts[2].startswith("Save the weather widget"), texts[2]


def test_the_models_own_checkmarks_never_mark_a_step_done():
    """[x] is a claim. Only a receipt can settle a step, so the plan starts with the work to do."""
    eng = _Engine()
    plan_action(eng, "plan_task", dict(THE_REAL_CALL))
    statuses = [s["status"] for s in eng._turn_plan["steps"]]
    assert "done" not in statuses, statuses
    assert statuses.count("active") == 1 and statuses[0] == "active", statuses


def test_bullets_and_numbers_are_normalised_too():
    eng = _Engine()
    plan_action(eng, "plan_task", {"steps": ["- 1. Write the file", "* Create the widget", "2) Verify it"]})
    assert [s["text"] for s in eng._turn_plan["steps"]] == ["Write the file", "Create the widget", "Verify it"]


def test_only_one_step_is_ever_active():
    eng = _Engine()
    plan_action(eng, "plan_task", {"steps": ["Write the file", "Create the widget", "Verify it"]})
    out = plan_action(eng, "update_plan", {"step_index": 1, "status": "in_progress"})
    assert out.get("ok"), out
    statuses = [s["status"] for s in eng._turn_plan["steps"]]
    assert statuses.count("active") == 1 and statuses[1] == "active", statuses
    assert statuses[0] == "pending", "the step left behind goes back to pending, not done"


def test_a_proposed_plan_is_not_a_missing_plan():
    eng = _Engine()
    out = plan_action(eng, "plan_task", {"steps": ["Rewrite the widget", "Verify the fix"], "status": "proposed"})
    assert out.get("proposed"), out
    out = plan_action(eng, "update_plan", {"step_index": 0, "status": "done"})
    msg = str(out.get("error", ""))
    assert "no active plan" not in msg, msg
    assert "yes" in msg.lower() or "approv" in msg.lower() or "confirm" in msg.lower(), msg


def test_the_refusal_says_evidence_not_permission():
    """The model read 'cannot be marked done' as a permission gate and asked for a second yes."""
    eng = _Engine()
    plan_action(eng, "plan_task", {"steps": ["Write weather_widget.html", "Verify it"]})
    out = plan_action(eng, "update_plan", {"step_index": 0, "status": "done"})
    msg = str(out.get("error", ""))
    assert not out.get("ok"), out
    assert "permission" in msg.lower() or "approval" in msg.lower(), \
        "the refusal must say it is not about authorisation: " + msg
