"""Phase 55 — the GENERAL directive lifecycle: FOLLOW -> CHANGE -> CLEAR -> persist (LEARN), for
ARBITRARY content (a joke, a curious fact, a quote…), NOT hardcoded to jokes.

This is the capability the user asked for: "testing if the system can make the llm follow a
directive, change directives and learn". The DirectiveStore is the deterministic engine; these
tests exercise it without Ollama. Live multilingual proof lives in scripts/smoke_live.py + bench.
"""

from __future__ import annotations

from hmgfu.directives import DirectiveStore


def _closer(spec, example):
    return {"kind": "conversation_closer", "value": spec, "fallback_text": example,
            "instruction": f"end every reply with {spec}"}


def test_follow_change_clear_lifecycle_is_content_general(tmp_path):
    db = str(tmp_path / "life.db")
    s = DirectiveStore(db)

    # 1) FOLLOW — a NON-joke directive (a curious fact). The prompt block states the spec; on an
    #    ACTION turn (render suppressed the closer) enforce appends the persisted example.
    s.apply("end every reply with a curious fact",
            detected=_closer("a curious fact", "Octopuses have three hearts."))
    block = s.render_block(first_turn=False)
    assert "curious fact" in block.lower()                       # content spec injected — general
    assert "joke" not in block.lower()                           # nothing joke-specific hardcoded
    forced = s.enforce("The sky is blue.", force_generated=True)
    assert forced.rstrip().endswith("Octopuses have three hearts.")
    # an ORDINARY turn trusts the in-prompt directive — no duplicate stapled
    assert s.enforce("The sky is blue.") == "The sky is blue."

    # 2) CHANGE — a newer directive of the SAME kind deterministically supersedes (PRIMARY KEY),
    #    fact -> joke, with no reliance on a fuzzy contradiction scorer.
    s.apply("actually, end every reply with a short joke instead",
            detected=_closer("a short joke", "Why did the array blush? It saw the byte-code!"))
    active = s.active()
    assert len(active) == 1 and active[0]["value"] == "a short joke"   # exactly one, replaced
    block2 = s.render_block(first_turn=False)
    assert "short joke" in block2.lower() and "curious fact" not in block2.lower()
    assert s.enforce("The sky is blue.", force_generated=True).rstrip().endswith("byte-code!")

    # 3) persist (LEARN) — survives a "restart" (a new store over the same db file)
    s2 = DirectiveStore(db)
    assert s2.active()[0]["value"] == "a short joke"

    # 4) CLEAR — an unambiguous cease-cue removes it entirely (no content left to enforce)
    s2.apply("stop telling jokes at the end")
    assert s2.active() == []
    assert s2.render_block(first_turn=False) == ""
    assert s2.enforce("Done.", force_generated=True) == "Done."       # nothing appended


def test_opener_lifecycle_is_content_general(tmp_path):
    """The opener slot is equally content-general — an inspiring quote, not a joke. The opener is
    applied ONLY by enforce (never injected into the prompt — Phase 52) on the first reply."""
    s = DirectiveStore(str(tmp_path / "op.db"))
    s.apply("open every conversation with an inspiring quote",
            detected={"kind": "conversation_opener", "value": "an inspiring quote",
                      "fallback_text": "The best way out is always through. — Robert Frost"})
    first = s.enforce("Hello!", first_turn=True)
    assert first.startswith("The best way out is always through")    # quote prepended, not a joke
    later = s.enforce("Hello again!", first_turn=False)
    assert "robert frost" not in later.lower()                       # opener only on the first reply


def test_lifecycle_multilingual_spec_passthrough(tmp_path):
    """A Portuguese content spec flows through verbatim — no English-only assumption (multilingual,
    self-growing). detect/store/render never rewrite the spec to a fixed language."""
    s = DirectiveStore(str(tmp_path / "pt.db"))
    s.apply("termine sempre com uma curiosidade",
            detected=_closer("uma curiosidade cientifica", "O mel nunca estraga."))
    block = s.render_block(first_turn=False)
    assert "uma curiosidade cientifica" in block                     # spec preserved in the user's language
    forced = s.enforce("Esta ensolarado.", force_generated=True)
    assert forced.rstrip().endswith("O mel nunca estraga.")


def test_echo_of_active_directive_is_a_noop(tmp_path):
    """Bench L25 regression: the router sees active directives as context and may re-emit one on
    an unrelated turn (a greeting). Same kind+value = restatement → the persisted example must
    stay STABLE (enforce depends on it) and no directive-change event fires."""
    s = DirectiveStore(str(tmp_path / "echo.db"))
    s.apply("end with a joke", detected=_closer("a short joke", "Original example joke?"))
    # echo with a REGENERATED example — must be discarded, stored example unchanged, no event
    assert s.apply("hello", detected=_closer("a short joke", "A different fresh joke!")) is None
    d = s.active()[0]
    assert d["fallback_text"] == "Original example joke?"
    # …but an echo may BACKFILL an EMPTY example (migrated rows) — still no change event
    s2 = DirectiveStore(str(tmp_path / "echo2.db"))
    s2.apply("end with a joke", detected=_closer("a short joke", ""))
    assert s2.apply("hello", detected=_closer("a short joke", "Backfilled example?")) is None
    assert s2.active()[0]["fallback_text"] == "Backfilled example?"
    # a genuinely NEW value still supersedes and takes the new example
    assert s.apply("make it a fact", detected=_closer("a curious fact", "Honey never spoils."))
    assert s.active()[0]["value"] == "a curious fact"
    assert s.active()[0]["fallback_text"] == "Honey never spoils."


def test_delete_point_cascades_edges_and_frees_hex(graph):
    """The store primitive behind a clean CLEAR: delete_point removes the point, its edges (from the
    map AND the other endpoint's adjacency AND SQLite), and frees its hex cell."""
    from hmgfu.models import MemoryPoint, FuEdge, Hex
    a = MemoryPoint(content="node A", hex=Hex(0, 0, 0))
    b = MemoryPoint(content="node B", hex=Hex(3, -3, 0))
    graph.save_point(a)
    graph.save_point(b)
    graph.save_edge(FuEdge(from_id=a.id, to_id=b.id, kappa=0.5))
    assert graph.edge_between(a.id, b.id) is not None
    a_key = a.hex.key()

    assert graph.delete_point(a.id) is True
    assert a.id not in graph.points                                  # point gone
    assert graph.get_edges(b.id) == []                              # edge unindexed from the OTHER endpoint
    assert graph.occupied.get(a_key) is None                        # hex cell freed
    assert graph.delete_point("nonexistent") is False               # no-op on a missing id
    # gone from SQLite too — a fresh graph over the same db does not resurrect it
    reopened = graph.__class__(db_path=graph.db_path)
    assert a.id not in reopened.points and not reopened.all_edges()
    reopened.close()


def test_clear_prunes_the_directive_graph_node(tmp_path):
    """CLEAR must remove a directive EVERYWHERE, not only from enforcement: the decay-immune HMG
    projection node is pruned too, so the viz/recall never shows a directive not in force."""
    from hmgfu.taxonomy import mirror_directive_nodes
    from tests.test_v2_agent import make_agent
    engine, _ = make_agent(tmp_path, [])

    def _closer_nodes():
        return [p for p in engine.graph.all_points()
                if p.type == "directive" and "directive:conversation_closer" in p.keywords]

    engine.directives.apply("end every reply with a curious fact",
                            detected={"kind": "conversation_closer", "value": "a curious fact"})
    mirror_directive_nodes(engine)
    assert len(_closer_nodes()) == 1                                 # projected into the graph

    engine.directives.apply("stop adding anything at the end",
                            detected={"kind": "conversation_closer", "clear": True})
    assert engine.directives.active() == []                         # store cleared (enforcement path)
    mirror_directive_nodes(engine)
    assert _closer_nodes() == []                                    # node pruned too — clean CLEAR everywhere
