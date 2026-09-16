"""94.4c — an approval must bind to the ACTION, the TARGET and the SESSION, not to a title.

The user's point 2: prove the correspondence between the proposal delivered and the action, target and
effects executed — not just that the titles match — and cover a changed proposal, a refusal, and a
different session.

`authority.py`'s docstring already claims the scope rule: *"an approved plan authorizes the tools its
steps name … when its steps name files, `write_file` may only touch those files."* A docstring is not
evidence, and this phase has already found two contracts that were declared and inert (`retract`
unreachable in `decide`; the judge's "no partial credit" comment that the code never checked). So the
claim is exercised here against the real `decide()` and the real `begin_turn()`.

These are TARGETED tests, as instructed. The integrated proof — that a live turn cannot execute
outside what was approved — belongs to the new pre-registered set, so this point stays PARTIAL.
"""
from __future__ import annotations

import pytest

from hmgfu.authority import decide
from hmgfu.session_plans import authorization_record, begin_turn, propose

SCHEMAS = {"create_widget": {}, "write_file": {}, "bash": {}, "read_file": {}, "memory_search": {}}


class _Tools:
    schemas = SCHEMAS


class _Store:
    def __init__(self):
        self.plans = {}

    def save(self, sid, plan):
        self.plans[sid] = dict(plan)

    def get(self, sid):
        return self.plans.get(sid)

    def pending(self, sid):
        p = self.plans.get(sid)
        return p if (p or {}).get("status") == "proposed" else None

    def resumable(self, sid):
        p = self.plans.get(sid)
        return p if (p or {}).get("status") in ("active", "proposed") else None

    def set_status(self, sid, status, reason=""):
        self.plans[sid]["status"] = status
        return dict(self.plans[sid])


class _Engine:
    def __init__(self, plan=None, message="", effects=True):
        self.tools = _Tools()
        self.session_plans = _Store()
        self._turn_plan = plan
        self._turn_proposed = False
        self._turn_seq = 5
        self._turn_user_message = message
        self._turn_effects_allowed = effects
        self._turn_prohibited = False
        self._turn_runbooks_shown = []
        self._turn_bandit = None
        self.receipts = None
        self.emitted = []

    def _emit(self, event):
        self.emitted.append(event)


def _approved(step_text):
    """A plan the USER approved, carrying a real authorization record."""
    return {"title": step_text[:80], "status": "active",
            "steps": [{"text": step_text, "status": "active"}],
            "authorization": authorization_record("user_approval", "yes", 4)}


# --- the ACTION the approval covers ---------------------------------------------------------------------

def test_the_approved_action_is_allowed():
    engine = _Engine(plan=_approved("create_widget: Valencia Weather"), effects=False)
    assert decide(engine, "create_widget", {"type": "weather"}).allowed


def test_a_different_action_is_not_carried_by_that_approval():
    """A yes to a widget is not a yes to writing a file."""
    engine = _Engine(plan=_approved("create_widget: Valencia Weather"), effects=False)
    got = decide(engine, "write_file", {"path": "notes.txt"})
    assert not got.allowed and "outside the approved plan" in got.reason


def test_a_read_needs_no_approval_at_all():
    engine = _Engine(plan=_approved("create_widget: Valencia Weather"), effects=False)
    assert decide(engine, "memory_search", {"query": "x"}).allowed


# --- the TARGET the approval covers ----------------------------------------------------------------------

def test_the_named_file_may_be_written():
    engine = _Engine(plan=_approved("write_file: fetch.py"), effects=False)
    assert decide(engine, "write_file", {"path": "fetch.py"}).allowed


def test_another_file_may_not():
    engine = _Engine(plan=_approved("write_file: fetch.py"), effects=False)
    got = decide(engine, "write_file", {"path": "secrets.env"})
    assert not got.allowed and "fetch.py" in got.reason


# --- a changed proposal ------------------------------------------------------------------------------------

def test_a_new_proposal_replaces_the_one_before_it():
    engine = _Engine(message="do the second thing")
    propose(engine, "s1", "create_widget: first", ["create_widget: first"], shown="widget? (yes/no)")
    propose(engine, "s1", "write_file: fetch.py", ["write_file: fetch.py"],
            shown="write_file: fetch.py? (yes/no)")
    begin_turn(engine, "s1", "yes")
    plan = engine.session_plans.get("s1")
    assert plan["steps"][0]["text"] == "write_file: fetch.py", "the yes approved a superseded proposal"
    assert plan["status"] == "active"


# --- a refusal ----------------------------------------------------------------------------------------------

def test_no_abandons_it():
    engine = _Engine(message="anything")
    propose(engine, "s1", "create_widget: x", ["create_widget: x"], shown="create_widget: x? (yes/no)")
    begin_turn(engine, "s1", "no")
    assert engine.session_plans.get("s1")["status"] == "abandoned"


def test_a_later_yes_does_not_resurrect_a_refused_proposal():
    engine = _Engine(message="anything")
    propose(engine, "s1", "create_widget: x", ["create_widget: x"], shown="create_widget: x? (yes/no)")
    begin_turn(engine, "s1", "no")
    begin_turn(engine, "s1", "yes")
    plan = engine.session_plans.get("s1")
    assert plan["status"] == "abandoned" and "authorization" not in plan


# --- a different session ---------------------------------------------------------------------------------------

def test_a_yes_in_another_session_does_not_approve_this_ones_proposal():
    engine = _Engine(message="anything")
    propose(engine, "s1", "create_widget: x", ["create_widget: x"], shown="create_widget: x? (yes/no)")
    begin_turn(engine, "other-session", "yes")
    plan = engine.session_plans.get("s1")
    assert plan["status"] == "proposed" and "authorization" not in plan


def test_and_the_proposal_is_still_answerable_in_its_own_session():
    engine = _Engine(message="anything")
    propose(engine, "s1", "create_widget: x", ["create_widget: x"], shown="create_widget: x? (yes/no)")
    begin_turn(engine, "other-session", "yes")
    begin_turn(engine, "s1", "yes")
    assert engine.session_plans.get("s1")["status"] == "active"


# --- a prohibition outranks an approval -------------------------------------------------------------------------

def test_a_prohibition_this_turn_closes_authority_even_with_an_approved_plan():
    engine = _Engine(plan=_approved("create_widget: x"), effects=False)
    engine._turn_prohibited = True
    assert not decide(engine, "create_widget", {"type": "note"}).allowed
