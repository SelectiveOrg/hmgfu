"""95.40 (X1 rep1 on 3c35b50 and 62d1d7d, E2 rep1 on 991c208) — a request echoed as a command is not a
command: it has no effect to authorise, and a short question is one too.

Three ask turns called withheld `bash` with the user's message as the command. The dispatch's echo
guard (95.9) fired only on messages >= 40 chars and ran after the loop's authority judgement, so "what
is in project.txt?" was blocked as a side effect "needing the user's confirmation" and the model asked
permission to read instead of reading. Positive: the short question echoed as the command is refused
as "not a command" by the dispatch, and the loop's dispatch step refuses it before the authority guard
(no "confirmation" block); a short request ("list the workspace") is an echo too. Negative: a short REAL
command the user typed ("ls", "echo hi") still runs; a long prefix is still refused (v184 kept); a
short STATEMENT echoed as a command is refused as not a command (95.64: its first word is no program on this host).
"""
from __future__ import annotations

import json

from tests.test_v2_agent import make_agent

ASK = "what is in project.txt?"


def _engine(tmp_path, message):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_user_message = message
    return engine


def test_a_short_question_echoed_as_the_command_is_refused_as_not_a_command(tmp_path):
    """THE CONTRACT — fails before: the 40-char threshold lets it through to the authority."""
    engine = _engine(tmp_path, ASK)
    out = json.loads(engine.tools.execute_tool("bash", {"command": ASK}))
    assert out.get("error") and "not a shell command" in out["error"], out
    assert engine.tools.echoes_the_request("bash", {"command": ASK}) is not None


def test_a_short_real_command_is_untouched_and_a_short_request_is_an_echo(tmp_path):
    for cmd in ("ls", "echo hi", "cat project.txt"):                     # the user typed a command: it runs
        engine = _engine(tmp_path, cmd)
        assert engine.tools.echoes_the_request("bash", {"command": cmd}) is None, cmd
    engine = _engine(tmp_path, "list the workspace")                     # a request (speech_act reads it as one), echoed
    assert engine.tools.echoes_the_request("bash", {"command": "list the workspace"}) is not None
    engine = _engine(tmp_path, "The weather is grey today.")            # 95.64: a statement is no command either --
    out = engine.tools.echoes_the_request("bash", {"command": "The weather is grey today."})   # refused with the true
    assert out is not None and "not a shell command" in out                                     # reason, not left to the authority


def test_the_loop_refuses_the_echo_before_the_authority_guard(tmp_path):
    """The blocked-as-side-effect outcome is what the traces showed; after 95.40 the echo answers first."""
    from hmgfu.tool_loop import run_tool_loop
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"id": "t1", "name": "bash", "arguments": {"command": ASK}}]},
        {"content": "I could not run that.", "tool_calls": []},
    ])
    engine._turn_user_message = ASK
    engine._turn_effects_allowed = False
    engine._turn_prohibited = False
    engine._turn_plan = None
    engine._turn_step_tools = []
    engine._turn_unconfirmed_effects = []
    messages = [{"role": "user", "content": ASK}]
    schemas = [engine.tools.schemas["read_file"]]
    _reply, trace, _fin = run_tool_loop(engine, messages, schemas, native=True, turn_seq=1)
    bash = [t for t in trace if t["name"] == "bash"]
    assert bash and "not a shell command" in bash[0]["result"] and not bash[0].get("blocked"), bash
