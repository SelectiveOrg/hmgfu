"""95.37 (H-APOLOGY: E2 rep1 step 2, L1 rep3 step 3 on 991c208) — on a question, a router-requested
tool the user did not name is offered, never REQUIRED.

Both ask turns ("what is the checksum line?", "what does ACME-7 mean?") were routed
conversation_act=question, action_requested=true, requested_tools=[bash]; plan_turn_actions FORCED
bash, the model answered in prose, the loop rejected it ("ACTION REQUIRED ... Call one of these
applicable tools now: bash") and the model's reply to that nudge — an apology about bash — was
published as the answer. Positive: on a question the requested tool stays offered and nothing is
forced. Negative: a tool the user NAMES on a question is still forced (v37's rule case); an
instruction still forces; an approved step's tool (67.12) is still forced on a question.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from hmgfu.turn_events import plan_turn_actions
from tests.test_v2_agent import make_agent


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_step_tools = []
    return engine


def _q(act, tools=("bash",)):
    return NS(requested_tools=list(tools), action_requested=True, extractor="nano", needs_memory=False,
              conversation_act=act, directive=None)


def test_a_question_offers_the_requested_tool_and_forces_nothing(tmp_path):
    """THE CONTRACT — fails before: bash is forced and the loop demands it."""
    e = _engine(tmp_path)
    requested, forced, _ = plan_turn_actions(e, _q("question"), "what is the checksum line?", ["bash", "read_file"], [])
    assert requested == ["bash"] and forced == []
    requested, forced, _ = plan_turn_actions(e, _q("question"), "what does ACME-7 mean?", ["bash"], [])
    assert requested == ["bash"] and forced == []


def test_a_tool_the_user_names_on_a_question_is_still_forced(tmp_path):
    e = _engine(tmp_path)
    _r, forced, _ = plan_turn_actions(e, _q("question"), "how many lines does ledger.txt have? use bash", ["bash"], [])
    assert forced == ["bash"]


def test_an_instruction_still_forces_and_a_step_tool_stays_forced(tmp_path):
    e = _engine(tmp_path)
    _r, forced, _ = plan_turn_actions(e, _q("instruction"), "Read the inventory file and tell me the checksum line.", ["bash"], [])
    assert forced == ["bash"]
    e._turn_step_tools = ["read_file"]
    _r, forced, _ = plan_turn_actions(e, _q("question", tools=()), "and the checksum line?", ["read_file"], [])
    assert forced == ["read_file"]
