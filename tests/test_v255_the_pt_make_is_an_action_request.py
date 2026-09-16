"""95.47c (X2 on v5, d95w19v5 rep2) — the PT "faz/fazer/faça" is an action opener, the twin of "make".

"Faz um script Python, ola_ibis.py, na area de trabalho, que imprime IBIS-OK." was not an action request
for the opener class (it had "make" and "cria", not "faz"), so write_file was never explicit or required and
95.47b had nothing to re-ask: only bash was offered, the model read "area de trabalho" as the Desktop, failed
twice and pasted the code. Positive: the sentence is an action request and write_file is offered first.
Preserve: "cria" still is; a non-imperative "faz" sentence about the user is not a workspace action; the
native write is not required for a file that already exists.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.models import QueryPoint
from hmgfu.speech_act import is_action_request
from hmgfu.tool_points import retrieve_tools_for_turn
from tests.test_v2_agent import fake_embed, make_agent

FAZ = "Faz um script Python, ola_ibis.py, na area de trabalho, que imprime IBIS-OK."


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def _q(text):
    return QueryPoint(text=text, embedding=fake_embed(text), intent="task", conversation_act="instruction", action_requested=False)


def test_faz_is_an_action_request_and_the_native_write_is_offered_first(ws, tmp_path):
    """THE CONTRACT — fails before: 'Faz ...' is not an action request; write_file is not explicit."""
    assert is_action_request(FAZ) and is_action_request("Faça um ficheiro notas.md com o texto NOTAS.") and is_action_request("Fazer um script x.py na area de trabalho.")
    engine, _ = make_agent(tmp_path, [])
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q(FAZ), max_tools=4)]
    assert names and names[0] == "write_file", names
    assert "write_file" in list(_q(FAZ).requested_tools or []) or names[0] == "write_file"


def test_cria_holds_and_the_non_actions_stay_out(ws, tmp_path):
    assert is_action_request("Cria um script Python chamado ola_tamarin.py na area de trabalho que imprime TAMARIN-OK.")
    assert not is_action_request("O meu irmao faz anos amanha.")
    assert not is_action_request("Faz sentido, obrigado.")
    (tmp_path / "ola_ibis.py").write_text("print('x')\n", encoding="utf-8")
    engine, _ = make_agent(tmp_path, [])
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q(FAZ), max_tools=4)]
    assert "write_file" not in names[:1] or "read_file" in names, names
