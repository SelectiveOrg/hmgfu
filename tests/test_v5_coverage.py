"""Phase 24: the SYSTEM covers sparse tool arguments — never blamed on the model."""

import json

from tests.test_v2_agent import make_agent


def test_app_widget_backfills_from_turn_file(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    engine._turn_files = ["todo.html"]
    engine._turn_url = None
    out = engine.widget_action("create_widget", {"type": "app", "title": "Todo"})
    assert out["ok"]
    w = engine.sessions.widgets(engine._turn_session)[0]
    assert w["props"]["file"] == "todo.html"     # backfilled deterministically


def test_app_widget_prefers_dev_url(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    engine._turn_files = ["a.html"]
    engine._turn_url = "http://localhost:5173/"
    out = engine.widget_action("create_widget", {"type": "app", "title": "Dev"})
    assert out["ok"]
    assert engine.sessions.widgets(engine._turn_session)[0]["props"]["url"] == "http://localhost:5173/"


def test_app_widget_without_artifacts_gets_guidance(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    engine._turn_files, engine._turn_url = [], None
    out = engine.widget_action("create_widget", {"type": "app", "title": "X"})
    assert "error" in out and "write the file first" in out["error"]


def test_required_props_feedback_not_blank_widget(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    out = engine.widget_action("create_widget", {"type": "weather", "title": "Lisbon"})
    assert "error" in out and "temp" in out["error"]          # precise retry guidance
    assert engine.sessions.widgets(engine._turn_session) == []  # NO blank widget created
    ok = engine.widget_action("create_widget", {"type": "weather", "title": "Lisbon",
                                                "props": {"temp": "22°", "place": "Lisbon"}})
    assert ok["ok"]


def test_flattened_widget_args_are_folded_into_props(tmp_path):
    """A model that FLATTENS the call — {type:'note', text:'…'} instead of props:{text:'…'} — must
    succeed, not be rejected for 'missing props'. ornith's EXACT bench-L10 calls (top-level `text`
    and the `content` synonym) both fold in. General coverage, not model-specific."""
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    # ornith call #2: `text` at the top level, not nested in props
    out = engine.widget_action("create_widget",
                               {"type": "note", "title": "Live Benchmark",
                                "text": "proactive widget complete"})
    assert out["ok"]
    w = engine.sessions.widgets(engine._turn_session)[0]
    assert w["props"]["text"] == "proactive widget complete"    # folded → honoured, not rejected
    # ornith call #1: the `content` synonym normalizes to the required `text`
    out2 = engine.widget_action("create_widget",
                                {"type": "note", "title": "N2", "content": "hello note"})
    assert out2["ok"]
    assert engine.sessions.widgets(engine._turn_session)[-1]["props"]["text"] == "hello note"
    # a genuinely empty call still gets precise retry guidance (no false success, no blank widget)
    bad = engine.widget_action("create_widget", {"type": "note", "title": "Empty"})
    assert "error" in bad and "text" in bad["error"]


def test_auto_serve_built_apps(tmp_path):
    from hmgfu.widgets import auto_serve_built_apps
    engine, _ = make_agent(tmp_path, [])
    engine._turn_session = engine.sessions.create_session()["id"]
    events = []
    engine._turn_emit = lambda ev: events.append(ev)
    engine._turn_files = ["game.html", "style.css", "picker.svg"]
    created = auto_serve_built_apps(engine)
    assert created == 2                                        # html + svg, not css
    widgets = engine.sessions.widgets(engine._turn_session)
    assert {w["props"]["file"] for w in widgets} == {"game.html", "picker.svg"}
    assert sum(1 for e in events if e["type"] == "widget") == 2
    # idempotent: already-served files are not duplicated
    assert auto_serve_built_apps(engine) == 0


def test_artifact_recording(tmp_path):
    import os
    from hmgfu.tool_builtins import get_workspace
    engine, _ = make_agent(tmp_path, [])
    engine._turn_files, engine._turn_url = [], None
    ws = get_workspace()
    engine._record_artifacts("write_file", json.dumps({"path": os.path.join(ws, "apps", "x.html"), "bytes": 5}))
    engine._record_artifacts("write_file", json.dumps({"path": r"C:\outside\evil.html"}))  # ignored
    engine._record_artifacts("bash", json.dumps({"stdout": "Server running at http://localhost:3000/ ready", "exit_code": 0}))
    assert engine._turn_files == ["apps/x.html"]
    assert engine._turn_url == "http://localhost:3000/"


def test_materialize_code_block_reply(tmp_path):
    """Model pastes the app as a chat code block → system writes + serves it."""
    import os
    from hmgfu.tool_builtins import get_workspace, set_workspace
    from hmgfu.widgets import auto_serve_built_apps, materialize_reply_artifacts
    set_workspace(str(tmp_path))
    try:
        engine, _ = make_agent(tmp_path, [])
        engine._turn_session = engine.sessions.create_session()["id"]
        engine._turn_files, engine._turn_url = [], None
        engine._turn_effects_allowed = True                     # 70.7: the materializer is a dispatched, authorized write
        reply = ("Here you go:\n```html\n<!DOCTYPE html><html><head><title>c</title></head>"
                 "<body><div class='sq'></div><script>console.log(1)</script></body></html>\n```")
        entries = materialize_reply_artifacts(engine, "save it as colors.html please", reply)
        assert len(entries) == 1 and entries[0]["name"] == "write_file" and not entries[0]["blocked"]   # a receipt
        assert engine._turn_files == ["colors.html"]
        assert os.path.isfile(os.path.join(get_workspace(), "colors.html"))
        assert auto_serve_built_apps(engine) == 1
        w = engine.sessions.widgets(engine._turn_session)[0]
        assert w["type"] == "app" and w["props"]["file"] == "colors.html"
        # no-ops: real files already written / no code block / tiny block
        engine._turn_files = ["already.html"]
        assert materialize_reply_artifacts(engine, "x", reply) == []
        engine._turn_files = []
        assert materialize_reply_artifacts(engine, "x", "no code here") == []
        assert materialize_reply_artifacts(engine, "x", "```html\n<html></html>\n```") == []
    finally:
        set_workspace(None)


def test_materialize_sanitizes_filename(tmp_path):
    from hmgfu.tool_builtins import set_workspace, get_workspace
    from hmgfu.widgets import materialize_reply_artifacts
    import os
    set_workspace(str(tmp_path))
    try:
        engine, _ = make_agent(tmp_path, [])
        engine._turn_files, engine._turn_url = [], None
        engine._turn_effects_allowed = True
        reply = "```html\n<!DOCTYPE html><html><body>" + "x" * 100 + "</body></html>\n```"
        materialize_reply_artifacts(engine, "save as ../../evil.html", reply)
        assert engine._turn_files == ["evil.html"]          # basename only — stays in workspace
        assert os.path.isfile(os.path.join(get_workspace(), "evil.html"))
    finally:
        set_workspace(None)


def test_explicit_correction_supersedes_at_ingest(tmp_path):
    """Bench B2 regression: a NEWER user-explicit statement supersedes a conflicting older
    one IMMEDIATELY at ingest — not at the next dream loop."""
    engine, _ = make_agent(tmp_path, [])
    old = engine.ingest("Directive: always end replies with the word Capitao",
                        source="user_explicit")
    new = engine.ingest("Directive: stop ending replies with Capitao, never use Capitao again, "
                        "end every reply with Chefe instead", source="user_explicit")
    assert engine.graph.points[old.id].status == "superseded"
    assert engine.graph.points[new.id].status == "active"
    # superseded points are OUT of retrieval
    _, retrieved, _ = engine.retrieve("how should replies end? directive Capitao Chefe")
    ids = [r.point.id for r in retrieved]
    assert old.id not in ids


def test_tailscale_url_extraction(monkeypatch):
    """Settings copy-link: url derived from Self.DNSName when serving."""
    import json as _json
    from hmgfu import system

    def fake_run(args, timeout=20):
        if "status" in args and "--json" in args:
            return {"exit_code": 0, "stdout": _json.dumps(
                {"BackendState": "Running", "Self": {"DNSName": "my-pc.tail1234.ts.net."}})}
        if "serve" in args:
            return {"exit_code": 0, "stdout": "https://my-pc.tail1234.ts.net/\n|-- proxy http://127.0.0.1:8777"}
        return {"exit_code": 1, "stdout": ""}

    monkeypatch.setattr(system, "_run", fake_run)
    status = system.tailscale_status()
    assert status["running"] and status["serving"]
    assert status["url"] == "https://my-pc.tail1234.ts.net"   # trailing dot stripped
    # serve on returns the shareable link too
    result = system.tailscale_serve("on")
    assert result["ok"] and result["url"] == "https://my-pc.tail1234.ts.net"


def test_agent_turn_auto_serves_end_to_end(tmp_path):
    """Model writes an html and NEVER creates a widget — the system serves it anyway."""
    from hmgfu.tool_builtins import get_workspace
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "write_file",
            "arguments": {"path": "mini.html", "content": "<h1>mini</h1>"}}]},
        {"content": "Built it.", "tool_calls": []},
    ])
    events = []
    result = engine.agent_chat("build a mini page", emit=lambda ev: events.append(ev))
    widget_events = [e for e in events if e["type"] == "widget" and e["action"] == "create"]
    assert widget_events and widget_events[0]["widget"]["type"] == "app"
    assert widget_events[0]["widget"]["props"]["file"] == "mini.html"
    widgets = engine.sessions.widgets(result["session_id"])
    assert any(w["type"] == "app" and w["props"].get("file") == "mini.html" for w in widgets)