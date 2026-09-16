"""95.19 (E7 c95h rep1) — a workspace file the message names makes `read_file` a required tool.

With 95.16 the block named inventory.txt and the model went straight to it — with a blind `bash`
(withheld; offered: list_files 0.37) and `grep -c "widget-B" inventory.txt` = 1, the count of matching
LINES, never the number beside the label. `read_file` was withheld: the router's semantic score never
reached it. The rule that makes a tool NAMED in the message required (`explicit`) extended to the data
the listing already carries: a message about the workspace that names one of its files (stem ≥ 4
letters) requires the native read. Positive: E7's sentence offers read_file first. Negative: a
workspace sentence naming no file does not; a sentence naming the file but not about the workspace
does not (the 67.6 gate). Preserve: a named TOOL is still required; one helper feeds block and router.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.models import QueryPoint
from hmgfu.prompts import workspace_block
from hmgfu.tool_points import retrieve_tools_for_turn
from tests.test_v2_agent import fake_embed, make_agent

E7 = "Show me a metric widget with the number of widget-B in the workspace inventory."


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


def test_the_named_file_makes_read_file_required(ws, tmp_path):
    """THE CONTRACT — fails before: read_file is not offered for E7's sentence."""
    engine, _ = make_agent(tmp_path, [])
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q(E7), max_tools=4)]
    assert names and names[0] == "read_file", names


def test_a_workspace_sentence_naming_no_file_is_unchanged(ws, tmp_path):
    engine, _ = make_agent(tmp_path, [])
    q = _q("Tell me about the workspace folder in general.")
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, q, max_tools=4)]
    assert "read_file" not in names[:1], names


def test_a_sentence_not_about_the_workspace_is_unchanged(ws, tmp_path):
    engine, _ = make_agent(tmp_path, [])
    q = _q("My inventory of ideas is long today.", intent="chat", conversation_act="statement")
    assert retrieve_tools_for_turn(engine.tools, engine, q, max_tools=4) == []


def test_a_named_tool_is_still_required(ws, tmp_path):
    engine, _ = make_agent(tmp_path, [])
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q("Use list_files on the workspace."), max_tools=4)]
    assert "list_files" in names


def test_one_helper_feeds_the_block_and_the_router(ws):
    assert "inventory.txt" in tool_builtins.workspace_names() and "inventory.txt" in workspace_block(str(ws))
