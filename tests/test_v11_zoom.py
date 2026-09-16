"""Phase 35 (ANALYSIS P1–P5): nano time-awareness, ephemeral macro exclusion, grader detail,
recursive hierarchy (memory Nanite), scoped viz + memory_zoom tool."""

import asyncio
import json
from types import SimpleNamespace

from hmgfu import config, hierarchy
from hmgfu.models import Hex, MemoryPoint, RetrievedMemory
from hmgfu.sensitizer import _cluster_bullets, _time_context
from hmgfu.store import HMGGraph
from tests.conftest import fake_embed
from tests.test_v2_agent import make_agent


# --- P1: time awareness --------------------------------------------------------------
def test_p1_time_context_and_aged_bullets():
    clock = _time_context()
    assert clock.startswith("=== AUTHORITATIVE RUNTIME CONTEXT")
    assert '"now_local":"20' in clock and '"utc_offset":' in clock
    p = MemoryPoint(content="the weather was 21C", summary="weather 21C",
                    timestamp="2026-06-01T00:00:00+00:00")
    bullets = _cluster_bullets([p])
    assert "weather 21C" in bullets and "ago)" in bullets     # age label attached


# --- P2: ephemeral exclusion + macro span ---------------------------------------------
def test_p2_ephemeral_never_clusters(tmp_path):
    from hmgfu.ingest import find_local_cluster
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("The current weather in Valencia is 27C with wind", source="user")
    pt = engine.graph.points[p.id]
    pt.density = 0.9                                          # dense enough to seed
    engine.graph.save_point(pt)
    assert "_ephemeral" in pt.keywords
    assert pt not in find_local_cluster(pt, engine.graph)     # excluded as seed AND member


def test_p2_macro_content_carries_span(tmp_path):
    from hmgfu.ingest import update_macros
    from hmgfu.models import FuEdge
    engine, _ = make_agent(tmp_path, [])
    pts = []
    for i in range(6):                                        # explicit cluster (ingest dedup
        p = MemoryPoint(content=f"project alpha step {i}",    # would merge similar sentences)
                        summary=f"project alpha step {i}", embedding=fake_embed(f"alpha {i}"),
                        density=0.8, hex=Hex(20 + i, -(20 + i), 0),
                        timestamp=f"2026-06-0{i + 1}T00:00:00+00:00")
        engine.graph.save_point(p)
        pts.append(p)
    for a in pts:
        for b in pts:
            if a.id < b.id:
                engine.graph.save_edge(FuEdge(from_id=a.id, to_id=b.id, kappa=0.6, trust=0.7,
                                              relation_type="project_related"))
    macro = update_macros(pts[0], engine.graph, engine.sensitizer, engine.embed)
    assert macro is not None
    assert "(observed 2026-06-01" in macro.content            # provenance span (P2)
    assert "(observed" not in macro.summary                   # summary stays clean


# --- P3: grader per-item detail ---------------------------------------------------------
def test_p3_grade_card_carries_memory_details(tmp_path):
    from hmgfu.grader import grade_turn
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("I love hiking in the Alps mountains", source="user")
    retrieved = [RetrievedMemory(point=engine.graph.points[p.id], score=0.7)]
    card = grade_turn(engine, "do I like hiking?", "You love hiking in the Alps", retrieved, [])
    assert card["memories_graded"] == len(card["memory_details"]) >= 1
    d = card["memory_details"][0]
    assert d["id"] == p.id and d["grade"] in ("cited", "implied", "unused")
    assert isinstance(d["before"], float) and isinstance(d["after"], float)


# --- P4: hierarchy ------------------------------------------------------------------------
def _macro(graph, text, kids):
    m = MemoryPoint(type="macro", title=f"Macro: {text[:20]}", content=text, summary=text,
                    embedding=fake_embed(text), density=0.6, hex=Hex(0, 0, 0))
    m.hex = None or m.hex
    graph.save_point(m)
    graph.save_macro_sources(m.id, [k.id for k in kids])
    return m


def test_p4_levels_frontier_cut_and_super_macros(tmp_path):
    g = HMGGraph(db_path=str(tmp_path / "h.db"))
    micros = []
    for i in range(9):
        p = MemoryPoint(content=f"note about project systems design {i}",
                        embedding=fake_embed(f"project systems design {i}"),
                        density=0.5, hex=Hex(i, -i, 0))
        g.save_point(p)
        micros.append(p)
    m1 = _macro(g, "project systems design patterns alpha", micros[0:3])
    m2 = _macro(g, "project systems design patterns beta", micros[3:6])
    m3 = _macro(g, "project systems design patterns gamma", micros[6:9])
    levels = hierarchy.macro_levels(g)
    assert levels[m1.id] == 1
    front = hierarchy.root_frontier(g)
    assert {m1.id, m2.id, m3.id} <= {p.id for p in front}
    assert all(m.id not in {p.id for p in front} for m in micros)   # covered → not in frontier
    err = hierarchy.coverage_error(g, m1)
    assert 0.0 <= err <= 1.0
    # cut respects the budget and starts coarse
    cut = hierarchy.select_cut(g, max_items=3)
    assert len(cut) <= 3
    # recursive consolidation: 3 similar parentless L1 macros → one L2 super-macro
    from hmgfu.sensitizer import Sensitizer
    sens = Sensitizer(client=None, enabled=False)
    created = hierarchy.build_super_macros(g, sens, fake_embed)
    assert len(created) == 1
    assert hierarchy.macro_levels(g)[created[0]] == 2
    assert hierarchy.parent_index(g)[m1.id] == created[0]
    g.close()


# --- P5: scoped viz + memory_zoom tool ------------------------------------------------------
def test_p5_viz_root_scopes_to_children(tmp_path):
    from hmgfu import runtime
    from hmgfu.routes.memory import graph_viz
    g = HMGGraph(db_path=str(tmp_path / "v.db"))
    kids = []
    for i in range(4):
        p = MemoryPoint(content=f"child memory {i} about databases",
                        embedding=fake_embed(f"child {i} databases"), density=0.5,
                        hex=Hex(i + 5, -(i + 5), 0))
        g.save_point(p)
        kids.append(p)
    m = _macro(g, "databases knowledge", kids)
    saved = runtime._engine
    runtime.set_engine(SimpleNamespace(graph=g))
    try:
        payload = asyncio.run(graph_viz(cap=50, root=m.id))
        ids = {n["id"] for n in payload["hex_nodes"]}
        assert ids == {k.id for k in kids}                       # ONLY the children
        assert {n["parent"] for n in payload["hex_nodes"]} == {m.id}
        assert payload["root"] == m.id
        assert payload["path"][-1]["id"] == m.id                 # breadcrumb ends here
        assert payload["hex_nodes"][0]["q"] == 0                 # fresh local honeycomb
    finally:
        runtime.set_engine(saved)
        g.close()


def test_p5_viz_roots_is_a_strict_coarse_level(tmp_path):
    """The map overview must not mix root macros with descendants pinned for compression."""
    from hmgfu import runtime
    from hmgfu.routes.memory import graph_viz

    g = HMGGraph(db_path=str(tmp_path / "roots.db"))
    leaves = []
    for i in range(3):
        p = MemoryPoint(content=f"leaf {i}", embedding=fake_embed(f"leaf {i}"),
                        density=0.4, hex=Hex(i, -i, 0))
        g.save_point(p)
        leaves.append(p)
    child_macro = _macro(g, "child macro", leaves)
    root_macro = _macro(g, "root macro", [child_macro])
    saved = runtime._engine
    runtime.set_engine(SimpleNamespace(graph=g))
    try:
        payload = asyncio.run(graph_viz(cap=24, roots=1))
        assert [n["id"] for n in payload["hex_nodes"]] == [root_macro.id]
        assert payload["hex_nodes"][0]["parent"] is None
        assert payload["hex_nodes"][0]["level"] == 2
        child_level = asyncio.run(graph_viz(cap=24, root=root_macro.id))
        assert [n["id"] for n in child_level["hex_nodes"]] == [child_macro.id]
        assert child_level["hex_nodes"][0]["parent"] == root_macro.id
    finally:
        runtime.set_engine(saved)
        g.close()


def test_p5_viz_advertises_only_expandable_active_children(tmp_path):
    """A displayed macro count must equal what the scoped expansion endpoint can return."""
    from hmgfu import runtime
    from hmgfu.routes.memory import graph_viz

    g = HMGGraph(db_path=str(tmp_path / "active-children.db"))
    active = MemoryPoint(content="active child", density=0.5)
    dormant = MemoryPoint(content="dormant child", density=0.5, status="dormant")
    g.save_point(active); g.save_point(dormant)
    macro = _macro(g, "truthful count", [active, dormant])
    saved = runtime._engine
    runtime.set_engine(SimpleNamespace(graph=g))
    try:
        overview = asyncio.run(graph_viz(cap=24, roots=1))
        shown = next(n for n in overview["hex_nodes"] if n["id"] == macro.id)
        expanded = asyncio.run(graph_viz(cap=24, root=macro.id))
        assert shown["children"] == len(expanded["hex_nodes"]) == 1
    finally:
        runtime.set_engine(saved)
        g.close()


def test_p5_memory_zoom_tool_roundtrip(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    kids = []
    for i in range(3):
        p = engine.ingest(f"design pattern note {i} for the API layer", source="user")
        kids.append(engine.graph.points[p.id])
    m = _macro(engine.graph, "API design patterns", kids)
    over = json.loads(engine.tools.execute_tool("memory_zoom", {"scope": "overview"}))
    assert any(it["id"] == m.id and it["zoomable"] for it in over["items"])
    into = json.loads(engine.tools.execute_tool("memory_zoom", {"scope": "in", "macro_id": m.id}))
    assert {it["id"] for it in into["items"]} == {k.id for k in kids}
    out = json.loads(engine.tools.execute_tool("memory_zoom",
                                               {"scope": "out", "macro_id": kids[0].id}))
    assert out["macro"]["id"] == m.id
    bad = json.loads(engine.tools.execute_tool("memory_zoom", {"scope": "in", "macro_id": "nope"}))
    assert "error" in bad



def test_74_8_macro_recency_is_its_members_recency(tmp_path):
    """74.8: a macro built today over backdated episodes is dated by its newest member, so it cannot outrank the
    episode that answers merely by having been consolidated now (the relational-bench colour loss)."""
    from hmgfu import config, fu_math
    from hmgfu.ingest import update_macros
    from hmgfu.models import FuEdge, MemoryPoint
    from hmgfu.store import HMGGraph

    class _S:
        def summarise_cluster(self, pts):
            return "Pattern over %d memories: walks" % len(pts)
    g = HMGGraph(str(tmp_path / "g.db"))
    pts = []
    for k in range(config.MACRO_MIN_CLUSTER + 1):
        p = MemoryPoint(type="message", content=f"Long walk after dinner {k}", summary="", source="user",
                        embedding=[1.0, 0.0, 0.0], density=max(config.MACRO_MIN_DENSITY, 0.7), topics=["walks"],
                        timestamp=f"2026-03-{10 + k:02d}T20:00:00+00:00")
        g.save_point(p); pts.append(p)
    for a in pts:
        for b in pts:
            if a.id < b.id:
                g.save_edge(FuEdge(from_id=a.id, to_id=b.id, relation_type="same_entity", kappa=0.9, trust=0.9,
                                   base_separation=1.0, distance=1.0))
    macro = update_macros(pts[-1], g, _S(), lambda s: [1.0, 0.0, 0.0])
    assert macro is not None and macro.type == "macro"
    assert macro.timestamp == max(p.timestamp for p in pts)
    assert fu_math.recency_score(macro.timestamp) < 0.01                 # months old, like its members — not "now"



def test_74_8b_ingest_carries_the_observation_time(tmp_path):
    """Imports/replays/benches ingest a memory as of when it was observed; derived nodes follow that date."""
    from hmgfu.agent import AgentEngine
    e = AgentEngine(db_path=str(tmp_path / "a.db"))
    e.sensitizer.enabled = False
    e.settings.set("tail_async", False)
    p = e.ingest("Comprei tinta burgundy para o quarto.", source="user", timestamp="2026-03-04T10:00:00+00:00")
    assert p.timestamp == "2026-03-04T10:00:00+00:00"
    q = e.ingest("Plain note without a time.", source="user")
    assert q.timestamp[:4] == "2026" and q.timestamp != p.timestamp
    e.graph.close()



def test_76_3_dream_budget_and_region(tmp_path):
    """A zero-second budget cuts every proposing stage (and says so); region_only limits the seeds to what changed
    since the last dream; an unbudgeted call is today's behaviour."""
    from hmgfu.dream import DreamBudget, dream_loop, dream_region
    from hmgfu.models import MemoryPoint
    from hmgfu.sensitizer import Sensitizer
    from hmgfu.store import HMGGraph
    g = HMGGraph(str(tmp_path / "g.db"))
    sens = Sensitizer(client=None, enabled=False)
    for k in range(6):
        old = MemoryPoint(type="message", content=f"note {k} about the garden and the fence", summary="", source="user",
                          embedding=[1.0, float(k) / 10, 0.0], density=0.7, energy=0.6, timestamp=f"2026-03-0{k + 1}T10:00:00+00:00")
        old.last_accessed_at = old.timestamp                 # neither written nor accessed since March
        g.save_point(old)
    plain = dream_loop(g, sens, lambda s: [1.0, 0.0, 0.0])
    assert "budget" not in plain.summary
    cut = dream_loop(g, sens, lambda s: [1.0, 0.0, 0.0], budget=DreamBudget(seconds=1e-9))
    assert "cut at:" in cut.summary and "macros" in cut.summary and cut.macros_created == []
    late = MemoryPoint(type="message", content="new note about the roof", summary="", source="user",
                       embedding=[0.0, 1.0, 0.0], density=0.7, energy=0.9, timestamp="2026-09-01T10:00:00+00:00")
    g.save_point(late)
    region = dream_region(g, "2026-08-01T00:00:00+00:00")
    assert late.id in {p.id for p in region} and len(region) < len(g.active_points())
    scoped = dream_loop(g, sens, lambda s: [1.0, 0.0, 0.0], budget=DreamBudget(region_only=True), since="2026-08-01T00:00:00+00:00")
    assert "region 1 pts" in scoped.summary
    g.close()
