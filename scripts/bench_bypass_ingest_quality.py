"""Phase 79.6 — ingest quality on the turns the pre-router claims: the deterministic heuristic extraction vs the nano
extraction (route off) on the sealed routing set's claimed turns. Reported, not gated: keyword / entity / topic overlap
(Jaccard), summary lengths, and the nano's own list-field emptiness rate (the fields the heuristic backfills today)."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.pre_router import pre_route  # noqa: E402
from hmgfu.sensitizer import heuristic_extract  # noqa: E402

ORACLE = os.path.join(ROOT, "scripts", "oracles", "routing_v1.json")


def jac(a, b):
    a, b = {str(x).lower() for x in a or []}, {str(x).lower() for x in b or []}
    return (len(a & b) / len(a | b)) if (a | b) else 1.0


def main() -> int:
    turns = json.load(open(ORACLE, encoding="utf-8"))["turns"]
    clone = os.path.join(SCRATCH, f"bypass_ingest_clone_{os.getpid()}.db")
    clone_live(clone)
    e = AgentEngine(db_path=clone)
    catalog = list(e.sensitizer._action_catalog())
    rows = []
    for t in turns:
        if pre_route(t["text"], catalog, e.facts) is None:
            continue
        nano = e.sensitizer.extract(t["text"], route=False)
        heur = heuristic_extract(t["text"])
        rows.append({"id": t["id"], "class": t["class"], "nano_extractor": nano.get("extractor"),
                     "kw_jaccard": round(jac(nano.get("keywords"), heur.get("keywords")), 3),
                     "ent_jaccard": round(jac(nano.get("entities"), heur.get("entities")), 3),
                     "topic_jaccard": round(jac(nano.get("topics"), heur.get("topics")), 3),
                     "nano_empty_lists": sum(1 for k in ("keywords", "entities", "topics") if not nano.get(k)),
                     "summary_nano": (nano.get("summary") or "")[:80], "summary_heur": (heur.get("summary") or "")[:80],
                     "type_nano": nano.get("type"), "type_heur": heur.get("type")})
    n = len(rows)
    mean = lambda k: (sum(r[k] for r in rows) / n) if n else 0.0
    print(f"INGEST QUALITY on {n} claimed turns · keyword Jaccard {mean('kw_jaccard'):.2f} · entity {mean('ent_jaccard'):.2f} · "
          f"topic {mean('topic_jaccard'):.2f} · nano empty list fields per turn {mean('nano_empty_lists'):.2f} · "
          f"type agreement {sum(1 for r in rows if r['type_nano'] == r['type_heur'])}/{n}")
    for r in rows:
        print(f"  {r['id']} {r['class']:>18} kw {r['kw_jaccard']:.2f} ent {r['ent_jaccard']:.2f} · nano: {r['summary_nano']!r} · heur: {r['summary_heur']!r}")
    print("versioned:", write_versioned("bypass_ingest_quality", {"rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
