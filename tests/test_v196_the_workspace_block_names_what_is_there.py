"""95.16 (E7, 0/3 in every batch) — the ACTIVE WORKSPACE block names what is there.

The block told the model to "inspect the workspace with read_file or bash before answering" and named
nothing; every E7 run searched the tree with `grep | wc` (0, 1) and never read the one file the request
names ("the workspace inventory" → inventory.txt, seeded). Grounding, not a phrase: the same listing
`list_files` (70.6) produces, top level only, capped. Positive: the seeded file is named in the block.
Negative: a directory beyond the cap shows the cap and an honest count. Preserve: an empty workspace
gives the block unchanged; the approval sentence and the bash guidance stay.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.prompts import WORKSPACE_LISTING_CAP, workspace_block


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def test_the_seeded_file_is_named(ws):
    """THE CONTRACT — fails before: the block names no file."""
    (ws / "inventory.txt").write_text("widget-B 11\n", encoding="utf-8")
    (ws / "notes").mkdir()
    block = workspace_block(str(ws))
    assert "inventory.txt" in block and "notes/" in block, block


def test_beyond_the_cap_the_count_is_honest(ws):
    for i in range(WORKSPACE_LISTING_CAP + 5):
        (ws / f"f{i:03d}.txt").write_text("x", encoding="utf-8")
    block = workspace_block(str(ws))
    assert f"(+5 more)" in block and "f000.txt" in block and "f044.txt" not in block, block


def test_an_empty_workspace_keeps_the_block_as_it_was(ws):
    block = workspace_block(str(ws))
    assert "Top-level entries" not in block
    assert "approved for read, write, and commands" in block and "read_file or bash" in block


def test_the_guidance_survives_with_a_listing(ws):
    (ws / "a.md").write_text("x", encoding="utf-8")
    block = workspace_block(str(ws))
    assert "use relative paths" in block and str(ws) in block
