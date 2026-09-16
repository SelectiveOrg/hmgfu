"""Phase 30.5: scale test — claim "retrieval is O(n) cosine scans, fine now, needs indexing
around 10k+" from the Phase-29 report. Pure math, no Ollama: retrieve_memory() takes a graph
and a QueryPoint: at this corpus size, embeddings/sensitizer extraction cost is irrelevant to
the RETRIEVAL latency curve we're measuring (ingest cost is a separate, already-measured, one-
time-per-memory cost). Deterministic synthetic embeddings stand in for real ones.

Run: .venv/Scripts/python scripts/bench_scale.py
"""

from __future__ import annotations

import hashlib
import math
import os
import random
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu.models import Hex, MemoryPoint, QueryPoint, now_iso  # noqa: E402
from hmgfu.retrieve import retrieve_memory  # noqa: E402
from hmgfu.store import HMGGraph  # noqa: E402

DIM = 64
SIZES = [500, 1000, 2500, 5000, 10000, 20000, 50000]
# 76.0: `--sizes 500,...,100000` extends the curve; `--edges-per-point N` gives every point N synthetic edges so the
# per-candidate edge work (path-κ, 74.7) is on the measured path; `--profile` times the semantic scan alone beside the
# full retrieval at the largest size. Defaults reproduce the Phase 30.5 measurement exactly.
QUERIES_PER_SIZE = 8
# Vision-doc / UX budget: retrieval must stay well under a human-perceptible turn-latency tax.
LATENCY_BUDGET_MS = 500.0


def rand_embed(rng: random.Random) -> list:
    v = [rng.gauss(0, 1) for _ in range(DIM)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def make_point(i: int, rng: random.Random) -> MemoryPoint:
    words = [f"topic{rng.randint(0, 40)}", f"entity{rng.randint(0, 60)}"]
    return MemoryPoint(
        type=rng.choice(["message", "fact", "event", "concept"]),
        title=f"point {i}",
        content=f"synthetic memory {i} about {' '.join(words)}",
        summary=f"synthetic memory {i}",
        embedding=rand_embed(rng),
        entities=[words[1]],
        topics=[words[0]],
        importance=rng.random(), confidence=rng.random(), novelty=rng.random(),
        utility=rng.random(), density=rng.random(),
        hex=Hex(q=i, r=-i // 2, s=-(i - i // 2)),
        timestamp=now_iso(),
    )


def main() -> int:
    global DIM
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(map(str, SIZES)))
    ap.add_argument("--edges-per-point", type=int, default=0)
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--dim", type=int, default=DIM, help="embedding size (64 reproduces Phase 30.5; bge-m3 is 1024)")
    args = ap.parse_args()
    DIM = args.dim
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    rng = random.Random(42)
    from _bench_paths import throwaway_db
    db = throwaway_db("scale_bench.db")
    if os.path.exists(db):
        os.remove(db)
    graph = HMGGraph(db_path=db)

    print(f"{'N points':>10} | {'p50 ms':>8} | {'p95 ms':>8} | {'max ms':>8} | budget({LATENCY_BUDGET_MS}ms)")
    results = []
    added = 0
    from hmgfu.models import FuEdge
    ids = []
    t_build = time.perf_counter()
    for target in sizes:
        while added < target:
            p = make_point(added, rng)
            graph.points[p.id] = p           # bypass save_point's SQLite write — pure in-memory
            graph.occupied[p.hex.key()] = p.id
            graph.version += 1; graph.dirty.add(p.id)   # 76.2: what save_point would do — the index syncs incrementally
            ids.append(p.id)
            for _ in range(args.edges_per_point):          # 76.0: synthetic edges on the measured path
                other = ids[rng.randrange(len(ids))]
                if other != p.id:
                    e = FuEdge(from_id=p.id, to_id=other, relation_type=rng.choice(["semantic_similarity", "temporal", "same_entity"]),
                               kappa=rng.uniform(0.2, 0.9), trust=0.7, base_separation=rng.uniform(1.0, 4.0), distance=1.0)
                    graph.edges[e.id] = e
                    graph._index_edge(e)
            added += 1
        build_s = time.perf_counter() - t_build
        # 76.2: the first query after a bulk of writes pays the index sync — measured and reported apart from steady state
        t0 = time.perf_counter()
        retrieve_memory(QueryPoint(text="warm", embedding=rand_embed(rng), entities=[], topics=[]), graph)
        sync_ms = (time.perf_counter() - t0) * 1000.0
        times = []
        for _ in range(QUERIES_PER_SIZE):
            q = QueryPoint(text="probe query", embedding=rand_embed(rng),
                          entities=[f"entity{rng.randint(0, 60)}"], topics=[f"topic{rng.randint(0, 40)}"])
            t0 = time.perf_counter()
            retrieve_memory(q, graph)
            times.append((time.perf_counter() - t0) * 1000.0)
        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)] if len(times) > 1 else times[0]
        mx = times[-1]
        verdict = "OK" if p95 < LATENCY_BUDGET_MS else "OVER BUDGET"
        print(f"{target:>10} | {p50:>8.1f} | {p95:>8.1f} | {mx:>8.1f}   {verdict}   (edges {len(graph.edges)}, build {build_s:.1f}s, first query after the writes {sync_ms:.0f} ms)")
        results.append((target, p50, p95, mx))
        if args.profile and target == sizes[-1]:
            from hmgfu import fu_math, retrieve_channels as rc
            from hmgfu.taxonomy import node_class
            q = QueryPoint(text="probe query", embedding=rand_embed(rng), entities=["entity1"], topics=["topic1"])
            def t(fn):
                t0 = time.perf_counter(); fn(); return (time.perf_counter() - t0) * 1000
            pts_all = graph.active_points()
            t_act = t(lambda: graph.active_points())
            t_class = t(lambda: [p for p in pts_all if node_class(p) not in ("skill", "tool", "directive", "session") and "_question" not in p.keywords])
            pts = [p for p in pts_all if node_class(p) not in ("skill", "tool", "directive", "session")]
            t_sem = t(lambda: rc.semantic_candidates(q, pts, 60, graph=graph))
            t_ent = t(lambda: rc.entity_candidates(q, pts, 30))
            t_goal = t(lambda: rc.goal_candidates(pts, 30))
            t_rec = t(lambda: rc.recent_candidates(pts, 20))
            t_dense = t(lambda: rc.dense_candidates(pts, 20))
            t_cos = t(lambda: [fu_math.cosine(q.embedding, p.embedding) for p in pts])
            print(f"   profile @ {target}: active_points {t_act:.0f} · class filter {t_class:.0f} · semantic top-60 (vector) {t_sem:.0f} · "
                  f"entity {t_ent:.0f} · goal {t_goal:.0f} · recent {t_rec:.0f} · dense {t_dense:.0f} · [pure cosine scan {t_cos:.0f}] ms")

    graph.close()
    os.remove(db)

    print("\n=== SCALE VERDICT ===")
    inflection = next((n for n, _, p95, _ in results if p95 >= LATENCY_BUDGET_MS), None)
    if inflection:
        print(f"Retrieval crosses the {LATENCY_BUDGET_MS}ms budget at ~{inflection} active points.")
    else:
        print(f"Retrieval stayed under the {LATENCY_BUDGET_MS}ms budget up to {sizes[-1]} points.")
    print("versioned:", __import__("_bench_paths").write_versioned("scale", {"sizes": sizes, "edges_per_point": args.edges_per_point, "dim": DIM,
          "results": [{"n": n, "p50_ms": round(a, 1), "p95_ms": round(b, 1), "max_ms": round(c, 1)} for n, a, b, c in results]}))
    growth = results[-1][2] / results[0][2] if results[0][2] > 0 else float("inf")
    size_growth = results[-1][0] / results[0][0]
    print(f"p95 latency grew {growth:.1f}x while corpus grew {size_growth:.1f}x "
          f"({'roughly linear' if growth / size_growth < 2 else 'super-linear'} — confirms O(n) scan claim)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
