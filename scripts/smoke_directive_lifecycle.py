"""Live proof of the GENERAL directive lifecycle (Phase 55) on real gemma4:12b + nano.

Drives the FULL pipeline (the live router classifies each natural-language message → DirectiveStore)
to prove the SYSTEM can make the LLM FOLLOW a standing directive, CHANGE its content (joke -> fact),
and CLEAR it — for ARBITRARY content, in English and Portuguese. Nothing here is joke-specific.

The DirectiveStore transitions are the hard PASS/FAIL (they prove the system learned / changed /
cleared purely from natural language — the multilingual part). The replies are printed so a human
can see the model actually following the directive.

Run:  .venv/Scripts/python scripts/smoke_directive_lifecycle.py
Uses a throwaway DB — it NEVER touches production hmgfu.db.
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.agent import AgentEngine  # noqa: E402  (the directive-aware engine)
from _bench_paths import throwaway_db  # noqa: E402

DB = throwaway_db("smoke_directive_lifecycle.db")


def _closer(engine):
    return next((d for d in engine.directives.active()
                 if d["kind"] == "conversation_closer"), None)


def _set_closer(engine, msg, want_substr=None, changed_from=None, tries=2):
    """Send an NL directive; retry a couple times to absorb the router's ~1-in-4 non-determinism.
    `changed_from` requires the stored value to actually differ (proves a CHANGE, not a no-op)."""
    for attempt in range(1, tries + 1):
        engine.agent_chat(msg)
        d = _closer(engine)
        if d and (want_substr is None or want_substr in d["value"].lower()) \
                and (changed_from is None or d["value"] != changed_from):
            return d, attempt
    return _closer(engine), tries


def _clear_closer(engine, msg, tries=2):
    for attempt in range(1, tries + 1):
        engine.agent_chat(msg)
        if _closer(engine) is None:
            return True, attempt
    return False, tries


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    engine = AgentEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama is not reachable")
        return 1

    results = []

    def stage(label, ok, detail=""):
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))

    # ================= EN: FOLLOW -> CHANGE -> CLEAR =================
    print("\n=== EN lifecycle: FOLLOW -> CHANGE -> CLEAR ===")
    d, n = _set_closer(engine, "From now on, end every reply with a short joke.", "joke")
    stage("FOLLOW: a joke closer is learned from NL", d is not None,
          f"value={d['value'] if d else None}, tries={n}")
    r = engine.agent_chat("What is two plus two?")
    print(f"      reply> ...{r['response'][-160:]!r}")

    before = d["value"] if d else None
    d, n = _set_closer(engine, "Actually, end every reply with a curious science fact instead.",
                       "fact")
    n_closers = len([x for x in engine.directives.active() if x["kind"] == "conversation_closer"])
    stage("CHANGE: joke -> fact, superseded to exactly ONE row",
          d is not None and n_closers == 1 and (d["value"] != before),
          f"{before!r} -> {d['value'] if d else None}, rows={n_closers}, tries={n}")
    r = engine.agent_chat("What is the capital of France?")
    print(f"      reply> ...{r['response'][-160:]!r}")

    cleared, n = _clear_closer(engine, "Stop adding anything at the end of your replies.")
    stage("CLEAR: the closer is removed from NL", cleared, f"tries={n}")
    r = engine.agent_chat("Say hello.")
    print(f"      reply> ...{r['response'][-160:]!r}")

    # ================= PT: SEGUIR -> MUDAR -> LIMPAR (multilingual) =================
    print("\n=== PT lifecycle: SEGUIR -> MUDAR -> LIMPAR ===")
    d, n = _set_closer(engine, "A partir de agora, termine cada resposta com uma piada curta.")
    stage("SEGUIR: a closer is learned from a Portuguese instruction", d is not None,
          f"value={d['value'] if d else None}, tries={n}")
    r = engine.agent_chat("Quanto e dois mais dois?")
    print(f"      reply> ...{r['response'][-160:]!r}")

    before = d["value"] if d else None
    d, n = _set_closer(engine, "Na verdade, termine cada resposta com uma curiosidade cientifica.",
                       changed_from=before)
    stage("MUDAR: the closer content changes (piada -> curiosidade)",
          d is not None and d["value"] != before,
          f"{before!r} -> {d['value'] if d else None}, tries={n}")
    r = engine.agent_chat("Qual e a capital de Portugal?")
    print(f"      reply> ...{r['response'][-160:]!r}")

    cleared, n = _clear_closer(engine, "Pare de adicionar qualquer coisa no final das respostas.")
    stage("LIMPAR: the closer is removed from a Portuguese instruction", cleared, f"tries={n}")

    engine.graph.close()
    engine.client.close()

    passed = sum(results)
    print(f"\nLIFECYCLE: {passed}/{len(results)} stages passed")
    print("SMOKE:", "PASS" if passed == len(results) else "FAIL")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
