"""Live end-to-end smoke test against real Ollama (gemma4:12b + nano + embedder).

Proves the PROJECT_ID success criterion: a fact taught in turn 1 is recalled in a later
turn via HMG-Fu retrieval — NOT via chat history (each turn is a fresh LLM call whose only
memory is the injected context). Also runs a full dream loop on the seeded graph.

Run:  .venv/Scripts/python scripts/smoke_live.py
Uses a throwaway DB (smoke_live.db) so it never touches real data.
"""

from __future__ import annotations

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import config  # noqa: E402
from hmgfu.chat import HMGFuEngine  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402

# L-03: keep the throwaway db in scratch/ with every other bench db (post-incident hygiene)
DB = throwaway_db("smoke_live.db")

FACTS = [
    "My dog is called Baltazar and he is a very old golden retriever.",
    "I am building a memory system called HMG-Fu based on hexagonal grids.",
    "I work best late at night, usually after 11pm.",
    "My sister Marta lives in Porto and visits me every summer.",
]

PROBE = "What is the name of my dog and what breed is he?"
EXPECT = "baltazar"


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    engine = HMGFuEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama is not reachable")
        return 1
    models = engine.client.models()
    for needed in (config.CHAT_MODEL, config.NANO_MODEL, config.EMBED_MODEL):
        if not any(m.startswith(needed.split(":")[0]) for m in models):
            print(f"FAIL: model {needed} not installed")
            return 1
    print(f"models ok: chat={config.CHAT_MODEL} nano={config.NANO_MODEL} embed={config.EMBED_MODEL}")

    # --- teach facts (ingestion only — no chat history exists afterwards) ----------
    for fact in FACTS:
        t0 = time.perf_counter()
        point = engine.ingest(fact, source="user")
        print(f"ingested [{point.extractor}] ρ={point.density:.2f} "
              f"hex=({point.hex.q},{point.hex.r}) {(time.perf_counter()-t0):.1f}s: {fact[:60]}")
    stats = engine.graph.stats()
    print(f"graph: {stats['points']} points, {stats['edges']} edges")

    # --- recall probe: fresh chat turn, memory must come from HMG retrieval --------
    print(f"\nprobe: {PROBE}")
    result = engine.chat(PROBE)
    print(f"retrieval: {len(result['retrieved'])} memories in {result['retrieval_ms']} ms")
    for r in result["retrieved"][:5]:
        print(f"  [{r['score']:.2f}] {r['point']['title'][:50]} — {r['reason']}")
    print(f"\ngemma4:12b> {result['response'][:400]}")

    answer_ok = EXPECT in result["response"].lower()
    injected_ok = EXPECT in result["injected_context"].lower()
    retrieval_fast = result["retrieval_ms"] < 1000

    # --- dream loop ------------------------------------------------------------------
    print("\nrunning full dream loop...")
    report = engine.dream()
    print(f"dream: {report.summary}")
    for insight in report.insights:
        print(f"  insight: {insight}")
    reports_persisted = len(engine.graph.dream_reports()) >= 1

    engine.graph.close()
    engine.client.close()

    print("\n--- verdict ---")
    print(f"fact injected into context : {'PASS' if injected_ok else 'FAIL'}")
    print(f"fact recalled in answer    : {'PASS' if answer_ok else 'FAIL'}")
    print(f"retrieval < 1000 ms        : {'PASS' if retrieval_fast else 'FAIL'} ({result['retrieval_ms']} ms)")
    print(f"dream report persisted     : {'PASS' if reports_persisted else 'FAIL'}")
    ok = injected_ok and answer_ok and reports_persisted
    print("SMOKE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
