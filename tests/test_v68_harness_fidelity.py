"""Phase 81.1 — the LongMemEval production arms ingest like the agent: user turns feed the ledger, assistant turns never do."""
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


class _Facts:
    def __init__(self): self.applied = []
    def apply_all(self, text, source): self.applied.append((text, source)); return []


class _Point:
    def __init__(self, content, source, ts): self.content, self.source, self.timestamp = content, source, ts


class _Engine:
    def __init__(self):
        self.facts = _Facts(); self.ingested = []; self.stored = []
        self.graph = SimpleNamespace(points={}, save_point=lambda p: None)
        self.settings = SimpleNamespace(get=lambda k: 12)
    def ingest(self, content, source="user", timestamp=None, **kw):
        self.ingested.append((content, source, timestamp)); return None
    def retrieve(self, text, limit=12, **kw): return None, [], 0.0
    def _store_assistant_reply(self, reply, retrieved):
        self.stored.append(reply)
        p = _Point(reply, "assistant", "9999"); self.graph.points[len(self.stored)] = p
        return "prefer" in reply or "name" in reply           # a trivia gate stand-in: not every reply is stored


def test_user_turns_feed_the_ledger_and_assistant_turns_never_do():
    H = _load_harness()
    e = _Engine()
    turns = [("2023-05-01T10:00:00+00:00", "01 May 2023", "user", "My favourite drink is hibiscus tea.", True),
             ("2023-05-01T10:00:00+00:00", "01 May 2023", "assistant", "I prefer green tea myself, but noted!", False),
             ("2023-05-01T10:01:00+00:00", "01 May 2023", "assistant", "Sure, here is a joke.", False)]
    counts = H.ingest_session_like_agent(e, turns)
    assert [s for _, s in e.facts.applied] == ["user_explicit"] and e.facts.applied[0][0].startswith("My favourite drink")
    assert [src for _, src, _ in e.ingested] == ["user"]                    # the assistant never enters the user ingest path
    assert e.stored == ["I prefer green tea myself, but noted!", "Sure, here is a joke."]   # both offered to the assistant path
    assert {k: counts[k] for k in ("user", "assistant_stored", "assistant_skipped")} == {"user": 1, "assistant_stored": 1, "assistant_skipped": 1}   # production gates decide storage; 88.1 adds extractor counters
