"""Phase 67 — say-do fidelity: claims as contracts, session plans with approval, anaphora window,
update form, workspace scoping, self-instructed recall. Deterministic (fake provider + fake embedder)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from hmgfu.facts import FactStore
from hmgfu.saydo import classify, transactions_of
from hmgfu.session_plans import SessionPlanStore, approval_signal, finalize_status, pinned_block
from hmgfu.speech_act import refers_to_workspace
from tests.test_v2_agent import make_agent


def _engine(tmp_path, script, router=None):
    engine, _ = make_agent(tmp_path, script)
    engine.settings.set("grader_enabled", False)     # the grader would consume a scripted provider reply
    if router:
        engine.sensitizer.extract = router
    return engine


def _sid(engine):
    return engine.sessions.create_session("say-do")["id"]      # a REAL session id (unknown ids get replaced)


def test_approval_signal_only_with_pending_proposal():
    assert approval_signal("yes please", True) == "yes" and approval_signal("sim", True) == "yes"
    assert approval_signal("no, not now", True) == "no" and approval_signal("não", True) == "no"
    assert approval_signal("yes", False) is None
    assert approval_signal("yes but first tell me the weather in Aveiro and then the news please", True) is None


def test_session_plan_lifecycle_and_pinned_block(tmp_path):
    st = SessionPlanStore(str(tmp_path / "p.db"))
    st.save("s1", {"title": "Links widget", "status": "proposed",
                   "steps": [{"text": "create widget", "status": "pending"}, {"text": "add links", "status": "pending"}]})
    assert st.pending("s1") and not st.resumable("s1")
    p = st.set_status("s1", "active")
    assert p["steps"][0]["status"] == "active" and st.resumable("s1")
    assert "PINNED PLAN (ACTIVE)" in pinned_block(p) and "[>] 0. create widget" in pinned_block(p)
    p["steps"][0]["status"] = "done"; p["steps"][1]["status"] = "done"
    assert finalize_status(p) == "done"
    assert st.set_status("s1", "abandoned", "no")["status"] == "abandoned" and st.resumable("s1") is None


def test_classify_claims_against_telemetry():
    c = classify("I'll take a look at the project structure to identify the issue.", [], {"facts": 0, "directive": False, "effects": 0})
    assert c["intent_no_action"] and c["read_only"]
    c = classify("I've updated your car location link in my records.", [], {"facts": 0, "directive": False, "effects": 0})
    assert c["false_exec_claim"]
    c = classify("I've updated your car location link.", [], {"facts": 1, "directive": False, "effects": 0})
    assert c["exec_claim"] and not c["false_exec_claim"]
    assert transactions_of([{"name": "create_widget", "failed": False}], [], None)["effects"] == 1


def test_intent_without_action_becomes_a_proposal_and_yes_activates_it(tmp_path):
    engine = _engine(tmp_path, [
        {"content": "I'll create a link storage widget for you.", "tool_calls": []},     # promise, no tool
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "note", "title": "Links",
                                                                               "props": {"text": "links"}}}]},
        {"content": "Done — the widget is on your canvas.", "tool_calls": []},
    ])
    s = _sid(engine)
    r1 = engine.agent_chat("you can maybe create a widget to keep my links", explicit=False, session_id=s)
    assert "Shall I go ahead" in r1["response"] and engine.session_plans.pending(s)
    assert not [t for t in r1["tool_trace"] if t["name"] == "create_widget"]           # nothing built yet
    r2 = engine.agent_chat("yes", explicit=False, session_id=s)
    assert any(t["name"] == "create_widget" and not t["blocked"] for t in r2["tool_trace"])   # approved → built
    assert engine.session_plans.get(s)["status"] in ("done", "active")


def test_decline_abandons_and_builds_nothing(tmp_path):
    engine = _engine(tmp_path, [
        {"content": "I'll create a link storage widget for you.", "tool_calls": []},
        {"content": "Okay, I won't.", "tool_calls": []},
    ])
    s = _sid(engine)
    engine.agent_chat("you can maybe create a widget to keep my links", explicit=False, session_id=s)
    r2 = engine.agent_chat("no, not now", explicit=False, session_id=s)
    assert r2["tool_trace"] == [] and engine.session_plans.get(s)["status"] == "abandoned"


def test_read_only_intent_is_executed_now(tmp_path):
    engine = _engine(tmp_path, [
        {"content": "Let me check the workspace files.", "tool_calls": []},               # promise
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "ls"}}]},  # the re-ask acts
        {"content": "The workspace contains README.txt.", "tool_calls": []},
    ])
    r = engine.agent_chat("can you check what files are in the workspace?", explicit=False, session_id=_sid(engine))
    assert any(t["name"] == "bash" for t in r["tool_trace"]) and "Shall I go ahead" not in r["response"]


def test_false_execution_claim_is_corrected_and_update_form_writes(tmp_path):
    engine = _engine(tmp_path, [{"content": "I've updated your car location link in my records.", "tool_calls": []}] * 2)
    r = engine.agent_chat("I've been told nothing about links.", explicit=False, session_id=_sid(engine))
    assert "Correction: nothing was actually written" in r["response"]
    fs = engine.facts
    fs.apply("here is the link for my car location: http://198.51.100.7/old", "user_explicit")
    r2 = engine.agent_chat("heres the updated link: http://198.51.100.7/new", explicit=False, session_id=_sid(engine))
    assert next(f["value"] for f in fs.active() if f["key"] == "asset.car_location_link") == "http://198.51.100.7/new"
    assert "Correction" not in r2["response"]                                           # the claim is now TRUE


def test_update_form_targets_the_single_typed_slot_else_stays_open(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    assert fs.apply("here's the updated link: http://198.51.100.7/c")["key"] == "open.link"   # no URL slot yet
    fs.apply("here is the link for my car location: http://198.51.100.7/a", "user_explicit")
    r = fs.apply("here's the updated link: http://198.51.100.7/d")
    assert r["key"] == "asset.car_location_link" and r["prev"] == "http://198.51.100.7/a"   # the one URL slot
    fs.apply("my lucky number is 17", "user_explicit")
    assert fs.apply("here's the new number: 42")["key"] == "misc.lucky_number"            # the one number slot


def test_recent_window_gives_anaphora_a_referent_and_workspace_is_scoped(tmp_path):
    engine = _engine(tmp_path, [{"content": "Here it is: http://198.51.100.7/x", "tool_calls": []},
                                {"content": "It should be clickable now.", "tool_calls": []}])
    engine.facts.apply("here is the link for my car location: http://198.51.100.7/x", "user_explicit")
    s = _sid(engine)
    engine.agent_chat("share the link to my car location", explicit=False, session_id=s)
    captured = {}
    orig = engine._tool_loop
    def spy(messages, *a, **k):
        captured["system"] = messages[0]["content"]; return orig(messages, *a, **k)
    engine._tool_loop = spy
    engine.agent_chat("hmm, is not clicable i think it might be ui issue.", explicit=False, session_id=s)
    assert "Recent conversation" in captured["system"] and "share the link to my car location" in captured["system"]
    assert "ACTIVE WORKSPACE" not in captured["system"]          # a UI complaint is not a project question
    assert refers_to_workspace("check the files in the repo") and not refers_to_workspace("it is not clickable")


def test_plan_step_recall_returns_memory_in_the_tool_result(tmp_path):
    engine = _engine(tmp_path, [])
    engine.ingest("the notes folder must use the hmg say-do test line", source="user_explicit")
    out = json.loads(engine.tools.execute_tool("plan_task", {"title": "notes", "steps": ["create the notes files with the test line", "verify"]}))
    assert out["ok"] and "memory_for_step" in out and any("say-do" in m for m in out["memory_for_step"])


def test_plan_survives_restart_and_resumes(tmp_path):
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "notes", "steps": ["write note one", "write note two", "write note three"]}}]},
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo a"}}]},
        {"content": "Step a done, continuing.", "tool_calls": []},
    ])
    engine.settings.set("plan_step_recall", False)
    s = _sid(engine)
    r1 = engine.agent_chat("plan and do a, b, c", explicit=False, session_id=s)
    saved = engine.session_plans.get(s)
    assert saved and saved["status"] in ("active", "done")
    engine2 = _engine(tmp_path, [{"content": "Continuing the plan.", "tool_calls": []}])   # restart
    engine2.settings.set("plan_step_recall", False)
    captured = {}
    orig = engine2._tool_loop
    def spy(messages, *a, **k):
        captured["system"] = messages[0]["content"]; return orig(messages, *a, **k)
    engine2._tool_loop = spy
    if saved["status"] == "active":
        engine2.agent_chat("continue", explicit=False, session_id=s)
        assert "PINNED PLAN (ACTIVE)" in captured["system"]


def test_suggestion_with_side_effect_is_proposed_by_the_harness(tmp_path):
    from hmgfu.speech_act import is_suggestion
    assert is_suggestion("you can maybe create a widget to keep links") and not is_suggestion("create a links widget")
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "note", "title": "Link Storage",
                                                                               "props": {"text": "links"}}}]},
        {"content": "I can set up a Link Storage widget for you.", "tool_calls": []},
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "note", "title": "Link Storage",
                                                                               "props": {"text": "links"}}}]},
        {"content": "Done.", "tool_calls": []},
    ])
    s = _sid(engine)
    r1 = engine.agent_chat("you can maybe create a widget to keep links i can click", explicit=False, session_id=s)
    assert all(t["blocked"] for t in r1["tool_trace"] if t["name"] == "create_widget")   # not executed
    assert "Shall I go ahead" in r1["response"] and engine.session_plans.pending(s)         # proposed by the harness
    r2 = engine.agent_chat("yes", explicit=False, session_id=s)
    assert any(t["name"] == "create_widget" and not t["blocked"] for t in r2["tool_trace"])  # approved → built


def test_let_me_know_is_not_a_promise():
    c = classify("Understood. Just let me know whenever you're ready.", [], {"facts": 0, "directive": False, "effects": 0})
    assert not c["intent_no_action"]


def test_plan_task_on_a_suggestion_turn_is_forced_to_a_proposal(tmp_path):
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "Links", "steps": ["create widget", "add links"]}}]},
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "note", "title": "Links",
                                                                               "props": {"text": "links"}}}]},
        {"content": "I can build a links widget.", "tool_calls": []},
    ])
    s = _sid(engine)
    r1 = engine.agent_chat("you can maybe create a widget to keep links", explicit=False, session_id=s)
    assert engine.session_plans.pending(s) and "Shall I go ahead" in r1["response"]
    assert all(t["blocked"] for t in r1["tool_trace"] if t["name"] == "create_widget")   # gate stayed shut


def test_promise_after_approval_is_executed_not_reproposed(tmp_path):
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "Links", "steps": ["create widget"],
                                                                           "status": "proposed"}}]},
        {"content": "I can build a Link Storage widget.", "tool_calls": []},
        {"content": "I'm on it! I'll start by creating the widget.", "tool_calls": []},      # promise after approval
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "note", "title": "Links",
                                                                               "props": {"text": "links"}}}]},
        {"content": "The widget is on your canvas.", "tool_calls": []},
    ])
    s = _sid(engine)
    r1 = engine.agent_chat("you can maybe create a widget to keep links", explicit=False, session_id=s)
    assert "Shall I go ahead" in r1["response"] and engine.session_plans.pending(s)
    r2 = engine.agent_chat("yes please", explicit=False, session_id=s)
    assert any(t["name"] == "create_widget" and not t["blocked"] for t in r2["tool_trace"])   # re-ask executed
    assert "Shall I go ahead" not in r2["response"] and engine.session_plans.get(s)["status"] != "proposed"


def test_continue_on_an_active_plan_with_no_tool_triggers_the_approved_reask(tmp_path):
    from hmgfu.session_plans import is_continuation
    assert is_continuation("continue") and is_continuation("next!") and not is_continuation("continue the weather report for Aveiro")
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "notes", "steps": ["write note one", "write note two"]}}]},
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo a"}}]},
        {"content": "Step a done.", "tool_calls": []},
    ])
    engine.settings.set("plan_step_recall", False)
    s = _sid(engine)
    engine.agent_chat("plan and do a, b", explicit=False, session_id=s)
    engine.session_plans.save(s, {"title": "notes", "status": "active",
                                  "authorization": {"origin": "user_request", "message": "plan and do a, b", "turn_seq": 1},
                                  "steps": [{"text": "a", "status": "done"}, {"text": "b", "status": "active"}]})
    engine2 = _engine(tmp_path, [
        {"content": "I apologize, I have not received a new instruction.", "tool_calls": []},   # the apology
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo b"}}]},   # the re-ask acts
        {"content": "Step b done.", "tool_calls": []},
    ])
    engine2.settings.set("plan_step_recall", False)
    r = engine2.agent_chat("continue", explicit=False, session_id=s)
    assert any(t["name"] == "bash" for t in r["tool_trace"]) and "apologize" not in r["response"]
    assert engine2.session_plans.get(s)["status"] == "done"


def test_sparse_widget_call_gets_props_from_the_ledger_and_plan_task_never_replaces_an_approved_plan(tmp_path):
    from hmgfu.deixis import grounded_props
    lines = ["Car location link: http://198.51.100.7/x"]
    assert grounded_props("table", None, lines) == {"rows": [{"name": "Car location link", "url": "http://198.51.100.7/x"}]}
    assert "http://198.51.100.7/x" in grounded_props("note", None, lines)["text"]
    assert grounded_props("weather", None, lines) is None and grounded_props("table", None, []) is None
    c = classify("I'm getting started on your Link Hub widget now.", [], {"facts": 0, "directive": False, "effects": 0})
    assert c["intent_no_action"]
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "Links", "steps": ["create the links widget"],
                                                                           "status": "proposed"}}]},
        {"content": "I can build it.", "tool_calls": []},
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "Link Hub", "steps": ["x", "y"]}}]},  # re-plan
        {"content": "I'm getting started on your Link Hub widget now.", "tool_calls": []},                    # promise
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "table", "title": "Links"}}]},  # sparse
        {"content": "Built.", "tool_calls": []},
    ])
    engine.facts.apply("here is the link for my car location: http://198.51.100.7/x", "user_explicit")
    s = _sid(engine)
    engine.agent_chat("you can maybe create a widget to keep links", explicit=False, session_id=s)
    r2 = engine.agent_chat("yes please", explicit=False, session_id=s)
    pt = next(t for t in r2["tool_trace"] if t["name"] == "plan_task")
    assert json.loads(pt["result"]).get("already_active")                                    # not replaced
    cw = next(t for t in r2["tool_trace"] if t["name"] == "create_widget")
    assert not cw["failed"] and "http://198.51.100.7/x" in json.dumps(cw["arguments"])       # props built, link inside
    assert engine.session_plans.get(s)["title"] == "Links"


def test_approved_step_tool_is_offered_and_required(tmp_path):
    from hmgfu.session_plans import tools_for_step
    assert tools_for_step("create_widget: Link Storage", ["create_widget", "bash"]) == ["create_widget"]
    assert tools_for_step("create the links widget", ["create_widget", "bash", "plan_task"]) == ["create_widget"]
    assert tools_for_step("verify the result", ["create_widget", "bash"]) == []
    engine = _engine(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {"title": "Links", "steps": ["create the links widget"],
                                                                           "status": "proposed"}}]},
        {"content": "I can build it.", "tool_calls": []},
        {"content": "I'll get that set up for you right now.", "tool_calls": []},          # ignores the plan
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "note", "title": "Links",
                                                                               "props": {"text": "links"}}}]},
        {"content": "Built.", "tool_calls": []},
    ])
    s = _sid(engine)
    engine.agent_chat("you can maybe create a widget to keep links", explicit=False, session_id=s)
    seen = []
    orig = engine._tool_loop
    def spy(messages, schemas, *a, **k):
        seen.append((sorted(t["name"] for t in schemas), list(k.get("required_actions") or [])))
        return orig(messages, schemas, *a, **k)
    engine._tool_loop = spy
    r2 = engine.agent_chat("yes please", explicit=False, session_id=s)
    assert all("create_widget" in names for names, _ in seen)                      # offered on every pass
    assert any("create_widget" in req for _, req in seen)                          # required (turn or re-ask)
    assert any(t["name"] == "create_widget" and not t["blocked"] for t in r2["tool_trace"])


def test_end_turn_completes_only_the_worked_step(tmp_path):
    from hmgfu.session_plans import end_turn
    engine = _engine(tmp_path, [])
    s = _sid(engine)
    engine._turn_session = s
    from hmgfu.receipts import close_for, open_for
    rid = open_for(engine, "bash", {"command": "echo a"}, 1)
    close_for(engine, rid, "bash", {"command": "echo a"}, '{"exit_code": 0}', False)
    engine._turn_plan = {"title": "notes", "status": "active",
                         "steps": [{"text": "a", "status": "active"}, {"text": "b", "status": "pending"}, {"text": "c", "status": "pending"}]}
    end_turn(engine, s, [{"name": "bash", "failed": False}], forced_finalization=False)
    p = engine.session_plans.get(s)
    assert [x["status"] for x in p["steps"]] == ["done", "active", "pending"] and p["status"] == "active"
    engine._turn_plan = p
    end_turn(engine, s, [{"name": "update_plan", "failed": False}], forced_finalization=False)   # planning is not work
    assert [x["status"] for x in engine.session_plans.get(s)["steps"]] == ["done", "active", "pending"]


def test_plan_remembers_its_tools_and_a_resume_requires_them(tmp_path):
    from hmgfu.session_plans import end_turn, ensure_step_tools
    engine = _engine(tmp_path, [])
    s = _sid(engine)
    engine._turn_session = s
    from hmgfu.receipts import close_for, open_for
    rid = open_for(engine, "write_file", {"path": "note1.txt", "content": "x"}, 1)
    close_for(engine, rid, "write_file", {"path": "note1.txt", "content": "x"}, '{"path": "note1.txt", "bytes": 1}', False)
    engine._turn_plan = {"title": "notes", "status": "active",
                         "steps": [{"text": "note1", "status": "active"}, {"text": "note3 with the test line", "status": "pending"}]}
    end_turn(engine, s, [{"name": "write_file", "failed": False}, {"name": "update_plan", "failed": False}], forced_finalization=False)
    plan = engine.session_plans.get(s)
    assert plan["tools_used"] == ["write_file"]                                   # planning is not a used tool
    schemas = ensure_step_tools(engine, plan, [])                                  # router offered nothing
    assert engine._turn_step_tools == ["write_file"] and [x["name"] for x in schemas] == ["write_file"]
