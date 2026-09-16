"""Experiment 1 (Phase 59): does the Fu FIELD beat plain cosine RAG on data we DON'T control?

Phase 30.1 proved "Fu > RAG" only on a 26-point corpus WE wrote (and 2 of its 4 categories are
things cosine literally cannot do). This runs the IDENTICAL comparison — production retrieve_memory()
vs plain cosine top-k — on a PUBLIC, foreign corpus: HotpotQA (multi-hop QA, validation/distractor).

Corpus = every unique context paragraph across N HotpotQA questions, ingested with the REAL sensitizer
(so entity-link edges form — otherwise Fu degrades to cosine and the test is rigged against it).
Query = the question. Targets = the gold supporting paragraphs (supporting_facts.title).

NUANCE (why per-type, not one number): HotpotQA has NO time axis, so recency/contradiction — where
Fu wins by construction on our own bench — are INAPPLICABLE here. What HotpotQA fairly tests is the
RELATIONAL / multi-hop claim: expand_through_fu reaching a gold paragraph that is NOT lexically close
to the question, via an entity edge. So we isolate the BRIDGE gold (the lower-cosine of the 2 gold,
i.e. the one reached by the hop) and report ITS recall separately — that is the real Fu-vs-RAG test.

HARD RULE (external-validity): run ONCE, record, walk away. Do NOT tune any weight to win this — the
moment we do, we've turned an external test back into a closed loop (Rule 3). Foreign data only.

Data: scratch/hotpot_slice.json (fetched from HF datasets-server; re-fetch note at bottom). Run:
  HOTPOT_N=100 .venv/Scripts/python scripts/bench_ab_hotpot.py
"""

from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import config, fu_math          # noqa: E402
from hmgfu.chat import HMGFuEngine          # noqa: E402
from hmgfu.retrieve import make_query_point, retrieve_memory  # noqa: E402
from _bench_paths import throwaway_db       # noqa: E402

SLICE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scratch", "hotpot_slice.json")
N = int(os.environ.get("HOTPOT_N", "100"))
TOP_K = 10       # report recall/hit @ this depth
LIMIT = 20       # retrieve this deep so rank is measurable beyond k for both systems


def para_doc(title: str, sentences) -> str:
    return f"{title}. " + " ".join(s.strip() for s in sentences).strip()


def rank_of(pid: str, ranked) -> int:
    for i, p in enumerate(ranked):
        if p.id == pid:
            return i + 1
    return 0   # not found within LIMIT


def main() -> int:
    rows = [r["row"] for r in json.load(open(SLICE, encoding="utf-8"))["rows"]][:N]
    DB = throwaway_db("hotpot_ab.db")
    if os.path.exists(DB):
        os.remove(DB)
    engine = HMGFuEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1

    print(f"Ingesting HotpotQA corpus (real embeddings + real sensitizer) for {len(rows)} questions...")
    title_to_id = {}
    for r in rows:
        ctx = r["context"]
        for title, sents in zip(ctx["title"], ctx["sentences"]):
            if title not in title_to_id:
                title_to_id[title] = engine.ingest(para_doc(title, sents), source="user").id
    points = engine.graph.active_points()
    print(f"Corpus: {len(points)} unique paragraphs from {len(rows)} questions\n")

    def cosine_topk(q, k=LIMIT):
        return [p for p, _ in sorted(((p, fu_math.cosine(q.embedding, p.embedding)) for p in points),
                                     key=lambda t: -t[1])[:k]]

    rec = []   # per-question records
    for idx, r in enumerate(rows):
        q = make_query_point(r["question"], engine.embed, engine.sensitizer)
        fu = [rm.point for rm in retrieve_memory(q, engine.graph, limit=LIMIT, min_score=0.0)]
        base = cosine_topk(q)
        gold = [title_to_id[t] for t in dict.fromkeys(r["supporting_facts"]["title"]) if t in title_to_id]
        # bridge gold = the gold paragraph LEAST similar to the question (reached via the hop, not
        # directly matchable); anchor = the more-similar one. Only meaningful for 2-gold bridge Qs.
        bridge = None
        if len(gold) == 2:
            gc = {g: fu_math.cosine(q.embedding, engine.graph.points[g].embedding) for g in gold}
            bridge = min(gc, key=gc.get)
        rec.append({
            "type": r["type"],
            "fu": [rank_of(g, fu) for g in gold],
            "base": [rank_of(g, base) for g in gold],
            "bridge_fu": rank_of(bridge, fu) if bridge else None,
            "bridge_base": rank_of(bridge, base) if bridge else None,
        })
        if (idx + 1) % 20 == 0:
            print(f"  ...{idx + 1}/{len(rows)} queries done")

    def hit(rank):          # found within TOP_K
        return 1 if 0 < rank <= TOP_K else 0

    def report(records, label):
        n = len(records)
        if not n:
            return
        # support recall@k = fraction of gold paragraphs found in top-k, averaged per question
        fu_rec = sum(sum(hit(x) for x in r["fu"]) / len(r["fu"]) for r in records) / n
        bs_rec = sum(sum(hit(x) for x in r["base"]) / len(r["base"]) for r in records) / n
        # full support@k = BOTH gold in top-k
        fu_full = sum(1 for r in records if all(hit(x) for x in r["fu"])) / n
        bs_full = sum(1 for r in records if all(hit(x) for x in r["base"])) / n
        # MRR of the FIRST gold found
        def mrr(key):
            tot = 0.0
            for r in records:
                best = min((x for x in r[key] if x > 0), default=0)
                tot += (1.0 / best) if best else 0.0
            return tot / n
        print(f"[{label:>11}] n={n:3d} | support_recall@{TOP_K}  FU {fu_rec:.3f}  BASE {bs_rec:.3f}"
              f"  | full_support@{TOP_K}  FU {fu_full:.3f}  BASE {bs_full:.3f}"
              f"  | MRR  FU {mrr('fu'):.3f}  BASE {mrr('base'):.3f}")

    print("=== A/B ON FOREIGN DATA (HotpotQA) — Fu retrieve_memory vs plain cosine top-k ===")
    report(rec, "OVERALL")
    report([r for r in rec if r["type"] == "bridge"], "bridge")
    report([r for r in rec if r["type"] == "comparison"], "comparison")

    # THE multi-hop signal: recall of the BRIDGE gold (the hop target), bridge questions only
    br = [r for r in rec if r["bridge_fu"] is not None and r["type"] == "bridge"]
    if br:
        fu_bridge = sum(hit(r["bridge_fu"]) for r in br) / len(br)
        bs_bridge = sum(hit(r["bridge_base"]) for r in br) / len(br)
        print(f"\n>>> BRIDGE-HOP recall@{TOP_K} (the gold reached via the entity hop, NOT lexically "
              f"close to Q): FU {fu_bridge:.3f} vs BASE {bs_bridge:.3f}  (n={len(br)})")
        print("    This is the ONE number that isolates whether expand_through_fu beats plain vector "
              "similarity on foreign multi-hop retrieval. Δ>0 = the field earns its keep here.")

    engine.graph.close()
    engine.client.close()
    try:
        os.remove(DB)
    except PermissionError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Re-fetch the slice (foreign data, never edit by hand):
#   curl -s "https://datasets-server.huggingface.co/rows?dataset=hotpotqa/hotpot_qa&config=distractor&split=validation&offset=0&length=100" -o scratch/hotpot_slice.json
