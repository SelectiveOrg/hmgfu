"""Phase 56 gap 4 — layer stratification: episodic content must not sit in identity layers.

Audit evidence: 1152/1539 production points in L3_identity (importer mapped assistant-derived
kinds to identity; Phase 48 re-typed without re-layering) → the injector's "User identity"
section and the dense-identity channel fired on chatter. Two enforcement points, one predicate
(taxonomy.episodic_repair_layer): hygiene DEMOTES existing pollution, the promotion gate CAPS
new pollution. No Ollama.
"""

from __future__ import annotations

from hmgfu.dream import promote_stable_memories
from hmgfu.hygiene import repair_layer_stratification
from hmgfu.models import MemoryPoint
from hmgfu.taxonomy import episodic_repair_layer, layer_cap
from tests.conftest import fake_embed


def _pt(graph, content, **kw):
    kw.setdefault("embedding", fake_embed(content))
    p = MemoryPoint(content=content, **kw)
    graph.save_point(p)
    return p


def test_repair_demotes_episodic_and_keeps_canon(graph):
    wrong_msg = _pt(graph, "user asked about the weather that day",
                    type="message", source="user", layer="L3_identity")
    wrong_dec = _pt(graph, "assistant decided to use the search tool",
                    type="decision", source="assistant", layer="L3_identity")
    wrong_fact = _pt(graph, "the assistant summarised a preference",
                     type="fact", source="assistant", layer="L3_identity")
    wrong_pattern = _pt(graph, "procedure for building weather widgets end to end",
                        type="pattern", source="assistant", layer="L3_identity")
    gold_fact = _pt(graph, "my name is Teodoro", type="fact",
                    source="user_explicit", layer="L3_identity")
    system_fact = _pt(graph, "canonical projection", type="fact",
                      source="system", layer="L3_identity")
    directive = _pt(graph, "conversation closer: a short joke", type="directive",
                    source="user_explicit", layer="L5_deep_pattern")
    macro = _pt(graph, "digest of a cluster of episodes about the trip",
                type="macro", source="dream", layer="L4_world_model")
    low_msg = _pt(graph, "plain low message", type="message", source="user", layer="L1_session")

    changed = repair_layer_stratification(graph)
    assert changed == 4                                       # exactly the four polluted nodes
    assert graph.points[wrong_msg.id].layer == "L1_session"
    assert graph.points[wrong_dec.id].layer == "L1_session"
    assert graph.points[wrong_fact.id].layer == "L1_session"
    assert graph.points[wrong_pattern.id].layer == "L2_project"
    assert graph.points[gold_fact.id].layer == "L3_identity"  # user canon untouched
    assert graph.points[system_fact.id].layer == "L3_identity"
    assert graph.points[directive.id].layer == "L5_deep_pattern"
    assert graph.points[macro.id].layer == "L4_world_model"   # hierarchy-owned, untouched
    assert graph.points[low_msg.id].layer == "L1_session"     # below L3: never touched
    assert repair_layer_stratification(graph) == 0            # idempotent


def test_promotion_gate_caps_episodic_at_project_layer(graph):
    """The other enforcement point: a heavily-used message may EARN L2 but never L3 — without
    this cap the repair would flap against organic promotion."""
    stats = dict(density=0.9, utility=0.9, confidence=0.9, access_count=10, energy=0.9)
    msg = _pt(graph, "extremely reinforced user message about deployments",
              type="message", source="user", layer="L2_project", **stats)
    fact = _pt(graph, "user explicit identity statement about their role",
               type="fact", source="user_explicit", layer="L2_project", **stats)
    promoted = promote_stable_memories(graph)
    assert fact.id in promoted
    assert graph.points[fact.id].layer == "L3_identity"       # canon rises normally
    assert msg.id not in promoted
    assert graph.points[msg.id].layer == "L2_project"         # episodic capped at its ceiling
    # and the same message DOES still promote below its cap (L1 → L2)
    msg2 = _pt(graph, "another heavily used user message about deployments daily",
               type="message", source="user", layer="L1_session", **stats)
    assert msg2.id in promote_stable_memories(graph)
    assert graph.points[msg2.id].layer == "L2_project"


def test_predicate_and_cap_are_consistent():
    """layer_cap derives from the SAME predicate as the repair (Rule 5): anything the repair
    would demote is capped at L2; anything it leaves alone may reach L5."""
    episodic = MemoryPoint(content="x", type="message", source="user")
    canon = MemoryPoint(content="x", type="fact", source="user_explicit")
    assert episodic_repair_layer(episodic) and layer_cap(episodic) == "L2_project"
    assert episodic_repair_layer(canon) is None and layer_cap(canon) == "L5_deep_pattern"
