"""Exp 1b — LoCoMo temporal-retrieval thesis test (the field's ACTUAL domain). bge-m3, run-once.

FOUR GATES (all pre-registered in ROADMAP, all green):
 G1 falsifiability: a NEGATIVE on the temporal category (cat 2), with recency ALIVE (config A), falsifies
    the temporal-retrieval thesis — no escape hatch.
 G2 clean labels: LoCoMo ships `evidence` (gold turn ids per question) — not self-derived.
 G3 recency window: raw 2023 dates zero the recency term (exp(-1150/14)≈0). So run BOTH —
    A = REBASED timeline (single constant shift so last session ≈ now; PRESERVES inter-session gaps
        exactly, only moves the origin into the 14-day window) → recency ALIVE, mechanism tested;
    B = RAW dates → recency DEAD. The A−B gap = the recency term's contribution (attribution discipline).
    Isolation: one ingest; toggle only p.timestamp (in-memory) at query time, everything else constant.
 G4 per-category: cat2=temporal is THE decisive line (aggregate hides it, per the HotpotQA lesson).
    cat1=multi-hop, cat4=single-hop, cat3=open-domain, cat5=adversarial/unanswerable (EXCLUDED).
    cat2 has 24-42 Qs/conversation (321 total) → holds weight.

Rule 3: τ stays 14 days (production config). We move the DATA into the window, never the knob. If Fu
wins, it wins with the config already in production. BASE = fresh pure-cosine on bge-m3.

Run:  LOCOMO_N=3 HMGFU_EMBED_MODEL=bge-m3 .venv/Scripts/python scripts/bench_locomo.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config, fu_math                       # noqa: E402
from hmgfu.chat import HMGFuEngine                       # noqa: E402
from hmgfu.taxonomy import node_class                    # noqa: E402
from hmgfu.retrieve import make_query_point, retrieve_memory  # noqa: E402
from hmgfu.ingest import build_fu_edges, find_relation_candidates  # noqa: E402
from hmgfu.models import now_iso                         # noqa: E402
from _bench_paths import throwaway_db                    # noqa: E402

DATA = ROOT / "scratch" / "locomo10.json"
N = int(os.environ.get("LOCOMO_N", "3"))
KS = (5, 10, 20)
CAT_NAME = {"1": "multi-hop", "2": "TEMPORAL", "3": "open-domain", "4": "single-hop"}
_SKIP = ("skill", "tool", "directive", "session")


def parse_date(s: str) -> dt.datetime:
    # "1:56 pm on 8 May, 2023"
    return dt.datetime.strptime(s.strip(), "%I:%M %p on %d %B, %Y")


def main() -> int:
    if config.EMBED_MODEL != "bge-m3":
        print(f"WARN: EMBED_MODEL={config.EMBED_MODEL} (want bge-m3). Set HMGFU_EMBED_MODEL=bge-m3.")
    convs = json.load(open(DATA, encoding="utf-8"))[:N]
    now = dt.datetime.now()

    # accumulate per-(config, category) rank lists
    stats = {cfg: {c: [] for c in CAT_NAME} for cfg in ("base", "fuA", "fuB")}

    for ci, conv in enumerate(convs):
        c = conv["conversation"]
        sess_ids = sorted((k for k in c if k.startswith("session_") and not k.endswith("date_time")),
                          key=lambda k: int(k.split("_")[1]))
        dates = {s: parse_date(c[s + "_date_time"]) for s in sess_ids if c.get(s + "_date_time")}
        if not dates:
            continue
        last = max(dates.values())
        delta = now - last                      # single constant shift → gaps preserved exactly
        DB = throwaway_db(f"locomo_{ci}.db")
        if os.path.exists(DB):
            os.remove(DB)
        engine = HMGFuEngine(db_path=DB)
        if not engine.client.available():
            print("FAIL: Ollama unreachable")
            return 1
        g = engine.graph
        dia_to_id, raw_ts, reb_ts = {}, {}, {}
        for s in sess_ids:
            turns = c.get(s, [])
            if s not in dates:
                continue
            raw_iso = dates[s].replace(tzinfo=dt.timezone.utc).isoformat()
            reb_iso = (dates[s] + delta).replace(tzinfo=dt.timezone.utc).isoformat()
            for t in turns:
                txt = (t.get("text") or "").strip()
                did = t.get("dia_id")
                if not txt or not did:
                    continue
                p = engine.ingest(f"{t.get('speaker','')}: {txt}", source="user")
                p.timestamp = reb_iso           # REBASED (config A default); gaps preserved
                g.save_point(p)
                dia_to_id[did] = p.id
                raw_ts[p.id], reb_ts[p.id] = raw_iso, reb_iso
        # rebuild edges so kappa/temporal reflect the rebased timestamps (held CONSTANT across A/B)
        g._db.execute("DELETE FROM fu_edges"); g._db.commit(); g.edges.clear(); g._adjacency.clear()
        for p in g.active_points():
            for e in build_fu_edges(p, find_relation_candidates(p, g), g):
                g.save_edge(e)
        points = [p for p in g.active_points() if node_class(p) not in _SKIP]
        print(f"conv{ci}: {len(points)} turns, {len(sess_ids)} sessions, {len(conv['qa'])} QAs")

        def cosine_rank(qv, gid):
            ranked = sorted(points, key=lambda p: -fu_math.cosine(qv, p.embedding))
            return next((i + 1 for i, p in enumerate(ranked) if p.id == gid), 0)

        def fu_rank(q, gid):
            r = retrieve_memory(q, g, limit=30, min_score=0.0)
            return next((i + 1 for i, rm in enumerate(r) if rm.point.id == gid), 0)

        def set_ts(which):
            for p in g.active_points():
                if p.id in raw_ts:
                    p.timestamp = raw_ts[p.id] if which == "raw" else reb_ts[p.id]

        for qa in conv["qa"]:
            cat = str(qa.get("category"))
            if cat not in CAT_NAME:            # cat 5 adversarial/unanswerable excluded
                continue
            ev = qa.get("evidence") or []
            if isinstance(ev, str):
                try: ev = json.loads(ev.replace("'", '"'))
                except Exception: ev = []
            gold = [dia_to_id[e] for e in ev if e in dia_to_id]
            if not gold:
                continue
            q = make_query_point(qa["question"], engine.embed, engine.sensitizer)
            # BASE (cosine, timestamp-independent) — best rank over the gold turns
            base = min((cosine_rank(q.embedding, gid) or 999) for gid in gold)
            # Fu-A (recency ALIVE — rebased ts, as ingested)
            set_ts("reb"); fuA = min((fu_rank(q, gid) or 999) for gid in gold)
            # Fu-B (recency DEAD — raw 2023 ts); restore after
            set_ts("raw"); fuB = min((fu_rank(q, gid) or 999) for gid in gold)
            set_ts("reb")
            stats["base"][cat].append(base)
            stats["fuA"][cat].append(fuA)
            stats["fuB"][cat].append(fuB)
        engine.graph.close(); engine.client.close()
        try: os.remove(DB)
        except PermissionError: pass

    # ---- report PER CATEGORY (cat2 temporal = decisive) ----
    def recall(ranks, k): return sum(1 for r in ranks if 0 < r <= k) / len(ranks) if ranks else 0.0
    def mrr(ranks): return sum((1.0 / r) if r else 0.0 for r in ranks) / len(ranks) if ranks else 0.0

    print(f"\n=== LoCoMo retrieval (bge-m3, N={N} convs) — BASE=cosine  fuA=recency-alive  fuB=recency-dead ===")
    print("(cat2 TEMPORAL is the decisive line; A−B gap = the recency term's contribution)\n")
    for cat in ("2", "1", "4", "3"):
        name = CAT_NAME[cat]
        n = len(stats["base"][cat])
        if not n:
            continue
        mark = "  <<< DECISIVE" if cat == "2" else ""
        print(f"[cat{cat} {name:>11}] n={n:4d}  MRR base {mrr(stats['base'][cat]):.3f} "
              f"fuA {mrr(stats['fuA'][cat]):.3f} fuB {mrr(stats['fuB'][cat]):.3f}{mark}")
        for k in KS:
            print(f"{'':>20} recall@{k:<2} base {recall(stats['base'][cat],k):.3f} "
                  f"fuA {recall(stats['fuA'][cat],k):.3f} fuB {recall(stats['fuB'][cat],k):.3f}")
    print("\nVERDICT rule (Gate 1): on cat2, if fuA (recency alive, fair window) does NOT beat BASE, "
          "the temporal-retrieval thesis is FALSIFIED. The fuA−fuB delta shows whether recency did the work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
