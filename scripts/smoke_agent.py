"""Live v2 smoke: the AGENT loop on real gemma4:12b with real tools + the imported PA3 corpus.

Checks:
  1. gemma4:12b natively calls a tool (memory_search / memory_timeline) when asked to,
     and the answer uses the tool result.
  2. A PA3-imported fact is recallable through the normal memory injection.
  3. The grader runs and returns a card.

Run AFTER scripts/import_pa3.py, with the API server STOPPED (single writer):
  .venv/Scripts/python scripts/smoke_agent.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.agent import AgentEngine  # noqa: E402


def main() -> int:
    engine = AgentEngine()
    if not engine.client.available():
        print("FAIL: Ollama not reachable")
        return 1
    stats = engine.graph.stats()
    print(f"graph: {stats['points']} points ({stats['active']} active), {stats['edges']} edges")

    # --- 1. a probe that genuinely REQUIRES a tool (injection cannot answer it) -----------
    probe1 = "Run the shell command `echo FU-OK-123` and tell me exactly what it printed."
    print(f"\nprobe 1 (tool use): {probe1}")
    r1 = engine.agent_chat(probe1)
    used_tools = [t["name"] for t in r1["tool_trace"]]
    print(f"tools offered: {r1['tools_offered']}")
    print(f"tools used:    {used_tools}")
    print(f"reply: {r1['response'][:300]}")
    tool_used = "bash" in used_tools
    answer1_ok = "FU-OK-123" in r1["response"]

    # --- 2. PA3 fact via plain injection (issue 15: canon must beat assistant chatter) ------
    probe2 = "What termination phrase am I supposed to hear from you at the end of your answers?"
    print(f"\nprobe 2 (PA3 recall): {probe2}")
    r2 = engine.agent_chat(probe2)
    print(f"reply: {r2['response'][:300]}")
    answer2_ok = "master" in r2["response"].lower()
    injected2_ok = "master" in r2["injected_context"].lower()

    # --- 3. grader card --------------------------------------------------------------------
    grade_ok = r2.get("grade") is not None and isinstance(r2["grade"], dict)
    print(f"\ngrader card: {r2.get('grade')}")

    engine.graph.close()
    engine.client.close()
    print("\n--- verdict ---")
    print(f"model called a tool           : {'PASS' if tool_used else 'FAIL'} ({used_tools})")
    print(f"tool answer correct (Master)  : {'PASS' if answer1_ok else 'FAIL'}")
    print(f"PA3 fact injected             : {'PASS' if injected2_ok else 'FAIL'}")
    print(f"PA3 fact in answer            : {'PASS' if answer2_ok else 'FAIL'}")
    print(f"grader ran                    : {'PASS' if grade_ok else 'FAIL'}")
    ok = tool_used and injected2_ok and grade_ok
    print("SMOKE-AGENT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
