"""Phase 76.1 — the relational quality curve at scale: the sealed relational corpus inside a haystack of 1k · 10k · 100k
filler lines (real bge-m3 embeddings), B2 (cosine top-k + provenance context) vs F (production retrieval) Hit@12 per size.

ONE database is built (`bench_relational_scale.db`): the 159 corpus messages through the REAL path (ledger + ingest at
their observed time — the same construction as bench_relational's arm F) and N filler lines as PLAIN points with real
embeddings (no ingest edges/macros: ingest is O(n) per message, O(n²) to fill a graph — Phase 76.0 fact — and the filler
is retrieval noise, not knowledge). Sizes are evaluated on the same database by masking active points to the first
`size` filler lines plus the corpus (bench-only wrapper, the 74.5 ablation pattern), so the three curves share every
embedding. Reported per size: Hit@12 B2 and F (all questions + per family), paired F − B2 CI, retrieval latency p50/p95
for F, and the context-truth rate. Gate (ROADMAP 76.1): F ≥ B2 − 0.05 at every size; F(100k) ≥ F(159) − 0.10.
Resumable: the filler already in the database is reused (`--fill N` adds up to N).
"""
from __future__ import annotations

import argparse
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
import bench_relational as br  # noqa: E402
from bench_relational import context_for, paired_ci, retrieve_for  # noqa: E402
from bench_recall_truth import _present  # noqa: E402
from haystack_corpus import filler  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.models import MemoryPoint  # noqa: E402
from hmgfu.retrieve import make_query_point  # noqa: E402

DB = throwaway_db("bench_relational_scale.db")
FILLER_KW = "_haystack"


def build_or_open(corpus: dict, fill: int) -> tuple:
    """Open the shared DB (build the corpus part once), then top the filler up to `fill` lines."""
    fresh = not os.path.exists(DB)
    guard_scratch(DB)
    e = AgentEngine(db_path=DB)
    e.sensitizer.enabled = False
    for k, v in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                 "runbooks_enabled": False, "prospective_enabled": False}.items():
        e.settings.set(k, v)
    id_map = {}
    if fresh:
        t0 = time.time()
        for m in corpus["messages"]:
            e.facts.apply_all(m["text"], "user_explicit")
            p = e.ingest(m["text"], source="user", timestamp=m["ts"])
            p.keywords = list(p.keywords) + [f"_corpus:{m['id']}"]
            e.graph.save_point(p)
            id_map[m["id"]] = p.id
        print(f"   corpus ingested through the real path: {len(id_map)} messages in {round(time.time() - t0)}s")
    else:
        for p in e.graph.points.values():
            for k in p.keywords:
                if k.startswith("_corpus:"):
                    id_map[k[8:]] = p.id
    have = sum(1 for p in e.graph.points.values() if FILLER_KW in p.keywords)

    def embed_retry(text: str, attempts: int = 5):
        """A transient Ollama timeout (the embedder shared with other benches) is retried with backoff, not fatal."""
        last = None
        for k in range(attempts):
            try:
                return e.embed(text)
            except Exception as exc:                       # OllamaError: embed failed: timed out
                last = exc
                time.sleep(2.0 * (k + 1))
        raise last

    if fill > have:
        t0 = time.time()
        for i, (text, ts) in enumerate(filler(fill)):
            if i < have:
                continue
            pt = MemoryPoint(type="message", content=text, summary="", source="user", embedding=embed_retry(text),
                             keywords=[FILLER_KW, f"_hay:{i}"], timestamp=ts, importance=0.3, utility=0.3, density=0.1)
            e.graph.save_point(pt)
            if (i + 1) % 1000 == 0:
                print(f"   filler {i + 1}/{fill} ({round(time.time() - t0)}s)")
    return e, id_map


def masked_active(e, size: int):
    """Active points = corpus + first `size` filler lines (bench-only, restored by the caller)."""
    keep = set()
    for p in e.graph.points.values():
        h = next((k for k in p.keywords if k.startswith("_hay:")), None)
        if h is None or int(h[5:]) < size:
            keep.add(p.id)
    orig = (e.graph.active_points, e.graph.all_points)
    return orig, ((lambda: [p for p in orig[0]() if p.id in keep]), (lambda: [p for p in orig[1]() if p.id in keep]))


def evaluate(e, id_map: dict, corpus: dict, size: int) -> dict:
    orig, masked = masked_active(e, size)
    e.graph.active_points, e.graph.all_points = masked            # the history channel reads all_points(): mask it too
    from hmgfu import vecindex
    vecindex.clear_cache()
    e.graph.version += 1                       # the masked pool is a different pool: no stale matrix
    families = list(corpus["families"])
    rows = {"b2": [], "f": []}
    try:
        for qd in corpus["questions"]:
            gold = {id_map[g] for g in qd["gold"]}
            q = make_query_point(qd["text"], e.embed, e.sensitizer)
            for arm in ("b2", "f"):
                t = time.perf_counter()
                got = retrieve_for(arm, e, q)
                ms = (time.perf_counter() - t) * 1000
                ids = {r.point.id for r in got}
                ctx = context_for(arm, e, q, got, qd["text"])
                rows[arm].append({"id": qd["id"], "family": qd["family"], "hit": gold <= ids,
                                  "ctx_truth": bool(_present(ctx, qd["truth"])) if qd["truth"] else None, "ms": round(ms, 1)})
    finally:
        e.graph.active_points, e.graph.all_points = orig
        vecindex.clear_cache(); e.graph.version += 1
    out = {"size": size, "n_active": len(masked[0]())}
    for arm in ("b2", "f"):
        r = rows[arm]
        out[arm] = {"hit": round(statistics.mean(x["hit"] for x in r), 3),
                    "ctx_truth": round(statistics.mean(x["ctx_truth"] for x in r if x["ctx_truth"] is not None), 3),
                    "ms_p50": round(statistics.median(x["ms"] for x in r), 1), "ms_p95": round(sorted(x["ms"] for x in r)[int(0.95 * len(r))], 1)}
        for fam in families:
            fr = [x for x in r if x["family"] == fam]
            out[arm][f"hit@{fam}"] = round(statistics.mean(x["hit"] for x in fr), 3) if fr else None
    f = {x["id"]: x for x in rows["f"]}; b = {x["id"]: x for x in rows["b2"]}; ids = sorted(f)
    out["f_minus_b2_ci"] = paired_ci([float(f[i]["hit"]) for i in ids], [float(b[i]["hit"]) for i in ids])
    out["rows"] = rows
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fill", type=int, default=100_000, help="filler lines to have in the DB (added incrementally)")
    ap.add_argument("--sizes", default="0,1000,10000,100000")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    if args.rebuild and os.path.exists(DB):
        os.remove(DB)
    corpus = json.load(open(br.SET, encoding="utf-8"))
    t0 = time.time()
    e, id_map = build_or_open(corpus, args.fill)
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    results = []
    for size in sizes:
        if size > args.fill:
            continue
        r = evaluate(e, id_map, corpus, size)
        results.append(r)
        print(f"[scale] filler {size:>7} (active {r['n_active']:>7}) · Hit@12 B2 {r['b2']['hit']:.3f} · F {r['f']['hit']:.3f} "
              f"(relational B2 {r['b2']['hit@relational']} · F {r['f']['hit@relational']}) · F−B2 CI {r['f_minus_b2_ci']} · "
              f"ctx_truth B2 {r['b2']['ctx_truth']} F {r['f']['ctx_truth']} · F retrieval p50 {r['f']['ms_p50']} ms p95 {r['f']['ms_p95']} ms")
    e.graph.close()
    print("versioned:", write_versioned("relational_scale", {"results": [{k: v for k, v in r.items() if k != "rows"} for r in results],
                                                             "rows": {str(r["size"]): r["rows"] for r in results},
                                                             "elapsed_s": round(time.time() - t0, 1)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
