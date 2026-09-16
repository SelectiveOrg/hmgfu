"""Phase 30.3: wormhole live-fire test — claim "wormholes have never fired live (zero created
on the real graph); the mechanism is tested, its VALUE is unproven."

This does NOT call should_create_wormhole()/create_wormhole() directly (that's already unit-
tested and would be circular). It builds a realistically DIVERSE corpus across ~7 unrelated
life domains via the REAL ingest pipeline (real embeddings, real nano sensitizer assigning
utility/novelty/entities/topics — nothing hand-set), plants 3 pairs of statements that are
"structurally analogous, cross-domain" (THEORY's own definition: same abstract pattern,
different entities) among it, then runs the REAL engine.dream() and checks graph.stats().

If it does NOT fire, this script also calls find_distant_analogical_pairs on the resulting
organic graph (read-only diagnostic, not a manipulation) to report exactly which THEORY
gate blocked each near-miss — honest negative-result diagnosis, not a manufactured pass.

Run: .venv/Scripts/python scripts/bench_wormhole_live.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import config, fu_math, hexgrid  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.dream import analogy_heuristic, should_create_wormhole  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402

DB = throwaway_db("wormhole_live.db")

# 7 unrelated domains, ~5 statements each, so hex placement genuinely spreads out.
DOMAINS = {
    "guitar": [
        "I've been learning guitar for two years now, mostly self-taught from videos.",
        "Practicing guitar scales every single day, even just 15 minutes, made the biggest difference.",
        "My guitar teacher says consistency beats long weekend sessions for building calluses and muscle memory.",
        "I finally nailed the barre chord transition after months of daily short practice sessions.",
        "Skipping guitar practice for a week set me back noticeably compared to daily short sessions.",
    ],
    "spanish": [
        "I'm studying Spanish using a language app, aiming for conversational fluency by next year.",
        "Doing Spanish vocabulary drills every morning for 15 minutes has been way more effective than weekend cramming.",
        "My Spanish tutor keeps saying daily short sessions beat occasional long study marathons for retention.",
        "I finally got past the subjunctive tense hurdle after weeks of small daily Spanish drills.",
        "Missing a week of Spanish practice noticeably hurt my recall compared to staying consistent daily.",
    ],
    "finance": [
        "I started tracking every expense in a spreadsheet to understand where my money actually goes.",
        "My rent went up this year so I'm rebalancing my monthly budget categories.",
        "I opened a high-yield savings account to stop letting emergency funds sit idle.",
        "Paying off the smallest credit card balance first kept me motivated to keep going.",
        "I set up automatic transfers to investments right after each paycheck lands.",
    ],
    "cooking": [
        "I've been experimenting with sourdough bread, the hydration ratio matters more than I expected.",
        "Meal prepping on Sundays saves me a surprising amount of time during the work week.",
        "My knife skills improved a lot once I actually learned proper grip and finger tucking.",
        "I burned the risotto twice before realizing I wasn't stirring nearly often enough.",
        "Fermenting my own hot sauce turned out way easier than I assumed going in.",
    ],
    "running": [
        "I ran my first 10k this spring after months of slowly building up mileage.",
        "New running shoes fixed the knee pain I'd been getting on longer runs.",
        "I switched to running in the early morning to beat the summer heat.",
        "Interval training twice a week improved my 5k time more than steady long runs alone.",
        "My running group keeps me accountable on weeks when motivation is low.",
    ],
    "home_reno": [
        "We're repainting the living room this weekend, went with a warmer neutral tone.",
        "The contractor found some water damage behind the bathroom tile we hadn't noticed.",
        "Refinishing the hardwood floors ourselves saved a lot compared to hiring it out.",
        "Picking out kitchen cabinet hardware took way longer than I expected.",
        "The new insulation in the attic already made a noticeable difference in heating bills.",
    ],
    "work_project": [
        "The Q3 project launch got pushed back two weeks because of a vendor delay.",
        "Our team switched to daily standups instead of the old weekly status meeting.",
        "I finally got budget approval for the new analytics dashboard project.",
        "The client asked for a scope change midway through the sprint, which threw off our estimate.",
        "We onboarded two new engineers onto the payments migration project this month.",
    ],
}


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    engine = AgentEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1

    print(f"Ingesting {sum(len(v) for v in DOMAINS.values())} statements across "
          f"{len(DOMAINS)} unrelated domains (real embeddings + real nano sensitizer)...")
    for domain, statements in DOMAINS.items():
        for text in statements:
            p = engine.ingest(text, source="user")
            print(f"  [{domain}] hex=({p.hex.q},{p.hex.r}) u={p.utility:.2f} n={p.novelty:.2f} "
                  f"topics={p.topics[:3]}")

    stats_before = engine.graph.stats()
    print(f"\nGraph before dream: {stats_before['points']} points, {stats_before['edges']} edges, "
          f"{stats_before['wormholes']} wormholes")

    print("\nRunning real dream()...")
    report = engine.dream()
    print(f"dream summary: {report.summary}")
    print(f"wormholes created this dream: {len(report.wormholes_created)}")

    stats_after = engine.graph.stats()
    fired = stats_after["wormholes"] > 0
    print(f"\nGraph after dream: {stats_after['wormholes']} wormholes total")

    if fired:
        print("\n=== VERDICT: WORMHOLE FIRED LIVE ===")
        for e in engine.graph.edges.values():
            if e.relation_type == "wormhole":
                a, b = engine.graph.points.get(e.from_id), engine.graph.points.get(e.to_id)
                if a and b:
                    print(f"  {a.title[:45]!r} <-> {b.title[:45]!r} "
                          f"(hexDist={hexgrid.hex_distance(a.hex, b.hex)})")
    else:
        print("\n=== VERDICT: NO WORMHOLE FIRED — diagnosing why (read-only, organic graph) ===")
        dense = sorted((p for p in engine.graph.active_points() if p.type != "macro"
                       and p.density > 0.35 and p.embedding), key=lambda p: -p.density)[:30]
        print(f"{len(dense)} dense candidate points considered (density > 0.35)")
        near_misses = []
        import itertools
        for a, b in itertools.combinations(dense, 2):
            if engine.graph.edge_between(a.id, b.id):
                continue
            analogy = analogy_heuristic(a, b)
            w = config.WORMHOLE
            gates = {
                "hexDistance": (hexgrid.hex_distance(a.hex, b.hex), w["minHexDistance"], ">"),
                "analogy": (analogy, w["minAnalogy"], ">"),
                "semantic": (fu_math.cosine(a.embedding, b.embedding), w["minSemantic"], ">"),
                "entityOverlap": (fu_math.jaccard(a.entities, b.entities), w["maxEntityOverlap"], "<"),
                "minDensity": (min(a.density, b.density), w["minDensity"], ">"),
            }
            passed = sum(1 for k, (v, t, op) in gates.items()
                        if (v > t if op == ">" else v < t if op == "<" else v >= t))
            near_misses.append((passed, len(gates), a, b, gates))
        near_misses.sort(key=lambda t: -t[0])
        print("\nTop 5 closest pairs overall (gates passed / total):")
        for passed, total, a, b, gates in near_misses[:5]:
            print(f"  {passed}/{total}: {a.title[:35]!r} <-> {b.title[:35]!r}")
            for k, (v, t, op) in gates.items():
                ok = (v > t if op == ">" else v < t if op == "<" else v >= t)
                print(f"      {'OK ' if ok else 'FAIL'} {k}: {v:.2f} (needs {op}{t})")

        print("\nSpecifically: the PLANTED cross-domain analogy (guitar-practice vs "
              "spanish-practice 'daily short beats weekend cramming')")
        guitar_habit = [p for p in engine.graph.active_points()
                       if "guitar" in p.content.lower() and "practice" in p.content.lower()
                       and ("consist" in p.content.lower() or "daily" in p.content.lower())]
        spanish_habit = [p for p in engine.graph.active_points()
                         if "spanish" in p.content.lower()
                         and ("consist" in p.content.lower() or "daily" in p.content.lower())]
        for a in guitar_habit:
            for b in spanish_habit:
                analogy = analogy_heuristic(a, b)
                w = config.WORMHOLE
                gates = {
                    "hexDistance": (hexgrid.hex_distance(a.hex, b.hex), w["minHexDistance"], ">"),
                    "analogy": (analogy, w["minAnalogy"], ">"),
                    "semantic": (fu_math.cosine(a.embedding, b.embedding), w["minSemantic"], ">"),
                    "entityOverlap": (fu_math.jaccard(a.entities, b.entities), w["maxEntityOverlap"], "<"),
                    "minDensity": (min(a.density, b.density), w["minDensity"], ">"),
                }
                print(f"  {a.content[:50]!r} <-> {b.content[:50]!r}")
                print(f"    topics a={a.topics} b={b.topics}")
                for k, (v, t, op) in gates.items():
                    ok = (v > t if op == ">" else v < t if op == "<" else v >= t)
                    print(f"      {'OK ' if ok else 'FAIL'} {k}: {v:.2f} (needs {op}{t})")

    engine.graph.close(); engine.client.close()
    try:
        os.remove(DB)
    except PermissionError:
        pass   # Windows file handle lag on a throwaway db — harmless, next run overwrites it
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
