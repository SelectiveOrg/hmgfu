"""Memory benchmark: directives across sessions, contradictions, tool recall, fact recall.

Each "session" is a FRESH AgentEngine instance over the same throwaway db (bench_memory.db)
— exactly what a server restart / new conversation looks like. Real gemma + nano.

Run: .venv/Scripts/python scripts/bench_memory.py   (server should be STOPPED — single writer)
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.tool_points import retrieve_tools_for_turn  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402

DB = throwaway_db("bench_memory.db")
RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def fresh_engine() -> AgentEngine:
    return AgentEngine(db_path=DB)


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)

    # ---- SESSION 1: teach a directive + a fact ------------------------------------
    print("SESSION 1 — teach")
    e1 = fresh_engine()
    if not e1.client.available():
        print("FAIL: Ollama unreachable")
        return 1
    r = e1.agent_chat("Standing directive: always end every one of your replies with the word "
                      "'Capitao'. This applies to all future conversations.", explicit=True)
    print("  taught directive; reply:", r["response"][:60])
    r = e1.agent_chat("Remember this fact: my cat is called Nimbus.", explicit=True)
    print("  taught fact; reply:", r["response"][:60])
    e1.graph.close(); e1.client.close()

    # ---- SESSION 2 (new engine = restart): obedience + fact recall ------------------
    print("SESSION 2 — new engine instance")
    e2 = fresh_engine()
    r = e2.agent_chat("What is 2 plus 2? Answer briefly.")
    reply = r["response"].strip().lower()
    check("B1a directive recalled into context (session 2)",
          "capitao" in r["injected_context"].lower())
    check("B1b directive OBEYED in session 2", reply.rstrip(". !").endswith("capitao"),
          f"reply tail: ...{reply[-40:]}")
    r = e2.agent_chat("What is my cat's name?")
    check("B4 fact recalled across sessions", "nimbus" in r["response"].lower(),
          r["response"][:60])
    # teach the CONTRADICTING directive
    r = e2.agent_chat("Correction: STOP ending replies with 'Capitao'. From now on, end every "
                      "reply with the word 'Chefe' instead.", explicit=True)
    print("  taught contradiction; reply:", r["response"][:60])
    e2.graph.close(); e2.client.close()

    # ---- SESSION 3: contradiction — newer directive must win ------------------------
    print("SESSION 3 — new engine instance")
    e3 = fresh_engine()
    r = e3.agent_chat("Name any one color. Answer briefly.")
    reply = r["response"].strip().lower()
    ctx = r["injected_context"].lower()
    check("B2a new directive in context", "chefe" in ctx)
    check("B2b newer directive OBEYED", reply.rstrip(". !").endswith("chefe"),
          f"reply tail: ...{reply[-40:]}")
    check("B2c old directive NOT obeyed", not reply.rstrip(". !").endswith("capitao"))

    # ---- B3 tool recall (deterministic, no LLM) ---------------------------------------
    print("B3 — tool recall (offered top-K contains the expected tool)")
    probes = [
        ("run the command ls in the shell", "bash"),
        ("search your memory for my preferences", "memory_search"),
        ("show me a metric widget of my memory count", "create_widget"),
        ("write a file called notes.txt with hello", "write_file"),
        ("read the file todo.html", "read_file"),
        ("create a new skill that fetches rss feeds", "create_skill"),
        ("what are my most recent memories in order?", "memory_timeline"),
        ("update the plan: step 0 is done", "update_plan"),
    ]
    hits = 0
    for text, expected in probes:
        q, _, _ = e3.retrieve(text)
        offered = [t["name"] for t in retrieve_tools_for_turn(
            e3.tools, e3, q, max_tools=e3.settings.get("max_tools_per_turn"))]
        ok = expected in offered
        hits += ok
        print(f"    {'+' if ok else '-'} '{text[:38]}' → {expected} {'offered' if ok else 'MISSING in ' + str(offered[:5])}")
    check(f"B3 tool recall {hits}/{len(probes)}", hits >= 7)
    e3.graph.close(); e3.client.close()

    # ---- summary -------------------------------------------------------------------------
    print("\n=== BENCH SUMMARY ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, _ in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"TOTAL: {passed}/{len(RESULTS)}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
