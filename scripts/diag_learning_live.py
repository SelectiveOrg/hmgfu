"""Phase 92.E4 — does the whole cycle work on the real model, end to end?

Teach a definition in one session, then ask for it in a NEW session, on a THROWAWAY synthetic base.
Reports, per turn, what the router actually emitted, what the controller decided, what was written,
and what the receipt said -- so a failure can be attributed to the router, the contract, the store or
the reader, rather than blamed on "the model".

The term and value are invented for this diagnostic and appear nowhere in the real memory.

    python scripts/diag_learning_live.py [--mode confirm|adapt|off]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.learning_state import read_definition  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

TERM, MEANING = "ACME-7", "Atlas Control Mesh"
TEACH = [
    f"In this project, {TERM} means {MEANING}.",
    "By the way, the rain here has been relentless all week.",
]
ASK = f"what does {TERM} stand for?"


def _find_definition(assertions, term):
    """Whatever context the model chose, find the definition entity for this term."""
    from hmgfu.learning_state import DEFINITION_RELATION
    out = []
    for a in assertions.active():
        if a.get("relation") == DEFINITION_RELATION:
            out.append({"value": a.get("value"), "entity_id": a.get("entity_id")})
    return out


def main() -> int:
    mode = "confirm"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    os.makedirs(SCRATCH, exist_ok=True)
    db = os.path.join(SCRATCH, f"learn_live_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    import sqlite3
    sqlite3.connect(db).close()      # a valid empty base; NEVER clone_live(None), which copies REAL memory
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", mode)
    print(f"mode = {e.settings.get('interactive_learning_mode')}\n")

    # instrument the entry itself: what the router emitted, what was decided, what was written
    import hmgfu.learning_state as ls
    seen = []
    original = ls.run_learning_turn

    def spy(engine, session_id, text, query, **kw):
        env = (getattr(query, "extraction", None) or {}).get("memory_update")
        out = original(engine, session_id, text, query, **kw)
        seen.append({"text": text[:70], "envelope": env,
                     "action": (out or {}).get("decision", {}).get("action"),
                     "reason": (out or {}).get("decision", {}).get("reason"),
                     "effects": (out or {}).get("effects"), "receipt": (out or {}).get("receipt")})
        return out

    ls.run_learning_turn = spy
    import hmgfu.agent  # the agent imports the symbol at call time, so the patch is seen
    rows = []
    # both sessions are created BEFORE any turn: creating one mid-run hits a write lock held by
    # the turn tail, and that is a property of this harness, not of the protocol (it reproduces
    # identically with the mode off).
    sid = sd.new_session(e, "teach")
    for msg in TEACH:
        r = sd.turn(e, sid, msg)
        wait_for_tail(e)
        got = seen[-1] if seen else {}
        rows.append({"turn": msg, **got, "reply": (r.get("response") or "")[:160], "secs": r.get("_secs")})
        print(f"[teach] {msg[:60]}")
        print(f"   envelope : {json.dumps(got.get('envelope'), ensure_ascii=False)[:260] if got.get('envelope') else 'NONE'}")
        print(f"   decision : {got.get('action')} - {str(got.get('reason'))[:90]}")
        print(f"   effects  : {json.dumps(got.get('effects'), ensure_ascii=False)[:160]}")
        print(f"   reply    : {(r.get('response') or '')[:110]}")

    stored = _find_definition(e.facts.assertions, TERM)
    print(f"\nstored definition: {stored}")

    # a genuinely NEW session: a second engine on the same file, as a later process would be
    e2 = sd.fresh_engine(db, None)
    e2.settings.set("interactive_learning_mode", mode)
    sid2 = sd.new_session(e2, "ask-in-a-new-session")
    r2 = sd.turn(e2, sid2, ASK)
    wait_for_tail(e2)
    answered = MEANING.casefold() in (r2.get("response") or "").casefold()
    print(f"\n[new session] {ASK}")
    print(f"   reply: {(r2.get('response') or '')[:200]}")
    print(f"   contains the taught meaning: {answered}")
    try:
        e.graph.close()
    except Exception:
        pass
    print("versioned:", write_versioned("learning_live", {"mode": mode, "rows": rows,
                                                          "stored": stored, "answered": answered,
                                                          "final_reply": (r2.get("response") or "")[:600]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
