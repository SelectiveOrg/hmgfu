"""95.17 (E7 c95g rep2) — the per-turn cap applies to a tool the model calls without it being offered.

The trace: create_widget was WITHHELD that turn (offered: list_files); the model called it anyway —
allowed, the registry executes — and the identical call with props={value: 0} succeeded TWICE (two
widgets on the canvas); only the third was blocked, by the stuck-loop guard. The loop read
`x-max-successful-calls-per-turn` from the OFFERED copy, so an un-offered tool had no cap. Reproduced
on the routed path with the tool withheld. Positive: the second identical call is refused with the
first result standing, one widget exists. Preserve: an un-offered READ with no cap still runs twice;
the offered path keeps its existing cap test (test_schema_caps_duplicate_successful_side_effect_tool).
"""
from __future__ import annotations

from tests.test_v2_agent import make_agent

MSG = "Show me a metric widget with the number of widget-B in the workspace inventory."
CALL = {"name": "create_widget", "arguments": {"type": "note", "title": "Widget-B Inventory", "props": {"text": "0 found"}}}


def _routed(engine, monkeypatch, tools):
    real = engine.retrieve

    def routed(text, **kw):
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = list(tools)          # what the router OFFERS this turn
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)


def test_an_unoffered_side_effect_is_still_capped(tmp_path, monkeypatch):
    """THE CONTRACT — fails before: the second identical call succeeds and two widgets exist."""
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [dict(CALL)]},
        {"content": "", "tool_calls": [dict(CALL)]},
        {"content": "I've created a note widget.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    _routed(engine, monkeypatch, ["list_files"])            # create_widget NOT offered
    result = engine.agent_chat(MSG)
    calls = [t for t in result["tool_trace"] if t["name"] == "create_widget"]
    assert len(calls) == 2, [(t["name"], t.get("blocked"), t["failed"]) for t in result["tool_trace"]]
    assert calls[0]["failed"] is False and not calls[0].get("blocked"), calls[0]
    assert calls[1].get("blocked") is True and "already succeeded" in calls[1]["result"], calls[1]


def test_an_unoffered_read_with_no_cap_still_runs_twice(tmp_path, monkeypatch):
    (tmp_path / "ws").mkdir()
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "list_files", "arguments": {"path": "."}}]},
        {"content": "", "tool_calls": [{"name": "list_files", "arguments": {"path": ".", "pattern": "*.txt"}}]},
        {"content": "done", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    _routed(engine, monkeypatch, ["read_file"])             # list_files NOT offered
    result = engine.agent_chat("What files are in the workspace folder?")
    calls = [t for t in result["tool_trace"] if t["name"] == "list_files"]
    assert len(calls) == 2 and not any(t.get("blocked") for t in calls), calls
