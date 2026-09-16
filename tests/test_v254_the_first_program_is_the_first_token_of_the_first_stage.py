"""95.64b (X2 on v5, d95w19v5 rep2) — the first program of a command is the first token of its FIRST STAGE.

`ls; cd Desktop && touch ola_ibis.py` was refused as "not a shell command": 95.64's first-program reader took
"ls;" (the separator glued to the token), `which` found nothing, and a real command failed — a regression of
95.64. Positive: the command is split at ; && || | and newlines before the token is read. Preserve: a prose
sentence is still refused; env-prefixed commands and paths still pass.
"""
from __future__ import annotations

from hmgfu import tool_builtins
from hmgfu.toolsys import _first_program
from tests.test_v2_agent import make_agent


def test_the_separator_does_not_glue_to_the_program(tmp_path, monkeypatch):
    """THE CONTRACT — fails before: 'ls;' is read as the program."""
    assert _first_program("ls; cd Desktop && touch ola_ibis.py") == "ls"
    assert _first_program("ls;cd x") == "ls"
    assert _first_program("cat a.txt | wc -l") == "cat"
    assert _first_program("cd Desktop && echo x > f") == "cd"
    assert _first_program("true || echo no") == "true"
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    engine, _ = make_agent(tmp_path, [])
    engine._turn_user_message = "Faz um script Python, ola_ibis.py, na area de trabalho, que imprime IBIS-OK."
    assert engine.tools.echoes_the_request("bash", {"command": "ls; cd Desktop && touch ola_ibis.py"}) is None
    assert engine.tools.echoes_the_request("bash", {"command": "Read the file project.txt; then tell me."}) is not None
    assert _first_program("FOO=1 ls; cd x") == "ls" and _first_program("./run.sh; ls") == "./run.sh"
