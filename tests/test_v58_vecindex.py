"""Phase 76.2 — the vector scan returns exactly the pure-Python ranking (same top-k, same nearest, cosines within float32
tolerance), honours the graph version (a write invalidates the cache), and falls back to the pure path without numpy."""
from __future__ import annotations

import random

import pytest

from hmgfu import fu_math, vecindex
from hmgfu.models import MemoryPoint
from hmgfu.store import HMGGraph


def _pts(n, dim, rng):
    out = []
    for i in range(n):
        v = [rng.gauss(0, 1) for _ in range(dim)]
        out.append(MemoryPoint(type="message", content=f"m{i}", summary="", source="user", embedding=v))
    return out


def test_scores_topk_best_match_pure_python_exactly(tmp_path):
    rng = random.Random(76)
    pts = _pts(500, 64, rng)
    q = [rng.gauss(0, 1) for _ in range(64)]
    pure = [fu_math.cosine(q, p.embedding) for p in pts]
    vec = vecindex.scores(q, pts)
    assert max(abs(a - b) for a, b in zip(pure, vec)) < 1e-5
    pure_top = [p.id for p in sorted(pts, key=lambda p: -fu_math.cosine(q, p.embedding))[:12]]
    assert [p.id for p in vecindex.top_k(q, pts, 12)] == pure_top
    b, s = vecindex.best(q, pts)
    assert b.id == pure_top[0] and abs(s - max(pure)) < 1e-5
    assert vecindex.top_k(q, pts, 0) == [] and vecindex.top_k(q, [], 5) == [] and vecindex.best(q, []) == (None, 0.0)
    assert len(vecindex.top_k(q, pts, 10_000)) == 500                       # k past n: everything, ranked


def test_cache_follows_the_graph_version(tmp_path):
    rng = random.Random(7)
    g = HMGGraph(str(tmp_path / "g.db"))
    for p in _pts(40, 16, rng):
        g.save_point(p)
    v0 = g.version
    q = [rng.gauss(0, 1) for _ in range(16)]
    pts = g.active_points()
    first = vecindex.top_k(q, pts, 3, graph=g)
    new = MemoryPoint(type="message", content="new", summary="", source="user", embedding=list(q))   # identical to the query
    g.save_point(new)
    assert g.version > v0
    pts = g.active_points()
    assert vecindex.top_k(q, pts, 1, graph=g)[0].id == new.id              # the cache was rebuilt, not reused
    assert first[0].id != new.id
    g.close()


def test_fallback_without_numpy(monkeypatch):
    rng = random.Random(3)
    pts = _pts(50, 8, rng)
    q = [rng.gauss(0, 1) for _ in range(8)]
    pure_top = [p.id for p in sorted(pts, key=lambda p: -fu_math.cosine(q, p.embedding))[:5]]
    monkeypatch.setattr(vecindex, "_np", None)
    assert not vecindex.available()
    assert [p.id for p in vecindex.top_k(q, pts, 5)] == pure_top
    assert vecindex.best(q, pts)[0].id == pure_top[0]
    monkeypatch.setattr(vecindex, "ENABLED", False)
    assert not vecindex.available()



def test_ties_break_by_input_order_like_sorted_and_incremental_sync(tmp_path):
    """The sealed corpus has identical filler lines → exact ties at the top-k boundary; the index must pick the same
    members as Python's stable sort. And a second write after the first index build must be applied incrementally."""
    rng = random.Random(11)
    g = HMGGraph(str(tmp_path / "g.db"))
    base = [rng.gauss(0, 1) for _ in range(16)]
    pts = []
    for i in range(30):
        emb = list(base) if i % 3 == 0 else [rng.gauss(0, 1) for _ in range(16)]     # ten exact duplicates of `base`
        p = MemoryPoint(type="message", content=f"m{i}", summary="", source="user", embedding=emb)
        g.save_point(p); pts.append(p)
    q = [x + 0.01 for x in base]
    active = g.active_points()
    for k in (3, 5, 7, 12):
        pure = [p.id for p in sorted(active, key=lambda p: -fu_math.cosine(q, p.embedding))[:k]]
        assert [p.id for p in vecindex.top_k(q, active, k, graph=g)] == pure, k
    idx_before = vecindex._CACHE[id(g)]
    extra = MemoryPoint(type="message", content="extra", summary="", source="user", embedding=list(q))
    g.save_point(extra)
    assert g.dirty == {extra.id}
    top = vecindex.top_k(q, g.active_points(), 1, graph=g)
    assert top[0].id == extra.id and vecindex._CACHE[id(g)] is idx_before and g.dirty == set()   # same index object, synced
    g.close()
