import math

import pytest

from hmgfu import config, fu_math
from hmgfu.models import FuEdge, MemoryPoint, QueryPoint, now_iso
from tests.conftest import fake_embed


def test_weight_tables_sum_to_one():
    sums = config.weight_sums()
    assert sums["density"] == pytest.approx(1.0)
    assert sums["kappa"] == pytest.approx(1.0)
    assert sums["memory_score_positive"] == pytest.approx(0.95)
    assert sums["memory_score_penalties"] == pytest.approx(0.05)


def test_cosine_bounds_and_identity():
    v = fake_embed("hexagonal memory grid")
    assert fu_math.cosine(v, v) == pytest.approx(1.0)
    assert fu_math.cosine(v, []) == 0.0
    a = fake_embed("hexagonal memory grid theory")
    b = fake_embed("banana pancake recipe")
    assert fu_math.cosine(a, v) > fu_math.cosine(b, v)


def test_lexical_relevance_uses_literal_query_coverage():
    assert fu_math.lexical_relevance("What is the project codeword ORCA-7?",
                                     "project_codeword: ORCA-7") == pytest.approx(1.0)
    assert fu_math.lexical_relevance("What is the project codeword?", "weather in Valencia") == 0


def test_jaccard():
    assert fu_math.jaccard(["A", "b"], ["a", "B"]) == 1.0
    assert fu_math.jaccard(["a"], ["b"]) == 0.0
    assert fu_math.jaccard([], ["b"]) == 0.0


def test_normalise_log_saturation():
    assert fu_math.normalise_log(0) == 0.0
    assert fu_math.normalise_log(config.RECURRENCE_REF) == pytest.approx(1.0)
    assert 0 < fu_math.normalise_log(3) < 1


def test_temporal_and_recency_monotonic():
    t0 = "2026-07-01T00:00:00+00:00"
    t_close = "2026-07-01T06:00:00+00:00"
    t_far = "2026-06-20T00:00:00+00:00"
    assert fu_math.temporal_proximity(t0, t_close) > fu_math.temporal_proximity(t0, t_far)
    assert fu_math.recency_score(t_close, now=t0) > fu_math.recency_score(t_far, now=t0)


def _point(content="x", **kw):
    defaults = dict(content=content, embedding=fake_embed(content))
    defaults.update(kw)
    return MemoryPoint(**defaults)


def test_density_range_and_ordering():
    weak = _point(importance=0.1, utility=0.1, confidence=0.3, novelty=0.1)
    strong = _point(importance=0.9, utility=0.9, confidence=0.9, novelty=0.8,
                    emotional_intensity=0.7, access_count=10)
    d_weak = fu_math.compute_density(weak, centrality=0.0)
    d_strong = fu_math.compute_density(strong, centrality=0.8)
    assert 0 <= d_weak < d_strong <= 1


def test_kappa_higher_for_related():
    a = _point("I am building the HMG memory project with Fu theory",
               entities=["HMG"], topics=["memory"])
    b = _point("The HMG project stores memory in a hexagonal grid",
               entities=["HMG"], topics=["memory"])
    c = _point("I ate a banana pancake for breakfast",
               entities=[], topics=["food"])
    assert fu_math.compute_kappa(a, b) > fu_math.compute_kappa(a, c)


def test_fu_distance_formula():
    # F = N·(1 + κ·ρa·ρb·Ω) — exact per THEORY §5/§9
    assert fu_math.fu_distance(0.5, 1.0, 0.8, 0.5, 2.0) == pytest.approx(2.0 * (1 + 0.5 * 0.8 * 0.5 * 1.0))
    # zero coupling → F = N
    assert fu_math.fu_distance(0.0, 1.2, 1.0, 1.0, 3.0) == 3.0


def test_omega_table_and_default():
    assert fu_math.compute_omega("wormhole") == 1.2
    assert fu_math.compute_omega("same_entity") == 1.0
    assert fu_math.compute_omega("unknown_relation") == config.OMEGA_DEFAULT


def test_propagation_never_amplifies():
    # even the strongest possible edge must attenuate (THEORY issue 3)
    edge = FuEdge(kappa=1.0, omega=1.2, trust=1.0, distance=0.5, tension=0.0)
    assert fu_math.propagation_factor(edge) <= config.PROPAGATION_MAX_FACTOR < 1.0


def test_memory_score_prefers_relevant():
    q = QueryPoint(text="tell me about the HMG memory project",
                   embedding=fake_embed("tell me about the HMG memory project"),
                   entities=["HMG"], topics=["memory"], intent="question")
    relevant = _point("HMG memory project uses hexagons", entities=["HMG"],
                      topics=["memory"], density=0.7, utility=0.7, type="fact")
    irrelevant = _point("banana pancakes taste great", topics=["food"],
                        density=0.2, utility=0.2)
    assert fu_math.memory_score(q, relevant) > fu_math.memory_score(q, irrelevant)


def test_memory_score_relevance_beats_repetition_after_gate_saturates():
    """A frequently reinforced partial match must not outrank a much closer answer.

    Both memories are above the relevance-gate reference point, which isolates the
    Phase-49 saturation defect: density/utility must remain supporting evidence rather
    than becoming more important than query fit.
    """
    q = QueryPoint(text="weather forecast Aveiro", embedding=[1.0, 0.0],
                   topics=["weather"], intent="question")
    relevant = MemoryPoint(content="specific Aveiro forecast", type="fact",
                           embedding=[0.8, 0.6], topics=["weather"],
                           density=0.1, utility=0.1)
    repeated = MemoryPoint(content="frequently repeated weather note", type="fact",
                           embedding=[0.55, math.sqrt(1.0 - 0.55 ** 2)],
                           topics=["weather"], density=1.0, utility=1.0)
    assert fu_math.memory_score(q, relevant) > fu_math.memory_score(q, repeated)


def test_wormhole_boost_increases_score():
    q = QueryPoint(text="q", embedding=fake_embed("q"))
    p = _point("something", density=0.5, utility=0.5)
    plain = FuEdge(kappa=0.5, base_separation=1.0, tension=0.0, relation_type="semantic_similarity")
    worm = FuEdge(kappa=0.5, base_separation=1.0, tension=0.0, relation_type="wormhole")
    assert fu_math.memory_score(q, p, worm) > fu_math.memory_score(q, p, plain)


def test_decay_zero_when_dense_or_new():
    dense = _point(density=1.0, utility=1.0)
    assert fu_math.compute_decay(dense) == 0.0
    fresh = _point(timestamp=now_iso())
    assert fu_math.compute_decay(fresh) == pytest.approx(0.0, abs=1e-3)


def test_decay_positive_for_old_weak():
    old = _point(timestamp="2026-01-01T00:00:00+00:00", density=0.05,
                 utility=0.05, access_count=0)
    d = fu_math.compute_decay(old, now="2026-07-01T00:00:00+00:00")
    assert 0 < d <= config.DECAY_CAP


def test_dormancy_centrality_guard():
    p = _point(energy=0.01, density=0.1, access_count=0)
    assert fu_math.should_go_dormant(p, centrality=0.1)
    assert not fu_math.should_go_dormant(p, centrality=0.9)  # hubs never sleep (issue 4)


def test_promotion_gate_and_layers():
    p = _point(density=0.8, utility=0.7, confidence=0.8, access_count=5, stability=0.7)
    assert fu_math.should_promote(p)
    assert fu_math.next_layer("L0_raw") == "L1_session"
    assert fu_math.next_layer("L5_deep_pattern") == "L5_deep_pattern"
    p.layer = "L5_deep_pattern"
    assert not fu_math.should_promote(p)  # already at the top


def test_contradiction_heuristic_needs_overlap():
    a = _point("I love using Google Maps", topics=["navigation"], entities=["Google Maps"],
               emotional_valence=0.6)
    b = _point("I do not use Google Maps anymore, I stopped", topics=["navigation"],
               entities=["Google Maps"], emotional_valence=-0.4)
    c = _point("the sky is blue", topics=["weather"])
    assert fu_math.contradiction_heuristic(a, b) > 0
    assert fu_math.contradiction_heuristic(a, c) == 0.0



def test_74_7_edge_kappa_is_query_relative():
    """74.7: an edge lends κ only in proportion to how relevant its OTHER endpoint is to the query. A cluster of
    self-similar filler linked by strong edges must not outrank a unique on-topic memory (the relational-bench loss)."""
    q = QueryPoint(text="what is my favourite colour", embedding=[1.0, 0.0, 0.0])
    p = _point("long walk after dinner", density=0.3, utility=0.3)
    p.embedding = [0.6, 0.8, 0.0]
    strong = FuEdge(kappa=0.75, base_separation=1.0, tension=0.0, relation_type="same_entity")
    full = fu_math.memory_score_components(q, p, strong, path_relevance=1.0)
    none = fu_math.memory_score_components(q, p, strong, path_relevance=0.0)
    assert full["kappa"] == pytest.approx(0.75)
    assert none["kappa"] == pytest.approx(fu_math.query_kappa(q, p))       # the direct path is all that is left
    assert none["fuDistancePenalty"] == pytest.approx(0.2)                  # an edge that lends nothing costs nothing
    assert fu_math.memory_score(q, p, strong, path_relevance=0.0) < fu_math.memory_score(q, p, strong)
    # legacy callers (no path_relevance) are unchanged when the edge is the strongest path
    assert fu_math.memory_score(q, p, strong) == pytest.approx(fu_math.memory_score(q, p, strong, path_relevance=1.0))


def test_74_7_best_edge_prefers_a_relevant_neighbour(tmp_path):
    """The edge chosen for a candidate is the one whose OTHER endpoint the query is about, not the strongest raw κ."""
    from hmgfu.retrieve import _best_edge_toward
    from hmgfu.store import HMGGraph
    g = HMGGraph(str(tmp_path / "g.db"))
    q = QueryPoint(text="favourite colour", embedding=[1.0, 0.0, 0.0])
    p = _point("candidate"); p.embedding = [0.7, 0.7, 0.0]
    on_topic = _point("my favourite colour is burgundy"); on_topic.embedding = [1.0, 0.0, 0.0]
    filler = _point("long walk after dinner"); filler.embedding = [0.0, 0.0, 1.0]
    for x in (p, on_topic, filler):
        g.save_point(x)
    g.save_edge(FuEdge(from_id=p.id, to_id=filler.id, kappa=0.9, base_separation=1.0, relation_type="same_entity"))
    g.save_edge(FuEdge(from_id=p.id, to_id=on_topic.id, kappa=0.4, base_separation=1.0, relation_type="temporal"))
    origin = {x.id: ("semantic", x) for x in (p, on_topic, filler)}
    edge, rel = _best_edge_toward(p, origin, g, q)
    assert edge is not None and edge.to_id == on_topic.id and rel > 0.5
    legacy, rel_legacy = _best_edge_toward(p, origin, g)                     # no query: raw κ, as before
    assert legacy.to_id == filler.id and rel_legacy == 1.0
