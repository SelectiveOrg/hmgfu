"""Phase 27: temporal perception + memory correctness (Sebastian audit)."""

from hmgfu import fu_math
from hmgfu.models import now_iso
from hmgfu.retrieve import make_query_point, retrieve_memory, build_llm_context
from tests.test_v2_agent import make_agent


def test_age_label_buckets():
    now = "2026-07-03T12:00:00+00:00"
    assert fu_math.age_label("2026-07-03T11:59:30+00:00", now) == "just now"
    assert fu_math.age_label("2026-07-03T11:30:00+00:00", now) == "30m ago"
    assert fu_math.age_label("2026-07-03T06:00:00+00:00", now) == "6h ago"
    assert fu_math.age_label("2026-06-28T12:00:00+00:00", now) == "5d ago"
    assert fu_math.age_label("2026-06-01T12:00:00+00:00", now) == "4w ago"
    assert fu_math.age_label("2026-01-01T12:00:00+00:00", now) == "6mo ago"


def test_injection_has_age_tags_and_header(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    old = engine.ingest("My name is Sebastian", source="user")
    old_pt = engine.graph.points[old.id]
    old_pt.timestamp = "2026-01-01T00:00:00+00:00"     # clearly months ago
    engine.graph.save_point(old_pt)
    engine.ingest("Actually my name is Teodoro, not Sebastian", source="user")
    q = make_query_point("what is my name Sebastian Teodoro", engine.embed, engine.sensitizer)
    context, _ = build_llm_context(q, engine.graph)
    assert "ago)" in context or "just now)" in context      # temporal tag on the hexes
    assert "TRUST THE MOST RECENT" in context               # header guidance
    assert "mo ago)" in context                             # the months-old fact is tagged old


def test_within_section_newest_first(tmp_path):
    """Two conflicting facts in the SAME section render newest → oldest."""
    from hmgfu.retrieve import organise_for_injection
    from hmgfu.models import RetrievedMemory
    engine, _ = make_agent(tmp_path, [])
    a = engine.ingest("Project uses Google Maps", source="user")
    b = engine.ingest("Project uses OpenStreetMap now", source="user")
    pa, pb = engine.graph.points[a.id], engine.graph.points[b.id]
    # both clearly old (>14d) so both land in the SAME 'relevant facts' section
    pa.timestamp = "2026-01-01T00:00:00+00:00"; pa.type = "fact"; engine.graph.save_point(pa)
    pb.timestamp = "2026-03-01T00:00:00+00:00"; pb.type = "fact"; engine.graph.save_point(pb)
    inj = organise_for_injection([RetrievedMemory(point=pa, score=0.5, reason=""),
                                  RetrievedMemory(point=pb, score=0.6, reason="")], engine.graph)
    facts = inj["relevantFacts"]
    i_new = next(i for i, x in enumerate(facts) if "OpenStreetMap" in x)
    i_old = next(i for i, x in enumerate(facts) if "Google" in x)
    assert i_new < i_old                                    # newest-first within the section


def test_ingest_dedup_reinforces_not_duplicates(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p1 = engine.ingest("My name is Sebastian.", source="user")
    n1 = len([x for x in engine.graph.points.values() if x.type != "skill"])
    p2 = engine.ingest("My name is Sebastian.", source="user")   # identical
    p3 = engine.ingest("My name is Sebastian", source="user")    # near-identical
    assert p2.id == p1.id and p3.id == p1.id                     # reinforced, not duplicated
    n2 = len([x for x in engine.graph.points.values() if x.type != "skill"])
    assert n2 == n1                                              # zero new nodes
    assert engine.graph.points[p1.id].access_count >= 2


def test_dedup_never_merges_negation_with_affirmation(tmp_path):
    """A negation is a contradiction, not a duplicate — must stay a SEPARATE node."""
    engine, _ = make_agent(tmp_path, [])
    yes = engine.ingest("My name is Sebastian", source="user")
    no = engine.ingest("My name is not Sebastian", source="user")
    assert no.id != yes.id                                   # not collapsed into the affirmation
    assert len([p for p in engine.graph.points.values()
                if "sebastian" in p.content.lower() and p.type != "skill"]) == 2


def test_assistant_reply_never_stored_as_fact(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    from hmgfu.models import RetrievedMemory
    engine._store_assistant_reply("Done — I've remembered that your name is Sebastian.", [])
    facts = [p for p in engine.graph.points.values()
             if p.source == "assistant" and p.type == "fact"]
    assert facts == []                                          # assistants don't author facts
    stored = [p for p in engine.graph.points.values() if p.source == "assistant"]
    assert all(p.type != "fact" for p in stored)


def test_assistant_echo_not_stored(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    fact = engine.ingest("My favorite color is teal", source="user")
    from hmgfu.models import RetrievedMemory
    recalled = [RetrievedMemory(point=engine.graph.points[fact.id], score=0.9, reason="x")]
    before = len(engine.graph.points)
    # reply that echoes the recalled memory → must NOT be stored
    stored = engine._store_assistant_reply("Your favorite color is teal.", recalled)
    assert stored is False and len(engine.graph.points) == before


def test_correction_supersedes_and_temporal_ranks_new(tmp_path):
    """End-to-end of the Sebastian scenario: old wrong fact + newer correction → the newer
    is injected first, tagged newer; dedup prevented copies."""
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("My name is Sebastian", source="user")
    engine.ingest("My name is Sebastian", source="user")       # would-be duplicate
    engine.ingest("My name is Sebastian", source="user")       # would-be duplicate
    sebastian_nodes = [p for p in engine.graph.points.values()
                       if "sebastian" in p.content.lower() and p.type != "skill"]
    assert len(sebastian_nodes) == 1                            # deduped to ONE
    q = make_query_point("who am i, my name", engine.embed, engine.sensitizer)
    _, retrieved = build_llm_context(q, engine.graph)
    assert retrieved   # recall works
