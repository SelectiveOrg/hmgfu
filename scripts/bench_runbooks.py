"""Phase 75.1 — runbook recall bench on the sealed set (`scripts/oracles/runbooks_v1.json`).

Fresh throwaway DB, REAL embedder (bge-m3), nano OFF, no chat calls. The 12 plans are finalized through the real
path (session_plans + receipts → runbooks.on_plan_finalized), then every paraphrased request and every unrelated
request is embedded once and matched with the production `match_runbooks` at the configured floor.
  Hit@1        = the gold runbook is the top match (per request; reported per language too)
  false_surf   = an unrelated request surfaces ANY runbook (count / 12)
Secondary: the same two numbers across a floor sweep (0.50 … 0.80) — to READ the floor, not to tune it after the fact.
Gate (pre-registered in ROADMAP 75.1): Hit@1 ≥ 0.9 and false surfacing ≤ 1/12 at the configured floor.
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
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.retrieve import make_query_point  # noqa: E402
from hmgfu.runbooks import match_runbooks, on_plan_finalized  # noqa: E402

SET = os.path.join(ROOT, "scripts", "oracles", "runbooks_v1.json")
SWEEP = (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80)


def build_engine(corpus: dict):
    db = throwaway_db("bench_runbooks.db")
    if os.path.exists(db):
        os.remove(db)
    guard_scratch(db)
    e = AgentEngine(db_path=db)
    e.sensitizer.enabled = False
    e.settings.set("grader_enabled", False)
    e.settings.set("tail_async", False)
    e.settings.set("runbooks_enabled", True)
    gold = {}
    for p in corpus["plans"]:
        sid = f"bench-{p['id']}"
        plan = {"title": p["title"], "status": "active", "steps": [{"text": s["text"], "status": "pending"} for s in p["steps"]]}
        if p.get("request"):
            plan["request"] = p["request"]           # v2: the user's original words (75.1b)
        for i, s in enumerate(p["steps"]):
            rid = e.receipts.open(sid, i + 1, s["tool"], {"path": f"{p['id']}_{i}.txt"}, "write", "user_approval", i)
            e.receipts.close(rid, "ok", "done", {"files": [{"path": f"{p['id']}_{i}.txt", "sha256": "x", "bytes": 1}]})
            e.receipts.consume([rid], i)
            plan["steps"][i]["status"] = "done"
        if p["status"] == "failed":
            plan["steps"][-1]["status"] = "failed"
        plan["status"] = p["status"]
        e.session_plans.save(sid, plan)
        rb = on_plan_finalized(e, sid, plan)
        gold[p["id"]] = rb.id
    return e, gold


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=SET)
    args = ap.parse_args()
    corpus = json.load(open(args.set, encoding="utf-8"))
    t0 = time.time()
    e, gold = build_engine(corpus)
    floor = float(e.settings.get("runbook_match_floor"))
    rows = []
    for p in corpus["plans"]:
        for req in p["requests"]:
            q = make_query_point(req, e.embed, e.sensitizer)
            sweep = {}
            for f in SWEEP + (floor,):
                m = match_runbooks(e, q, f, limit=1)
                sweep[str(f)] = bool(m) and m[0][1].id == gold[p["id"]]
            top = match_runbooks(e, q, 0.0, limit=1)
            rows.append({"kind": "request", "plan": p["id"], "text": req, "lang": "pt" if any(ch in req for ch in "ãçéóê") or req.split()[0] in ("cria", "faz", "converte", "prepara", "renomeia", "limpa", "resume", "verifica", "arquiva") else "en",
                         "top_score": round(top[0][0], 3) if top else None, "top_is_gold": bool(top) and top[0][1].id == gold[p["id"]], "hit_by_floor": sweep})
    for req in corpus["unrelated"]:
        q = make_query_point(req, e.embed, e.sensitizer)
        top = match_runbooks(e, q, 0.0, limit=1)
        rows.append({"kind": "unrelated", "text": req, "top_score": round(top[0][0], 3) if top else None,
                     "surfaced_by_floor": {str(f): bool(match_runbooks(e, q, f, limit=1)) for f in SWEEP + (floor,)}})
    reqs = [r for r in rows if r["kind"] == "request"]; unrel = [r for r in rows if r["kind"] == "unrelated"]
    summary = {"floor": floor, "n_requests": len(reqs), "n_unrelated": len(unrel),
               "hit1": round(sum(r["hit_by_floor"][str(floor)] for r in reqs) / len(reqs), 3),
               "hit1_pt": round(sum(r["hit_by_floor"][str(floor)] for r in reqs if r["lang"] == "pt") / max(1, sum(r["lang"] == "pt" for r in reqs)), 3),
               "hit1_en": round(sum(r["hit_by_floor"][str(floor)] for r in reqs if r["lang"] == "en") / max(1, sum(r["lang"] == "en" for r in reqs)), 3),
               "top_is_gold_any_floor": round(sum(r["top_is_gold"] for r in reqs) / len(reqs), 3),
               "false_surfacing": sum(r["surfaced_by_floor"][str(floor)] for r in unrel),
               "sweep": {str(f): {"hit1": round(sum(r["hit_by_floor"][str(f)] for r in reqs) / len(reqs), 3),
                                  "false": sum(r["surfaced_by_floor"][str(f)] for r in unrel)} for f in SWEEP},
               "elapsed_s": round(time.time() - t0, 1)}
    print(f"[runbooks] floor {floor} · Hit@1 {summary['hit1']:.3f} (pt {summary['hit1_pt']:.3f} · en {summary['hit1_en']:.3f}) · "
          f"top-is-gold (no floor) {summary['top_is_gold_any_floor']:.3f} · false surfacing {summary['false_surfacing']}/{len(unrel)} · {summary['elapsed_s']}s")
    print("sweep:", " ".join(f"{f}:{v['hit1']:.2f}/{v['false']}" for f, v in summary["sweep"].items()))
    misses = [(r["plan"], r["text"], r["top_score"]) for r in reqs if not r["hit_by_floor"][str(floor)]]
    if misses:
        print("misses:", misses)
    fs = [(r["text"], r["top_score"]) for r in unrel if r["surfaced_by_floor"][str(floor)]]
    if fs:
        print("false surfacing:", fs)
    print("versioned:", write_versioned("runbooks", {"summary": summary, "rows": rows}))
    e.graph.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
