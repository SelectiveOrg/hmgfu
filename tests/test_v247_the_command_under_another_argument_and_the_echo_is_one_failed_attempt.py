"""95.60a + 95.60b (E2 on the chains, c95w16 rep3) — the one other string argument that is not the echo is
the command; an echoed request is one failed attempt like any other.

The model called bash four times with {"description": "ls", "command": "<the user's message>"}: the
echo guard refused each (the intended command sat under a name 95.9b's alias class did not hold), and
the four identical refusals were never cut because the echo branch came before the loop's guards; the
answer then came from the inline workspace block and no tool ever succeeded. Positive: the command is
taken from the one other string argument, whatever its name; the third identical echo is blocked.
Preserve: a plain echo with no other argument is still refused; two candidates decide nothing; the
named aliases still work; a short real command passes.
"""
from __future__ import annotations

import json

from hmgfu import tool_builtins
from tests.test_v2_agent import make_agent

MSG = "It must be under another name then - find the inventory file and read it."


def _tools(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    engine, fake = make_agent(tmp_path, [])
    engine._turn_user_message = MSG
    return engine, fake


def test_the_one_other_string_argument_is_the_command(tmp_path, monkeypatch):
    """THE CONTRACT (95.60a) — fails before: 'description' is not in the alias class."""
    engine, _ = _tools(tmp_path, monkeypatch)
    args = {"description": "ls", "command": MSG}
    assert engine.tools._echoes_the_request("bash", args) is None and args["command"] == "ls"
    args = {"cmd": "ls -F", "command": MSG}
    assert engine.tools._echoes_the_request("bash", args) is None and args["command"] == "ls -F"
    assert engine.tools._echoes_the_request("bash", {"command": MSG}) is not None
    assert engine.tools._echoes_the_request("bash", {"description": "ls", "cmd": "pwd", "command": MSG}) is not None
    assert engine.tools._echoes_the_request("bash", {"command": "ls"}) is None


def test_the_third_identical_echo_is_blocked(tmp_path, monkeypatch):
    """THE CONTRACT (95.60b) — fails before: four echoes, four refusals, none blocked."""
    echo = {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": MSG}}]}
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    engine, fake = make_agent(tmp_path, [echo, echo, echo, echo, {"content": "I could not run it.", "tool_calls": []}])
    events = []
    engine.agent_chat(MSG, explicit=False, session_id="s1", emit=lambda ev: events.append(ev))
    results = [ev for ev in events if ev.get("type") == "tool_result" and ev.get("name") == "bash"]
    assert len(results) >= 3, results
    assert not json.loads(results[0]["result"]).get("blocked") and not json.loads(results[1]["result"]).get("blocked")
    assert json.loads(results[2]["result"]).get("blocked"), results[2]
