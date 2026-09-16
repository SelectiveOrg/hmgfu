"""Phase 75.4 — self-recall bench on the sealed set (`scripts/oracles/selfrecall_v1.json`).

Fresh throwaway DB, REAL embedder, nano OFF, no chat calls. For each problem: the user's request is ingested (turn N),
the agent's reflection is stored through the production path (`taxonomy.store_reflection` → a `reflection` node,
source=assistant, linked to the request); the facts are ingested through the ledger. Then, for each later paraphrase,
PRODUCTION retrieval runs and we ask whether the gold reflection is in the recalled set (recall@k) — and whether it
survives into the answer context (`build_llm_context`, echo-free OFF for a task) — and for each user-fact question
whether ANY reflection leaks into the echo-free answer context.
Gate (ROADMAP 75.4): recall ≥ 0.8 on recurrence; 0 leaks into user-fact answers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import guard_scratch, throwaway_db, write_versioned  # noqa: E402
from hmgfu import fu_math  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.retrieve import build_llm_context, make_query_point, retrieve_memory, user_fact_question  # noqa: E402
from hmgfu.taxonomy import store_reflection  # noqa: E402

SET = os.path.join(ROOT, "scripts", "oracles", "selfrecall_v1.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=SET)
    args = ap.parse_args()
    corpus = json.load(open(args.set, encoding="utf-8"))
    db = throwaway_db("bench_selfrecall.db")
    if os.path.exists(db):
        os.remove(db)
    guard_scratch(db)
    e = AgentEngine(db_path=db)
    e.sensitizer.enabled = False
    for k, v in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                 "runbooks_enabled": False, "prospective_enabled": False}.items():
        e.settings.set(k, v)
    t0 = time.time()
    for f in corpus["facts"]:
        e.facts.apply_all(f, "user_explicit")
        e.ingest(f, source="user_explicit")
    gold = {}
    for p in corpus["problems"]:
        user_point = e.ingest(p["request"], source="user")
        refl = store_reflection(e, [p["reflection"]], user_point)
        assert refl is not None, p["id"]
        gold[p["id"]] = refl.id
    limit = e.settings.get("retrieval_limit"); floor = e.settings.get("retrieval_min_score")
    rows = []
    for p in corpus["problems"]:
        for later in p["later"]:
            q = make_query_point(later, e.embed, e.sensitizer)
            got = retrieve_memory(q, e.graph, limit=limit, min_score=floor, expansion_depth=e.settings.get("expansion_depth"),
                                  weights=e.weight_learner.weights())
            ids = [r.point.id for r in got]
            ctx, _ = build_llm_context(q, e.graph, retrieved=got, token_budget=e.settings.get("token_budget"),
                                       canonical=e.facts.render_lines(), superseded=e.facts.superseded_values(),
                                       reverted=e.facts.reverted_values(), echo_free=False)
            rp = e.graph.points[gold[p["id"]]]
            rows.append({"kind": "recurrence", "problem": p["id"], "text": later, "recalled": gold[p["id"]] in ids,
                         "in_context": rp.content[:40] in ctx or (rp.summary or "")[:40] in ctx,
                         "rank": ids.index(gold[p["id"]]) + 1 if gold[p["id"]] in ids else None,
                         "cos": round(fu_math.cosine(q.embedding, rp.embedding), 3), "n_retrieved": len(ids)})
    for qtext in corpus["user_fact_questions"]:
        q = make_query_point(qtext, e.embed, e.sensitizer)
        got = retrieve_memory(q, e.graph, limit=limit, min_score=floor, expansion_depth=e.settings.get("expansion_depth"),
                              weights=e.weight_learner.weights())
        ef = user_fact_question(q, e.facts)
        ctx, _ = build_llm_context(q, e.graph, retrieved=got, token_budget=e.settings.get("token_budget"),
                                   canonical=e.facts.render_lines(), superseded=e.facts.superseded_values(),
                                   reverted=e.facts.reverted_values(), echo_free=ef)
        leaked = [pid for pid, rid in gold.items() if e.graph.points[rid].content[:40] in ctx]
        rows.append({"kind": "user_fact", "text": qtext, "echo_free": ef, "reflections_recalled": sum(1 for r in got if r.point.type == "reflection"),
                     "leaked": leaked})
    rec = [r for r in rows if r["kind"] == "recurrence"]; uf = [r for r in rows if r["kind"] == "user_fact"]
    summary = {"recall": round(sum(r["recalled"] for r in rec) / len(rec), 3), "in_context": round(sum(r["in_context"] for r in rec) / len(rec), 3),
               "n_recurrence": len(rec), "leaks": sum(1 for r in uf if r["leaked"]), "n_user_fact": len(uf),
               "echo_free_applied": sum(1 for r in uf if r["echo_free"]), "elapsed_s": round(time.time() - t0, 1)}
    print(f"[selfrecall] recall {summary['recall']:.3f} · in answer context {summary['in_context']:.3f} (n {len(rec)}) · "
          f"leaks into user-fact answers {summary['leaks']}/{len(uf)} (echo-free applied on {summary['echo_free_applied']}) · {summary['elapsed_s']}s")
    misses = [(r["problem"], r["text"][:50], r["cos"], r["rank"]) for r in rec if not r["recalled"]]
    if misses:
        print("misses (problem, text, cos, rank):", misses)
    print("versioned:", write_versioned("selfrecall", {"summary": summary, "rows": rows}))
    e.graph.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
