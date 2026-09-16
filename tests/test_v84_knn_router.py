"""Phase 89.1 — the nearest-exemplar router: claims only when the k nearest labelled exemplars agree and are close; never a
directive turn; the sealed bases load with full decisions; the cache is keyed by the embedder."""
from __future__ import annotations

import json
import os

from hmgfu.knn_router import DECISION, ExemplarBase, knn_route, load_exemplars

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fake_embed(text: str):
    t = text.lower()
    return [1.0 if "name" in t or "chamo" in t else 0.0, 1.0 if "file" in t else 0.0, 1.0 if "joke" in t or "piada" in t else 0.0, 0.1]


def _base(tmp_path, turns):
    path = tmp_path / "base.json"
    path.write_text(json.dumps({"turns": turns}), encoding="utf-8")
    return ExemplarBase(_fake_embed, "fake", sources=(str(path),), cache_dir=str(tmp_path))


def test_sealed_sets_load_with_full_decisions():
    items = load_exemplars()
    assert len(items) >= 180
    for i in items[:200]:
        assert all(f in i["decision"] for f in DECISION) and isinstance(i["decision"]["requested_tools"], list)


def test_claims_only_on_agreement_and_closeness(tmp_path):
    turns = [{"text": "What is my name?", "reference": {"action_requested": True, "requested_tools": ["memory_search"], "conversation_act": "question", "needs_memory": True, "freshness": "none"}},
             {"text": "Como me chamo?", "reference": {"action_requested": True, "requested_tools": ["memory_search"], "conversation_act": "question", "needs_memory": True, "freshness": "none"}},
             {"text": "Tell me my name.", "admissible": [{"action_requested": True, "requested_tools": ["memory_search"], "conversation_act": ["question", "instruction"], "needs_memory": True}]},
             {"text": "List the files.", "reference": {"action_requested": True, "requested_tools": ["list_files"], "conversation_act": "instruction", "needs_memory": False, "freshness": "none"}},
             {"text": "Show my files.", "reference": {"action_requested": False, "requested_tools": [], "conversation_act": "question", "needs_memory": False, "freshness": "none"}},
             {"text": "End every reply with a joke.", "reference": {"action_requested": False, "requested_tools": [], "conversation_act": "instruction", "needs_memory": False, "freshness": "none", "directive_kind": "conversation_closer"}}]
    base = _base(tmp_path, turns)
    r = knn_route(_fake_embed("What's my name again?"), base, k=3, min_sim=0.8)
    assert r and r["route_source"] == "knn" and r["requested_tools"] == ["memory_search"] and r["needs_memory"] is True
    assert knn_route(_fake_embed("Which files are here?"), base, k=2, min_sim=0.8) is None      # the two file exemplars disagree
    assert knn_route(_fake_embed("Tell me a joke"), base, k=1, min_sim=0.8) is None                # directive neighbour: never claimed
    assert knn_route(_fake_embed("Something unrelated entirely"), base, k=1, min_sim=0.8) is None   # too far


def test_cache_is_per_embedder(tmp_path):
    turns = [{"text": "What is my name?", "reference": {"action_requested": True, "requested_tools": ["memory_search"], "conversation_act": "question", "needs_memory": True, "freshness": "none"}}]
    _base(tmp_path, turns)
    files = [f for f in os.listdir(tmp_path) if f.startswith("knn_router_base_")]
    assert len(files) == 1
    path = tmp_path / "base.json"
    ExemplarBase(_fake_embed, "other-embedder", sources=(str(path),), cache_dir=str(tmp_path))
    assert len([f for f in os.listdir(tmp_path) if f.startswith("knn_router_base_")]) == 2
