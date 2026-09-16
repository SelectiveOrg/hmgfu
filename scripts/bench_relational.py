"""Phase 74.2 — the relational bench: four arms on the SAME sealed corpus (`scripts/oracles/relational_v1.json`).

  B0  plain cosine top-k (bench-only comparator)             + memory lines with dates
  B1  cosine top-k                                          + canonical ledger lines (validity at query time, history on past cue)
  B2  cosine top-k                                          + provenance / FIXED-policy revision (superseded + reverted excluded,
                                                              echo-free)  ← the STRONG control
  F   production retrieve_memory (6 channels, Fu expansion, wormholes, weights) + the same B2 context policy

Same embedder, same k, same budget, nano OFF at ingestion (heuristic extraction, identical across arms). Primary metric:
Hit@k of the GOLD ids in the retrieved set (deterministic). Secondary: context contains a truth value and no stale
value. `--answer`: the reader (gemma4:12b) answers from each arm's context (LLM leg, `--reps`). Cost: model calls from
the Phase 73 ledger. Paired bootstrap 95% CI for F − B2 on Hit@k. Versioned output; production never touched.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import guard_scratch, throwaway_db, write_versioned  # noqa: E402
from bench_ab_retrieval import baseline_cosine_topk  # noqa: E402
from bench_recall_truth import _present  # noqa: E402
from hmgfu import config  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.retrieve import (RetrievedMemory, build_llm_context, make_query_point, retrieve_memory,  # noqa: E402
                            user_fact_question)
from hmgfu.turn_timing import call_index, calls_since  # noqa: E402

ARMS = ("b0", "b1", "b2", "p2", "f")      # p2 (77.1): the PRODUCT cosine mode — must reproduce B2 through the switch
K = config.RETRIEVAL_LIMIT
SET = os.path.join(ROOT, "scripts", "oracles", "relational_v1.json")


def build_engine(arm: str, corpus: dict) -> tuple:
    """Fresh DB, the corpus ingested through the REAL path (facts ledger + graph), points backdated to message time."""
    db = throwaway_db(f"bench_relational_{arm}{'' if ABLATE == 'none' else '_' + ABLATE}.db")   # one DB per variant: runs may overlap
    if os.path.exists(db):
        os.remove(db)
    guard_scratch(db)
    e = AgentEngine(db_path=db)
    e.sensitizer.enabled = False                       # heuristic extraction: deterministic, identical across arms
    e.settings.set("grader_enabled", False)
    e.settings.set("full_dream_every_n_turns", 0)
    e.settings.set("mini_dream_every_n_turns", 0)
    e.settings.set("tail_async", False)
    if EXCERPT is not None:
        e.settings.set("excerpt_max_chars", EXCERPT)                    # 78 candidate (throwaway engine)
    if ECHO_SCOPE is not None:
        e.settings.set("echo_guard_scope", ECHO_SCOPE)
    id_map = {}
    t0 = call_index()
    for m in corpus["messages"]:
        e.facts.apply_all(m["text"], "user_explicit")   # the ledger (B1/B2/F read it; B0 ignores it)
        p = e.ingest(m["text"], source="user", timestamp=m["ts"])   # 74.8b: observed at message time — macros follow
        id_map[m["id"]] = p.id
    ingest_calls = len(calls_since(t0))
    return e, id_map, ingest_calls


ABLATIONS = {
    # 74.5: which part of the Fu package moves gold out of the top-k? Each variant removes ONE part of F.
    "none": {},
    "noexpand": {"expansion_depth": 0},
    "no_wormhole": {"channels": {"wormhole": 0}},
    "no_dense_recent_goal": {"channels": {"dense": 0, "recent": 0, "goal": 0}},
    "semantic_entity_only": {"channels": {"dense": 0, "recent": 0, "goal": 0, "wormhole": 0}, "expansion_depth": 0},
    "semantic_only": {"channels": {"dense": 0, "recent": 0, "goal": 0, "wormhole": 0, "entity": 0}, "expansion_depth": 0},
    "no_macros": {"no_macros": True},        # dream macros ("Pattern over N memories") excluded from the candidate pool
    "no_edge_kappa": {"no_edge_kappa": True},  # κ from the query only: no edge-to-another-candidate bonus (74.5 hub finding)
}
ABLATE = "none"


def retrieve_for(arm: str, e, q) -> list:
    if arm == "p2":                                        # 77.1: product `retrieval_mode = cosine`
        return retrieve_memory(q, e.graph, limit=K, min_score=e.settings.get("retrieval_min_score"), mode="cosine")
    if arm in ("b0", "b1", "b2"):
        pts = [p for p in e.graph.active_points() if p.type not in ("skill", "session", "directive", "pattern")]
        return [RetrievedMemory(point=p, edge=None, score=1.0, reason="cosine") for p in baseline_cosine_topk(q, pts, K)]
    spec = ABLATIONS[ABLATE]
    saved = dict(config.RETRIEVAL_CHANNELS)
    saved_active = e.graph.active_points
    import hmgfu.retrieve as R
    saved_edge = R._best_edge_toward
    try:
        config.RETRIEVAL_CHANNELS.update(spec.get("channels", {}))          # bench-only, restored right after
        if spec.get("no_macros"):
            e.graph.active_points = lambda: [p for p in saved_active() if p.type != "macro"]   # bench-only
        if spec.get("no_edge_kappa"):
            R._best_edge_toward = lambda p, origin, graph, query=None: (None, 1.0)   # bench-only: every candidate edge-free
        return retrieve_memory(q, e.graph, limit=K, min_score=e.settings.get("retrieval_min_score"),
                               expansion_depth=spec.get("expansion_depth", e.settings.get("expansion_depth")),
                               weights=e.weight_learner.weights())
    finally:
        config.RETRIEVAL_CHANNELS.clear(); config.RETRIEVAL_CHANNELS.update(saved)
        e.graph.active_points = saved_active
        R._best_edge_toward = saved_edge


def context_for(arm: str, e, q, retrieved, question_text: str) -> str:
    from hmgfu.utterance import past_cue
    canonical = [] if arm == "b0" else e.facts.render_lines() + (e.facts.render_history_lines() if past_cue(question_text) else [])
    if arm in ("b0", "b1"):
        ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved, token_budget=e.settings.get("token_budget"),
                                   canonical=canonical, superseded=None, reverted=None, echo_free=False)
    else:
        ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved, token_budget=e.settings.get("token_budget"),
                                   canonical=canonical, superseded=e.facts.superseded_values(),
                                   reverted=e.facts.reverted_values(), echo_free=user_fact_question(q, e.facts),
                                   excerpt_chars=e.settings.get("excerpt_max_chars"), echo_scope=e.settings.get("echo_guard_scope"),
                                   echo_pairs=e.facts.active_pairs())
    return ctx


def answer_with_reader(e, context: str, question: str) -> str:
    provider, model = e.registry.resolve("chat")
    out = provider.chat(model, [
        {"role": "system", "content": "Answer the user's question about THEIR OWN life from the memory context only. "
                                      "One short sentence. If the context does not say, answer 'unknown'.\n\n" + context},
        {"role": "user", "content": question}], temperature=0.0, think=False)
    return (out.get("content") or "").strip() if isinstance(out, dict) else str(out or "")


def paired_ci(a: list, b: list, seed: int = 74, n: int = 2000) -> tuple:
    rng = random.Random(seed)
    diffs = [x - y for x, y in zip(a, b)]
    vals = sorted(statistics.mean(rng.choice(diffs) for _ in diffs) for _ in range(n))
    return round(vals[int(0.025 * n)], 3), round(vals[int(0.975 * n)], 3)


def run_arm(arm: str, corpus: dict, answer: bool, reps: int) -> list:
    e, id_map, ingest_calls = build_engine(arm, corpus)
    rows = []
    for qd in corpus["questions"]:
        gold = {id_map[g] for g in qd["gold"]}
        t0 = call_index(); t = time.perf_counter()
        q = make_query_point(qd["text"], e.embed, e.sensitizer)
        retrieved = retrieve_for(arm, e, q)
        got = {r.point.id for r in retrieved}
        ctx = context_for(arm, e, q, retrieved, qd["text"])
        hit = gold <= got
        ctx_truth = bool(_present(ctx, qd["truth"])) if qd["truth"] else None
        ctx_stale = bool(_present(ctx, qd["stale"])) if qd["stale"] else False
        row = {"arm": arm, "id": qd["id"], "family": qd["family"], "hit": hit, "gold_found": len(gold & got), "gold_n": len(gold),
               "ctx_truth": ctx_truth, "ctx_stale": ctx_stale, "n_retrieved": len(retrieved),
               "query_calls": len(calls_since(t0)), "ms": round((time.perf_counter() - t) * 1000, 1)}
        if answer:
            oks = []
            for _ in range(reps):
                reply = answer_with_reader(e, ctx, qd["text"])
                oks.append(bool(_present(reply, qd["truth"])) and not _present(reply, qd["stale"]))
                row.setdefault("replies", []).append(reply)      # full reply: a leg can be re-scored offline
            row["answer_ok"] = sum(oks) / len(oks)
        rows.append(row)
    for r in rows:
        r["ingest_calls"] = ingest_calls
    e.graph.close()
    return rows


def summarise(rows_by_arm: dict, families: list) -> dict:
    out = {}
    for arm, rows in rows_by_arm.items():
        s = {"hit": round(statistics.mean(r["hit"] for r in rows), 3),
             "ctx_truth": round(statistics.mean(r["ctx_truth"] for r in rows if r["ctx_truth"] is not None), 3),
             "ctx_stale": round(statistics.mean(r["ctx_stale"] for r in rows), 3),
             "query_calls_mean": round(statistics.mean(r["query_calls"] for r in rows), 2),
             "ingest_calls": rows[0]["ingest_calls"] if rows else 0,
             "ms_mean": round(statistics.mean(r["ms"] for r in rows), 1)}
        if any("answer_ok" in r for r in rows):
            s["answer_ok"] = round(statistics.mean(r["answer_ok"] for r in rows), 3)
        for fam in families:
            fr = [r for r in rows if r["family"] == fam]
            s[f"hit@{fam}"] = round(statistics.mean(r["hit"] for r in fr), 3) if fr else None
        out[arm] = s
    if "f" in rows_by_arm and "b2" in rows_by_arm:
        f = {r["id"]: r for r in rows_by_arm["f"]}; b2 = {r["id"]: r for r in rows_by_arm["b2"]}
        ids = sorted(set(f) & set(b2))
        out["f_minus_b2"] = {"hit_all": paired_ci([float(f[i]["hit"]) for i in ids], [float(b2[i]["hit"]) for i in ids])}
        for fam in families:
            fids = [i for i in ids if f[i]["family"] == fam]
            if fids:
                out["f_minus_b2"][f"hit@{fam}"] = paired_ci([float(f[i]["hit"]) for i in fids], [float(b2[i]["hit"]) for i in fids])
    return out


EXCERPT = None       # 78: set from --excerpt
ECHO_SCOPE = None    # 78: set from --echo-scope


def main() -> int:
    global EXCERPT, ECHO_SCOPE
    ap = argparse.ArgumentParser()
    ap.add_argument("--excerpt", type=int, default=None, help="78: excerpt_max_chars for every arm's engine (default: the setting)")
    ap.add_argument("--echo-scope", default=None, choices=("all", "echoes"), help="78: echo_guard_scope for every arm's engine")
    ap.add_argument("--arm", default="all", help="b0|b1|b2|f|all")
    ap.add_argument("--set", default=SET)
    ap.add_argument("--answer", action="store_true", help="LLM leg: the reader answers from each arm's context")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--ablate", default="none", choices=sorted(ABLATIONS), help="74.5: remove one part of the Fu package (arm f only)")
    args = ap.parse_args()
    EXCERPT, ECHO_SCOPE = args.excerpt, args.echo_scope
    global ABLATE
    ABLATE = args.ablate
    corpus = json.load(open(args.set, encoding="utf-8"))
    families = list(corpus["families"])
    arms = ARMS if args.arm == "all" else tuple(args.arm.split(","))
    rows_by_arm = {}
    for arm in arms:
        t0 = time.time()
        rows_by_arm[arm] = run_arm(arm, corpus, args.answer, args.reps)
        s = summarise({arm: rows_by_arm[arm]}, families)[arm]
        print(f"[{arm.upper():2s}] Hit@{K} {s['hit']:.3f} · ctx_truth {s['ctx_truth']:.3f} · ctx_stale {s['ctx_stale']:.3f}"
              f"{' · answer ' + format(s['answer_ok'], '.3f') if 'answer_ok' in s else ''} · per family "
              + " ".join(f"{fam}={s['hit@' + fam]}" for fam in families) + f" · {round(time.time() - t0)}s")
    summary = summarise(rows_by_arm, families)
    if "f_minus_b2" in summary:
        print("F − B2 (paired 95% CI):", json.dumps(summary["f_minus_b2"]))
    summary["ablate"] = ABLATE
    print("versioned:", write_versioned("relational", {"summary": summary, "rows": rows_by_arm, "ablate": ABLATE}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
