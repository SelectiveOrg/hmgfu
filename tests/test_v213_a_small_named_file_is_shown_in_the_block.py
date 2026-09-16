"""H-E7 / 95.33 (product hypothesis) — a small workspace file the message names is shown in the block.

E7's remaining untested product link: the model never sees the file it is asked about. Positive: a
turn naming inventory.txt gets its content in the block. Negative: a file the message does not name
is not shown; a file above the size cap is not shown. Preserve: the listing (95.16) and the guidance
stay; a turn naming no file keeps the block as it was.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.prompts import WORKSPACE_INLINE_BYTES, workspace_block

E7 = "Show me a metric widget with the number of widget-B in the workspace inventory."


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "inventory.txt").write_text("widget-A 4\nwidget-B 11\nchecksum VEGA-INVENTORY-OK\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("private notes\n", encoding="utf-8")
    (tmp_path / "large.txt").write_text("x" * (WORKSPACE_INLINE_BYTES + 1), encoding="utf-8")
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def test_the_named_small_file_is_shown(ws):
    """THE CONTRACT — fails before: workspace_block takes no message and shows no content."""
    block = workspace_block(str(ws), E7)
    assert "Content of inventory.txt:" in block and "widget-B 11" in block, block


def test_unnamed_and_oversized_files_are_not_shown(ws):
    block = workspace_block(str(ws), E7)
    assert "private notes" not in block
    assert "Content of large.txt" not in workspace_block(str(ws), "please read the large file")


def test_the_listing_and_guidance_stay_and_no_name_means_no_content(ws):
    block = workspace_block(str(ws), "tell me about the workspace")
    assert "Top-level entries" in block and "read_file or bash" in block and "Content of" not in block
    assert "Content of" not in workspace_block(str(ws))
