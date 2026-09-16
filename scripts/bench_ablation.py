"""Phase 30.4: ablation — claim "the hard-won reliability came largely from the deterministic
layers (canonical facts, keyed directives, hygiene, dedup) on top of the Fu substrate ... the
field gives associative recall and explainability; the canon layers give guarantees."

Runs the IDENTICAL scenarios (fact correction, standing-directive obedience, directive
contradiction) through two engines on the same real gemma:
  SUBSTRATE = chat.HMGFuEngine   — pure Fu math: embeddings, kappa, density, recency, tension.
              NO facts.py, NO directives.py, NO hygiene.py, NO dedup-on-ingest reinforcement
              beyond ingest.py's own dedup (that one IS substrate-level, left in for both).
  CANON     = agent.AgentEngine  — substrate + FactStore + DirectiveStore + hygiene.

Each "session" is a fresh engine instance over the same db (server-restart equivalent).

Run: .venv/Scripts/python scripts/bench_ablation.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.chat import HMGFuEngine  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402
RESULTS = []


def check(condition_label: str, name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((condition_label, name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def run_fact_correction(condition_label: str, make_engine) -> None:
    print(f"\n-- {condition_label}: fact correction (Sebastian -> Teodoro) --")
    db = throwaway_db(f"ablation_{condition_label}_facts.db")
    if os.path.exists(db):
        os.remove(db)
    e1 = make_engine(db)
    if condition_label == "SUBSTRATE":
        e1.chat("My name is Sebastian.", explicit=True)
    else:
        e1.agent_chat("My name is Sebastian.", explicit=True)
    e1.graph.close()

    e2 = make_engine(db)
    if condition_label == "SUBSTRATE":
        e2.chat("Correction: I'm not Sebastian. My name is Teodoro Ferreira.", explicit=True)
        r = e2.chat("What is my name?")
    else:
        e2.agent_chat("Correction: I'm not Sebastian. My name is Teodoro Ferreira.", explicit=True)
        r = e2.agent_chat("What is my name?")
    reply = r["response"].lower()
    check(condition_label, "fact correction: names ONLY Teodoro (not Sebastian)",
          "teodoro" in reply and "sebastian" not in reply, reply[:150])
    e2.graph.close()
    try:
        os.remove(db)
    except PermissionError:
        pass


def run_directive_obedience(condition_label: str, make_engine) -> None:
    print(f"\n-- {condition_label}: standing directive obedience across sessions --")
    db = throwaway_db(f"ablation_{condition_label}_dir.db")
    if os.path.exists(db):
        os.remove(db)
    e1 = make_engine(db)
    teach = ("Standing directive: always end every one of your replies with the word "
            "'Capitao'. This applies to all future conversations.")
    if condition_label == "SUBSTRATE":
        e1.chat(teach, explicit=True)
    else:
        e1.agent_chat(teach, explicit=True)
    e1.graph.close()

    e2 = make_engine(db)
    if condition_label == "SUBSTRATE":
        r = e2.chat("What is 2 plus 2? Answer briefly.")
    else:
        r = e2.agent_chat("What is 2 plus 2? Answer briefly.")
    reply = r["response"].strip().lower()
    check(condition_label, "directive OBEYED in a later session (fresh engine)",
          reply.rstrip(". !").endswith("capitao"), f"reply tail: ...{reply[-40:]}")

    # contradiction: newer directive must win
    contradiction = ("Correction: STOP ending replies with 'Capitao'. From now on, end every "
                     "reply with the word 'Chefe' instead.")
    if condition_label == "SUBSTRATE":
        e2.chat(contradiction, explicit=True)
    else:
        e2.agent_chat(contradiction, explicit=True)
    e2.graph.close()

    e3 = make_engine(db)
    if condition_label == "SUBSTRATE":
        r = e3.chat("Name any one color. Answer briefly.")
    else:
        r = e3.agent_chat("Name any one color. Answer briefly.")
    reply = r["response"].strip().lower()
    check(condition_label, "NEWER directive (Chefe) obeyed, OLD (Capitao) dropped",
          reply.rstrip(". !").endswith("chefe") and not reply.rstrip(". !").endswith("capitao"),
          f"reply tail: ...{reply[-40:]}")
    e3.graph.close()
    try:
        os.remove(db)
    except PermissionError:
        pass


def main() -> int:
    probe = HMGFuEngine(db_path=throwaway_db("ablation_probe.db"))
    available = probe.client.available()
    probe.graph.close()
    os.remove(throwaway_db("ablation_probe.db"))
    if not available:
        print("FAIL: Ollama unreachable")
        return 1

    conditions = [
        ("SUBSTRATE", lambda db: HMGFuEngine(db_path=db)),
        ("CANON", lambda db: AgentEngine(db_path=db)),
    ]
    for label, factory in conditions:
        run_fact_correction(label, factory)
        run_directive_obedience(label, factory)

    print("\n=== ABLATION SUMMARY ===")
    by_condition = {}
    for label, name, ok, _ in RESULTS:
        by_condition.setdefault(label, []).append(ok)
        print(f"  [{label:^10}] {'PASS' if ok else 'FAIL'}  {name}")
    for label, oks in by_condition.items():
        print(f"  {label}: {sum(oks)}/{len(oks)}")
    substrate_rate = sum(by_condition.get("SUBSTRATE", [])) / max(1, len(by_condition.get("SUBSTRATE", [])))
    canon_rate = sum(by_condition.get("CANON", [])) / max(1, len(by_condition.get("CANON", [])))
    print(f"\nSUBSTRATE-only pass rate: {substrate_rate*100:.0f}%   CANON (substrate+facts+directives) "
          f"pass rate: {canon_rate*100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
