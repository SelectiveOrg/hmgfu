"""Phase 69.5 — provenance and lifecycle: tombstones vs startup migration, session delete cascade, raw evidence in
recall, canon on empty retrieval, legacy chat writes the ledger, user-grounded predicate."""

from __future__ import annotations

import json

from hmgfu.hygiene import migrate_tool_rules
from hmgfu.models import MemoryPoint, QueryPoint, RetrievedMemory
from hmgfu.plans import step_recall
from hmgfu.taxonomy import is_user_grounded
from tests.test_v2_agent import make_agent


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    return engine


def test_cleared_tool_rule_is_not_resurrected_by_the_startup_migration(tmp_path):
    engine = _engine(tmp_path)
    statement = "Always use read_file for project summaries."
    engine.ingest(statement, source="user_explicit")
    engine.directives.apply(statement)
    engine.directives.apply("Stop using read_file")
    assert engine.directives.active() == [] and engine.directives.is_cleared("tool_rule:read_file")
    assert migrate_tool_rules(engine) == 0 and engine.directives.active() == []
    engine.directives.apply(statement)                     # the USER states it again → lifted
    assert not engine.directives.is_cleared("tool_rule:read_file") and engine.directives.active()
    # idempotent by tag: a second startup counts no change and creates no duplicate
    engine.ingest("From now on always use brave search for weather.", source="user_explicit")
    assert migrate_tool_rules(engine) >= 0
    n = len(engine.directives.active())
    assert migrate_tool_rules(engine) == 0 and len(engine.directives.active()) == n


def test_session_delete_cascades_to_its_plan(tmp_path):
    engine = _engine(tmp_path)
    sid = engine.sessions.create_session("d")["id"]
    engine.session_plans.save(sid, {"title": "p", "status": "proposed", "steps": [{"text": "s", "status": "pending"}]})
    engine.sessions.delete_session(sid)
    assert engine.session_plans.get(sid) is None


def test_recall_returns_raw_user_evidence_and_canon_on_empty(tmp_path):
    engine = _engine(tmp_path)
    engine.facts.apply_all("My favorite color is ochre.")
    engine.retrieve = lambda *a, **k: (QueryPoint(text="q"), [], 0.0)
    empty = json.loads(engine.tools._memory_search({"query": "unmatched"}))
    assert empty["results"] == [] and empty["canonical_facts"]
    p = MemoryPoint(content="Only raw user evidence", summary="The user's mother's name is Invented.", type="fact", source="user_explicit")
    engine.retrieve = lambda *a, **k: (QueryPoint(text="q"), [RetrievedMemory(point=p, score=0.8, reason="t")], 0.0)
    payload = json.loads(engine.tools._memory_search({"query": "raw"}))
    assert "Invented" not in json.dumps(payload) and payload["results"][0]["content"] == "Only raw user evidence"
    engine.settings.set("plan_step_recall", True)
    assert "Invented" not in json.dumps(step_recall(engine, "prepare next step"))
    q = MemoryPoint(content="Assistant reply about the weather", summary="A derived summary", type="message", source="assistant")
    engine.retrieve = lambda *a, **k: (QueryPoint(text="q"), [RetrievedMemory(point=q, score=0.5, reason="t")], 0.0)
    rec = json.loads(engine.tools._memory_search({"query": "w"}))["results"][0]
    assert rec["derived_summary"] == "A derived summary" and rec["content"].startswith("Assistant reply")


def test_legacy_chat_writes_the_same_ledger(tmp_path):
    engine = _engine(tmp_path)
    engine.client.chat = lambda *a, **k: "Saved."
    engine.chat("My favorite color is ultramarine.")
    assert {f["key"]: f["value"] for f in engine.facts.active()}.get("pref.color") == "ultramarine"


def test_user_grounded_rejects_bare_digit_assistant_lines():
    fake = MemoryPoint(content="The user's medical record contains 42 surgeries.", summary="x", type="message", source="assistant", entities=[])
    assert not is_user_grounded(fake)
    echo = MemoryPoint(content="Your dog's name is Green.", summary="x", type="message", source="assistant", entities=["Green"])
    assert not is_user_grounded(echo)                       # 70.3 (M0.6): an assistant echo is never user-grounded
    real = MemoryPoint(content="My dog is Green.", summary="x", type="message", source="user_explicit")
    assert is_user_grounded(real)
