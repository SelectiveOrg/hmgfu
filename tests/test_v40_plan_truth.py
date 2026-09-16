"""Phase 69.2 — plan truth: cancel, step evidence, self-certification, failed plans, approvals, shell default."""

from __future__ import annotations

from hmgfu.authority import shell_is_mutating
from hmgfu.plans import plan_action
from hmgfu.session_plans import approval_signal, begin_turn, end_turn, finalize_status, step_evidence
from tests.test_v2_agent import make_agent


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    return engine


def test_shell_is_fail_closed_but_read_only_pipelines_pass():
    assert shell_is_mutating("synthetic-write-canary") and shell_is_mutating("unknownprog --flag")
    assert shell_is_mutating("git checkout main") and shell_is_mutating("git branch -d x") and shell_is_mutating("sed -i s/a/b/ f")
    assert not shell_is_mutating("git status") and not shell_is_mutating("git log --oneline -3")
    assert not shell_is_mutating("git log --oneline -3 | head")             # 95.23: a pipeline of reads is a read (70.6 refused every `|`)
    assert shell_is_mutating("git log --oneline -3 | xargs rm")             # ... a writing stage still refuses; chains below unchanged
    assert shell_is_mutating("cd src && ls -la | grep py") and shell_is_mutating("cat a.txt; wc -l b.txt")
    assert shell_is_mutating("cat a.txt > b.txt") and shell_is_mutating("ls $(rm x)")


def test_cancel_abandons_an_active_plan(tmp_path):
    engine = _engine(tmp_path)
    sid = engine.sessions.create_session("c")["id"]
    engine.session_plans.save(sid, {"title": "Build reports", "status": "active",
                                    "steps": [{"text": "write_file: remaining.txt", "status": "active"}]})
    block = begin_turn(engine, sid, "Stop. Cancel the remaining work.")
    assert engine.session_plans.get(sid)["status"] == "abandoned" and engine._turn_plan is None
    assert "CANCELLED" in block
    engine.session_plans.save(sid, {"title": "t", "status": "active", "steps": [{"text": "a", "status": "active"}]})
    assert "PINNED PLAN" in begin_turn(engine, sid, "continue")            # a continuation still resumes


def test_step_evidence_must_fit_the_step(tmp_path):
    known = ["write_file", "bash", "memory_timeline", "read_file", "plan_task"]
    step = {"text": "write report.txt with results", "status": "active"}
    assert not step_evidence(step, [{"name": "memory_timeline", "failed": False}], known)
    assert not step_evidence(step, [{"name": "bash", "failed": False}], known)            # 71: the step names a FILE
    assert step_evidence(step, [{"name": "write_file", "arguments": {"path": "report.txt"}, "failed": False}], known)
    named = {"text": "write_file: remaining.txt", "status": "active"}
    assert not step_evidence(named, [{"name": "bash", "failed": False}], known)      # names write_file
    assert step_evidence(named, [{"name": "write_file", "arguments": {"path": "remaining.txt"}, "failed": False}], known)   # 71: the named file
    engine = _engine(tmp_path)
    sid = engine.sessions.create_session("e")["id"]
    engine._turn_plan = {"title": "Write report", "status": "active", "steps": [{"text": "write report.txt", "status": "active"}]}
    end_turn(engine, sid, [{"name": "memory_timeline", "failed": False, "blocked": False}], False)
    assert engine._turn_plan["steps"][0]["status"] == "active" and engine._turn_plan["status"] == "active"


def test_done_claims_need_verified_receipts_and_all_failed_is_failed(tmp_path):
    engine = _engine(tmp_path)
    engine.settings.set("workspace_dir", str(tmp_path))
    from hmgfu.tool_builtins import set_workspace
    set_workspace(str(tmp_path))
    engine._turn_session = engine.sessions.create_session("r")["id"]
    engine._turn_plan = {"title": "Two files", "status": "active",
                         "steps": [{"text": "write a.txt", "status": "active"}, {"text": "write b.txt", "status": "pending"}]}
    out = plan_action(engine, "update_plan", {"step": 0, "status": "done"})
    assert not out["ok"] and engine._turn_plan["steps"][0]["status"] == "active"           # no receipt, no file
    from hmgfu.receipts import close_for, open_for
    rid = open_for(engine, "write_file", {"path": "a.txt", "content": "x"}, 1)
    (tmp_path / "a.txt").write_text("x")
    close_for(engine, rid, "write_file", {"path": "a.txt", "content": "x"}, '{"path": "%s", "bytes": 1}' % str(tmp_path / "a.txt").replace("\\", "/"), False)
    assert plan_action(engine, "update_plan", {"step": 0, "status": "done"})["ok"]
    assert engine._turn_plan["steps"][0]["status"] == "done" and engine._turn_plan["steps"][0]["evidence"] == [rid]
    assert not plan_action(engine, "update_plan", {"step": 1, "status": "done"})["ok"]   # a.txt cannot certify b.txt
    assert finalize_status({"status": "active", "steps": [{"status": "failed"}, {"status": "failed"}]}) == "failed"
    assert finalize_status({"status": "active", "steps": [{"status": "done"}, {"status": "failed"}]}) == "partial"   # 71.3


def test_approval_phrases():
    assert approval_signal("Sim, podes avançar.", True) == "yes"
    assert approval_signal("yes, go ahead and do it", True) == "yes"
    assert approval_signal("ok please", True) == "yes" and approval_signal("avança", True) == "yes"
    assert approval_signal("yes but first tell me the weather in Aveiro", True) is None
    assert approval_signal("", True) is None and approval_signal("please", True) is None



def test_75_1e_continuation_word_approves_a_pending_proposal_only(tmp_path):
    """say-do plan_restart: the model proposed in turn 1; the user's "continue" is that proposal's yes. An unapproved
    RESUMED plan (no authorization record) is NOT approved by "continue" — 70.4 keeps explicit approval there."""
    from hmgfu.session_plans import approval_signal, begin_turn, propose
    from tests.test_v2_agent import make_agent
    assert approval_signal("continue", True) is None                         # not a yes-word by itself
    e, _ = make_agent(tmp_path, [])
    e._emit = lambda ev: None
    for word in ("continue", "next", "prossegue"):
        sid = f"s-{word}"
        propose(e, sid, "Create the notes", ["write note1.txt", "write note2.txt"])
        block = begin_turn(e, sid, word)
        plan = e.session_plans.get(sid)
        assert plan["status"] == "active" and plan["authorization"]["origin"] == "user_approval", word
        assert "APPROVED this plan" in block
    # a proposal + a long message is new instruction, still pending
    propose(e, "s-long", "Create the notes", ["write note1.txt"])
    begin_turn(e, "s-long", "continue with the other idea instead, this plan is wrong and I want something else entirely")
    assert e.session_plans.get("s-long")["status"] == "proposed"
    # an unapproved resumed plan stays unapproved on "continue" (70.4)
    e.session_plans.save("s-legacy", {"title": "old", "status": "active", "approved": True,
                                      "steps": [{"text": "create_widget: Old", "status": "active"}]})
    block = begin_turn(e, "s-legacy", "continue")
    assert "NONE ON RECORD" in block and not e.session_plans.get("s-legacy").get("authorization")
