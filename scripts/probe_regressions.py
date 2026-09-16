"""Phase 29: targeted live-trace regression probe (real gemma), scenarios from the Phase 28
user-reported trace that the unit-level hygiene tests don't exercise end-to-end:
  P1 — stale ephemeral weather fact must NOT be answered as current after hygiene decay
  P2 — hygiene_pass() runs inside the real dream() call (not just called standalone in tests)
  P3 — a real chat correction (not a direct facts.apply() call) fully propagates: canonical
       value updates, stale node superseded, NEXT turn recalls the new value only

Uses a throwaway db (probe_regressions.db). Run with the main server STOPPED (single writer).
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.agent import AgentEngine  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402

DB = throwaway_db("probe_regressions.db")
RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    e = AgentEngine(db_path=DB)
    if not e.client.available():
        print("FAIL: Ollama unreachable")
        return 1

    # ---- P1: seed an old ephemeral weather node, decay it, ask "what's the weather" ----
    print("P1 — stale ephemeral weather must not be answered as current")
    p = e.ingest("The current weather in Valencia is 27C with scattered clouds", source="user")
    pt = e.graph.points[p.id]
    pt.timestamp = "2026-06-01T00:00:00+00:00"   # weeks old
    e.graph.save_point(pt)
    r = e.agent_chat("What is the weather in Valencia right now?")
    reply = r["response"].lower()
    stale_leak = "27" in reply or "scattered clouds" in reply
    check("P1 stale weather NOT repeated as current fact", not stale_leak, reply[:160])

    # ---- P2: real dream() call runs hygiene internally -----------------------------------
    print("P2 — hygiene runs inside real dream()")
    # seed a duplicate + junk fact the way real pollution looks (bypass ingest dedup)
    for i in range(3):
        q = e.ingest(f"dup seed {i}", source="user")
        qt = e.graph.points[q.id]
        qt.content = qt.summary = "Your favorite color is blue."
        qt.type = "fact"
        e.graph.save_point(qt)
    report = e.dream()
    hygiene_ran = "hygiene" in (report.summary or "").lower() or any(
        "hygiene" in str(i).lower() for i in report.insights)
    check("P2 dream() summary/insights mention hygiene", hygiene_ran, report.summary[:160])

    # ---- P3: correction via REAL chat turn (not direct facts.apply) --------------------
    print("P3 — end-to-end chat correction propagates")
    e.agent_chat("My name is Sebastian.", explicit=True)
    e.agent_chat("Correction: I'm not Sebastian. My name is Teodoro Ferreira.", explicit=True)
    fact = e.facts.active()
    name_fact = next((f for f in fact if f["key"] == "name"), None)
    check("P3a canonical fact updated via chat", bool(name_fact) and name_fact["value"] == "Teodoro Ferreira",
          str(name_fact))
    r = e.agent_chat("What is my name?")
    reply = r["response"].lower()
    check("P3b next turn recalls ONLY the corrected name",
          "teodoro" in reply and "sebastian" not in reply, reply[:160])

    e.graph.close(); e.client.close()

    print("\n=== PROBE SUMMARY ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, _ in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"TOTAL: {passed}/{len(RESULTS)}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
