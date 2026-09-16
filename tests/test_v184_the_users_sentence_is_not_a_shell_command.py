"""95.9 — a published value has evidence; a request echoed as a command produces none (guide §8).

Reproduced live (E7, 0/3 both arms, X6 rep2): asked *"Show me a metric widget with the number of
widget-B in the workspace inventory."*, the model passed that sentence to `bash` — twice, "Show:
command not found" — the retry-storm guard then blocked the tool for the turn, the provenance guard
refused a valueless widget, and the reply admitted it had no number. The guards downstream were right;
the boundary that let the turn burn its two attempts on a non-command is the dispatch, which knows
the turn's message and could see that the "command" WAS it.

Invariant: the user's request is never a shell command. Structural, no phrase list: equality with the
turn's message (or a long prefix of it) at the one dispatch point. A genuine command that happens to
be short is untouched (the rule needs a sentence-length message).
"""
from __future__ import annotations

import json

import pytest

from tests.test_v2_agent import make_agent

ASK = "Show me a metric widget with the number of widget-B in the workspace inventory."


def _engine(tmp_path, message=ASK):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_user_message = message
    return engine


def test_the_users_sentence_is_refused_as_a_command(tmp_path):
    """THE CONTRACT — fails before: bash runs the sentence and reports 'Show: command not found'."""
    engine = _engine(tmp_path)
    out = json.loads(engine.tools.execute_tool("bash", {"command": ASK}))
    assert out.get("error") and "command" in out["error"].lower(), out
    assert "stdout" not in out


def test_a_long_prefix_of_the_sentence_is_refused_too(tmp_path):
    engine = _engine(tmp_path)
    out = json.loads(engine.tools.execute_tool("bash", {"command": ASK[:48]}))
    assert out.get("error"), out


def test_a_real_command_still_runs(tmp_path):
    engine = _engine(tmp_path)
    out = json.loads(engine.tools.execute_tool("bash", {"command": "echo VEGA-OK"}))
    assert "VEGA-OK" in out.get("stdout", ""), out


def test_a_short_message_that_is_a_command_is_not_refused(tmp_path):
    """NEGATIVE — the user typed a command and the model ran it: 'ls' is both, and it must run."""
    engine = _engine(tmp_path, message="ls")
    out = json.loads(engine.tools.execute_tool("bash", {"command": "ls"}))
    assert not out.get("error"), out


def test_no_turn_message_no_rule(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_user_message = ""
    out = json.loads(engine.tools.execute_tool("bash", {"command": "echo hi"}))
    assert "hi" in out.get("stdout", ""), out
