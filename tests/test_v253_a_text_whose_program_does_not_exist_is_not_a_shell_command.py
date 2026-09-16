"""95.64 (X1 on v4 w17 rep2 and on v3 w18 rep2) — a bash call whose first program is not a program on this host
is not a shell command.

On a read question the model put a prose sentence in the bash command ("Read the content of the file project.txt
to answer the user's question ..."); the authority refused it as a side effect needing confirmation, so the model
asked permission instead of reading. Positive: the call is refused as "not a shell command" with the program
named, before the authority, and the loop counts it as one failed attempt (the third repetition is cut).
Preserve: real commands, builtins, env-prefixed commands and paths pass to the authority as before; the echo
guard still refuses the user's own message.
"""
from __future__ import annotations

import json

from hmgfu import tool_builtins
from hmgfu.toolsys import _first_program, _is_program
from tests.test_v2_agent import make_agent

PROSE = "Read the content of the file project.txt to answer the user's question about its contents."
ASK = "what is in project.txt?"


def _tools(tmp_path, monkeypatch, msg=ASK):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    engine, fake = make_agent(tmp_path, [])
    engine._turn_user_message = msg
    return engine, fake


def test_a_prose_sentence_is_not_a_shell_command(tmp_path, monkeypatch):
    """THE CONTRACT — fails before: the prose goes to the authority and is 'a side effect'."""
    engine, _ = _tools(tmp_path, monkeypatch)
    out = engine.tools.echoes_the_request("bash", {"command": PROSE, "description": PROSE})
    assert out is not None and "not a shell command" in json.loads(out)["error"] and "'Read'" in json.loads(out)["error"], out
    assert _first_program("Count the lines in contagem.txt") == "Count" and not _is_program("Count")
    assert _first_program("FOO=1 BAR=x cat a.txt") == "cat" and _is_program("cat")


def test_real_commands_builtins_and_paths_pass_and_the_echo_still_refuses(tmp_path, monkeypatch):
    engine, _ = _tools(tmp_path, monkeypatch)
    for c in ("wc -l < contagem.txt", "ls -F && cd x", "cd Desktop && echo x > f", "FOO=1 cat a.txt", "./script.sh --x",
              "/usr/bin/env python x.py", "grep -c '' a.txt | sort", "echo \"print('X')\" > x.py", "[ -f a ] && cat a"):
        assert engine.tools.echoes_the_request("bash", {"command": c}) is None, c
    engine2, _ = _tools(tmp_path, monkeypatch, msg="Show me the inventory file and tell me what the checksum line says please")
    assert engine2.tools.echoes_the_request("bash", {"command": "Show me the inventory file and tell me what the checksum line says please"}) is not None


def test_the_third_identical_prose_call_is_cut(tmp_path, monkeypatch):
    prose = {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": PROSE}}]}
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    engine, _ = make_agent(tmp_path, [prose, prose, prose, {"content": "I could not read it.", "tool_calls": []}])
    events = []
    engine.agent_chat(ASK, explicit=False, session_id=engine.sessions.create_session()["id"], emit=lambda ev: events.append(ev))
    results = [json.loads(ev["result"]) for ev in events if ev.get("type") == "tool_result" and ev.get("name") == "bash"]
    assert len(results) >= 3 and "not a shell command" in (results[0].get("error") or "") and results[2].get("blocked"), results
