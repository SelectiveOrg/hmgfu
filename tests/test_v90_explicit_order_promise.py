"""Phase 90.G1 — a promise on an EXPLICIT order must become execution, not a proposal. Live/DEV shape (after a proposal exchange in
another session the model answered 'I will create the three notes for you now.' with no tool): the say-do gate proposed and asked
"Shall I go ahead?" although the user had given an order and the turn's effects were allowed. With the existing single re-ask the
intent is executed; a suggestion turn (effects not allowed) still gets the proposal (Phase 67 permission-first rule unchanged)."""
from __future__ import annotations

from hmgfu.saydo import PROPOSAL_SUFFIX, enforce, transactions_of
from tests.test_v41_saydo_claims import _Stub

PROMISE = "I will create the three notes for you now."


def _engine(effects_allowed: bool):
    eng = _Stub(None, [])
    eng._turn_effects_allowed = effects_allowed
    eng._turn_user_message = ("Plan and create three text files note1.txt, note2.txt and note3.txt in the workspace." if effects_allowed
                              else "you can maybe create a widget to keep links")
    from types import SimpleNamespace
    store = {}
    eng.session_plans = SimpleNamespace(pending=lambda sid: None, save=lambda sid, plan: store.__setitem__(sid, plan), get=lambda sid: store.get(sid))
    eng._turn_session = "s1"
    return eng


def test_explicit_order_promise_is_executed_by_the_reask():
    eng = _engine(effects_allowed=True)
    tx = transactions_of([], [], None, 0, episode=True)
    calls = []
    def rerun(instr, required=None):
        calls.append(instr)
        return ("Done: note1.txt written.", [{"name": "write_file", "arguments": {"path": "note1.txt"}, "result": "ok"}])
    reply, trace, rep = enforce(eng, PROMISE, [], tx, "s1", eng._turn_user_message, rerun, 1)
    assert rep["action"] == "executed_intent" and trace and trace[0]["name"] == "write_file"
    assert PROPOSAL_SUFFIX not in reply and len(calls) == 1


def test_suggestion_turn_still_proposes():
    eng = _engine(effects_allowed=False)
    tx = transactions_of([], [], None, 0, episode=True)
    calls = []
    rerun = lambda instr, required=None: (calls.append(instr) or ("x", [{"name": "write_file", "arguments": {}, "result": "ok"}]))
    reply, trace, rep = enforce(eng, PROMISE, [], tx, "s1", eng._turn_user_message, rerun, 1)
    assert rep["action"] == "proposed" and PROPOSAL_SUFFIX in reply and calls == []


def test_explicit_order_that_still_does_nothing_after_the_reask_is_proposed_not_faked():
    eng = _engine(effects_allowed=True)
    tx = transactions_of([], [], None, 0, episode=True)
    rerun = lambda instr, required=None: ("I will do it shortly.", [])
    reply, trace, rep = enforce(eng, PROMISE, [], tx, "s1", eng._turn_user_message, rerun, 1)
    assert rep["action"] == "proposed" and PROPOSAL_SUFFIX in reply and trace == []
