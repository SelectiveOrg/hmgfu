"""Cross-SESSION recall matrix (real gemma, throwaway db). User's test: tell the agent something
in one session, "close" it, open a DIFFERENT session, ask a related question -> does it recall?
Run across every user-authorable node CLASS the recall path serves, so we prove recall works for
all of them, not just identity.

  TELL  -> session "alpha", explicit user statements, one fact per turn.
  ASK   -> session "beta" (a DIFFERENT session_id = the "reopened" session), related question.
  PASS  -> the stored token appears in beta's answer, drawn from the persistent global graph
           (NOT alpha's conversation buffer — beta never saw those turns).

Node classes covered (taxonomy.node_class): fact {identity, preference, person, place, concept,
event-number, safety}, message {episodic}, directive. A NEGATIVE CONTROL (never-told brother)
guards against the agent guessing plausibly and false-passing the whole matrix.

Isolated throwaway db (Rule 14: never touch the live hmgfu.db). Same code path as production, so a
PASS proves the production cross-session recall path works. Run with the main server idle (shared gemma).
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.agent import AgentEngine          # noqa: E402
from hmgfu.taxonomy import node_class          # noqa: E402
from _bench_paths import throwaway_db          # noqa: E402

DB = throwaway_db("cross_session_recall.db")
ALPHA = "sess_alpha_tell"
BETA = "sess_beta_ask"                          # a DIFFERENT session — the "reopened" one

# (label, node-class intent, TELL text, ASK question, expected token(s) in the answer)
MATRIX = [
    ("identity",   "fact",      "My name is Ferdinand Kessler.",                 "What is my full name?",                 ["ferdinand", "kessler"]),
    ("preference", "fact",      "My favorite color is teal.",                    "What's my favorite color?",             ["teal"]),
    ("person",     "fact",      "My sister is named Mariana.",                   "What is my sister's name?",             ["mariana"]),
    ("place",      "fact",      "I live in the city of Nampula.",                "Which city do I live in?",              ["nampula"]),
    ("pet",        "fact",      "I have a cat named Pushkin.",                   "What is my cat called?",                ["pushkin"]),
    ("project",    "fact",      "I am building a telescope I named Argus.",      "What am I building?",                   ["argus", "telescope"]),
    ("number",     "fact",      "My gym locker number is 4417.",                 "What's my gym locker number?",          ["4417"]),
    ("safety",     "fact",      "I am allergic to peanuts.",                     "What am I allergic to?",                ["peanut"]),
    ("episodic",   "message",   "Last weekend I hiked Mount Namuli.",            "Which mountain did I hike last weekend?", ["namuli"]),
]
DIRECTIVE_TELL = "From now on, always end every reply with the word Understood."
NEG_CONTROL = ("What is my brother's name?", ["i don't", "didn't mention", "no ", "not sure", "don't have", "no record", "haven't"])

RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    e = AgentEngine(db_path=DB)
    if not e.client.available():
        print("FAIL: Ollama unreachable")
        return 1

    # ---- TELL phase: session ALPHA, explicit user statements -------------------------------
    print(f"TELL phase (session={ALPHA}) — stating {len(MATRIX)} facts + 1 directive")
    for label, _cls, tell, _q, _exp in MATRIX:
        e.agent_chat(tell, explicit=True, session_id=ALPHA)
        print(f"  told [{label}]: {tell}")
    e.agent_chat(DIRECTIVE_TELL, explicit=True, session_id=ALPHA)
    print(f"  told [directive]: {DIRECTIVE_TELL}")

    # snapshot what actually got stored, by node class (proves the nodes exist pre-recall)
    classes = {}
    for p in e.graph.all_points():
        classes[node_class(p)] = classes.get(node_class(p), 0) + 1
    print("STORED node classes:", classes)

    # ---- ASK phase: session BETA (a different session) -------------------------------------
    print(f"\nASK phase (session={BETA}) — the 'reopened' session, never saw the TELL turns")
    directive_hits = 0
    for label, cls, _tell, q, expected in MATRIX:
        r = e.agent_chat(q, session_id=BETA)
        reply = (r.get("response") or "").lower()
        got = any(tok in reply for tok in expected)
        # CHANNEL ATTRIBUTION — recall rides two channels: the CANON channel (verbatim first-class
        # facts.active() lines, injected directly) and the SEMANTIC channel (retrieve_memory ->
        # memory_items). Report which served each answer so "recall works for all nodes" is proven
        # per-channel, not just by the final wording.
        canon_vals = " ".join((f.get("value") or "") + " " + (f.get("verbatim") or "")
                              for f in e.facts.active()).lower()
        via_canon = any(tok in canon_vals for tok in expected)
        via_sem = sorted({node_class(e.graph.points[m["id"]])
                          for m in (r.get("memory_items") or []) if m.get("id") in e.graph.points})
        chan = ("canon " if via_canon else "") + (f"semantic{via_sem} " if via_sem else "")
        check(f"{label:10s} [{cls}]", got, f"via={chan.strip() or 'NONE?'} | {reply[:80]}")
        if "understood" in reply:
            directive_hits += 1

    # ---- directive: carried cross-session? (beta never heard the directive) ----------------
    check("directive  [directive]", directive_hits >= max(1, len(MATRIX) // 2),
          f"replies ending-in/containing 'understood': {directive_hits}/{len(MATRIX)}")

    # ---- negative control: the agent must NOT fabricate an untold fact ---------------------
    # PASS = acknowledges it doesn't know AND invents no concrete brother name. The agent may
    # legitimately mention the KNOWN sister while refusing the unknown brother ("I don't have a
    # brother on record, but your sister is Mariana") — so we check for a fabricated brother NAME
    # ("your brother is X" / "brother's name is X"), not the mere presence of any other name.
    q, refuse_cues = NEG_CONTROL
    r = e.agent_chat(q, session_id=BETA)
    reply = (r.get("response") or "").lower()
    fabricated = re.search(r"brother(?:'s)?(?:\s+name)?\s+is\s+([a-z]+)", reply)
    refused = any(c in reply for c in refuse_cues) and not fabricated
    check("neg-control (no fabrication)", refused,
          (f"FABRICATED brother={fabricated.group(1)} | " if fabricated else "") + reply[:100])

    e.graph.close(); e.client.close()

    print("\n=== CROSS-SESSION RECALL SUMMARY ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for label, ok, _ in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print(f"TOTAL: {passed}/{len(RESULTS)}")
    return 0 if passed == len(RESULTS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
