"""Phase 77.1 — the retrieval-mode switch: `cosine` is the B2 control as product (same pool, floor on similarity, no
expansion), `fu` is unchanged; the engine passes the setting; an unknown mode is rejected by the settings layer."""
from __future__ import annotations

from hmgfu.models import MemoryPoint
from hmgfu.retrieve import COSINE_POOL_EXCLUDED, make_query_point, retrieve_cosine, retrieve_memory
from tests.test_v2_agent import fake_embed, make_agent


def test_cosine_mode_is_topk_by_similarity_over_the_episodic_pool(tmp_path):
    e, _ = make_agent(tmp_path, [])
    g = e.graph
    pts = [MemoryPoint(type="message", content=f"note {k}", summary="", source="user", embedding=[1.0, k / 10.0, 0.0]) for k in range(6)]
    skill = MemoryPoint(type="skill", content="tool", summary="", source="system", embedding=[1.0, 0.0, 0.0], keywords=["tool:x"])
    for p in pts + [skill]:
        g.save_point(p)
    q = make_query_point("note", fake_embed, e.sensitizer); q.embedding = [1.0, 0.0, 0.0]
    got = retrieve_cosine(q, g, limit=3, min_score=0.0)
    assert [r.point.id for r in got] == [pts[0].id, pts[1].id, pts[2].id]           # by similarity, best first
    assert all(r.point.type not in COSINE_POOL_EXCLUDED for r in got) and all(r.edge is None for r in got)
    assert retrieve_cosine(q, g, limit=3, min_score=0.9999) and len(retrieve_cosine(q, g, limit=3, min_score=1.01)) == 0
    assert [r.point.id for r in retrieve_memory(q, g, limit=3, min_score=0.0, mode="cosine")] == [r.point.id for r in got]


def test_engine_passes_the_setting_and_rejects_unknown_modes(tmp_path):
    e, _ = make_agent(tmp_path, [])
    assert e.settings.get("retrieval_mode") == "fu"
    e.settings.set("retrieval_mode", "cosine")
    p = MemoryPoint(type="message", content="my dog is called Green", summary="", source="user", embedding=fake_embed("my dog is called Green"))
    e.graph.save_point(p)
    q, retrieved, _ = e.retrieve("what is my dog called?", limit=5, min_score=0.0)
    assert retrieved and retrieved[0].reason.startswith("cosine")
    e.settings.set("retrieval_mode", "fu")                # the fu path keeps its echo filter; a paraphrase is recalled
    q, retrieved, _ = e.retrieve("what is my dog called?", limit=5, min_score=0.0)
    assert retrieved and retrieved[0].reason.startswith("channel=")
    import pytest
    with pytest.raises(ValueError):
        e.settings.set("retrieval_mode", "banana")                             # enum-checked by the settings layer
