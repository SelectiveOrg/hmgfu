"""Phase 90.G — demonstration (a): a promised memory search is actually executed. The live shape of 2026-09-07 turns 9–12: the user asks
how many links the assistant has, the assistant offers to search its broader memory and asks; the user says "yes"; the search must RUN
(a memory_search / memory_timeline / memory_zoom call in the trace), and the reply must not be a promise. Throwaway clone; reuses the
say-do runner's engine, sessions and turn wrapper. Prints one line per repetition and a summary."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

MEMORY_TOOLS = {"memory_search", "memory_timeline", "memory_zoom"}
PROMISE = ("i'll start", "i will start", "i'll search", "i will search", "let me search", "i'm performing", "i am performing", "shall i go ahead")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=3); ap.add_argument("--db", default=None)
    args = ap.parse_args()
    rows = []
    for rep in range(1, args.reps + 1):
        clone = os.path.join(SCRATCH, f"promised_search_{rep}_{os.getpid()}.db"); sd.clone_live(clone, args.db)
        e = sd.fresh_engine(clone, None); sid = sd.new_session(e, "links")
        r1 = sd.turn(e, sid, "how many links do you have?"); wait_for_tail(e)
        asked = "?" in (r1.get("response") or "")[-160:]
        # the live shape when the assistant offers ("Shall I…?") is "yes"; when it answers from the profile directly (the 90.G first
        # reading: 3/3 grounded "one link"), the user asks the broader search explicitly — an explicit read request must RUN
        follow = "yes" if asked else "can you check your broader memory for other links I shared, and tell me how many you find?"
        r2 = sd.turn(e, sid, follow); wait_for_tail(e)
        final = r2 or r1
        tools = [t["name"] for t in final["tool_trace"] if not t.get("blocked")]
        searched = bool(set(tools) & MEMORY_TOOLS) or bool(set(r1["_tools"]) & MEMORY_TOOLS)
        reply = (final.get("response") or "").lower()
        promised = any(p in reply for p in PROMISE) and not searched
        row = {"rep": rep, "turn1_tools": r1["_tools"], "turn1_asked": asked, "turn1_reply": (r1.get("response") or "")[:160], "follow": follow, "turn2_tools": tools if r2 else None,
               "searched": searched, "still_a_promise": promised, "saydo": final.get("saydo"), "reply": (final.get("response") or "")[:200]}
        rows.append(row)
        print(f"[{'OK ' if searched and not promised else 'BAD'}] rep {rep}: turn1 tools {r1['_tools']} asked={asked} · turn2 tools {row['turn2_tools']} · searched={searched} promise={promised} · saydo={(final.get('saydo') or {}).get('action')}")
        print("      reply:", row["reply"][:160].replace("\n", " | "))
        e.graph.close()
    ok = sum(1 for r in rows if r["searched"] and not r["still_a_promise"])
    print(f"\nPROMISED SEARCH EXECUTED: {ok}/{len(rows)}")
    print("versioned:", write_versioned("promised_search", {"rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
