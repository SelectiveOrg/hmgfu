"""Phase 75.1 — procedural memory: a finalized plan leaves ONE runbook; a similar later request sees it beside the
tools; it never enters the episodic panel; the outcome of a hinted plan moves the runbook's utility."""
from __future__ import annotations

from hmgfu.runbooks import (RUNBOOK_TYPE, list_runbooks, match_runbooks, on_plan_finalized, render_block,
                            runbooks_for_turn)
from hmgfu.session_plans import propose
from tests.test_v2_agent import fake_embed, make_agent


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    for k, v in {"grader_enabled": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(k, v)
    engine._emit = lambda ev: None
    return engine


def _finalized_plan(engine, sid, title, steps, status="done"):
    plan = {"title": title, "status": "active", "steps": [{"text": s, "status": "pending"} for s in steps]}
    for i, step in enumerate(plan["steps"]):
        rid = engine.receipts.open(sid, i + 1, "write_file", {"path": f"{i}.txt"}, "write", "user_approval", i)
        engine.receipts.close(rid, "ok", "written", {"files": [{"path": f"{i}.txt", "sha256": "x", "bytes": 1}]})
        engine.receipts.consume([rid], i)
        step["status"] = "done"; step["evidence"] = [rid]
    plan["status"] = status
    if status != "done":
        plan["steps"][-1]["status"] = "failed"
    engine.session_plans.save(sid, plan)
    return plan


def test_finalized_plan_leaves_one_runbook_with_tools_and_files(tmp_path):
    e = _engine(tmp_path)
    plan = _finalized_plan(e, "s1", "Build the links widget", ["write the html", "create the widget"])
    rb = on_plan_finalized(e, "s1", plan)
    assert rb is not None and rb.type == RUNBOOK_TYPE and plan["runbook_id"] == rb.id
    assert "1. ✓ write the html [write_file] → 0.txt" in rb.content and "Outcome: done" in rb.content
    assert "tool:write_file" in rb.keywords and any(k.startswith("receipt:") for k in rb.keywords)
    # idempotent: finalizing the same plan again refreshes, never duplicates
    plan["status"] = "partial"
    rb2 = on_plan_finalized(e, "s1", plan)
    assert rb2.id == rb.id and "Outcome: partial" in rb2.content
    assert len([p for p in e.graph.points.values() if p.type == RUNBOOK_TYPE]) == 1
    assert list_runbooks(e)[0]["title"] == "Build the links widget"


def test_runbook_is_procedural_not_episodic(tmp_path):
    """Class `skill`: never recalled by retrieve_memory, never user-grounded, never decayed as an episode."""
    from hmgfu.retrieve import make_query_point, retrieve_memory
    from hmgfu.taxonomy import SPECIAL_TYPES, is_user_grounded, node_class
    e = _engine(tmp_path)
    plan = _finalized_plan(e, "s1", "Build the links widget", ["write the html", "create the widget"])
    rb = on_plan_finalized(e, "s1", plan)
    assert node_class(rb) == "skill" and not is_user_grounded(rb) and RUNBOOK_TYPE in SPECIAL_TYPES
    q = make_query_point("Build the links widget", fake_embed, e.sensitizer)
    assert all(r.point.id != rb.id for r in retrieve_memory(q, e.graph, limit=12, min_score=0.0))


def test_runbooks_for_turn_gated_by_setting_floor_and_user_fact_questions(tmp_path):
    from hmgfu.retrieve import make_query_point
    e = _engine(tmp_path)
    plan = _finalized_plan(e, "s1", "Build the links widget", ["write the html", "create the widget"])
    rb = on_plan_finalized(e, "s1", plan)
    q = make_query_point("Build the links widget\nwrite the html\ncreate the widget", fake_embed, e.sensitizer)
    assert runbooks_for_turn(e, q) == "" and e._turn_runbooks_shown == []          # default OFF
    e.settings.set("runbooks_enabled", True)
    block = runbooks_for_turn(e, q)
    assert "RUNBOOKS" in block and rb.title in block and e._turn_runbooks_shown == [rb.id]
    other = make_query_point("what is the weather like today in Valencia", fake_embed, e.sensitizer)
    assert runbooks_for_turn(e, other) == ""                                        # below the floor
    assert match_runbooks(e, other, floor=0.0)[0][1].id == rb.id                     # floor is the only gate
    assert render_block([]) == ""


def test_hinted_runbook_utility_follows_the_outcome(tmp_path):
    e = _engine(tmp_path)
    src = on_plan_finalized(e, "s1", _finalized_plan(e, "s1", "Build the links widget", ["write the html", "create the widget"]))
    before = src.utility
    e._turn_runbooks_shown = [src.id]
    plan = propose(e, "s2", "Build the links widget again", ["write the html", "create the widget"])
    assert plan["runbook_hint"] == src.id
    plan = _finalized_plan(e, "s2", "Build the links widget again", ["write the html", "create the widget"])
    plan["runbook_hint"] = src.id
    on_plan_finalized(e, "s2", plan)
    src = e.graph.points[src.id]
    assert src.utility > before and src.access_count == 1 and "followed:done" in src.keywords



def test_75_1b_runbook_task_carries_the_users_request_and_learns_followed_phrasings(tmp_path):
    from hmgfu.runbooks import learn_request_phrase, task_text
    e = _engine(tmp_path)
    e._turn_user_message = "faz um backup da minha pasta de notas"
    plan = propose(e, "s1", "Back up the notes folder", ["list the notes", "copy them to backup/"])
    assert plan["request"] == "faz um backup da minha pasta de notas"
    plan = _finalized_plan(e, "s1", "Back up the notes folder", ["list the notes", "copy them to backup/"])
    plan["request"] = "faz um backup da minha pasta de notas"
    rb = on_plan_finalized(e, "s1", plan)
    assert "Asked as: faz um backup" in rb.content and any(k.startswith("request:") for k in rb.keywords)
    assert task_text("T", "R", ["s1"], ["p"]) == "T\nR\np\ns1"
    # a followed runbook absorbs a NOVEL phrasing (fake embeddings: different text → low cosine) and re-embeds
    before = list(rb.embedding)
    assert learn_request_phrase(e, rb, "back up my notes again please", rb.title, "faz um backup da minha pasta de notas", ["list the notes"])
    assert any(k == "phrase:back up my notes again please" for k in rb.keywords) and rb.embedding != before
    assert not learn_request_phrase(e, rb, "back up my notes again please", rb.title, "", [])   # already known
    assert not learn_request_phrase(e, rb, "short", rb.title, "", [])                          # too short



def test_75_5_bandit_chooses_offer_or_skip_and_is_paid_by_the_plan_outcome(tmp_path):
    """With the bandit ON the runbook offer is a learned choice; the arm rides on the plan and is rewarded on finalize."""
    import random
    from hmgfu.retrieve import make_query_point
    e = _engine(tmp_path)
    e.settings.set("runbooks_enabled", True)
    rb = on_plan_finalized(e, "s1", _finalized_plan(e, "s1", "Build the links widget", ["write the html", "create the widget"]))
    q = make_query_point("Build the links widget\nwrite the html\ncreate the widget", fake_embed, e.sensitizer)
    runbooks_for_turn(e, q)
    assert e._turn_bandit is None and e._turn_runbooks_shown == [rb.id]      # OFF: always offer, nothing recorded
    e.settings.set("bandit_enabled", True)
    e.bandit._rng = random.Random(3)
    arms = set()
    for _ in range(12):
        runbooks_for_turn(e, q)
        arms.add(e._turn_bandit[1])
    assert arms == {"offer", "skip"}                                        # a fresh bandit explores both arms
    e._turn_bandit = ("runbook_offer", "offer"); e._turn_runbooks_shown = [rb.id]
    plan = propose(e, "s2", "Build the links widget again", ["write the html", "create the widget"])
    assert plan["bandit"] == ["runbook_offer", "offer"] and plan["runbook_hint"] == rb.id
    before = e.bandit.estimate("runbook_offer", "offer")
    plan = _finalized_plan(e, "s2", "Build the links widget again", ["write the html", "create the widget"])
    plan["bandit"] = ["runbook_offer", "offer"]; plan["runbook_hint"] = rb.id
    on_plan_finalized(e, "s2", plan)
    assert e.bandit.estimate("runbook_offer", "offer") > before             # done → the offer arm is paid
    snap = e.bandit.snapshot()
    assert "runbook_offer" in snap and snap["runbook_offer"]["offer"]["pulls"] >= 1
