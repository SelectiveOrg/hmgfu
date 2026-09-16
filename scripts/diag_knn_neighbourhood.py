"""Phase 89.2 diagnostic — why does the nearest-exemplar router claim so few turns? For every exemplar (leave-one-out) print the
top-k similarities and whether the neighbours agree on the decision; summarise claim share as a function of k and min_sim, and the
correctness of what would be claimed. DEV sets only (routing_v1 / decision_v1); never the reserved set. Read-only: embeddings
come from the same cached base the router uses."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu import fu_math  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.knn_router import DECISION, ExemplarBase, knn_route  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--ks", default="1,2,3")
    ap.add_argument("--sims", default="0.70,0.75,0.80,0.85,0.90")
    ap.add_argument("--show", type=int, default=12, help="print this many per-turn neighbourhoods")
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    clone = os.path.join(SCRATCH, f"diag_knn_clone_{os.getpid()}.db")
    clone_live(clone, args.db)
    engine = AgentEngine(db_path=clone)
    for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(key, val)
    name = str(engine.settings.get("embed_model") or "")
    base = ExemplarBase(engine.embed, name)
    items = base.items
    print(f"embedder {name} · exemplars {len(items)} · sources {sorted({i['source'] for i in items})}")
    # nearest-neighbour similarity distribution (LOO) and agreement of the nearest
    top1, agree1 = [], 0
    for it in items:
        pool = [j for j in items if j is not it and j["text"] != it["text"]]
        scored = sorted(((fu_math.cosine(it["embedding"], j["embedding"]), j) for j in pool), key=lambda t: -t[0])
        s1, n1 = scored[0]
        top1.append(s1)
        agree1 += int(all(n1["decision"].get(f) == it["decision"].get(f) for f in DECISION))
    top1s = sorted(top1)
    q = lambda p: top1s[min(len(top1s) - 1, int(p * len(top1s)))]
    print(f"nearest-neighbour similarity (LOO): p10 {q(0.1):.3f} · p25 {q(0.25):.3f} · p50 {q(0.5):.3f} · p75 {q(0.75):.3f} · p90 {q(0.9):.3f} · max {top1s[-1]:.3f}")
    print(f"nearest neighbour agrees on the full decision: {agree1}/{len(items)}")
    # claim share × correctness grid
    print("\nk × min_sim → claimed / correct-on-claims (LOO over the base)")
    for k in [int(x) for x in args.ks.split(",")]:
        row = []
        for ms in [float(x) for x in args.sims.split(",")]:
            claimed = correct = 0
            for it in items:
                r = knn_route(it["embedding"], base, k=k, min_sim=ms, exclude_text=it["text"])
                if r is None:
                    continue
                claimed += 1
                correct += int(all(r.get(f) == it["decision"].get(f) for f in DECISION))
            row.append(f"{ms:.2f}: {claimed}/{len(items)} ({correct}/{claimed} ok)")
        print(f"  k={k}  " + " · ".join(row))
    # a few neighbourhoods
    print(f"\nfirst {args.show} neighbourhoods (LOO, top 3):")
    for it in items[: args.show]:
        pool = [j for j in items if j is not it and j["text"] != it["text"]]
        scored = sorted(((fu_math.cosine(it["embedding"], j["embedding"]), j) for j in pool), key=lambda t: -t[0])[:3]
        same = ["=" if all(n["decision"].get(f) == it["decision"].get(f) for f in DECISION) else "≠" for _s, n in scored]
        print(f"  {it['text'][:48]!r:52} " + " | ".join(f"{s:.3f}{m} {n['text'][:30]!r}" for (s, n), m in zip(scored, same)))
    try:
        os.remove(clone)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
