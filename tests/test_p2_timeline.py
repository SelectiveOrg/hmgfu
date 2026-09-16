"""P2 — the Timeline Reader ("a linha", Plan.txt G2): freshness=historical routes to a chain-walk
over EXISTING data (points incl. superseded + dates; no new storage), surfaced oldest→newest.
Pre-registered legs: current-value routing unchanged; before/previous ≥0.9; A-B-A return case
(the chain preserves the loop); split-fact (two keys coexist). Falsifier: history leaking into
present intent = ROUTER bug — fix the class, not the chain."""

import datetime as dt

from hmgfu.retrieve import make_query_point, retrieve_memory, organise_for_injection, render_injection
from tests.test_v2_agent import make_agent

HIST = ["what was my favorite color before?", "qual era a minha cor favorita antes?",
        "when did I change my hometown?", "how long have I been vegetarian?",
        "desde quando moro na Aveiro?", "há quanto tempo sou vegetariano?",
        "what did I say previously about my diet?", "primeira vez que falei do meu carro?"]
PRESENT = ["what is my favorite color?", "qual é a minha cor favorita?", "where do I live?",
           "am I vegetarian?", "tell me about my diet"]


def _stamp(engine, p, days_ago):
    p.timestamp = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).isoformat()
    engine.graph.save_point(p)


def test_regression_router_historical_without_cue_does_not_hijack(tmp_path):
    """REGRESSION GUARD (2026-07-20): the nano router over-fires freshness=historical on plain
    present-tense queries (it was decorative until P2 made it load-bearing). A historical flag
    WITHOUT a text past-reference cue must NOT route to the timeline — that hijacked ~80% of live
    recall. retrieve_memory routes on the CUE (deterministic), not the router field alone."""
    from hmgfu.retrieve import make_query_point, retrieve_memory
    engine, _ = make_agent(tmp_path, [])
    fact = engine.ingest("my dog is a golden retriever named Baltazar", source="user")
    q = make_query_point("what is my dog name", engine.embed, engine.sensitizer)
    q.freshness = "historical"                        # simulate the router false-positive
    got = retrieve_memory(q, engine.graph)
    assert got and not got[0].reason.startswith("history")   # NORMAL recall, not the timeline
    assert any(r.point.id == fact.id for r in got)           # the dog fact is actually recalled


def test_g2_history_routing_and_present_unchanged(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    hits = sum(1 for q in HIST
               if make_query_point(q, engine.embed, engine.sensitizer).freshness == "historical")
    assert hits >= round(0.9 * len(HIST)), f"history routed only {hits}/{len(HIST)}"
    for q in PRESENT:   # falsifier leg: present-value questions must NOT leak to history mode
        assert make_query_point(q, engine.embed, engine.sensitizer).freshness != "historical", q


def test_g2_aba_chain_preserves_the_loop(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    # NB: an IDENTICAL restatement dedups into the original point (by design) — the return leg
    # is worded as a real user would rephrase it, so the loop exists as three dated points.
    a1 = engine.ingest("my diet is vegetarian", source="user"); _stamp(engine, a1, 300)
    b = engine.ingest("my diet is omnivore now", source="user"); _stamp(engine, b, 100)
    a2 = engine.ingest("my diet is vegetarian again", source="user_explicit"); _stamp(engine, a2, 5)
    a1.status = "superseded"; engine.graph.save_point(a1)        # the old A leg was superseded
    q = make_query_point("what was my diet before?", engine.embed, engine.sensitizer)
    assert q.freshness == "historical"
    got = retrieve_memory(q, engine.graph)
    ids = [r.point.id for r in got]
    assert ids.index(a1.id) < ids.index(b.id) < ids.index(a2.id)   # chronological, loop intact
    assert a1.id in ids                                            # superseded STILL on the line
    assert all(r.reason.startswith("history") for r in got)


def test_g2_split_fact_keys_coexist(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "ok", "tool_calls": []}] * 2)
    engine.agent_chat("my morning coffee is espresso", explicit=False)
    engine.agent_chat("my evening coffee is decaf", explicit=False)
    canon = {f["key"]: f["value"] for f in engine.facts.active()}
    # Phase 62: attributes outside the closed schema keep DISTINCT open keys (no collapse)
    assert canon.get("open.morning_coffee") == "espresso" and canon.get("open.evening_coffee") == "decaf"
    assert all(p.status == "active" for p in engine.graph.points.values()
               if "coffee" in p.content)                           # no cross-supersession
    q = make_query_point("what was my morning coffee before?", engine.embed, engine.sensitizer)
    tl = [r.point.content for r in retrieve_memory(q, engine.graph)]
    assert any("espresso" in t for t in tl)                        # the asked line is present


def test_g2_injection_renders_dated_chronological_timeline(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    old = engine.ingest("my favorite color is blue", source="user"); _stamp(engine, old, 200)
    new = engine.ingest("my favorite color is green", source="user_explicit"); _stamp(engine, new, 2)
    old.status = "superseded"; engine.graph.save_point(old)
    q = make_query_point("what was my favorite color before?", engine.embed, engine.sensitizer)
    got = retrieve_memory(q, engine.graph)
    inj = organise_for_injection(got, engine.graph,
                                 superseded=[("favorite_color", "blue")])   # stale filter MUST not drop it
    lines = inj["subjectTimeline"]
    assert len(lines) >= 2 and lines == sorted(lines)              # dated + chronological
    assert any("[superseded]" in l and "blue" in l for l in lines)  # annotated, never removed
    text = render_injection(inj)
    assert "Subject timeline" in text and "blue" in text and "green" in text
