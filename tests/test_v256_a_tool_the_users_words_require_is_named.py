"""95.47d (X1 on v4, d95w19v4 rep1) — a tool the user's own words require is NAMED, even when the message refers
to the user.

"Save the name of my main project into a workspace file called trabalho.txt." — write_file was explicit (95.47)
and offered, the model wrote the file with a bash redirect, and 95.47b did not re-ask: `forced` excludes a
requested tool when the message refers to the user ("my main project", 65.2's autobiographical rule), so nothing
was required. Positive: tool_points records the explicit tools on the query point; plan_turn_actions forces them
as named; after a bash write the loop asks once for the native write. Preserve: a router pin on a self-referring
message is still not forced (65.2); a question is still not forced (95.37).
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.models import QueryPoint
from hmgfu.tool_points import retrieve_tools_for_turn
from hmgfu.turn_events import plan_turn_actions
from tests.test_v2_agent import fake_embed, make_agent

SAVE = "Save the name of my main project into a workspace file called trabalho.txt."


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def _q(text, **kw):
    base = dict(text=text, embedding=fake_embed(text), intent="task", conversation_act="instruction", action_requested=True)
    base.update(kw)
    return QueryPoint(**base)


def test_the_named_file_forces_the_native_write_on_a_self_referring_message(ws, tmp_path):
    """THE CONTRACT — fails before: the query point carries no explicit tools and write_file is not forced."""
    engine, _ = make_agent(tmp_path, [])
    engine._turn_step_tools = []
    q = _q(SAVE)
    schemas = retrieve_tools_for_turn(engine.tools, engine, q, max_tools=4)
    assert "write_file" in q.explicit_tools, q.explicit_tools
    _r, forced, _ = plan_turn_actions(engine, q, SAVE, [s["name"] for s in schemas], [])
    assert "write_file" in forced, forced


def test_a_bash_write_on_that_message_is_re_asked_for_the_native_write(ws, tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo \"Tamarin\" > trabalho.txt"}}]},
        {"content": "Saved.", "tool_calls": []},
        {"content": "", "tool_calls": [{"name": "write_file", "arguments": {"path": "trabalho.txt", "content": "Tamarin"}}]},
        {"content": "Saved Tamarin into trabalho.txt.", "tool_calls": []}])
    engine.facts.apply_all("My main project is called Tamarin.", "user_explicit", session="s0")
    r = engine.agent_chat(SAVE, explicit=False, session_id=engine.sessions.create_session()["id"])
    assert "write_file" in [t["name"] for t in r["tool_trace"]]
    assert any("ACTION REQUIRED" in str(m.get("content", "")) for call in fake.calls for m in call["messages"])


def test_a_router_pin_on_a_self_referring_message_and_a_question_stay_unforced(ws, tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_step_tools = []
    q = _q("Tell me about my main project.", requested_tools=["brave_web_search"], explicit_tools=[])
    _r, forced, _ = plan_turn_actions(engine, q, "Tell me about my main project.", ["brave_web_search"], [])
    assert forced == []
    q2 = _q("What does trabalho.txt say?", conversation_act="question", requested_tools=["read_file"], explicit_tools=["read_file"])
    _r, forced2, _ = plan_turn_actions(engine, q2, "What does trabalho.txt say?", ["read_file"], [])
    assert forced2 == ["read_file"]                    # a NAMED tool is required even on a question (66.5); a read is a means (95.47b)
