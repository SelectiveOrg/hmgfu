"""Phase 52 — semantic action recovery for a misrouted command.

The nano/main router is non-deterministic (~1 in 4 it mislabels a clear imperative as a
declarative 'statement' with action_requested=False, offering zero tools → the L6 'not
proactive' failure). retrieve_tools_for_turn recovers the action from the HMG semantic tool
score for instruction/statement turns — but never for questions/greetings (which only match a
capability weakly and whose autobiographical context must be preserved). No Ollama — fake embedder.
"""

from __future__ import annotations

from hmgfu.retrieve import make_query_point
from hmgfu.tool_points import retrieve_tools_for_turn
from tests.test_v2_agent import make_agent


def _q(engine, text, conv_act):
    q = make_query_point(text, engine.embed, engine.sensitizer)
    q.action_requested = False          # the router DROPPED the action
    q.requested_tools = []
    q.conversation_act = conv_act
    return q


def test_statement_misroute_recovers_the_tool(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("tool_points_enabled", True)
    # a clear command the router mislabelled as a declarative statement
    q = _q(engine, "run a shell command in git bash to echo the marker", "statement")
    offered = [t["name"] for t in retrieve_tools_for_turn(engine.tools, engine, q, max_tools=8)]
    assert offered                        # recovered — tools offered despite action_requested=False
    assert q.action_requested is True     # recovery flips the flag so the agent ENFORCES the action


def test_question_is_not_force_tooled(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("tool_points_enabled", True)
    # a question must stay tool-free so its autobiographical memory is preserved (no identity regress)
    q = _q(engine, "what is my favourite colour and where do i live", "question")
    offered = retrieve_tools_for_turn(engine.tools, engine, q, max_tools=8)
    assert offered == []


def test_greeting_is_not_force_tooled(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("tool_points_enabled", True)
    q = _q(engine, "hello there how are you", "greeting")
    assert retrieve_tools_for_turn(engine.tools, engine, q, max_tools=8) == []
