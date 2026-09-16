"""Phase 59 Phase-B — the DECISIVE architecture measurement + a decoupled-append A/B (HotpotQA, bge-m3).

Context: the FUSED memory_score loses MRR to pure cosine on HotpotQA because its relational/lexical/
distance terms dilute the cosine ranking on a static corpus (diag_fu_vs_cosine.py). Trailblazer's
correction: that argues for DECOUPLING (rank by cosine, append the Fu entity-hop BELOW the winners —
append-only, can only add), not surrender.

THE decisive number (Trailblazer): the PURE-COSINE rank of the missing bridge gold in the cases where
cosine misses it in top-10. 11-40 => an append/insert policy can pull it up (bridge is winnable);
100+ => even the Fu-hop can't reach it (append only TIES base on bridge, but still recovers the fused
TAX on no-hop comparison cases). This harness reports that distribution FIRST.

Then a run-once A/B on the SAME ingested corpus:
  BASE     = pure cosine top-k.
  DECOUPLE = cosine top-P primary (no reorder) + Fu strong-neighbour expansion of the winners appended
             below. Measured at k in {10,20,30} per type. NO tuning.

Runs on bge-m3 (post-promotion): set HMGFU_EMBED_MODEL=bge-m3 so the fresh corpus is embedded in the
SAME space as production — a moved baseline would invalidate the comparison.

Run:  HOTPOT_N=100 HMGFU_EMBED_MODEL=bge-m3 .venv/Scripts/python scripts/bench_decouple_hotpot.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config, fu_math                 # noqa: E402
from hmgfu.chat import HMGFuEngine                 # noqa: E402
from hmgfu.taxonomy import node_class              # noqa: E402
from hmgfu.retrieve import make_query_point        # noqa: E402
from _bench_paths import throwaway_db              # noqa: E402

SLICE = ROOT / "scratch" / "hotpot_slice.json"
N = int(os.environ.get("HOTPOT_N", "100"))
KS = (10, 20, 30)
PRIMARY = 10   # cosine winners kept at the top under DECOUPLE (no reorder)
_SKIP = ("skill", "tool", "directive", "session")


def para_doc(title, sentences):
    return f"{title}. " + " ".join(s.strip() for s in sentences).strip()


def main() -> int:
    if config.EMBED_MODEL != "bge-m3":
        print(f"WARN: EMBED_MODEL={config.EMBED_MODEL} (want bge-m3 to match production space). "
              "Set HMGFU_EMBED_MODEL=bge-m3.")
    rows = [r["row"] for r in json.load(open(SLICE, encoding="utf-8"))["rows"]][:N]
    DB = throwaway_db("decouple_hotpot.db")
    if os.path.exists(DB):
        os.remove(DB)
    engine = HMGFuEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1
    print(f"EMBED_MODEL={config.EMBED_MODEL}  ingesting {len(rows)} HotpotQA questions...")
    title_to_id = {}
    for r in rows:
        for t, s in zip(r["context"]["title"], r["context"]["sentences"]):
            if t not in title_to_id:
                title_to_id[t] = engine.ingest(para_doc(t, s), source="user").id
    g = engine.graph
    points = [p for p in g.active_points() if node_class(p) not in _SKIP]
    print(f"corpus: {len(points)} paragraphs\n")

    def cosine_ranked(q):
        return sorted(points, key=lambda p: -fu_math.cosine(q.embedding, p.embedding))

    def decouple_ranked(q):
        cos = cosine_ranked(q)
        primary = cos[:PRIMARY]
        seen = {p.id for p in primary}
        appended = []
        for p in primary:                       # append Fu strong-neighbours BELOW the cosine winners
            for nb, _e in g.strong_neighbours(
                    p.id, min_kappa=config.EXPANSION_MIN_KAPPA,
                    min_trust=config.EXPANSION_MIN_TRUST, depth=config.EXPANSION_DEPTH):
                if nb.id not in seen and node_class(nb) not in _SKIP:
                    seen.add(nb.id)
                    appended.append(nb)
        # everything else keeps cosine order after the appended block
        rest = [p for p in cos[PRIMARY:] if p.id not in seen]
        return primary + appended + rest

    def rank_of(pid, ranked):
        return next((i + 1 for i, p in enumerate(ranked) if p.id == pid), 0)

    # ---- run both systems once per question ----
    recs = []
    missing_bridge_cos_rank = []   # THE decisive distribution
    for r in rows:
        q = make_query_point(r["question"], engine.embed, engine.sensitizer)
        cos = cosine_ranked(q)
        dec = decouple_ranked(q)
        gold = [title_to_id[t] for t in dict.fromkeys(r["supporting_facts"]["title"]) if t in title_to_id]
        cos_ranks = {gid: rank_of(gid, cos) for gid in gold}
        dec_ranks = {gid: rank_of(gid, dec) for gid in gold}
        recs.append({"type": r["type"], "cos": cos_ranks, "dec": dec_ranks})
        if r["type"] == "bridge":
            for gid, cr in cos_ranks.items():
                if cr > 10:                    # cosine missed this gold in top-10
                    missing_bridge_cos_rank.append(cr)

    # ---- THE decisive measurement ----
    print("=== DECISIVE: pure-cosine rank of BRIDGE golds that cosine misses in top-10 ===")
    if missing_bridge_cos_rank:
        buckets = {"11-20": 0, "21-40": 0, "41-100": 0, "101-500": 0, "500+/none": 0}
        for cr in missing_bridge_cos_rank:
            k = ("11-20" if cr <= 20 else "21-40" if cr <= 40 else "41-100" if cr <= 100
                 else "101-500" if cr <= 500 else "500+/none")
            buckets[k] += 1
        n = len(missing_bridge_cos_rank)
        med = sorted(missing_bridge_cos_rank)[n // 2]
        print(f"  n={n} missing bridge golds | median cosine rank={med}")
        for b, c in buckets.items():
            bar = "█" * int(40 * c / n)
            print(f"    rank {b:>9}: {c:>3} ({c/n:.0%}) {bar}")
        winnable = sum(1 for cr in missing_bridge_cos_rank if cr <= 40) / n
        print(f"  => {winnable:.0%} sit at cosine-rank <=40 (append/insert HEADROOM); "
              "the rest need too deep a hop (append only ties BASE there).")
    else:
        print("  none — cosine already gets every bridge gold in top-10 on this slice.")

    # ---- A/B: BASE (cosine) vs DECOUPLE (cosine+append) at k in KS ----
    def recall_at(recs_sub, key, k):
        tot = 0.0
        for r in recs_sub:
            ranks = r[key].values()
            tot += sum(1 for x in ranks if 0 < x <= k) / len(ranks)
        return tot / len(recs_sub) if recs_sub else 0.0

    def mrr(recs_sub, key):
        tot = 0.0
        for r in recs_sub:
            best = min((x for x in r[key].values() if x > 0), default=0)
            tot += (1.0 / best) if best else 0.0
        return tot / len(recs_sub) if recs_sub else 0.0

    print("\n=== BASE (cosine) vs DECOUPLE (cosine + Fu-append) ===")
    for label, sub in (("OVERALL", recs),
                       ("bridge", [r for r in recs if r["type"] == "bridge"]),
                       ("comparison", [r for r in recs if r["type"] == "comparison"])):
        line = f"[{label:>11}] n={len(sub):3d} | MRR base {mrr(sub,'cos'):.3f} dec {mrr(sub,'dec'):.3f}"
        for k in KS:
            line += f" | recall@{k} base {recall_at(sub,'cos',k):.3f} dec {recall_at(sub,'dec',k):.3f}"
        print(line)
    print("\nDECOUPLE keeps cosine's top-10 (so recall@10 == base by construction); the append only "
          "helps at deeper k IF a missing gold is a Fu-neighbour of a cosine winner. A positive "
          "recall@20/@30 delta on bridge = the field earns its keep as an APPEND, not as a ranking term.")

    engine.graph.close()
    engine.client.close()
    try:
        os.remove(DB)
    except PermissionError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
