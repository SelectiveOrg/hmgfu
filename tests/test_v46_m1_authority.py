"""Phase 70 M1 — scoped authority record, prohibition, resume never mints, declared effects, shell grammar,
list_files, alias resolved once, materializer receipt."""

from __future__ import annotations

import json
from types import SimpleNamespace

from hmgfu.authority import decide, effect_of, guard, shell_is_mutating, shell_is_read_only
from hmgfu.session_plans import begin_turn, is_authorized
from hmgfu.speech_act import prohibits_effect
from tests.test_v2_agent import make_agent


def _engine(tmp_path, script, act="statement"):
    engine, _ = make_agent(tmp_path, script)
    engine.settings.set("grader_enabled", False)
    engine.settings.set("workspace_dir", str(tmp_path))
    engine.settings.set("plan_step_recall", False)
    engine.settings.set("full_dream_every_n_turns", 0)      # engines share the tmp DB: a dream would eat a scripted reply
    engine.settings.set("mini_dream_every_n_turns", 0)
    engine.settings.set("thinking_mode", "off")               # a thinking pass would consume the scripted reply
    orig = engine.retrieve
    def retrieve(text, **kw):
        q, rs, ms = orig(text, **kw)
        q.conversation_act = act; q.requested_tools = []; q.action_requested = False
        return q, rs, ms
    engine.retrieve = retrieve
    return engine


def _call(name, arguments):
    return {"content": "", "tool_calls": [{"name": name, "arguments": arguments}]}


def _sid(engine):
    return engine.sessions.create_session("m1")["id"]


def test_shell_grammar_is_fail_closed():
    for cmd in ["find . -exec touch marker.txt +", "env touch marker.txt", "xargs touch marker.txt",
                "awk 'BEGIN {system(\"touch marker.txt\")}'", "sed 'w marker.txt' input.txt", "sort input.txt -o marker.txt",
                "git config audit.marker yes", "git branch audit-test main", "git tag audit-test", "git worktree add ../x",
                "date --set=2026-09-05", "cd .\ntouch marker.txt", "ls -la; rm -rf build", "cat a | tee b", "ls $(rm x)",
                "cat a.txt > b.txt", "git checkout -- .", "python -c \"print(1)\"", "ls --color=always"]:
        assert shell_is_mutating(cmd), cmd
    for cmd in ["git status", "ls -la", "ls", "pwd", "cat README.md", "head -n 3 a.txt", "head -3 a.txt", "tail -n 20 log.txt",
                "wc -l data.csv", "git log --oneline -5", "git diff --stat", "git branch --show-current", "tree -L 2"]:
        assert shell_is_read_only(cmd), cmd


def test_effects_declared_and_unknown_is_an_effect():
    assert effect_of("read_file", {}) == "read" and effect_of("create_widget", {}) == "write"
    assert effect_of("bash", {"command": "ls"}) == "read" and effect_of("bash", {"command": "rm x"}) == "write"
    assert effect_of("audit_export", {}, {}) == "unknown" and effect_of("audit_export", {}, {"x-effect": "read"}) == "read"
    engine = SimpleNamespace(_turn_effects_allowed=False, _turn_plan=None, _turn_unconfirmed_effects=[],
                             tools=SimpleNamespace(schemas={"audit_export": {}}))
    assert guard(engine, "audit_export", {}) is not None and engine._turn_unconfirmed_effects[0]["effect"] == "unknown"
    engine._turn_effects_allowed = True
    assert guard(engine, "audit_export", {}) is None                                  # the user asked → allowed


def test_prohibition_closes_authority(tmp_path):
    assert prohibits_effect("Do not create a widget. Just answer.") and prohibits_effect("Não cries nenhum ficheiro, responde só.")
    assert prohibits_effect("please don't build anything") and not prohibits_effect("create a widget for my links")
    engine = _engine(tmp_path, [_call("create_widget", {"type": "note", "title": "Canary", "props": {"text": "x"}}), {"content": "Done.", "tool_calls": []}])
    r = engine.agent_chat("Do not create a widget. Just answer.", session_id=_sid(engine))
    assert r["tool_trace"][0]["blocked"] and engine.sessions.widgets(r["session_id"]) == []


def test_resume_never_mints_approval_but_the_users_yes_does(tmp_path):
    engine = _engine(tmp_path, [_call("plan_task", {"title": "unrequested", "steps": ["create a note widget"]}),
                                {"content": "Volcanoes are geological features.", "tool_calls": []},
                                _call("create_widget", {"type": "note", "title": "Unasked", "props": {"text": "x"}}),
                                {"content": "A note.", "tool_calls": []},
                                _call("create_widget", {"type": "note", "title": "Asked", "props": {"text": "x"}}),
                                {"content": "Built.", "tool_calls": []}], act="question")
    s = _sid(engine)
    engine.agent_chat("What do you know about volcanoes?", session_id=s)
    assert not is_authorized(engine.session_plans.get(s))
    r = engine.agent_chat("Thanks.", session_id=s)
    assert engine.sessions.widgets(s) == [] and any(t["blocked"] for t in r["tool_trace"])   # resume did not mint
    assert not is_authorized(engine.session_plans.get(s))
    r3 = engine.agent_chat("yes, go ahead", session_id=s)                                 # the USER approves
    assert is_authorized(engine.session_plans.get(s)) and len(engine.sessions.widgets(s)) == 1
    assert engine.session_plans.get(s)["authorization"]["origin"] == "user_approval"


def test_legacy_boolean_plan_is_unapproved(tmp_path):
    engine = _engine(tmp_path, [_call("create_widget", {"type": "note", "title": "Old", "props": {"text": "x"}}), {"content": "ok", "tool_calls": []}])
    s = _sid(engine)
    engine.session_plans.save(s, {"title": "old", "status": "active", "authorized": True, "steps": [{"text": "create_widget: Old", "status": "active"}]})
    block = begin_turn(engine, s, "continue")
    assert "NONE ON RECORD" in block
    r = engine.agent_chat("continue", session_id=s)
    assert engine.sessions.widgets(s) == [] and r["tool_trace"][0]["blocked"]


def test_approved_plan_scope_tool_and_file(tmp_path):
    engine = _engine(tmp_path, [_call("plan_task", {"title": "Links", "steps": ["create the links widget"], "status": "proposed"}),
                                {"content": "I can do that.", "tool_calls": []},
                                _call("write_file", {"path": "notes.txt", "content": "x"}),
                                _call("create_widget", {"type": "note", "title": "Links", "props": {"text": "links"}}),
                                {"content": "Done.", "tool_calls": []}])
    s = _sid(engine)
    engine.agent_chat("you could maybe make a note widget with my links", session_id=s)
    r = engine.agent_chat("yes", session_id=s)
    by = {t["name"]: t for t in r["tool_trace"]}
    assert by["write_file"]["blocked"] and "scope" in by["write_file"]["result"] and not by["create_widget"]["blocked"]
    assert not (tmp_path / "notes.txt").exists() and len(engine.sessions.widgets(s)) == 1
    plan = {"title": "files", "status": "active", "authorization": {"origin": "user_approval", "message": "yes", "turn_seq": 1},
            "steps": [{"text": "write_file: a.txt", "status": "active"}, {"text": "write_file: b.txt", "status": "pending"}]}
    fake = SimpleNamespace(_turn_effects_allowed=False, _turn_prohibited=False, _turn_plan=plan, _turn_unconfirmed_effects=[],
                           tools=SimpleNamespace(schemas={"write_file": {"x-effect": "write"}}))
    assert decide(fake, "write_file", {"path": "a.txt"}).allowed and not decide(fake, "write_file", {"path": "c.txt"}).allowed


def test_alias_resolved_once_and_materializer_leaves_a_receipt(tmp_path):
    engine = _engine(tmp_path, [_call("create_widgett", {"type": "note", "title": "Groceries", "props": {"text": "milk"}}), {"content": "Created.", "tool_calls": []}])
    r = engine.agent_chat("create a note widget titled Groceries with the text milk", session_id=_sid(engine))
    t = r["tool_trace"][0]
    assert t["name"] == "create_widget" and t["alias"] == "create_widgett" and not t["blocked"] and "_rerouted" not in t["result"]
    html = "<!doctype html><html><body><h1>Tides</h1><p>" + "t" * 90 + "</p></body></html>"
    engine2 = _engine(tmp_path, [{"content": "Here it is.\n```html\n" + html + "\n```", "tool_calls": []}])
    r2 = engine2.agent_chat("make me a page named tides.html explaining tides", session_id=_sid(engine2))
    wf = [t for t in r2["tool_trace"] if t["name"] == "write_file"]
    assert wf and wf[0]["synthetic"] == "materializer" and not wf[0]["failed"] and (tmp_path / "tides.html").exists()
    engine3 = _engine(tmp_path, [{"content": "A draft.\n```html\n" + html + "\n```", "tool_calls": []}])
    r3 = engine3.agent_chat("maybe later we could make a page about tides, not now", session_id=_sid(engine3))
    assert not (tmp_path / "app.html").exists() and any(t["blocked"] for t in r3["tool_trace"]) and "Shall I go ahead" in r3["response"]


def test_list_files_is_the_native_read(tmp_path):
    engine = _engine(tmp_path, [_call("list_files", {}), {"content": "The workspace has README.txt.", "tool_calls": []}], act="question")
    (tmp_path / "README.txt").write_text("x")
    r = engine.agent_chat("what files are in the workspace?", session_id=_sid(engine))
    out = json.loads(r["tool_trace"][0]["result"])
    assert not r["tool_trace"][0]["blocked"] and any(f["name"] == "README.txt" for f in out["files"])


def test_long_cancellation_revokes(tmp_path):
    engine = _engine(tmp_path, [])
    s = _sid(engine)
    engine.session_plans.save(s, {"title": "t", "status": "active", "authorization": {"origin": "user_approval", "message": "yes", "turn_seq": 1},
                                  "steps": [{"text": "write_file: a.txt", "status": "active"}]})
    text = "Stop. Cancel the unfinished work. " + "The business requirements have changed and the previous deliverable is no longer useful. " * 3
    begin_turn(engine, s, text)
    assert engine.session_plans.get(s)["status"] == "abandoned"


def test_side_effects_are_never_forced_when_the_boundary_would_block(tmp_path):
    from types import SimpleNamespace as NS
    from hmgfu.turn_events import plan_turn_actions
    engine = _engine(tmp_path, [])
    engine._turn_step_tools = []
    q = NS(requested_tools=["write_file"], action_requested=True, extractor="nano", needs_memory=False, conversation_act="statement")
    requested, forced, _ = plan_turn_actions(engine, q, "maybe later we could make a page, not now", ["write_file", "read_file"], [])
    assert not engine._turn_effects_allowed and forced == []                       # suggestion: nothing forced
    q2 = NS(requested_tools=["write_file"], action_requested=True, extractor="nano", needs_memory=False, conversation_act="statement")
    _, forced2, _ = plan_turn_actions(engine, q2, "make me a page named tides.html now", ["write_file"], [])
    assert engine._turn_effects_allowed and forced2 == ["write_file"]              # order: forced as before
