"""95.75 P2/P3 — why a finished build could never tick its own step (live session 61915ec3).

P2  the step said "design the HTML/JS structure for a weather widget". It names no file, and the word
    "widget" alone made the post-condition demand a CANVAS widget, so the write_file of
    weather_widget.html in the same turn did not count: "no receipt touched the widget weather", twice.
    "Widget" is also the user's word for the thing being built. A step that names an artefact is proven
    by the artefact, wherever it landed — canvas or disk — at the same evidence standard.
P3  the system's own safety net (auto_serve_built_apps) put the app widget on the canvas by calling
    widget_action directly, after the turn had closed. No receipt, and too late to prove anything, so a
    widget the system itself created could never satisfy the step that asked for it.
"""

from __future__ import annotations

import hashlib
import json

from hmgfu.receipts import ReceiptStore, verify_step
from tests.test_v2_agent import make_agent

NAMES = ["write_file", "read_file", "create_widget", "update_widget", "list_files", "bash"]


def _engine(tmp_path, script):
    engine, _ = make_agent(tmp_path, script)
    for k, v in {"grader_enabled": False, "workspace_dir": str(tmp_path), "plan_step_recall": False,
                 "thinking_mode": "off", "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(k, v)
    from hmgfu.tool_builtins import set_workspace
    set_workspace(str(tmp_path))
    return engine


def _call(name, arguments):
    return {"content": "", "tool_calls": [{"name": name, "arguments": arguments}]}


def _wrote(st, tmp_path, filename, session="s"):
    (tmp_path / filename).write_text("<!DOCTYPE html><html><body>built</body></html>", encoding="utf-8")
    digest = hashlib.sha256((tmp_path / filename).read_bytes()).hexdigest()
    rid = st.open(session, 1, "write_file", {"path": filename}, "write", "user_request", 0)
    st.close(rid, "ok", "written", {"files": [{"path": filename, "sha256": digest,
                                               "bytes": (tmp_path / filename).stat().st_size}]})
    return rid


def test_the_file_that_is_the_widget_proves_the_step(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = _wrote(st, tmp_path, "weather_widget.html")
    step = "Research current weather data and design the HTML/JS structure for a weather widget."
    ok, evidence, missing = verify_step(step, st.for_session("s"), str(tmp_path), NAMES)
    assert ok, missing
    assert evidence == [rid]


def test_an_unrelated_file_proves_nothing(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    _wrote(st, tmp_path, "notes.txt")
    ok, _evidence, missing = verify_step("Create the weather widget", st.for_session("s"), str(tmp_path), NAMES)
    assert not ok and missing == ["no receipt touched the widget weather"]


def test_a_widget_step_with_nothing_built_still_fails(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    ok, _evidence, missing = verify_step("Create the weather widget", st.for_session("s"), str(tmp_path), NAMES)
    assert not ok and missing


def test_a_file_whose_hash_moved_on_proves_nothing(tmp_path):
    """The artefact route carries the same standard as the file route — no weaker."""
    st = ReceiptStore(str(tmp_path / "r.db"))
    _wrote(st, tmp_path, "weather_widget.html")
    (tmp_path / "weather_widget.html").write_text("edited by someone else", encoding="utf-8")
    ok, _evidence, _missing = verify_step("Create the weather widget", st.for_session("s"), str(tmp_path), NAMES)
    assert not ok


def test_the_auto_served_widget_leaves_a_receipt_and_settles_its_step(tmp_path):
    """End to end: plan, write the page, tick step 0. The system serves the app widget itself, and the
    step that asked for it is settled by a receipt — not left active with the widget already on screen."""
    engine = _engine(tmp_path, [
        _call("plan_task", {"steps": ["Write the pong game to pong.html", "Deploy the pong game widget"]}),
        _call("write_file", {"path": "pong.html", "content": "<!DOCTYPE html><html><body>pong</body></html>"}),
        _call("update_plan", {"step": 0, "status": "done"}),
        {"content": "Built and served.", "tool_calls": []},
    ])
    sid = engine.sessions.create_session("pong")["id"]
    engine.agent_chat("build me a pong game widget", session_id=sid)

    plan = engine.session_plans.get(sid)
    assert [s["status"] for s in plan["steps"]] == ["done", "done"], plan["steps"]
    served = [r for r in engine.receipts.for_session(sid) if r["tool"] == "create_widget"]
    assert served and served[0]["status"] == "ok", "the widget the system created must leave a receipt"
    assert json.dumps(served[0]["effects"]).find("w_") >= 0, served[0]["effects"]
    assert plan["steps"][1]["evidence"] == [served[0]["id"]]
