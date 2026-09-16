"""95.6c (E8 c95c rep1) — a plan is born only from a request, and a clarification asks.

Rep1: step 0 the promise path delivered the clarification (95.6b fired) but the model's reply was an
imperative ("Please let me know what task...") with no question; step 1, on the QUESTION "what are
you working on for me right now?", the model's conditional promise ("once you tell me ... I'll create
a plan") was proposed as a plan whose step is that sentence. Same rule, one predicate wider: a bare
answer with nothing pending OR a question that asks for no effect and suggests none is a clarification
turn — no producer makes a plan on it, and the harness guarantees the clarification asks.
"""
from __future__ import annotations

from hmgfu.plans import plan_action
from hmgfu.saydo import CLARIFICATION_SUFFIX, PROPOSAL_SUFFIX, enforce, transactions_of
from hmgfu.plans import clarification_turn
from tests.test_v175_a_bare_yes_with_nothing_pending_makes_no_plan import _E as _PlanE
from tests.test_v186_no_plan_is_born_from_a_bare_yes_whoever_would_make_it import _E, _rerun

TX = transactions_of([], [], None, 0)
QUESTION = "what are you working on for me right now?"
PROMISE = ("I'm currently standing by! Just let me know what you'd like to tackle and I'll create a plan "
           "to track my progress.")


def test_a_question_about_state_makes_no_plan_and_the_reply_asks(tmp_path):
    """THE CONTRACT — fails before: the conditional promise becomes a proposed plan."""
    e = _E(tmp_path, QUESTION)
    reply, _t, report = enforce(e, PROMISE, [], TX, "s1", QUESTION, _rerun, 2)
    assert e.session_plans.get("s1") is None
    assert report.get("action") == "clarification" and reply.rstrip().endswith("?"), (report, reply)


def test_a_clarification_without_a_question_gets_one(tmp_path):
    e = _E(tmp_path, "yes")
    reply, _t, _r = enforce(e, "I apologize. Please let me know what specific task you would like me to work on "
                               "and I will get started.", [], TX, "s1", "yes", _rerun, 2)
    assert reply.endswith(CLARIFICATION_SUFFIX), reply


def test_a_clarification_that_already_asks_is_left_alone(tmp_path):
    e = _E(tmp_path, "yes")
    reply, _t, _r = enforce(e, "I will help once I know the task. What would you like me to do?", [], TX, "s1", "yes", _rerun, 2)
    assert CLARIFICATION_SUFFIX not in reply and reply.count("?") == 1


def test_a_suggestion_phrased_as_a_question_is_still_proposed(tmp_path):
    e = _E(tmp_path, "can you tidy the notes folder?")
    reply, _t, report = enforce(e, "I will tidy the notes folder for you.", [], TX, "s1",
                                "can you tidy the notes folder?", _rerun, 2)
    assert report.get("action") == "proposed" and reply.endswith(PROPOSAL_SUFFIX)


def test_plan_task_on_an_information_request_still_plans():
    """plan_task keeps 95.6b only: "tell me a curious fact" is planned work (the full suite caught the
    wider gate on test_plan_task_capped_to_one_declaration_per_turn)."""
    e = _PlanE("Tell me a curious fact.")
    out = plan_action(e, "plan_task", {"steps": ["pick topic", "verify", "write it"]})
    assert "error" not in out and e._turn_plan is not None, out


def test_an_order_is_not_a_clarification_turn(tmp_path):
    e = _E(tmp_path, "tidy the notes folder now")
    assert clarification_turn(e, "s1") is False
