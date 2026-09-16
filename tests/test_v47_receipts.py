"""Phase 71 — receipts per action, post-conditions per step, partial status, unknown outcome, cancellation,
idempotent writes. Own reproductions of Codex's four deferred M2 checks."""

from __future__ import annotations

import json

from hmgfu.receipts import ReceiptStore, observe_effects, postcondition, verify_step
from hmgfu.session_plans import begin_turn, finalize_status, step_evidence
from tests.test_v2_agent import make_agent


def _engine(tmp_path, script):
    engine, _ = make_agent(tmp_path, script)
    for k, v in {"grader_enabled": False, "workspace_dir": str(tmp_path), "plan_step_recall": False, "thinking_mode": "off",
                 "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(k, v)
    from hmgfu.tool_builtins import set_workspace
    set_workspace(str(tmp_path))
    return engine


def _call(name, arguments):
    return {"content": "", "tool_calls": [{"name": name, "arguments": arguments}]}


def test_store_open_close_consume(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = st.open("s", 1, "write_file", {"path": "a.txt"}, "write", "user_request", 0)
    assert st.pending("s")[0]["id"] == rid
    st.close(rid, "ok", "written", {"files": [{"path": "a.txt", "sha256": "x", "bytes": 1}]})
    r = st.for_session("s")[0]
    assert r["status"] == "ok" and r["effects"]["files"][0]["path"] == "a.txt" and r["consumed_by"] is None
    st.consume([rid], 0)
    assert st.for_session("s")[0]["consumed_by"] == 0
    rid2 = st.open("s", 2, "bash", {"command": "x"}, "write", "", None)
    assert st.cancel_pending("s") == 1 and st.for_session("s")[1]["status"] == "cancelled"


def test_postcondition_and_verify_rules(tmp_path):
    names = ["write_file", "create_widget", "bash", "read_file", "list_files"]
    assert postcondition("write_file: a.txt", names)["files"] == ["a.txt"]
    assert postcondition("create the links widget", names)["widget"]
    assert postcondition("run the tests with bash", names)["tools"] == ["bash"]
    (tmp_path / "a.txt").write_text("x")
    import hashlib
    sha = hashlib.sha256(b"x").hexdigest()                          # 82.4: real receipts carry the observed hash
    ok_a = {"id": "r1", "tool": "write_file", "status": "ok", "consumed_by": None, "effects": {"files": [{"path": "a.txt", "sha256": sha}]}}
    ok_b = {"id": "r2", "tool": "write_file", "status": "ok", "consumed_by": None, "effects": {"files": [{"path": "b.txt", "sha256": sha}]}}
    read = {"id": "r3", "tool": "list_files", "status": "ok", "consumed_by": None, "effects": {}}
    assert verify_step("write_file: a.txt", [ok_a], str(tmp_path), names) == (True, ["r1"], [])
    assert not verify_step("write_file: a.txt", [ok_b], str(tmp_path), names)[0]            # b.txt is not a.txt
    assert not verify_step("write_file: a.txt", [read], str(tmp_path), names)[0]            # a read cannot certify a write
    assert not verify_step("write_file: b.txt", [ok_b], str(tmp_path), names)[0]            # receipt but nothing on disk
    consumed = dict(ok_a, consumed_by=0)
    assert not verify_step("write_file: a.txt", [consumed], str(tmp_path), names)[0]        # consumed once, never again
    assert not verify_step("verify the result", [read], str(tmp_path), names)[0]            # 90.2: an unrelated action never proves a generic step
    assert verify_step("list the files in the workspace", [read], str(tmp_path), names)[0]  # 90.2: the requested action does
    assert not step_evidence({"text": "write_file: a.txt"}, [{"name": "write_file", "arguments": {"path": "b.txt"}, "failed": False}], ["write_file"])


def test_observe_effects_reads_the_world(tmp_path):
    (tmp_path / "x.txt").write_text("hello")
    eff = observe_effects("write_file", {"path": "x.txt"}, json.dumps({"path": str(tmp_path / "x.txt"), "bytes": 5}), str(tmp_path))
    assert eff["files"][0]["path"] == "x.txt" and len(eff["files"][0]["sha256"]) == 64
    assert observe_effects("create_widget", {}, json.dumps({"ok": True, "widget_id": "w1"}), str(tmp_path)) == {"widgets": ["w1"]}


def test_read_then_done_is_rejected_and_one_write_completes_only_its_step(tmp_path):
    engine = _engine(tmp_path, [_call("plan_task", {"steps": ["write_file: result.txt"]}), _call("list_files", {}),
                                _call("update_plan", {"step": 0, "status": "done"}), {"content": "Finished.", "tool_calls": []}])
    s = engine.sessions.create_session("a")["id"]
    r = engine.agent_chat("Create result.txt with the text AUDIT.", session_id=s)
    plan = engine.session_plans.get(s)
    assert plan["steps"][0]["status"] != "done" and not (tmp_path / "result.txt").exists()
    up = [t for t in r["tool_trace"] if t["name"] == "update_plan"][0]
    assert "post-condition not met" in up["result"]
    (tmp_path / "b").mkdir()
    engine2 = _engine(tmp_path / "b", [_call("plan_task", {"steps": ["write_file: a.txt", "write_file: b.txt"]}),
                                       _call("write_file", {"path": "a.txt", "content": "AUDIT"}),
                                       _call("update_plan", {"step": 0, "status": "done"}), {"content": "First written.", "tool_calls": []}])
    s2 = engine2.sessions.create_session("b")["id"]
    engine2.agent_chat("Write a.txt and b.txt, each containing AUDIT.", session_id=s2)
    plan2 = engine2.session_plans.get(s2)
    assert [x["status"] for x in plan2["steps"]] == ["done", "active"] and plan2["status"] == "active"
    assert plan2["steps"][0]["evidence"] and engine2.receipts.for_session(s2)[1]["consumed_by"] == 0


def test_partial_status_unknown_outcome_and_cancel(tmp_path):
    assert finalize_status({"status": "active", "steps": [{"status": "done"}, {"status": "failed"}]}) == "partial"
    assert finalize_status({"status": "active", "steps": [{"status": "failed"}, {"status": "failed"}]}) == "failed"
    engine = _engine(tmp_path, [{"content": "Checking.", "tool_calls": []}])
    s = engine.sessions.create_session("c")["id"]
    engine.session_plans.save(s, {"title": "t", "status": "active", "authorization": {"origin": "user_approval", "message": "yes", "turn_seq": 1},
                                  "steps": [{"text": "write_file: a.txt", "status": "active"}]})
    engine.receipts.open(s, 1, "write_file", {"path": "a.txt"}, "write", "approved_plan", 0)     # a crash left it pending
    block = begin_turn(engine, s, "continue")
    assert "UNKNOWN OUTCOME" in block and "a.txt" in block
    begin_turn(engine, s, "Stop. Cancel the remaining work.")
    assert engine.receipts.for_session(s)[0]["status"] == "cancelled"


def test_idempotent_write_and_materializer_receipt(tmp_path):
    from hmgfu.tool_builtins import set_workspace, write_file
    set_workspace(str(tmp_path))
    first = write_file("same.txt", "HELD"); second = write_file("same.txt", "HELD")
    assert not first.get("already_present") and second.get("already_present") and (tmp_path / "same.txt").read_text() == "HELD"
    html = "<!doctype html><html><body><h1>T</h1><p>" + "t" * 90 + "</p></body></html>"
    engine = _engine(tmp_path, [_call("plan_task", {"steps": ["write_file: held.html"]}), {"content": "Here it is.\n```html\n" + html + "\n```", "tool_calls": []}])
    s = engine.sessions.create_session("m")["id"]
    engine.agent_chat("Make me a page named held.html and mark the plan done.", session_id=s)
    plan = engine.session_plans.get(s)
    assert (tmp_path / "held.html").exists() and plan["steps"][0]["status"] == "done" and plan["steps"][0]["evidence"]


def test_file_tools_accept_path_aliases_and_reject_folders(tmp_path):
    from hmgfu.tool_builtins import set_workspace, write_file
    set_workspace(str(tmp_path))
    assert "folder" in write_file("", "x").get("error", "") or "file name" in write_file("", "x").get("error", "")
    assert "folder" in write_file(".", "x").get("error", "")
    engine = _engine(tmp_path, [_call("write_file", {"filename": "aliased.txt", "content": "ok"}), {"content": "Written.", "tool_calls": []}])
    r = engine.agent_chat("create aliased.txt with ok", session_id=engine.sessions.create_session("f")["id"])
    assert not r["tool_trace"][0]["failed"] and (tmp_path / "aliased.txt").read_text() == "ok"


def test_free_text_plan_status_and_plan_update_claims(tmp_path):
    from hmgfu.plans import plan_action
    from hmgfu.saydo import classify, transactions_of
    engine = _engine(tmp_path, [])
    engine._turn_session = engine.sessions.create_session("s")["id"]
    engine._turn_plan = {"title": "t", "status": "active", "steps": [{"text": "a", "status": "active"}, {"text": "b", "status": "pending"}]}
    out = plan_action(engine, "update_plan", {"step": 0, "status": "failed due to a permission error; switching approach"})
    assert out["ok"] and engine._turn_plan["steps"][0]["status"] == "failed" and "permission" in engine._turn_plan["steps"][0]["note"]
    tx = transactions_of([{"name": "update_plan", "failed": False}], [], None, episode=True)
    assert tx["plan_ops"] == 1 and not classify("I've updated the plan to reflect the failure.", [], tx)["false_exec_claim"]
    assert classify("I've completed the creation of all three files.", [], tx)["false_exec_claim"]              # no effect ran
    tx2 = transactions_of([{"name": "write_file", "arguments": {"path": "a.txt"}, "failed": False}], [], None)
    assert not classify("I've completed the creation of the file.", [], tx2)["false_exec_claim"]


def test_plan_task_accepts_step_aliases(tmp_path):
    from hmgfu.plans import plan_action
    engine = _engine(tmp_path, [])
    engine._turn_session = engine.sessions.create_session("p")["id"]
    engine._turn_effects_allowed = True
    out = plan_action(engine, "plan_task", {"title": "T", "tasks": ["write_file: a.txt", "write_file: b.txt"]})
    assert out["ok"] and [s["text"] for s in engine._turn_plan["steps"]] == ["write_file: a.txt", "write_file: b.txt"]
    assert "error" in plan_action(engine, "plan_task", {"title": "T"})                  # still no steps → honest error


def test_abbreviations_are_not_files_and_thinking_steps_need_no_receipt():
    names = ["write_file", "create_widget", "bash"]
    assert postcondition("Identify the categories of links the user wants to store (e.g., Work, Personal).", names)["files"] == []
    assert postcondition("Identify the categories of links the user wants (e.g., Work).", names)["thinking"]
    assert postcondition("write_file: notes.v2.txt", names)["files"] == ["notes.v2.txt"]
    ok, evidence, missing = verify_step("Identify the categories of links (e.g., Work).", [], "", names)
    assert ok and evidence == [] and missing == []
    widget_receipt = {"id": "w", "tool": "create_widget", "status": "ok", "consumed_by": None, "effects": {"widgets": ["w_1"]}}
    ok2, ev2, _ = verify_step("Create a 'Link Hub' widget using create_widget(type='table').", [widget_receipt], "", names)
    assert ok2 and ev2 == ["w"]                       # the widget receipt goes to the widget step, not the thinking step
