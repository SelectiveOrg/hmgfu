"""95.47 (X2 on v4) — a creation request that names a new workspace file makes `write_file` a required
tool, the mirror of 95.19.

"Cria um script Python chamado ola_tamarin.py na area de trabalho que imprime TAMARIN-OK." got a pack
with only `bash`; the model echoed the request into bash four times and printed the code in prose.
Positive: the sentence offers write_file first. Negative: a request naming an EXISTING file is 95.19's
case (read_file) and does not add the write; a statement naming a file is not an action request; a
workspace sentence naming no file is unchanged.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.models import QueryPoint
from hmgfu.tool_points import retrieve_tools_for_turn
from tests.test_v2_agent import fake_embed, make_agent

X2 = "Cria um script Python chamado ola_tamarin.py na area de trabalho que imprime TAMARIN-OK."
X2EN = "Write a file summary.md in the workspace containing SUMMARY-OK."


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "inventory.txt").write_text("widget-A 4\nwidget-B 11\n", encoding="utf-8")
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def _q(text, **kw):
    base = dict(text=text, embedding=fake_embed(text), intent="task", conversation_act="instruction",
                action_requested=False)
    base.update(kw)
    return QueryPoint(**base)


def test_a_new_file_to_create_makes_write_file_required(ws, tmp_path):
    """THE CONTRACT — fails before: write_file is not offered for X2's sentence."""
    engine, _ = make_agent(tmp_path, [])
    for text in (X2, X2EN):
        names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q(text), max_tools=4)]
        assert names and names[0] == "write_file", (text, names)


def test_an_existing_file_stays_a_read_and_non_requests_are_unchanged(ws, tmp_path):
    engine, _ = make_agent(tmp_path, [])
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q("Read the file inventory.txt and tell me the checksum line."), max_tools=4)]
    assert names and names[0] == "read_file" and "write_file" not in names[:1], names
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q("My notes are in notas.md, by the way.", conversation_act="statement", intent="info"), max_tools=4)]
    assert "write_file" not in names[:1], names
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q("Tell me about the workspace folder in general."), max_tools=4)]
    assert "write_file" not in names[:1], names
