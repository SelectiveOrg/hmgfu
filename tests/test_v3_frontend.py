"""v3 tests: sessions store, widget tools, event emission, viz mapping — no Ollama."""

import json
from pathlib import Path

import pytest

from hmgfu.sessions import SessionStore, WIDGET_TYPES
from tests.test_v2_agent import make_agent  # reuse the fake-provider AgentEngine


def test_canvas_panel_exposes_resize_contract():
    """The desktop canvas pane must have an accessible, pointer-driven splitter."""
    source = (Path(__file__).parents[1] / "web" / "app" / "Canvas.jsx").read_text(encoding="utf-8")
    assert 'role="separator"' in source
    assert 'aria-label="Resize canvas panel"' in source
    assert "aria-valuenow={panelWidth}" in source
    assert "tabIndex={0}" in source
    assert "onPointerDown={startPanelResize}" in source
    assert 'width: "min(400px, 100vw)"' not in source


def test_settings_uses_real_model_select_not_filtered_datalist():
    source = (Path(__file__).parents[1] / "web" / "app" / "Settings.jsx").read_text(encoding="utf-8")
    assert '<datalist id={"models-" + role}>' not in source
    assert '<select value={settings[role + "_model"]}' in source
    assert "providerModels.map" in source


def test_transcript_hides_empty_recall_and_context_pills():
    source = (Path(__file__).parents[1] / "web" / "app" / "Transcript.jsx").read_text(encoding="utf-8")
    assert "if (!m.count) return null" in source
    assert "m.tools?.length || m.skills?.length || m.directives?.length" in source


def test_memory_hex_keeps_live_field_and_restores_macro_compression():
    source = (Path(__file__).parents[1] / "web" / "app" / "MemoryWidgets.jsx").read_text(encoding="utf-8")
    assert "HmgHexGrid" in source
    assert 'data-hex-mode="field"' in source
    assert 'data-hex-mode="compression"' in source
    assert "active: activeIds.has(n.id)" in source
    assert "<canvas ref={canvasRef}" in source  # Phase-31 live field remains intact


def test_hex_zoom_uses_zoom_driven_lod():
    source = (Path(__file__).parents[1] / "web" / "app" / "HexZoom.jsx").read_text(encoding="utf-8")
    assert "HZ_EXPAND_DIAM" in source
    assert "HZ_COLLAPSE_DIAM" in source
    assert "syncAutoLod" in source
    assert "hzLayoutSpatialLod" in source
    assert "detail replaces each macro in place" in source
    assert "click a green macro to open it" not in source
    assert "graphViz(HZ_ROOT_CAP, null, false, true)" in source
    assert 'addEventListener("wheel"' in source
    assert "onWheel={" not in source


def test_hex_zoom_core_encodes_spatial_subdivision():
    source = (Path(__file__).parents[1] / "web" / "app" / "HexZoomCore.js").read_text(encoding="utf-8")
    assert "HZ_BAND_COLORS" in source
    assert "hzChildRingRadius" in source
    assert "hzCenteredCells" in source
    assert "hzConvergeOffset" in source
    assert "hzHexNorm" in source
    assert "hzChildFootprint" in source
    assert "hzLayoutSpatialLod" in source
    assert "hzLodAction" in source
    assert "ctx.clip()" not in source
    assert "2 * ring + 1" in source
    assert "HZ_ROOT_RADIUS * 1.06" not in source
    assert "parent.radius" in source
    assert "parent.x +" not in source


def test_hex_zoom_does_not_open_an_empty_numbered_macro():
    source = (Path(__file__).parents[1] / "web" / "app" / "HexZoom.jsx").read_text(encoding="utf-8")
    assert "entry.n.children = 0" in source
    assert "payload.hex_nodes || []" in source


def test_graph_viz_pins_sources_for_included_macro(tmp_path):
    import asyncio
    from types import SimpleNamespace
    from hmgfu import runtime
    from hmgfu.models import MemoryPoint
    from hmgfu.routes.memory import graph_viz
    from hmgfu.store import HMGGraph

    graph = HMGGraph(str(tmp_path / "viz.db"))
    macro = MemoryPoint(type="macro", title="M", density=1.0); graph.save_point(macro)
    sources = [MemoryPoint(title=f"source-{i}", density=0.1) for i in range(2)]
    for point in sources: graph.save_point(point)
    graph.save_macro_sources(macro.id, [point.id for point in sources])
    for i in range(5): graph.save_point(MemoryPoint(title=f"decoy-{i}", density=0.9))
    saved = runtime._engine; runtime.set_engine(SimpleNamespace(graph=graph))
    try:
        payload = asyncio.run(graph_viz(cap=4))
        ids = {node["id"] for node in payload["hex_nodes"]}
        assert {macro.id, *(point.id for point in sources)} <= ids
    finally:
        runtime.set_engine(saved); graph.close()


def test_session_store_crud(tmp_path):
    s = SessionStore(str(tmp_path / "s.db"))
    sess = s.create_session()          # default title → eligible for auto-title
    assert sess["id"]
    assert s.ensure_session(sess["id"]) == sess["id"]
    fresh = s.ensure_session(None)      # None → new session
    assert fresh != sess["id"]
    s.save_message(sess["id"], "user", "hello", 1)
    s.save_message(sess["id"], "assistant", "hi", 1, metadata={"memory_count": 2})
    hist = s.history(sess["id"])
    assert len(hist) == 2 and hist[1]["metadata"]["memory_count"] == 2
    assert s.next_turn_seq(sess["id"]) == 2
    listed = {x["id"]: x for x in s.list_sessions()}
    assert listed[sess["id"]]["messages"] == 2
    assert listed[sess["id"]]["title"] == "hello"   # auto-titled from first user msg


def test_session_widgets(tmp_path):
    s = SessionStore(str(tmp_path / "s.db"))
    sid = s.create_session()["id"]
    s.upsert_widget(sid, {"id": "w1", "type": "metric", "title": "M", "props": {"value": 5}, "generated": True})
    ws = s.widgets(sid)
    assert len(ws) == 1 and ws[0]["props"]["value"] == 5 and ws[0]["generated"]
    s.remove_widget(sid, "w1")
    assert s.widgets(sid) == []


def test_widget_tool_creates_and_emits(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    events = []
    engine._turn_session = engine.sessions.create_session()["id"]
    engine._turn_emit = lambda ev: events.append(ev)
    out = engine.widget_action("create_widget", {"type": "metric", "title": "Density",
                                                 "props": {"value": "0.7"}})
    assert out["ok"] and out["type"] == "metric"
    assert any(e["type"] == "widget" and e["action"] == "create" for e in events)
    assert engine.sessions.widgets(engine._turn_session)[0]["title"] == "Density"


def test_widget_tool_rejects_unknown_type(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    out = engine.widget_action("create_widget", {"type": "hologram", "title": "x"})
    assert "error" in out and "types" in out


def test_all_widget_types_declared():
    # every type the create_widget schema advertises is in WIDGET_TYPES
    for t in ("metric", "table", "weather", "plan", "diff", "note", "memory-hex",
              "memory-graph", "timeline"):
        assert t in WIDGET_TYPES


def test_agent_chat_emits_full_event_sequence(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "memory_timeline", "arguments": {"limit": 2}}]},
        {"content": "here you go", "tool_calls": []},
    ])
    events = []
    result = engine.agent_chat("what do you remember?", emit=lambda ev: events.append(ev))
    types = [e["type"] for e in events]
    assert "status" in types           # "Recalling memories" is a status (not a thinking card)
    assert "memory_used" in types
    assert "tool_call" in types and "tool_result" in types
    assert types[-1] == "done"
    assert result["session_id"]
    # done carries the final text + stats
    done = events[-1]
    assert done["final_text"] == "here you go" and "stats" in done
    # the turn was persisted for restore
    hist = engine.sessions.history(result["session_id"])
    assert len(hist) == 2
    assert hist[1]["metadata"]["tool_calls"][0]["name"] == "memory_timeline"


def test_settings_recall_knobs_honored(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    for i in range(10):
        engine.ingest(f"memory number {i} about the hexagonal grid system", source="user")
    engine.settings.set("retrieval_limit", 3)
    engine.settings.set("retrieval_min_score", 0.05)
    engine.settings.set("expansion_depth", 0)
    _, retrieved, _ = engine.retrieve("hexagonal grid system")
    assert 0 < len(retrieved) <= 3          # limit + no expansion → hard cap


def test_settings_nano_gates_applied(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("nano_sensitizer_enabled", False)
    engine.settings.set("nano_dream_enabled", False)
    engine.retrieve("anything")             # gates applied on retrieve
    assert engine.sensitizer.extract_enabled is False
    assert engine.sensitizer.dream_enabled is False
    assert engine.sensitizer.score_pair("analogy", "a", "b") is None  # dream nano off


def test_settings_float_validation(tmp_path):
    from hmgfu.settings import Settings
    s = Settings(str(tmp_path / "s.db"))
    s.set("retrieval_min_score", 0.5)
    assert s.get("retrieval_min_score") == 0.5
    s.set("retrieval_min_score", 1)         # int coerced to float
    assert s.get("retrieval_min_score") == 1.0
    with pytest.raises(ValueError):
        s.set("retrieval_min_score", "high")


def test_mini_dream_cadence_zero_disables(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("mini_dream_every_n_turns", 0)
    engine.turn_count = 8
    assert engine._should_run_mini_dream() is False


def test_agent_widget_tool_end_to_end(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "create_widget",
                                        "arguments": {"type": "note", "title": "Reminder",
                                                      "props": {"text": "buy milk"}}}]},
        {"content": "Added a note to your canvas.", "tool_calls": []},
    ])
    events = []
    result = engine.agent_chat("remember to buy milk on the canvas", emit=lambda ev: events.append(ev))
    widget_events = [e for e in events if e["type"] == "widget"]
    assert widget_events and widget_events[0]["widget"]["type"] == "note"
    # persisted on the session
    assert engine.sessions.widgets(result["session_id"])[0]["props"]["text"] == "buy milk"
