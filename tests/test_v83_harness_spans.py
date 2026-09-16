"""Phase 88.1 — the LME harness ingests with the span extractor per user turn: regex first, the extractor adds only slots the
regex did not write, provenance is linked to the turn's point, open-slot regex writes are honoured, the cost is counted."""
from __future__ import annotations

import importlib.util
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_harness():
    sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location("bench_longmemeval_e2", os.path.join(ROOT, "scripts", "bench_longmemeval_e2.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_harness_ingest_with_extractor(tmp_path):
    from hmgfu.facts import FactStore
    H = _load_harness()
    facts = FactStore(str(tmp_path / "f.db"))
    ingested = []
    class _P:
        def __init__(self, i): self.id = f"pt-{i}"
    def ingest(content, source="user", timestamp=None, **kw):
        ingested.append(content); return _P(len(ingested))
    engine = SimpleNamespace(facts=facts, ingest=ingest, settings=SimpleNamespace(get=lambda k: {"open_slot_regex_writes": False, "fact_mapper_mode": "spans",
                                                                                                    "retrieval_limit": 12}.get(k)),
                             retrieve=lambda t, limit=12, **kw: (None, [], 0.0), _store_assistant_reply=lambda r, ret: False,
                             graph=SimpleNamespace(points={}, save_point=lambda p: None))
    calls = []
    def extractor(text):
        calls.append(text)
        return [{"key": "pref.color", "value": "amber", "supersedes": None, "path": "spans"},        # the regex wrote this one → skipped
                {"key": "identity.alias", "value": "Kiki", "supersedes": None, "path": "spans"}]      # added
    turns = [("2023-05-01T10:00:00+00:00", "01 May 2023", "user", "My favourite colour is amber and I answer to Kiki.", True),
             ("2023-05-01T10:01:00+00:00", "01 May 2023", "assistant", "Noted.", False)]
    counts = H.ingest_session_like_agent(engine, turns, extractor)
    assert calls == ["My favourite colour is amber and I answer to Kiki."] and counts["extractor_calls"] == 1 and counts["extractor_writes"] == 1
    canon = {r["key"]: r for r in facts.active()}
    assert canon["pref.color"]["value"] == "amber" and canon["identity.alias"]["value"] == "Kiki"
    assert canon["pref.color"]["source_turn_id"] == "pt-1" and canon["identity.alias"]["source_turn_id"] == "pt-1"   # provenance to the turn's point
    assert facts.open_slot_regex_writes is False and facts.use_mapper is False
    # without an extractor the harness is byte-for-byte the 81.1 path
    facts2 = FactStore(str(tmp_path / "g.db")); engine.facts = facts2
    counts2 = H.ingest_session_like_agent(engine, turns)
    assert counts2["extractor_calls"] == 0 and {r["key"] for r in facts2.active()} == {"pref.color"}
