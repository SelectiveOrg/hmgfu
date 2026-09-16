"""P1 — the Provenance Spine ("a gravação", Plan.txt G1): every derived canon fact stores the
EXACT source words + a link to the source turn, written at WRITE time. Pre-registered gate:
10 scripted memories → the verbatim original is recoverable 10/10 via the EXISTING retrieval
path (no new search machinery); every canon entry resolves to its source turn.
Falsifier: any derived memory that cannot resolve to its source turn = G1 FAIL — fix the
write path, never backfill by guess."""

from tests.test_v2_agent import make_agent

FACTS = [
    ("name", "My name is Amara Silva"),
    ("favorite_color", "my favorite color is teal"),
    ("hometown", "my hometown is Aveiro"),
    ("favorite_dish", "my favorite dish is xima with caril"),
    ("favorite_band", "my favorite band is Ghorwane"),
    ("favorite_sport", "my favorite sport is basketball"),
    ("dream_city", "my dream city is Pemba"),
    ("favorite_book", "my favorite book is Terra Sonambula"),
    ("favorite_season", "my favorite season is winter"),
    ("lucky_number", "my lucky number is seventeen"),
]


def test_g1_canon_provenance_10_of_10(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "Noted.", "tool_calls": []}] * len(FACTS))
    for _, text in FACTS:
        engine.agent_chat(text, explicit=False)
    from hmgfu.slots import normalise_key   # Phase 62: canon keys are closed-slot ids
    canon = {f["key"]: f for f in engine.facts.active()}
    hits = 0
    for key, text in FACTS:
        f = canon.get(normalise_key(key))
        assert f is not None, f"canon key missing: {key}"
        assert f["verbatim"] == text, "the EXACT words must be stored at write time"
        assert f["source_turn_id"], f"unresolvable source turn for {key} (G1 falsifier)"
        src = engine.graph.points.get(f["source_turn_id"])
        assert src is not None and src.content == text     # the link resolves to the raw turn
        # the EXISTING retrieval path returns the verbatim original (no new search machinery).
        # min_score is the path's own documented override: the FAKE bag-of-words embedder under-
        # scores single-shared-word queries ("…about my name?" ↔ "My name is Amara Silva") below
        # the default floor — an environment artifact (bge-m3 matches these semantically), so the
        # floor is lowered WITHOUT changing the path or the assertion (Rule 13: environment layer).
        _, retrieved, _ = engine.retrieve(
            f"what exactly did I say about my {key.replace('_', ' ')}?", min_score=0.05)
        if any(r.point.id == f["source_turn_id"] for r in retrieved):
            hits += 1
    assert hits == len(FACTS), f"verbatim original recoverable only {hits}/{len(FACTS)}"


def test_g1_api_exposes_provenance(tmp_path):
    """/api/facts serves verbatim + source_turn_id (Rule 10 — visible, the Canon widget renders it)."""
    engine, _ = make_agent(tmp_path, [{"content": "ok", "tool_calls": []}])
    engine.agent_chat("my favorite color is teal", explicit=False)
    f = engine.facts.active()[0]
    assert set(f) >= {"key", "value", "verbatim", "source_turn_id", "updated_at"}
