"""Phase 48 — memory-content quality: assistant-fact guard, ephemeral choke-point, procedural
recall isolation, legacy-procedure migration. Runs without Ollama (fake embedder/sensitizer)."""

from __future__ import annotations

from hmgfu.hygiene import apply_ephemeral_meta, is_ephemeral, retype_legacy_procedures
from hmgfu.ingest import ingest_memory
from hmgfu.models import FuEdge, RetrievedMemory
from hmgfu.retrieve import (build_llm_context, expand_through_fu, make_query_point,
                            retrieve_memory)
from hmgfu.taxonomy import node_class


# --- Fix 1: assistant/dream content is never stored as canonical fact ---------------------

def test_assistant_fact_demoted_to_message(graph, sensitizer, embed):
    p = ingest_memory("The user's name is Alice.", source="assistant", graph=graph,
                      sensitizer=sensitizer, embed=embed, mtype="fact")
    assert p.type == "message"          # authorship guard demoted it
    assert node_class(p) == "message"


def test_dream_fact_demoted_but_user_fact_kept(graph, sensitizer, embed):
    d = ingest_memory("Aveiro is the capital.", source="dream", graph=graph,
                      sensitizer=sensitizer, embed=embed, mtype="fact")
    assert d.type == "message"
    u = ingest_memory("My name is Teodoro.", source="user_explicit", graph=graph,
                      sensitizer=sensitizer, embed=embed, mtype="fact")
    assert u.type == "fact"             # genuine user canon untouched


# --- Fix 2: one ephemeral choke-point, idempotent -----------------------------------------

def test_apply_ephemeral_meta_tags_and_caps(graph, sensitizer, embed):
    p = ingest_memory("The weather in Aveiro is 27C right now.", source="user", graph=graph,
                      sensitizer=sensitizer, embed=embed)
    assert is_ephemeral(p.content) and "_ephemeral" in p.keywords
    assert p.utility <= 0.3


def test_ephemeral_not_injected_but_directive_added(graph, sensitizer, embed):
    """Phase 49: a stale weather value must NOT reach the model as answerable context — instead
    a fetch-live directive appears so the model calls brave_web_search."""
    ingest_memory("The weather in Aveiro is 27C and sunny.", source="user", graph=graph,
                  sensitizer=sensitizer, embed=embed)
    ingest_memory("My favourite colour is blue.", source="user", graph=graph,
                  sensitizer=sensitizer, embed=embed, mtype="fact")
    q = make_query_point("what is the current weather in Aveiro", embed, sensitizer)
    ctx, _ = build_llm_context(q, graph)
    assert "27C" not in ctx and "sunny" not in ctx        # stale value NOT injected
    assert "brave_web_search" in ctx                       # fetch-live directive present


def test_apply_ephemeral_meta_idempotent():
    class _P:
        content = "current weather is sunny"
        keywords = []
        utility = 0.9
    p = _P()
    apply_ephemeral_meta(p)
    apply_ephemeral_meta(p)
    assert p.keywords.count("_ephemeral") == 1 and p.utility <= 0.3


# --- Fix 3: procedural/skill nodes never appear in the memory recall pool ------------------

def test_recall_excludes_procedural_and_skill(graph, sensitizer, embed):
    fact = ingest_memory("My favourite colour is blue.", source="user", graph=graph,
                         sensitizer=sensitizer, embed=embed, mtype="fact")
    ingest_memory("Procedure: fetch weather (steps: bash -> bash)", source="dream",
                  graph=graph, sensitizer=sensitizer, embed=embed, mtype="pattern")
    ingest_memory("memory_search tool", source="system", graph=graph,
                  sensitizer=sensitizer, embed=embed, mtype="skill")
    q = make_query_point("what is my favourite colour", embed, sensitizer)
    recalled = retrieve_memory(q, graph)
    ids = {r.point.id for r in recalled}
    classes = {node_class(r.point) for r in recalled}
    assert fact.id in ids                       # episodic fact recalled
    assert not (classes & {"skill", "tool", "directive", "session"})   # procedural excluded


def test_fu_expansion_cannot_reintroduce_special_nodes(graph, sensitizer, embed):
    fact = ingest_memory("My favourite colour is blue.", source="user", graph=graph,
                         sensitizer=sensitizer, embed=embed, mtype="fact")
    tool = ingest_memory("memory_search tool", source="system", graph=graph,
                         sensitizer=sensitizer, embed=embed, mtype="skill")
    graph.save_edge(FuEdge(from_id=fact.id, to_id=tool.id, kappa=1.0, trust=1.0,
                           base_separation=1.0, distance=1.0))
    q = make_query_point("what is my favourite colour", embed, sensitizer)
    expanded = expand_through_fu([RetrievedMemory(point=fact, score=0.8)], graph, 1, q)
    assert {node_class(r.point) for r in expanded}.isdisjoint(
        {"skill", "tool", "directive", "session"}
    )


def test_retrieval_limit_is_final_after_fu_expansion(graph, sensitizer, embed):
    points = [ingest_memory(f"related project memory {i}", source="user", graph=graph,
                            sensitizer=sensitizer, embed=embed, mtype="fact")
              for i in range(4)]
    for point in points[1:]:
        graph.save_edge(FuEdge(from_id=points[0].id, to_id=point.id, kappa=1.0,
                               trust=1.0, base_separation=1.0, distance=1.0))
    q = make_query_point("project memory", embed, sensitizer)
    seed = RetrievedMemory(point=points[0], score=0.8)
    assert len(expand_through_fu([seed], graph, 1, q, limit=1)) <= 1


def test_low_information_greeting_does_not_activate_memory(graph, sensitizer, embed):
    from hmgfu.retrieve import is_low_information_query
    from hmgfu.models import QueryPoint
    assert is_low_information_query(QueryPoint(conversation_act="greeting"))
    assert not is_low_information_query(QueryPoint(conversation_act="question"))
    for text in ("weather in Valencia", "my project uses Python", "my name is Alice"):
        ingest_memory(text, source="user", graph=graph, sensitizer=sensitizer, embed=embed,
                      mtype="fact")
    q = make_query_point("hello", embed, sensitizer)
    q.conversation_act = "greeting"
    assert retrieve_memory(q, graph) == []


# --- Fix 3b: legacy PA3 'Procedure for:' fact nodes migrate to pattern ---------------------

def test_retype_legacy_procedures(graph, sensitizer, embed):
    legacy = ingest_memory("Procedure for: what is the weather? | Tools: bash -> bash",
                           source="user", graph=graph, sensitizer=sensitizer, embed=embed,
                           mtype="fact")
    assert legacy.type == "fact" and node_class(legacy) == "fact"   # mis-typed as fact
    n = retype_legacy_procedures(graph)
    assert n == 1
    migrated = graph.points[legacy.id]
    assert migrated.type == "pattern" and node_class(migrated) == "skill"  # now excluded from recall


def test_startup_repair_demotes_derived_imports_and_stale_canonical_identity(tmp_path):
    from hmgfu.hygiene import repair_memory_provenance
    from tests.test_v2_agent import make_agent
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply("My name is Teodoro H. Ferreira.", "user_explicit")
    stale = ingest_memory("Your name is Mary.", source="user", graph=engine.graph,
                          sensitizer=engine.sensitizer, embed=engine.embed, mtype="fact")
    derived = ingest_memory("A generated summary about the user.", source="user",
                            graph=engine.graph, sensitizer=engine.sensitizer,
                            embed=engine.embed, mtype="fact")
    derived.keywords.append("pa3:nodes:abc")
    engine.graph.save_point(derived)
    report = repair_memory_provenance(engine)
    assert report == {"legacy_derived_reclassified": 1, "canonical_conflicts_superseded": 1,
                      "layers_restratified": 0,    # Phase 56: stratification repair runs here too
                      "questions_retyped": 0,      # Phase 62: stored questions leave the fact class
                      "tool_rules_migrated": 0}    # Phase 66: standing tool rules become directives
    assert engine.graph.points[stale.id].status == "superseded"
    fixed = engine.graph.points[derived.id]
    assert fixed.source == "assistant" and fixed.type == "message"
    assert "_legacy_derived" in fixed.keywords
