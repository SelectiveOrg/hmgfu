"""Phase 62 — TRUTH bench: does the memory system present the user's CURRENT facts, and only them?

Ground truth = `scripts/truth_set.json` (the user's own latest statements, with provenance).
Runs on an online-backup CLONE of the live DB (production is never written). Two modes:

  --retrieval   (default) real embedder, no chat model: for every query, build the exact context the
                agent would inject and check it contains a truth value and NO stale value.
  --answer      additionally run the full agent turn (gemma4) and check the visible reply.

Every memory change in Phase 62+ is gated on this bench (Rule 12). Usage:
  .venv/Scripts/python scripts/bench_recall_truth.py [--answer] [--db PATH] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hmgfu import config  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.retrieve import build_llm_context  # noqa: E402
from hmgfu.taxonomy import is_user_grounded  # noqa: E402

from _bench_paths import guard_scratch, throwaway_db, write_versioned  # noqa: E402

TRUTH = os.path.join(ROOT, "scripts", "truth_set.json")     # PRIVATE (gitignored); see truth_set.example.json
NO_CANON = False   # --no-canon: ablation — score the graph retrieval alone, without the canonical ledger lines
NO_ECHO = False    # --no-echo (73.3, M6): assistant/dream-authored memories excluded from the answer context



# 80.3: --set key=value (repeatable) → applied to the clone's settings after the engine is built (same helper as the other benches)
EXTRA_SETTINGS: dict = {}


def apply_extra_settings(engine) -> None:
    for key, raw in EXTRA_SETTINGS.items():
        cur = engine.settings.get(key)
        if isinstance(cur, bool):
            val = str(raw).strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, int):
            val = int(raw)
        elif isinstance(cur, float):
            val = float(raw)
        else:
            val = raw
        engine.settings.set(key, val)


def parse_set_args(items) -> None:
    for item in items or []:
        key, _, val = item.partition("=")
        EXTRA_SETTINGS[key.strip()] = val.strip()

def clone_live(dst: str, src: str | None = None) -> None:
    if os.path.exists(dst):
        os.remove(dst)
    source = sqlite3.connect(src or config.DB_PATH)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


# 69.7: a hit counts only when the CLAUSE holding it asserts it now — negation, past tense or uncertainty anywhere in
# that clause (split on . , ; : and newlines) disqualifies it ("Java was my old preference", "not sure whether Java…")
# Explicit negation / uncertainty: disqualifies the value anywhere in its clause.
_NEGATED = (r"n['’]t\b|^\s*(?:no|n[aã]o)\b|\bno\s+(?:longer|more|idea)\b|\bn[aã]o\s+(?:é|e|era|foi|mais|sei)\b|\bjá\s+n[aã]o\b|"
            r"\b(?:not|never|nunca|don'?t know|do not know|not sure|unsure|whether|maybe|perhaps|might|talvez)\b")
# Historical marker: disqualifies the value only when ADJACENT to it (≤ 1 word between) — "Java was old", "used to be Java",
# "the previous colour amber". 74.4: clause-wide it rejected correct answers — "the OLD spreadsheet kept breaking" for a
# project question, "you WERE working on Atlas" for a past-tense one — in both arms alike.
_HIST = r"(?:was|were|formerly|used\s+to(?:\s+be)?|before|old|previous(?:ly)?|former|antes|antigamente|era|foi)"
_W = r"(?:\s+\S+)?\s+"                       # at most one intervening word


def _present(text: str, needles: list) -> list:
    """Whole-word match; a hit does not count when the value sits in a negated/uncertain clause ('not Java', 'unsure
    whether Java') or right beside a historical marker ('Java was old', 'used to be Java') — audit finding: lexical truth
    must not accept negation or retraction as success. Historical markers elsewhere in the clause are plain narration."""
    import re
    low = (text or "").lower()
    hits = []
    for n in needles:
        val = r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])"
        hist = re.compile(val + _W + _HIST + r"\b|\b" + _HIST + _W + val)
        # clause = sentence / comma-separated part; dotted values (IPs, URLs, versions) stay intact (69.8)
        for clause in re.split(r"(?<=[.!?;:])\s+|,\s+|\n", low):
            if re.search(val, clause) and not re.search(_NEGATED, clause) and not hist.search(clause):
                hits.append(n)
                break
    return hits


def _carries_stale(point, stale_values: list) -> bool:
    """73.3 (M6): a memory that carries a superseded or reverted value is not CURRENT evidence, whoever wrote it."""
    from hmgfu.slots import value_in_text
    text = f"{point.summary} {point.title} {point.content}"
    return any(value_in_text(v, text) for v in stale_values)


def run(engine: AgentEngine, cases: list, answer: bool) -> dict:
    results, t_all = [], time.time()
    stale_values = [v for _, v in engine.facts.superseded_values() + engine.facts.reverted_values() if v and len(v) >= 4]
    for case in cases:
        for q in case["queries"]:
            t = time.time()
            query, retrieved, ms = engine.retrieve(q, limit=engine.settings.get("retrieval_limit"))
            from hmgfu.retrieve import user_fact_question
            echo_free = NO_ECHO or user_fact_question(query, engine.facts)     # product gate; --no-echo forces it
            # 78: the builder applies the echo guard itself (scope from settings) — one implementation, the gate measures production
            context, _ = build_llm_context(query, engine.graph, retrieved=retrieved,
                                           token_budget=engine.settings.get("token_budget"),
                                           canonical=[] if NO_CANON else engine.facts.render_lines(),
                                           superseded=engine.facts.superseded_values(),
                                           reverted=engine.facts.reverted_values(), echo_free=echo_free,
                                           excerpt_chars=engine.settings.get("excerpt_max_chars"),
                                           echo_scope=engine.settings.get("echo_guard_scope"),
                                           echo_pairs=engine.facts.active_pairs())
            hit = _present(context, case["truth"])
            leak = _present(context, case["stale"])
            # 78.4: precision over the memories the builder KEPT after its echo guard (the 73.3 bench pre-filtered the list itself;
            # now the builder is the one implementation and reports what it left)
            from hmgfu.retrieve import organise_for_injection as _org
            kept_ids = set(_org(retrieved, engine.graph, canonical=[] if NO_CANON else engine.facts.render_lines(),
                                superseded=engine.facts.superseded_values(), reverted=engine.facts.reverted_values(),
                                echo_free=echo_free, query=query, excerpt_chars=engine.settings.get("excerpt_max_chars"),
                                echo_scope=engine.settings.get("echo_guard_scope"),
                                echo_pairs=engine.facts.active_pairs()).get("_kept_ids", []))
            retrieved = [r for r in retrieved if r.point.id in kept_ids]
            grounded = sum(1 for r in retrieved if is_user_grounded(r.point))
            current = sum(1 for r in retrieved if is_user_grounded(r.point) and not _carries_stale(r.point, stale_values))
            row = {"id": case["id"], "slot": case["slot"], "query": q, "context_ok": bool(hit) and not leak,
                   "grounded": grounded, "precision": round(grounded / len(retrieved), 2) if retrieved else None,
                   "grounded_current": current,
                   "precision_current": round(current / len(retrieved), 2) if retrieved else None,
                   "retrieval_ok": bool(hit) and not leak,   # legacy name kept for older JSON readers
                   "ctx_truth": hit, "ctx_stale": leak, "retrieval_ms": round(ms, 1),
                   "n_memories": len(retrieved)}
            if answer:
                r = engine.agent_chat(q)
                reply = r.get("response", "")
                a_hit, a_leak = _present(reply, case["truth"]), _present(reply, case["stale"])
                row.update({"answer_ok": bool(a_hit) and not a_leak, "answer_truth": a_hit,
                            "answer_stale": a_leak, "reply": reply[:200]})
            row["secs"] = round(time.time() - t, 1)
            results.append(row)
            flag = "PASS" if row["retrieval_ok"] else "FAIL"
            extra = f" | answer {'PASS' if row.get('answer_ok') else 'FAIL'}: {row.get('reply', '')[:80]!r}" if answer else ""
            print(f"  [{flag}] {case['id']:12s} {q!r:55s} truth={hit} stale={leak} n={len(retrieved)} "
                  f"grounded={grounded}{extra}")
    n = len(results)
    tot_n = sum(r["n_memories"] for r in results)
    tot_g = sum(r["grounded"] for r in results)
    tot_c = sum(r.get("grounded_current", 0) for r in results)
    summary = {"n": n, "retrieval_pass": sum(r["retrieval_ok"] for r in results),
               "recalled_total": tot_n, "grounded_total": tot_g, "grounded_current_total": tot_c,
               "precision": round(tot_g / tot_n, 3) if tot_n else None,
               "precision_current": round(tot_c / tot_n, 3) if tot_n else None,      # 73.3 (M6): grounded AND current
               "arm": "no_echo" if NO_ECHO else "default",
               "elapsed_s": round(time.time() - t_all, 1)}
    if answer:
        summary["answer_pass"] = sum(bool(r.get("answer_ok")) for r in results)
    return {"summary": summary, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer", action="store_true", help="also run the full agent turn (gemma4)")
    ap.add_argument("--db", default=None, help="source DB to clone (default: live config.DB_PATH)")
    ap.add_argument("--json", default=None, help="write results JSON here")
    ap.add_argument("--only", default=None, help="comma-separated case ids")
    ap.add_argument("--mode", default=None, choices=("fu", "cosine"), help="77.1: retrieval_mode arm on the clone (default: the setting)")
    ap.add_argument("--excerpt", type=int, default=None, help="78: excerpt_max_chars on the clone (default: the setting, 200 = head cut)")
    ap.add_argument("--echo-scope", default=None, choices=("all", "echoes"), help="78: echo_guard_scope on the clone (default: the setting)")
    ap.add_argument("--set", action="append", default=[], help="80.3: key=value applied to the clone settings (repeatable)")
    ap.add_argument("--no-echo", action="store_true",
                    help="73.3 (M6) arm: assistant/dream-authored memories excluded from the answer context")
    ap.add_argument("--no-canon", action="store_true",
                    help="ablation: drop the canonical ledger lines so only graph retrieval is scored (the "
                         "default score is a CONTEXT score: ledger + retrieval, i.e. what the model sees)")
    ap.add_argument("--assistant-factor", type=float, default=None,
                    help="experiment: override SOURCE_SCORE_FACTOR['assistant'] (live 0.85) for this run")
    ap.add_argument("--dormant-chatter", action="store_true",
                    help="experiment: on the CLONE, put content-free assistant chatter to sleep (hygiene predicate) before scoring")
    ap.add_argument("--weights", default="fu", choices=["fu", "lean"],
                    help="ranker profile: 'fu' = config.MEMORY_SCORE_WEIGHTS (live); 'lean' = semantic-dominant, "
                         "no density/utility/kappa (THEORY_V2 A1) — an EXPERIMENT arm, never the live default")
    args = ap.parse_args()
    parse_set_args(args.set)
    global NO_CANON, NO_ECHO
    NO_CANON = args.no_canon
    NO_ECHO = bool(args.no_echo)
    if args.assistant_factor is not None:
        config.SOURCE_SCORE_FACTOR = dict(config.SOURCE_SCORE_FACTOR, assistant=args.assistant_factor)
    if args.weights == "lean":
        config.MEMORY_SCORE_WEIGHTS = {"semantic": 0.78, "kappa": 0.0, "density": 0.0, "utility": 0.0,
                                       "recency": 0.10, "modeMatch": 0.07, "wormholeBoost": 0.0,
                                       "fuDistancePenalty": 0.03, "tensionPenalty": 0.02}

    cases = json.load(open(TRUTH, encoding="utf-8"))["cases"]
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    clone = throwaway_db("bench_truth_clone.db")
    clone_live(clone, args.db)
    guard_scratch(clone)                                      # M0.2
    engine = AgentEngine(db_path=clone)
    apply_extra_settings(engine)                                  # 80.3: candidate configuration on the clone
    if args.mode:
        engine.settings.set("retrieval_mode", args.mode)                # 77.1 arm
    if args.excerpt is not None:
        engine.settings.set("excerpt_max_chars", args.excerpt)          # 78 candidate (clone only)
    if args.echo_scope is not None:
        engine.settings.set("echo_guard_scope", args.echo_scope)        # 78 candidate (clone only)
    if args.dormant_chatter:
        from hmgfu.hygiene import sleep_content_free_chatter
        print("dormant-chatter experiment: put to sleep", sleep_content_free_chatter(engine.graph), "points")
    if not engine.client.available():
        print("FAIL: Ollama unreachable (embedder needed)")
        return 2
    print(f"TRUTH BENCH on clone of {args.db or config.DB_PATH} — {len(engine.graph.active_points())} active points, "
          f"embed={engine.settings.get('embed_model')}, mode={'answer' if args.answer else 'context'}"
          f"{', NO CANON (retrieval-only ablation)' if NO_CANON else ''}")
    out = run(engine, cases, args.answer)
    s = out["summary"]
    line = f"{'RETRIEVAL-ONLY (no canon)' if NO_CANON else 'CONTEXT (ledger+retrieval)'} {s['retrieval_pass']}/{s['n']}"
    line += f" · PRECISION {s['grounded_total']}/{s['recalled_total']} = {s['precision']}"
    line += f" · PRECISION_CURRENT {s['grounded_current_total']}/{s['recalled_total']} = {s['precision_current']} · arm={s['arm']}"
    if args.answer:
        line += f" · ANSWER {s['answer_pass']}/{s['n']}"
    print(f"\n{line} · {s['elapsed_s']}s")
    print("versioned:", write_versioned("recall_truth", out))   # M0.1
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        json.dump(out, open(args.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("wrote", args.json)
    engine.graph.close()
    return 0 if s["retrieval_pass"] == s["n"] and (not args.answer or s["answer_pass"] == s["n"]) else 1


if __name__ == "__main__":
    sys.exit(main())
