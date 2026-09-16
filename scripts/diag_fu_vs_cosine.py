"""Phase 59 diagnostic — PROVE which memory_score term demotes the gold vs pure cosine (HotpotQA).

Exp 1 showed Fu loses MRR to cosine (0.825 vs 0.936). The analytical claim (from the weights): the
non-semantic terms dilute the cosine signal on a static corpus. This CONFIRMS it empirically: for
every query where Fu ranks the gold LOWER than cosine does, we compare the WEIGHTED per-term
contributions of the gold vs the distractor Fu promoted above it. The term with the largest mean
(distractor − gold) contribution is what flipped the ranking. No tuning — measurement only.

Run:  HOTPOT_N=60 .venv/Scripts/python scripts/diag_fu_vs_cosine.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config, fu_math                              # noqa: E402
from hmgfu.chat import HMGFuEngine                             # noqa: E402
from hmgfu.retrieve import make_query_point, retrieve_memory   # noqa: E402
from _bench_paths import throwaway_db                          # noqa: E402

SLICE = ROOT / "scratch" / "hotpot_slice.json"
N = int(os.environ.get("HOTPOT_N", "60"))
WEIGHTS = config.MEMORY_SCORE_WEIGHTS


def para_doc(title, sentences):
    return f"{title}. " + " ".join(s.strip() for s in sentences).strip()


def weighted_contributions(q, p, edge):
    """Per-term signed contribution to raw memory_score (weight × component × sign), × factor —
    exactly what the ranking summed. Lets us see which term actually moved the score."""
    c = fu_math.memory_score_components(q, p, edge)
    factor = c["_factor"]
    out = {}
    for k in WEIGHTS:
        sign = -1.0 if k.endswith("Penalty") else 1.0
        out[k] = WEIGHTS[k] * c[k] * sign * factor
    out["_total"] = sum(out.values())
    return out


def main() -> int:
    rows = [r["row"] for r in json.load(open(SLICE, encoding="utf-8"))["rows"]][:N]
    DB = throwaway_db("diag_fu.db")
    if os.path.exists(DB):
        os.remove(DB)
    engine = HMGFuEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1

    print(f"Ingesting {len(rows)} HotpotQA questions...")
    title_to_id = {}
    for r in rows:
        for t, s in zip(r["context"]["title"], r["context"]["sentences"]):
            if t not in title_to_id:
                title_to_id[t] = engine.ingest(para_doc(t, s), source="user").id
    g = engine.graph
    points = g.active_points()
    print(f"corpus: {len(points)} paragraphs\n")

    def cosine_rank(q, target_id):
        ranked = sorted(points, key=lambda p: -fu_math.cosine(q.embedding, p.embedding))
        return next((i + 1 for i, p in enumerate(ranked) if p.id == target_id), 0)

    deltas = {k: [] for k in list(WEIGHTS) + ["_total"]}
    demotions = 0
    checked = 0
    for r in rows:
        q = make_query_point(r["question"], engine.embed, engine.sensitizer)
        fu = retrieve_memory(q, g, limit=30, min_score=0.0)
        fu_ids = [rm.point.id for rm in fu]
        fu_by_id = {rm.point.id: rm for rm in fu}
        for title in dict.fromkeys(r["supporting_facts"]["title"]):
            gid = title_to_id.get(title)
            if gid is None:
                continue
            checked += 1
            fu_rank = (fu_ids.index(gid) + 1) if gid in fu_ids else 999
            base_rank = cosine_rank(q, gid)
            # a DEMOTION: cosine ranked the gold higher (smaller rank) than Fu did
            if base_rank and fu_rank > base_rank and gid in fu_by_id:
                # the distractor Fu placed directly ABOVE the gold (the one that displaced it)
                gpos = fu_ids.index(gid)
                promoter = next((fu_by_id[pid] for pid in fu_ids[:gpos]
                                 if pid not in {title_to_id.get(t) for t in r["supporting_facts"]["title"]}),
                                None)
                if promoter is None:
                    continue
                demotions += 1
                gold_rm = fu_by_id[gid]
                gc = weighted_contributions(q, gold_rm.point, gold_rm.edge)
                dc = weighted_contributions(q, promoter.point, promoter.edge)
                for k in deltas:
                    deltas[k].append(dc[k] - gc[k])   # promoter − gold, per weighted term

    print(f"=== DEMOTION ANALYSIS ===  gold instances checked: {checked}, "
          f"Fu-demoted-below-cosine: {demotions}\n")
    if not demotions:
        print("No demotions found in this slice.")
    else:
        print(f"{'term':>18}  {'mean Δ (promoter − gold)':>26}   interpretation")
        ordered = sorted(((k, sum(v) / len(v)) for k, v in deltas.items() if k != "_total"),
                         key=lambda t: -abs(t[1]))
        for k, mean in ordered:
            bar = "█" * min(40, int(abs(mean) * 400))
            tag = "  ← promotes distractor" if mean > 0 else ("  (favours gold)" if mean < 0 else "")
            print(f"{k:>18}  {mean:>+26.4f}   {bar}{tag}")
        tot = sum(deltas["_total"]) / len(deltas["_total"])
        print(f"\n{'_total':>18}  {tot:>+26.4f}   (net score gap the promoter had over the gold)")
        print("\nThe term with the largest POSITIVE mean Δ is what tips the promoter above the gold —"
              "\ni.e. the specific part of memory_score that beats pure cosine's clean ranking.")

    engine.graph.close()
    engine.client.close()
    try:
        os.remove(DB)
    except PermissionError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
