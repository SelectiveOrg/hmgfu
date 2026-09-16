"""95.47b (X2 on v4, d95w18v4 rep1) — a required WRITE is satisfied only by itself; a required read is a means.

"Cria um script Python chamado ola_tamarin.py na area de trabalho que imprime TAMARIN-OK." — write_file was
required (95.47) and the model wrote the file with a bash redirect; the loop re-asked only when NOTHING had
run, so the native write whose receipt proves a creation never ran and the judge saw no write_file.
Positive: after a bash write the loop asks once for the required write and the model calls it. Preserve: a
required read satisfied by a bash `cat` is not re-asked; a turn with no required tool is untouched.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from tests.test_v2_agent import make_agent

CREATE = "Cria um script Python chamado ola_tamarin.py na area de trabalho que imprime TAMARIN-OK."
BASH_WRITE = {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo \"print('TAMARIN-OK')\" > ola_tamarin.py"}}]}
NATIVE_WRITE = {"content": "", "tool_calls": [{"name": "write_file", "arguments": {"path": "ola_tamarin.py", "content": "print('TAMARIN-OK')\n"}}]}
REPORT = {"content": "Criei o ola_tamarin.py com o texto TAMARIN-OK.", "tool_calls": []}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def _asked(fake):
    return any("ACTION REQUIRED" in str(m.get("content", "")) for call in fake.calls for m in call["messages"])


def test_a_bash_write_does_not_meet_a_required_write_file(ws, tmp_path):
    """THE CONTRACT — fails before: the bash write satisfies the requirement and no re-ask happens."""
    engine, fake = make_agent(tmp_path, [BASH_WRITE, REPORT, NATIVE_WRITE, REPORT])
    r = engine.agent_chat(CREATE, explicit=False, session_id=engine.sessions.create_session()["id"])
    names = [t["name"] for t in r["tool_trace"]]
    assert _asked(fake) and "write_file" in names, (names, _asked(fake))
    assert (tmp_path / "ola_tamarin.py").read_text(encoding="utf-8").strip() == "print('TAMARIN-OK')"


def test_a_required_read_is_met_by_a_shell_read_and_a_plain_turn_is_untouched(ws, tmp_path):
    (tmp_path / "ledger.txt").write_text("checksum X-OK\n", encoding="utf-8")
    engine, fake = make_agent(tmp_path, [{"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "cat ledger.txt"}}]},
                                         {"content": "The checksum line is checksum X-OK.", "tool_calls": []}])
    engine.agent_chat("Read ledger.txt in the workspace and tell me its checksum line.", explicit=False,
                      session_id=engine.sessions.create_session()["id"])
    assert not _asked(fake)
    engine2, fake2 = make_agent(tmp_path, [{"content": "Ola!", "tool_calls": []}])
    engine2.agent_chat("Ola, tudo bem?", explicit=False, session_id=engine2.sessions.create_session()["id"])
    assert not _asked(fake2)
