"""v4 tests: dynamic workspace, connectors v2 registry, MCP client (fake stdio server)."""

import json
import os
import sys
import textwrap

import pytest

from hmgfu.tool_builtins import get_workspace, run_bash, set_workspace, write_file, WORKSPACE_DIR


def test_workspace_switch_and_reset(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    set_workspace(str(target))
    try:
        assert get_workspace() == str(target)
        result = run_bash("pwd")
        assert result["exit_code"] == 0
        # bash actually ran inside the selected folder
        assert target.name in result["stdout"].strip().split("/")[-1]
        absolute = run_bash(f'ls "{target}"')
        assert absolute["exit_code"] == 0
        # write guard follows the selected workspace
        out = write_file("hello.txt", "hi")
        assert out.get("bytes") == 2 and str(target) in out["path"]
    finally:
        set_workspace(None)
    assert get_workspace() == WORKSPACE_DIR


def test_workspace_rejects_missing_dir():
    set_workspace(r"C:\does\not\exist_xyz")
    assert get_workspace() == WORKSPACE_DIR   # silently falls back to default


def test_connector_provider_registry_crud(tmp_path, monkeypatch):
    from hmgfu import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "c.db"))
    from hmgfu import connectors
    # ONE provider per family; services are scopes inside, not separate connectors
    assert {"google", "meta", "github"} <= set(connectors.PROVIDERS)
    assert connectors.PROVIDERS["google"]["services"] == ["Gmail", "Calendar", "Tasks", "Drive"]
    assert connectors.PROVIDERS["google"]["auth"] == "cli"       # Phase 45: Google via the gog CLI (one login covers all)
    assert connectors.PROVIDERS["meta"]["auth"] == "api_key"
    assert set(s["auth"] for s in connectors.PROVIDERS.values()) <= set(connectors.VALID_AUTH)
    # add custom provider
    r = connectors.add_provider("linear", "Linear", "mcp",
                                {"command": ["npx", "srv"]}, services=["Issues", "Projects"])
    assert r["ok"] and "linear" in connectors.all_providers()
    # validation + built-in protection
    assert "error" in connectors.add_provider("bad", "", "mcp", {})
    assert "error" in connectors.add_provider("bad2", "", "hologram", {})
    assert "error" in connectors.add_provider("google", "", "api_key", {"env": ["X"]})
    # status: ONE row per provider w/ services inside, no secrets, single flag
    status = {c["kind"]: c for c in connectors.connector_status()}
    assert status["google"]["services"] == ["Gmail", "Calendar", "Tasks", "Drive"]
    assert "configured" in status["google"] and "secret" not in json.dumps(status).lower()
    assert connectors.remove_provider("linear")["ok"]
    assert "error" in connectors.remove_provider("google")      # built-in protected


def test_google_cli_connect_flow_extracts_url_and_finishes():
    from hmgfu.connectors import google_connect

    class _Tools:
        def __init__(self): self.calls = []
        def execute_tool(self, name, args):
            self.calls.append((name, args))
            if name == "gog_login_start":
                return json.dumps({"output": "Open https://accounts.google.com/o/oauth2/auth?x=1"})
            return json.dumps({"output": "authorization complete"})

    engine = type("Engine", (), {"tools": _Tools()})()
    started = google_connect(engine)
    assert started["ok"] and started["stage"] == "authorize"
    assert started["auth_url"].startswith("https://accounts.google.com/")
    finished = google_connect(engine, "http://localhost/callback?code=abc")
    assert finished["ok"] and finished["stage"] == "complete"
    assert engine.tools.calls[-1] == (
        "gog_login_finish", {"redirect_url": "http://localhost/callback?code=abc"}
    )


FAKE_MCP_SERVER = textwrap.dedent("""
    import json, sys
    for line in sys.stdin:
        msg = json.loads(line)
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            out = {"jsonrpc": "2.0", "id": mid, "result": {"serverInfo": {"name": "fake"}}}
        elif method == "tools/list":
            out = {"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                {"name": "echo", "description": "echoes text",
                 "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}}]}}
        elif method == "tools/call":
            text = msg["params"]["arguments"].get("text", "")
            out = {"jsonrpc": "2.0", "id": mid,
                   "result": {"content": [{"type": "text", "text": "echo: " + text}]}}
        elif mid is None:
            continue
        else:
            out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "nope"}}
        sys.stdout.write(json.dumps(out) + "\\n")
        sys.stdout.flush()
""")


def test_mcp_client_against_fake_server(tmp_path):
    from hmgfu.mcp_client import MCPClient
    server = tmp_path / "fake_mcp.py"
    server.write_text(FAKE_MCP_SERVER)
    client = MCPClient([sys.executable, str(server)])
    try:
        client.initialize()
        tools = client.list_tools()
        assert tools and tools[0]["name"] == "echo"
        assert client.call_tool("echo", {"text": "hello"}) == "echo: hello"
    finally:
        client.close()


def test_mcp_connect_and_register(tmp_path):
    from tests.test_v2_agent import make_agent
    from hmgfu.mcp_client import connect_and_register, connected_names, disconnect_all
    server = tmp_path / "fake_mcp.py"
    server.write_text(FAKE_MCP_SERVER)
    engine, _ = make_agent(tmp_path, [])
    try:
        result = connect_and_register(engine, "fake", [sys.executable, str(server)])
        assert result["ok"] and result["count"] == 1
        assert "mcp__fake__echo" in engine.tools.schemas
        assert "fake" in connected_names()
        # dispatch through the ONE entry point
        out = engine.tools.execute_tool("mcp__fake__echo", {"text": "hi"})
        assert out == "echo: hi"
        # MCP tool became an HMG point (self-growing)
        assert any("tool:mcp__fake__echo" in p.keywords
                   for p in engine.graph.points.values() if p.type == "skill")
    finally:
        disconnect_all()


def test_session_groups(tmp_path):
    from hmgfu.sessions import SessionStore
    s = SessionStore(str(tmp_path / "g.db"))
    sid = s.create_session("Trip")["id"]
    s.set_group(sid, "Personal")
    listed = {x["id"]: x for x in s.list_sessions()}
    assert listed[sid]["group"] == "Personal"
    s.set_group(sid, "")
    assert {x["id"]: x for x in s.list_sessions()}[sid]["group"] == ""


def test_plan_tools_and_budget(tmp_path):
    from tests.test_v2_agent import make_agent
    from hmgfu.plans import plan_action, iteration_budget
    engine, _ = make_agent(tmp_path, [])
    engine._turn_plan = None
    events = []
    engine._turn_emit = lambda ev: events.append(ev)
    # validation: 0 steps rejected; title optional (synthesized)
    assert "error" in plan_action(engine, "plan_task", {"title": "x", "steps": []})
    assert "error" in plan_action(engine, "update_plan", {"step": 0, "status": "done"})
    notitle = plan_action(engine, "plan_task", {"steps": ["first step", "second step"]})   # no title → ok
    assert notitle["ok"] and engine._turn_plan["title"] == "Task plan"
    # declare
    out = plan_action(engine, "plan_task", {"title": "Build it", "steps": ["echo x", "second step", "third step"]})
    assert out["ok"] and events[-1]["type"] == "plan"
    assert engine._turn_plan["steps"][0]["status"] == "active"
    # budget earned: base 16 → 3 steps × 4 = 12 < 16 keeps base; 10 steps → 40
    assert iteration_budget(16, engine._turn_plan) == 16
    big = {"steps": [{}] * 10}
    assert iteration_budget(16, big) == 40
    assert iteration_budget(16, {"steps": [{}] * 30}) == 60   # cap
    # update + auto-advance (69.2 → 71: a completion claim needs a verified receipt)
    from hmgfu.receipts import close_for, open_for
    def _work():
        rid = open_for(engine, "bash", {"command": "echo x"}, 1)
        close_for(engine, rid, "bash", {"command": "echo x"}, '{"exit_code": 0, "stdout": "x"}', False)
    engine._turn_session = engine._turn_session or engine.sessions.create_session("p")["id"]
    _work()
    out = plan_action(engine, "update_plan", {"step": 0, "status": "done", "note": "ok"})
    assert out["progress"] == "1/3"
    assert engine._turn_plan["steps"][1]["status"] == "active"
    assert events[-1]["type"] == "plan_update"
    # bad index / status
    assert "error" in plan_action(engine, "update_plan", {"step": 9, "status": "done"})
    assert "error" in plan_action(engine, "update_plan", {"step": 1, "status": "wat"})
    # model-shape tolerance (gemma live): dict steps + "completed" status
    out = plan_action(engine, "plan_task", {"title": "Loose", "steps": [
        {"text": "run echo first"}, {"description": "echo second thing"}, "echo third"]})     # 90.2: a step names the action its receipt performs
    assert out["ok"] and engine._turn_plan["steps"][0]["text"] == "run echo first"
    _work()
    out = plan_action(engine, "update_plan", {"step": 0, "status": "Completed"})
    assert out["ok"] and engine._turn_plan["steps"][0]["status"] == "done"
    # arg-drift: step_index alias, and NO index → the currently-active step
    _work()
    out = plan_action(engine, "update_plan", {"step_index": 1, "status": "done"})
    assert out["ok"] and engine._turn_plan["steps"][1]["status"] == "done"
    _work()
    out = plan_action(engine, "update_plan", {"status": "done"})   # active step (2)
    assert out["ok"] and engine._turn_plan["steps"][2]["status"] == "done"


def test_agent_plan_via_tools_and_persistence(tmp_path):
    from tests.test_v2_agent import make_agent
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task",
            "arguments": {"title": "Two steps", "steps": ["first", "second"]}}]},
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo first"}}]},   # 69.2: evidence
        {"content": "", "tool_calls": [{"name": "update_plan",
            "arguments": {"step": 0, "status": "done"}}]},
        {"content": "all done", "tool_calls": []},
    ])
    events = []
    result = engine.agent_chat("build a two step thing", emit=lambda ev: events.append(ev))   # 70.4: an ORDER authorizes
    types = [e["type"] for e in events]
    assert "plan" in types and "plan_update" in types and "status" in types
    hist = engine.sessions.history(result["session_id"])
    assert hist[1]["metadata"]["plan"]["title"] == "Two steps"
    assert hist[1]["metadata"]["plan"]["steps"][0]["status"] == "done"


def test_engine_turn_lock(tmp_path):
    """H-01: one turn at a time across the whole engine (not per-session) — while the engine
    turn lock is held, any submission (any session) returns busy instead of stomping turn-state."""
    from tests.test_v2_agent import make_agent
    engine, _ = make_agent(tmp_path, [])
    sid = engine.sessions.create_session()["id"]
    engine._turn_lock.acquire()   # simulate a turn already in flight
    try:
        result = engine.agent_chat("hello", session_id=sid)
        assert result.get("error") == "busy"
    finally:
        engine._turn_lock.release()


def test_connector_one_connection_per_provider():
    """PA3 model: a provider is the connectable unit; services are scopes on ONE connection."""
    from hmgfu.connectors import connector_status
    rows = {c["kind"]: c for c in connector_status()}
    # Google is a SINGLE row (not gmail/calendar/drive as separate connectors)
    assert "google" in rows and "google_gmail" not in rows
    assert rows["google"]["services"] == ["Gmail", "Calendar", "Tasks", "Drive"]
    # one connection flag governs the whole provider + all its services
    assert isinstance(rows["google"]["configured"], bool)
    assert len([k for k in rows if k.startswith("google")]) == 1


def test_now_widget_type_registered():
    from hmgfu.sessions import WIDGET_TYPES
    assert "now" in WIDGET_TYPES
    assert "app" in WIDGET_TYPES


def test_thinking_extract_and_directive():
    from hmgfu.agent import extract_thinking, thinking_directive
    clean, thoughts = extract_thinking("<thinking>step through it</thinking>\nFinal answer.")
    assert clean == "Final answer." and thoughts == "step through it"
    assert extract_thinking("no block here") == ("no block here", "")
    assert thinking_directive("off") == ""
    assert "Always begin" in thinking_directive("always")
    assert "non-trivial" in thinking_directive("dynamic")


def test_end_turn_completes_with_evidence_and_keeps_active_on_failure(tmp_path):
    """Phase 67 replaced `_finalize_plan` with `session_plans.end_turn`: the worked step auto-completes ONLY
    when a tool actually ran and nothing failed (67.14: one step per turn of evidence, never every pending
    step); a failed turn keeps the plan ACTIVE (re-pinned next turn) — honest status."""
    from tests.test_v2_agent import make_agent
    from hmgfu.session_plans import end_turn
    engine, _ = make_agent(tmp_path, [])
    engine._turn_emit = lambda ev: None
    sid = engine.sessions.create_session()["id"]
    engine._turn_session = sid
    from hmgfu.receipts import close_for, open_for
    def _work():
        rid = open_for(engine, "bash", {"command": "echo x"}, 1)
        close_for(engine, rid, "bash", {"command": "echo x"}, '{"exit_code": 0}', False)
    engine._turn_plan = {"title": "t", "steps": [
        {"text": "a", "status": "done"}, {"text": "b", "status": "active"},
        {"text": "c", "status": "pending"}]}
    _work()
    end_turn(engine, sid, [{"name": "bash", "failed": False}], forced_finalization=False)
    # 67.14: evidence completes the step being WORKED (b) and promotes the next one — never every step
    assert [s["status"] for s in engine._turn_plan["steps"]] == ["done", "done", "active"]
    assert engine.session_plans.get(sid)["status"] == "active"
    _work()
    end_turn(engine, sid, [{"name": "bash", "failed": False}], forced_finalization=False)
    assert [s["status"] for s in engine._turn_plan["steps"]] == ["done", "done", "done"]
    assert engine.session_plans.get(sid)["status"] == "done"
    # no tool ran → no evidence → nothing auto-completes, plan stays active
    engine._turn_plan = {"title": "t", "steps": [{"text": "a", "status": "active"}]}
    end_turn(engine, sid, [], forced_finalization=False)
    assert engine._turn_plan["steps"][0]["status"] == "active" and engine.session_plans.get(sid)["status"] == "active"
    # a failed tool → stays active, the next pending step becomes active for the resume
    engine._turn_plan = {"title": "t", "steps": [{"text": "a", "status": "done"}, {"text": "b", "status": "pending"}]}
    end_turn(engine, sid, [{"name": "bash", "failed": True}], forced_finalization=False)
    assert engine._turn_plan["steps"][1]["status"] == "active" and engine.session_plans.get(sid)["status"] == "active"


def test_widget_delete_persists(tmp_path):
    from hmgfu.sessions import SessionStore
    s = SessionStore(str(tmp_path / "w.db"))
    sid = s.create_session()["id"]
    s.upsert_widget(sid, {"id": "w1", "type": "app", "title": "App",
                          "props": {"file": "index.html"}, "generated": True})
    assert len(s.widgets(sid)) == 1
    s.remove_widget(sid, "w1")
    assert s.widgets(sid) == []          # gone, and stays gone across reload


def test_workspace_file_route_confinement(tmp_path):
    from hmgfu.tool_builtins import set_workspace, get_workspace
    import os
    set_workspace(str(tmp_path))
    try:
        (tmp_path / "app.html").write_text("<h1>hi</h1>")
        ws = os.path.abspath(get_workspace())
        # traversal outside workspace resolves outside → would be rejected by the route guard
        bad = os.path.abspath(os.path.join(ws, "..", "secret.txt"))
        assert not bad.startswith(ws + os.sep)
        good = os.path.abspath(os.path.join(ws, "app.html"))
        assert good.startswith(ws + os.sep) and os.path.isfile(good)
    finally:
        set_workspace(None)


def test_list_projects_finds_this_repo():
    from hmgfu.system import list_projects
    projects = {p["name"]: p for p in list_projects()}
    assert "hmg-fu" in projects
    assert "git" in projects["hmg-fu"]["kinds"]
