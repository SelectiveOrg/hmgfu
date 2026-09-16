"""Phase 81.4 — the reserved DECISION set: author-adjudicated admissible routes, judged by any-of semantics; sealed shape."""
from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bench():
    sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location("bench_router_agreement", os.path.join(ROOT, "scripts", "bench_router_agreement.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _route(**kw):
    base = {"action_requested": False, "requested_tools": [], "conversation_act": "statement", "needs_memory": False,
            "freshness": "none", "feedback_polarity": None, "directive_kind": None}
    base.update(kw); return base


def test_admissible_semantics():
    B = _bench()
    adm = [{"action_requested": True, "requested_tools": ["memory_search"], "conversation_act": ["question", "instruction"], "needs_memory": True},
           {"action_requested": False, "requested_tools": [], "conversation_act": "question", "needs_memory": True}]
    assert B.judge_admissible(_route(action_requested=True, requested_tools=["memory_search"], conversation_act="instruction", needs_memory=True), adm)["decision"]
    assert B.judge_admissible(_route(conversation_act="question", needs_memory=True), adm)["decision"]
    assert not B.judge_admissible(_route(conversation_act="question", needs_memory=False), adm)["decision"]       # no entry admits
    assert not B.judge_admissible(_route(action_requested=True, requested_tools=["memory_search", "list_files"], conversation_act="question", needs_memory=True), adm)["decision"]
    j = B.judge_admissible(_route(conversation_act="question", needs_memory=True, freshness="current"), adm)
    assert j["agree"]["freshness"] is True                                # wildcard: no entry names freshness
    d = [{"requested_tools": [], "conversation_act": "instruction", "directive_kind": "conversation_closer"}]
    assert B.judge_admissible(_route(action_requested=True, conversation_act="instruction", directive_kind="conversation_closer"), d)["decision"]
    assert not B.judge_admissible(_route(conversation_act="instruction", directive_kind=None), d)["decision"]


def test_decision_set_shape():
    o = json.load(open(os.path.join(ROOT, "scripts", "oracles", "decision_v1.json"), encoding="utf-8"))
    turns = o["turns"]
    assert len(turns) == 100 and len({t["id"] for t in turns}) == 100
    names = set(o["catalog_names_used"])
    for t in turns:
        assert t["admissible"] and "reference" not in t
        for e in t["admissible"]:
            assert set(e) <= {"action_requested", "requested_tools", "conversation_act", "needs_memory", "directive_kind"}
            assert set(e.get("requested_tools", [])) <= names
    assert {t["lang"] for t in turns} == {"en", "pt"}
