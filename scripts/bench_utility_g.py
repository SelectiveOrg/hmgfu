"""Phase 75.6 — Fu-R utility G(f) and interaction I_Fu, estimated OFFLINE on the sealed relational set with the reader fixed.

  G(f | Q, K) = U(K with f) − U(K without f)           U = answer accuracy (the reader answers from the injected context,
  I_Fu(A, B)  = U(K+A+B) − U(K+A) − U(K+B) + U(K)      judged by the truth/stale rule already used by bench_relational)

Variants (one per package part removed from arm F's context policy; "removed" includes its derived copies):
  full          the F context as measured in Phase 74 (ledger + history on past cue + provenance exclusion + echo-free +
                Fu expansion)
  no_ledger     canonical lines out (history lines out too — they are derived from the ledger)
  no_history    history lines out (ledger stays)
  no_provenance superseded / reverted exclusion off
  no_both       no_ledger + no_provenance (for I_Fu(ledger, provenance))
  no_echofree   echo-free off
  no_expansion  retrieval with expansion depth 0
Cheap estimator: the grader's deterministic cited-count on each reply (grader._heuristic_grades) — reported per variant
beside U with a Pearson correlation across variants; "unknown" is printed for any G whose bootstrap 95% CI includes 0.
One repetition per question (pre-registered: 60 questions × 7 variants = 420 reader calls). A bench, not product.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import write_versioned  # noqa: E402
import bench_relational as br  # noqa: E402
from bench_recall_truth import _present  # noqa: E402
from hmgfu import config  # noqa: E402
from hmgfu.grader import _heuristic_grades  # noqa: E402
from hmgfu.retrieve import build_llm_context, make_query_point, retrieve_memory, user_fact_question  # noqa: E402
from hmgfu.utterance import past_cue  # noqa: E402

VARIANTS = ("full", "no_ledger", "no_history", "no_provenance", "no_both", "no_echofree", "no_expansion")


def context_variant(e, q, retrieved, question: str, variant: str) -> str:
    ledger = variant not in ("no_ledger", "no_both")
    history = ledger and variant != "no_history"
    provenance = variant not in ("no_provenance", "no_both")
    echo_free = variant != "no_echofree" and user_fact_question(q, e.facts)
    canonical = (e.facts.render_lines() if ledger else []) + (e.facts.render_history_lines() if history and past_cue(question) else [])
    ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved, token_budget=e.settings.get("token_budget"), canonical=canonical,
                               superseded=e.facts.superseded_values() if provenance else None,
                               reverted=e.facts.reverted_values() if provenance else None, echo_free=echo_free)
    return ctx


def boot_ci(diffs: list, seed: int = 75, n: int = 2000) -> tuple:
    rng = random.Random(seed)
    vals = sorted(statistics.mean(rng.choice(diffs) for _ in diffs) for _ in range(n))
    return round(vals[int(0.025 * n)], 3), round(vals[int(0.975 * n)], 3)


def pearson(xs: list, ys: list) -> float:
    if len(xs) < 3:
        return float("nan")
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return round(num / den, 3) if den else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=br.SET)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--limit", type=int, default=0, help="debug: first N questions")
    args = ap.parse_args()
    variants = tuple(v for v in args.variants.split(",") if v)
    corpus = json.load(open(args.set, encoding="utf-8"))
    questions = corpus["questions"][:args.limit] if args.limit else corpus["questions"]
    t0 = time.time()
    e, id_map, _ = br.build_engine("utility_g", corpus)
    rows = []
    for n, qd in enumerate(questions, 1):
        q = make_query_point(qd["text"], e.embed, e.sensitizer)
        weights = e.weight_learner.weights()
        full_ret = retrieve_memory(q, e.graph, limit=br.K, min_score=e.settings.get("retrieval_min_score"),
                                   expansion_depth=e.settings.get("expansion_depth"), weights=weights)
        noexp_ret = retrieve_memory(q, e.graph, limit=br.K, min_score=e.settings.get("retrieval_min_score"),
                                    expansion_depth=0, weights=weights) if "no_expansion" in variants else full_ret
        for v in variants:
            retrieved = noexp_ret if v == "no_expansion" else full_ret
            ctx = context_variant(e, q, retrieved, qd["text"], v)
            reply = br.answer_with_reader(e, ctx, qd["text"])
            ok = bool(_present(reply, qd["truth"])) and not _present(reply, qd["stale"])
            cited = sum(1 for g in _heuristic_grades(reply, retrieved, qd["text"]) if g["grade"] == "cited")
            rows.append({"id": qd["id"], "family": qd["family"], "variant": v, "ok": ok, "cited": cited, "reply": reply[:160]})
        if n % 5 == 0:
            print(f"   {n}/{len(questions)} questions ({round(time.time() - t0)}s)")
    e.graph.close()
    U = {v: statistics.mean(r["ok"] for r in rows if r["variant"] == v) for v in variants}
    C = {v: statistics.mean(r["cited"] for r in rows if r["variant"] == v) for v in variants}
    by = {(r["id"], r["variant"]): r for r in rows}
    ids = [qd["id"] for qd in questions]
    G = {}
    for v in variants:
        if v == "full":
            continue
        diffs = [float(by[(i, "full")]["ok"]) - float(by[(i, v)]["ok"]) for i in ids]
        lo, hi = boot_ci(diffs)
        G[v.replace("no_", "")] = {"G": round(statistics.mean(diffs), 3), "ci": [lo, hi], "verdict": "unknown" if lo <= 0 <= hi else ("useful" if lo > 0 else "harmful")}
    I = None
    if all(v in variants for v in ("full", "no_ledger", "no_provenance", "no_both")):
        inter = [float(by[(i, "full")]["ok"]) - float(by[(i, "no_ledger")]["ok"]) - float(by[(i, "no_provenance")]["ok"]) + float(by[(i, "no_both")]["ok"]) for i in ids]
        lo, hi = boot_ci(inter)
        I = {"I_Fu(ledger,provenance)": round(statistics.mean(inter), 3), "ci": [lo, hi], "verdict": "unknown" if lo <= 0 <= hi else ("complementary" if lo > 0 else "redundant")}
    corr = pearson([U[v] for v in variants], [C[v] for v in variants])
    summary = {"n_questions": len(questions), "variants": list(variants), "U": {v: round(U[v], 3) for v in variants},
               "cheap_cited_mean": {v: round(C[v], 3) for v in variants}, "G": G, "I": I,
               "pearson_U_vs_cited_across_variants": corr, "elapsed_s": round(time.time() - t0, 1)}
    print("[utility G] U by variant:", summary["U"])
    print("            G(f):", {k: f"{v['G']} {v['ci']} {v['verdict']}" for k, v in G.items()})
    print("            I_Fu:", I)
    print("            cheap estimator (mean cited):", summary["cheap_cited_mean"], "| Pearson(U, cited) across variants:", corr)
    print("versioned:", write_versioned("utility_g", {"summary": summary, "rows": rows}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
