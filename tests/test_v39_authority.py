"""Phase 69.1 — ONE authority boundary: aliases, mutating shell, model-declared plans, the materializer."""

from __future__ import annotations

import json

from hmgfu.authority import effect_authorized, is_side_effect, shell_is_mutating
from tests.test_v2_agent import make_agent


def _engine(tmp_path, script, act="statement"):
    engine, _ = make_agent(tmp_path, script)
    engine.settings.set("grader_enabled", False)
    engine.settings.set("workspace_dir", str(tmp_path))
    orig = engine.retrieve
    def retrieve(text, **kw):
        q, rs, ms = orig(text, **kw)
        q.conversation_act = act; q.requested_tools = []; q.action_requested = False
        return q, rs, ms
    engine.retrieve = retrieve
    return engine


def _sid(engine):
    return engine.sessions.create_session("auth")["id"]


def _call(name, arguments):
    return {"content": "", "tool_calls": [{"name": name, "arguments": arguments}]}


def test_shell_classifier_and_effect_predicate():
    assert shell_is_mutating("rm -rf build") and shell_is_mutating("echo hi > notes.txt")
    assert shell_is_mutating("git commit -m x") and shell_is_mutating("pip install requests")
    assert shell_is_mutating("cd src && touch a.py") and shell_is_mutating("Remove-Item a.txt")
    assert not shell_is_mutating("ls -la") and not shell_is_mutating("git status")
    assert not shell_is_mutating("cat README.md | head")                   # 95.23: a pipeline of READS is a read (70.6 refused every `|`)
    assert shell_is_mutating("cat README.md | tee out.txt")                # ... and a pipeline with a writing stage is not
    assert is_side_effect("create_widget", {}) and is_side_effect("bash", {"command": "mkdir x"})
    assert not is_side_effect("bash", {"command": "ls"}) and not is_side_effect("read_file", {})


def test_alias_of_a_side_effect_is_gated(tmp_path):
    engine = _engine(tmp_path, [_call("create_widge", {"type": "note", "title": "Canary", "props": {"text": "x"}}),
                                {"content": "Noted.", "tool_calls": []}])
    r = engine.agent_chat("Perhaps we could display a note later; wait for confirmation.", session_id=_sid(engine))
    cw = [t for t in r["tool_trace"] if t.get("alias") == "create_widge"]          # 70.7: resolved once
    assert cw and cw[0]["name"] == "create_widget" and cw[0]["blocked"]            # never executed
    assert engine.sessions.widgets(r["session_id"]) == [] and "Shall I go ahead" in r["response"]


def test_mutating_shell_is_gated_but_read_only_shell_is_not(tmp_path):
    engine = _engine(tmp_path, [_call("bash", {"command": "echo canary > canary.txt"}), {"content": "Done.", "tool_calls": []}])
    r = engine.agent_chat("Perhaps make that change later, after I confirm.", session_id=_sid(engine))
    assert r["tool_trace"][0]["blocked"] and not (tmp_path / "canary.txt").exists()
    engine2 = _engine(tmp_path, [_call("bash", {"command": "ls"}), {"content": "Files listed.", "tool_calls": []}], act="question")
    r2 = engine2.agent_chat("what files are in the workspace?", session_id=_sid(engine2))
    assert not r2["tool_trace"][0]["blocked"]                                          # read-only shell runs


def test_model_declared_plan_grants_no_authority_on_a_question(tmp_path):
    engine = _engine(tmp_path, [_call("plan_task", {"title": "unrequested", "steps": ["create a note widget"]}),
                                _call("create_widget", {"type": "note", "title": "Unrequested", "props": {"text": "x"}}),
                                {"content": "Volcanoes are mountains.", "tool_calls": []}], act="question")
    r = engine.agent_chat("What do you know about volcanoes?", session_id=_sid(engine))
    cw = [t for t in r["tool_trace"] if t["name"] == "create_widget"]
    assert cw and cw[0]["blocked"] and engine.sessions.widgets(r["session_id"]) == []
    assert engine._turn_plan is None or not engine._turn_plan.get("authorization")


def test_user_approved_plan_is_authorized(tmp_path):
    engine = _engine(tmp_path, [_call("plan_task", {"title": "Links", "steps": ["create the links widget"], "status": "proposed"}),
                                {"content": "I can build it.", "tool_calls": []},
                                _call("create_widget", {"type": "note", "title": "Links", "props": {"text": "links"}}),
                                {"content": "Built.", "tool_calls": []}])
    s = _sid(engine)
    engine.agent_chat("you can maybe create a widget to keep links", session_id=s)
    r2 = engine.agent_chat("yes please", session_id=s)
    assert any(t["name"] == "create_widget" and not t["blocked"] for t in r2["tool_trace"])
    assert len(engine.sessions.widgets(s)) == 1


def test_code_block_materializer_obeys_the_boundary(tmp_path):
    html = "<!doctype html><html><body><h1>Proposed page</h1><p>" + "x" * 80 + "</p></body></html>"
    engine = _engine(tmp_path, [{"content": "Here is a possible page, awaiting confirmation.\n```html\n" + html + "\n```", "tool_calls": []}])
    r = engine.agent_chat("Maybe we could create a page later. Please wait for confirmation.", session_id=_sid(engine))
    assert not (tmp_path / "app.html").exists() and "Shall I go ahead" in r["response"]
    engine2 = _engine(tmp_path, [{"content": "Here it is.\n```html\n" + html + "\n```", "tool_calls": []}])
    engine2.agent_chat("create a page called page.html for me", session_id=_sid(engine2))
    assert (tmp_path / "page.html").exists()                                            # asked → written
