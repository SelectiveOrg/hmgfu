"""Phase 75.3 — calibrated abstention on LongMemEval (local oracle) with a PRE-REGISTERED dev/test split.

Items: the 30 abstention questions (`question_id` ends in `_abs`: the answer is NOT in the sessions) and the 72
knowledge-update questions (answerable). Split: parity of the first hex digit of md5(question_id) — even → dev,
odd → test — fixed in ROADMAP 75.3 before any number.

Phase 1 (deterministic, no reader): every item's sessions are ingested into a fresh throwaway engine (nano OFF, the
E.2 harness functions reused), the question goes through PRODUCTION retrieval (`engine.retrieve`), and the evidence
strength e(q) is `abstention.evidence_strength` (max cosine of the question to a recalled memory; 1.0 on a ledger hit
for a user-fact question). On DEV the floor maximising abstention F1 (predict-abstain iff e < floor) is chosen; on
TEST it is reported (F1, precision, recall, false-abstention rate on the KU items). Controls (all answerable, must NOT
abstain): the truth set's 17 queries on a clone of the live DB and the relational set's 60 questions on arm F.
Phase 2 (`--answer`): the reader (E.2 prompt and judge, unchanged) answers the TEST items from the production context
WITHOUT (base) and WITH (gate) the abstention line — accuracy per category, paired.
Gate (ROADMAP 75.3): test F1 ≥ 0.8; false abstention ≤ 1/77 on the controls; truth 17/17 held.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import guard_scratch, throwaway_db, write_versioned  # noqa: E402
from bench_longmemeval_e2 import DATA, answer, ingest_turns, judge, session_turns  # noqa: E402
from hmgfu.abstention import abstention_line, coverage_strength, evidence_strength  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.retrieve import build_llm_context, user_fact_question  # noqa: E402

FLOORS = [round(0.30 + 0.02 * i, 2) for i in range(26)]        # 0.30 … 0.80 (cosine)
COVERAGE_FLOORS = [round(0.1 * i, 1) for i in range(1, 11)]      # 0.1 … 1.0 (coverage share)


def split_of(qid: str) -> str:
    return "dev" if int(hashlib.md5(qid.encode("utf-8")).hexdigest()[0], 16) % 2 == 0 else "test"


def fresh_engine(name: str) -> AgentEngine:
    db = throwaway_db(name)
    if os.path.exists(db):
        os.remove(db)
    guard_scratch(db)
    e = AgentEngine(db_path=db)
    e.sensitizer.enabled = False
    for k, v in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                 "runbooks_enabled": False, "prospective_enabled": False}.items():
        e.settings.set(k, v)
    return e


SIGNAL = "cosine"          # --signal cosine | coverage  (75.3b: the second, pre-registered signal)


def item_evidence(e: AgentEngine, question: str) -> tuple:
    q, retrieved, _ms = e.retrieve(question, limit=e.settings.get("retrieval_limit"))
    ledger = user_fact_question(q, e.facts) and bool(e.facts.render_lines())
    if SIGNAL == "claim":                                       # 77.4: the ANSWER's unsupported share (higher = abstain)
        from hmgfu.grounding import unsupported_share
        canonical = e.facts.render_lines()
        ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved, token_budget=e.settings.get("token_budget"),
                                   canonical=canonical, superseded=e.facts.superseded_values(),
                                   reverted=e.facts.reverted_values(), echo_free=False,
                                   excerpt_chars=e.settings.get("excerpt_max_chars"), echo_scope=e.settings.get("echo_guard_scope"),
                                   echo_pairs=e.facts.active_pairs())
        reply = answer(e, question, ctx)
        u = unsupported_share(reply, question, [ctx])
        return 1.0 - u, q, retrieved                            # keep the convention "low evidence → abstain"
    if SIGNAL == "coverage":
        return coverage_strength(question, retrieved, e.facts.render_lines()), q, retrieved
    return evidence_strength(q, retrieved, ledger_hit=ledger), q, retrieved


def f1_at(rows: list, floor: float) -> dict:
    tp = sum(1 for r in rows if r["abstain"] and r["evidence"] < floor)
    fp = sum(1 for r in rows if not r["abstain"] and r["evidence"] < floor)
    fn = sum(1 for r in rows if r["abstain"] and r["evidence"] >= floor)
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0.0, "precision": round(p, 3), "recall": round(rc, 3),
            "false_abstain": fp, "n_answerable": sum(1 for r in rows if not r["abstain"])}


def controls_evidence() -> dict:
    """Must-not-abstain controls: truth-set queries on a live clone; relational questions on arm F."""
    out = {"truth": [], "relational": []}
    from bench_recall_truth import clone_live
    clone = throwaway_db("bench_abstention_truth_clone.db")
    clone_live(clone)
    guard_scratch(clone)
    e = AgentEngine(db_path=clone)
    e.sensitizer.enabled = False
    e.settings.set("tail_async", False); e.settings.set("grader_enabled", False)
    cases = json.load(open(os.path.join(ROOT, "scripts", "truth_set.json"), encoding="utf-8"))["cases"]
    for c in cases:
        for qtext in c["queries"]:
            ev, _, _ = item_evidence(e, qtext)
            out["truth"].append({"id": c["id"], "text": qtext, "evidence": round(ev, 3)})
    e.graph.close()
    import bench_relational as br
    corpus = json.load(open(br.SET, encoding="utf-8"))
    e, _, _ = br.build_engine("abst_ctl", corpus)
    for qd in corpus["questions"]:
        ev, _, _ = item_evidence(e, qd["text"])
        out["relational"].append({"id": qd["id"], "text": qd["text"], "evidence": round(ev, 3)})
    e.graph.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer", action="store_true", help="phase 2: reader base vs gate on the TEST items")
    ap.add_argument("--floor", type=float, default=None, help="phase 2: the floor to use (default: the dev-chosen one from phase 1)")
    ap.add_argument("--limit", type=int, default=0, help="debug: cap items per category")
    ap.add_argument("--signal", default="cosine", choices=("cosine", "coverage", "claim"),
                    help="75.3b/77.4: cosine | coverage (question-side) | claim (answer-side: the reader's reply vs the context)")
    args = ap.parse_args()
    global SIGNAL
    SIGNAL = args.signal
    data = json.load(open(DATA, encoding="utf-8"))
    items = [i for i in data if str(i.get("question_id", "")).endswith("_abs") or i["question_type"] == "knowledge-update"]
    if args.limit:
        items = [i for i in items if str(i.get("question_id", "")).endswith("_abs")][:args.limit] + \
                [i for i in items if not str(i.get("question_id", "")).endswith("_abs")][:args.limit]
    t0 = time.time()
    rows = []
    for n, it in enumerate(items, 1):
        qid = str(it["question_id"]); abst = qid.endswith("_abs")
        e = fresh_engine(f"bench_abstention_{n}.db")
        ingest_turns(e, session_turns(it))
        ev, q, retrieved = item_evidence(e, it["question"])
        row = {"qid": qid, "abstain": abst, "split": split_of(qid), "evidence": round(ev, 3), "n_retrieved": len(retrieved),
               "question": it["question"][:160], "gold": str(it.get("answer", ""))[:160]}
        if args.answer and row["split"] == "test":
            canonical = e.facts.render_lines()
            ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved, token_budget=e.settings.get("token_budget"),
                                       canonical=canonical, superseded=e.facts.superseded_values(),
                                       reverted=e.facts.reverted_values(), echo_free=False)
            if args.floor is None:
                raise SystemExit("--answer needs --floor <dev-chosen floor from phase 1>")
            floor = args.floor
            line = abstention_line(ev, floor)
            out_base = answer(e, it["question"], ctx)
            out_gate = answer(e, it["question"], (line + "\n" + ctx) if line else ctx)
            row.update({"base_ok": bool(judge(out_base, row["gold"], abst)), "gate_ok": bool(judge(out_gate, row["gold"], abst)),
                        "gated": bool(line), "base_reply": out_base[:160], "gate_reply": out_gate[:160]})
        e.graph.close()
        rows.append(row)
        if n % 10 == 0:
            print(f"   {n}/{len(items)} items ({round(time.time() - t0)}s)")
    dev = [r for r in rows if r["split"] == "dev"]; test = [r for r in rows if r["split"] == "test"]
    floors = COVERAGE_FLOORS if SIGNAL in ("coverage", "claim") else FLOORS
    sweep = {str(f): f1_at(dev, f) for f in floors}
    best = max(floors, key=lambda f: (sweep[str(f)]["f1"], -sweep[str(f)]["false_abstain"]))
    on_test = f1_at(test, best)
    ctl = controls_evidence()
    ctl_false = {k: sum(1 for r in v if r["evidence"] < best) for k, v in ctl.items()}
    summary = {"signal": SIGNAL, "n_items": len(rows), "n_dev": len(dev), "n_test": len(test), "floor": best, "dev": sweep[str(best)], "test": on_test,
               "dev_sweep": sweep, "controls_false_abstain": ctl_false,
               "controls_n": {k: len(v) for k, v in ctl.items()},
               "controls_min_evidence": {k: min((r["evidence"] for r in v), default=None) for k, v in ctl.items()},
               "evidence_abstain_median": round(statistics.median(r["evidence"] for r in rows if r["abstain"]), 3),
               "evidence_answerable_median": round(statistics.median(r["evidence"] for r in rows if not r["abstain"]), 3),
               "elapsed_s": round(time.time() - t0, 1)}
    if args.answer:
        for arm in ("base", "gate"):
            for cat, flag in (("abstention", True), ("knowledge-update", False)):
                sel = [r for r in test if r["abstain"] == flag and f"{arm}_ok" in r]
                summary[f"{arm}_{cat}"] = round(sum(r[f"{arm}_ok"] for r in sel) / len(sel), 3) if sel else None
        summary["gated_test_items"] = sum(1 for r in test if r.get("gated"))
    print(f"[abstention:{SIGNAL}] floor (dev) {best} · dev F1 {summary['dev']['f1']} · TEST F1 {on_test['f1']} (P {on_test['precision']} · R {on_test['recall']}) · "
          f"false abstention on KU test {on_test['false_abstain']}/{on_test['n_answerable']} · controls false: {ctl_false} (n {summary['controls_n']}) · "
          f"median e: abstain {summary['evidence_abstain_median']} vs answerable {summary['evidence_answerable_median']} · {summary['elapsed_s']}s")
    if args.answer:
        print("LLM leg (test):", {k: v for k, v in summary.items() if k.startswith(("base_", "gate_", "gated"))})
    print("versioned:", write_versioned("abstention", {"summary": summary, "rows": rows, "controls": ctl}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
