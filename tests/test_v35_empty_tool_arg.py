"""Phase 62.14 — the live T4 failure: memory_search called with {} → embedded "" → error → no answer."""

from __future__ import annotations

import json

from hmgfu.tool_loop import fill_missing_single_arg
from tests.test_v2_agent import make_agent

MS = {"name": "memory_search", "parameters": {"type": "object", "properties": {
      "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}
MULTI = {"name": "create_skill", "parameters": {"type": "object", "properties": {
         "name": {"type": "string"}, "source": {"type": "string"}}, "required": ["name", "source"]}}


def test_missing_single_required_string_arg_is_filled_with_user_message():
    assert fill_missing_single_arg({}, MS, "what do you know about me?") == {"query": "what do you know about me?"}
    assert fill_missing_single_arg({"query": ""}, MS, "who am I") == {"query": "who am I"}
    assert fill_missing_single_arg({"query": "dog"}, MS, "who am I") == {"query": "dog"}   # never overrides
    assert fill_missing_single_arg({}, MULTI, "x") == {}                                 # multi-arg: never guessed
    assert fill_missing_single_arg({}, MS, "") == {}


def test_memory_search_never_embeds_empty_and_keeps_ledger_on_failure(tmp_path, monkeypatch):
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply("my name is Amara", source="user_explicit")
    out = json.loads(engine.tools.execute_tool("memory_search", {}))
    assert "error" in out and out["canonical_facts"] == ["Your name is Amara"]
    monkeypatch.setattr(engine, "retrieve", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("embed down")))
    out = json.loads(engine.tools.execute_tool("memory_search", {"query": "who am I"}))
    assert "retrieval failed" in out["error"] and out["canonical_facts"] == ["Your name is Amara"]


def test_agent_turn_backfills_empty_memory_search(tmp_path):
    # the fake provider first calls memory_search with NO arguments, then answers
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "memory_search", "arguments": {}}]},
        {"content": "You are Amara.", "tool_calls": []},
    ])
    engine.facts.apply("my name is Amara", source="user_explicit")
    r = engine.agent_chat("what do you know about me?", explicit=False)
    trace = [t for t in r["tool_trace"] if t["name"] == "memory_search"]
    assert trace and trace[0]["arguments"].get("query") == "what do you know about me?"
    assert not trace[0]["failed"]
