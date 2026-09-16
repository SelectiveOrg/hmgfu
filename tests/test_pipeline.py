"""End-to-end pipeline tests on the fake embedder + heuristic sensitizer (no Ollama)."""

from hmgfu import config, fu_math
from hmgfu.dream import (create_wormhole, dream_loop, infer_resolution,
                         should_create_wormhole)
from hmgfu.ingest import ingest_memory
from hmgfu.models import Hex, MemoryPoint, QueryPoint
from hmgfu.retrieve import build_llm_context, retrieve_memory
from hmgfu.sensitizer import heuristic_extract, parse_nano_json
from tests.conftest import fake_embed


def _ingest(text, graph, sensitizer, embed, **kw):
    return ingest_memory(text, kw.pop("source", "user"), graph, sensitizer, embed, **kw)


def _query(text):
    ex = heuristic_extract(text)
    return QueryPoint(text=text, embedding=fake_embed(text),
                      entities=ex["entities"], topics=ex["topics"], intent=ex["intent"])


def test_ingest_creates_point_and_edges(graph, sensitizer, embed):
    p1 = _ingest("I am building the HMG memory project with hexagons", graph, sensitizer, embed)
    p2 = _ingest("The HMG memory project uses Fu theory for relations", graph, sensitizer, embed)
    assert p1.id in graph.points and p2.id in graph.points
    assert p1.hex.key() != p2.hex.key()          # one point per cell
    assert graph.edge_between(p1.id, p2.id) is not None  # related → edge exists
    assert 0 <= p2.density <= 1


def test_unrelated_points_get_no_edge(graph, sensitizer, embed):
    p1 = _ingest("quantum hexagonal memory architecture design", graph, sensitizer, embed)
    p2 = _ingest("banana pancake breakfast delicious syrup", graph, sensitizer, embed)
    edge = graph.edge_between(p1.id, p2.id)
    assert edge is None or edge.kappa < config.KAPPA_MIN_EDGE + 0.15


def test_persistence_roundtrip(tmp_path, sensitizer, embed):
    from hmgfu.store import HMGGraph
    db = str(tmp_path / "roundtrip.db")
    g1 = HMGGraph(db_path=db)
    p = _ingest("persistent memory survives restart", g1, sensitizer, embed)
    g1.close()
    g2 = HMGGraph(db_path=db)
    assert p.id in g2.points
    assert g2.points[p.id].content == "persistent memory survives restart"
    assert g2.points[p.id].embedding  # embedding survived serialisation
    g2.close()


def test_retrieval_ranks_relevant_first(graph, sensitizer, embed):
    _ingest("My dog Rex loves playing fetch in the park", graph, sensitizer, embed)
    _ingest("The HMG project stores memories in hexagonal grids", graph, sensitizer, embed)
    _ingest("Rex the dog hates thunderstorms and hides", graph, sensitizer, embed)
    results = retrieve_memory(_query("tell me about Rex the dog"), graph, min_score=0.05)
    assert results, "retrieval returned nothing"
    top_contents = " ".join(r.point.content for r in results[:2])
    assert "Rex" in top_contents
    assert all(r.reason for r in results)  # explainability: every result has a trace


def test_injection_respects_budget_and_sections(graph, sensitizer, embed):
    for i in range(8):
        _ingest(f"fact number {i} about the hexagonal memory system design", graph, sensitizer, embed)
    q = _query("memory system")
    context, retrieved = build_llm_context(q, graph, token_budget=100)
    assert len(context) <= 100 * 4 + 80  # header tolerance
    assert context.startswith("Relevant memory context")


def test_energy_propagates_to_neighbours(graph, sensitizer, embed):
    p1 = _ingest("the hexagonal memory grid stores relational intervals", graph, sensitizer, embed)
    before = {pid: pt.energy for pid, pt in graph.points.items()}
    p2 = _ingest("relational intervals in the hexagonal memory grid are called Fu",
                 graph, sensitizer, embed)
    edge = graph.edge_between(p1.id, p2.id)
    if edge and edge.kappa > 0.2:
        assert graph.points[p1.id].energy >= before[p1.id]


def test_decay_and_dormancy(graph, sensitizer, embed):
    p = _ingest("trivial noise nobody cares about", graph, sensitizer, embed)
    stored = graph.points[p.id]
    stored.timestamp = "2026-01-01T00:00:00+00:00"
    stored.energy = 0.02
    stored.importance = 0.05
    stored.utility = 0.05
    stored.density = 0.1
    graph.save_point(stored)
    from hmgfu.dream import decay_weak_memories
    decayed = decay_weak_memories(graph)
    assert p.id in decayed
    assert graph.points[p.id].status == "dormant"


def test_dormant_reawakens_on_entity_mention(graph, sensitizer, embed):
    p = _ingest("Zorblatt is my secret project codename", graph, sensitizer, embed)
    stored = graph.points[p.id]
    stored.status = "dormant"
    graph.save_point(stored)
    _ingest("I want to continue working on Zorblatt today", graph, sensitizer, embed)
    assert graph.points[p.id].status == "active"  # THEORY issue 4 reawakening


def test_promotion(graph, sensitizer, embed):
    p = _ingest("I always prefer dark mode in every app", graph, sensitizer, embed)
    stored = graph.points[p.id]
    stored.density = 0.8
    stored.utility = 0.7
    stored.confidence = 0.9
    stored.access_count = 5
    stored.stability = 0.7
    graph.save_point(stored)
    from hmgfu.dream import promote_stable_memories
    promoted = promote_stable_memories(graph)
    assert p.id in promoted
    assert graph.points[p.id].layer == "L1_session"


def test_macro_created_for_dense_cluster(graph, sensitizer, embed):
    texts = [
        "the hexagonal memory grid organises memory points spatially",
        "memory points in the hexagonal grid link through Fu intervals",
        "Fu intervals measure the relational coupling of memory points",
        "the memory grid propagates energy along Fu intervals",
        "hexagonal memory placement uses semantic neighbourhood centroids",
        "the grid promotes dense memory points to higher layers",
    ]
    ids = []
    for t in texts:
        p = _ingest(t, graph, sensitizer, embed)
        stored = graph.points[p.id]
        stored.density = 0.6
        graph.save_point(stored)
        ids.append(p.id)
    # the fake bag-of-words embedder undershoots real semantic cosine, so simulate the
    # reinforced-cluster state directly: κ computation itself is covered in test_fu_math
    for e in list(graph.edges.values()):
        if e.from_id in ids and e.to_id in ids:
            e.kappa = 0.6
            graph.save_edge(e)
    # dream loop consolidates the cluster
    report = dream_loop(graph, sensitizer, embed)
    macros = [p for p in graph.points.values() if p.type == "macro"]
    assert macros, f"no macro created (report: {report.summary})"
    assert graph.macro_sources.get(macros[0].id)


def test_wormhole_criteria_and_creation():
    a = MemoryPoint(content="theory of darkness with layered structure",
                    embedding=fake_embed("layered structural theory hierarchy depth"),
                    topics=["theory", "structure"], entities=["Darkness"],
                    utility=0.8, novelty=0.7, hex=Hex(0, 0, 0), density=0.6)
    b = MemoryPoint(content="Fu theory has layered structure and hierarchy",
                    embedding=fake_embed("layered structural theory hierarchy depth Fu"),
                    topics=["theory", "structure"], entities=["Fu"],
                    utility=0.8, novelty=0.7, hex=Hex(10, -10, 0), density=0.6)
    from hmgfu.dream import analogy_heuristic
    analogy = analogy_heuristic(a, b)
    assert should_create_wormhole(a, b, analogy)
    w = create_wormhole(a, b)
    assert w.relation_type == "wormhole" and w.omega == 1.2 and w.direction == "two_way"


def test_wormhole_fires_for_established_low_novelty_pair():
    """Phase 33: a wormhole connects ESTABLISHED analogies — the old minNovelty>0.5 gate blocked
    every mature-graph candidate (established memories aren't novel), and the hard topicOverlap
    gate blocked genuine CROSS-domain analogies (disjoint topic tags). Both removed; density is
    the 'load-bearing' signal now."""
    common = "layered structural theory hierarchy depth recursion"
    a = MemoryPoint(content="theory of darkness with a layered recursive structure",
                    embedding=fake_embed(common + " darkness"),
                    topics=["darkness"], entities=["Darkness"],   # DISJOINT topics (cross-domain)
                    utility=0.3, novelty=0.05, hex=Hex(0, 0, 0), density=0.6)  # established: low novelty
    b = MemoryPoint(content="Fu theory has a layered recursive structure and hierarchy",
                    embedding=fake_embed(common + " Fu"),
                    topics=["fu"], entities=["Fu"],
                    utility=0.3, novelty=0.05, hex=Hex(10, -10, 0), density=0.6)
    from hmgfu.dream import analogy_heuristic
    # would FAIL the old gate (novelty 0.05<0.5, topicOverlap 0<0.25); now forms on density+analogy
    assert should_create_wormhole(a, b, analogy_heuristic(a, b))


def test_infer_resolution_symmetric():
    old = MemoryPoint(content="use Google Maps", timestamp="2026-01-01T00:00:00+00:00")
    new = MemoryPoint(content="use OpenStreetMap", timestamp="2026-06-01T00:00:00+00:00")
    r1 = infer_resolution(old, new)
    r2 = infer_resolution(new, old)
    assert r1["winner"] == new.id == r2["winner"]  # order must not matter (issue 7)
    assert r1["reason"] == "newer_memory"


def test_nano_json_parser_stages():
    assert parse_nano_json('{"a": 1}') == {"a": 1}
    assert parse_nano_json('junk before {"a": 1} junk after') == {"a": 1}
    scraped = parse_nano_json('broken "title": "hello", "importance": 0.7 no braces')
    assert scraped["title"] == "hello" and scraped["importance"] == 0.7
    assert parse_nano_json("total garbage") is None


def test_heuristic_extractor_never_fails():
    for text in ["", "?", "a", "Rex loves Anna in Lisbon.", "porque não gosto de RAG"]:
        out = heuristic_extract(text)
        assert out["extractor"] == "fallback"
        assert -1 <= out["emotional_valence"] <= 1
        assert 0 <= out["importance"] <= 1


def test_sensitizer_routes_nano_and_dream_through_runtime_roles():
    from hmgfu.sensitizer import Sensitizer
    calls = []

    def role_chat(role, messages, **kwargs):
        calls.append(role)
        if role == "nano":
            return {"content": '{"title":"T","summary":"S","type":"message"}'}
        return {"content": "A grounded macro summary."}

    sensitizer = Sensitizer(client=None, enabled=False)
    sensitizer.bind_role_chat(role_chat)
    assert sensitizer.extract("hello")["extractor"] == "nano"
    assert sensitizer.summarise_cluster([MemoryPoint(content="hello", summary="hello")])
    assert calls == ["nano", "dream"]
