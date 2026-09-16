"""Phase 63: measure actual retrieved points, without canonical prompt injection."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from hmgfu import config, fu_math  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.taxonomy import node_class  # noqa: E402
from _bench_paths import throwaway_db  # noqa: E402


def present(text: str, needles: list[str]) -> list[str]:
    low = (text or "").lower()
    return [n for n in needles if re.search(
        r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])", low)]


def blob(point) -> str:
    return " ".join((point.title or "", point.summary or "", point.content or ""))


def analyse(items, truth: list[str], stale: list[str]) -> dict:
    truth_ranks = [i for i, item in enumerate(items, 1) if present(blob(item.point), truth)]
    stale_ranks = [i for i, item in enumerate(items, 1) if present(blob(item.point), stale)]
    return {
        "truth_rank": truth_ranks[0] if truth_ranks else None,
        "stale_rank": stale_ranks[0] if stale_ranks else None,
        "hit": bool(truth_ranks),
        "clean_hit": bool(truth_ranks) and not stale_ranks,
        "items": [{"id": x.point.id, "source": x.point.source, "status": x.point.status,
                   "score": round(x.score, 5), "reason": x.reason,
                   "text": blob(x.point)[:300]} for x in items],
    }


def main() -> int:
    src_path = Path(config.DB_PATH).resolve()
    clone = Path(throwaway_db("phase63_retrieval_clone.db")).resolve()
    if clone == src_path or clone.parent.name != "scratch":
        raise RuntimeError("refusing unsafe benchmark destination")
    if clone.exists():
        clone.unlink()
    src = sqlite3.connect(f"file:{src_path.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(clone))
    src.backup(dst); dst.close(); src.close()
    engine = AgentEngine(db_path=str(clone))
    cases = json.loads((ROOT / "scripts" / "truth_set.json").read_text(encoding="utf-8"))["cases"]
    cases = [case for case in cases if case["id"] != "no_two_values"]
    rows, started = [], time.perf_counter()
    for case in cases:
        q = case["queries"][0]
        query, fu_items, query_ms = engine.retrieve(q, limit=12)
        pool = [p for p in engine.graph.active_points()
                if node_class(p) not in ("skill", "tool", "directive", "session")]
        cosine_points = sorted(pool, key=lambda p: -fu_math.cosine(query.embedding, p.embedding))[:12]
        from hmgfu.models import RetrievedMemory
        cosine_items = [RetrievedMemory(point=p, score=fu_math.cosine(query.embedding, p.embedding),
                                        reason="pure embedding cosine") for p in cosine_points]
        row = {"id": case["id"], "query": q, "query_ms_reported": round(query_ms, 2),
               "fu": analyse(fu_items, case["truth"], case["stale"]),
               "cosine": analyse(cosine_items, case["truth"], case["stale"])}
        rows.append(row)
        print(case["id"], "FU", {k: row["fu"][k] for k in ("truth_rank", "stale_rank", "clean_hit")},
              "COS", {k: row["cosine"][k] for k in ("truth_rank", "stale_rank", "clean_hit")})
    summary = {"n": len(rows), "elapsed_s": round(time.perf_counter() - started, 1)}
    for arm in ("fu", "cosine"):
        summary[arm] = {
            "hit_at_12": sum(row[arm]["hit"] for row in rows),
            "clean_hit_at_12": sum(row[arm]["clean_hit"] for row in rows),
            "mrr": round(sum(1 / row[arm]["truth_rank"] if row[arm]["truth_rank"] else 0
                             for row in rows) / len(rows), 4),
        }
    out = {"summary": summary, "results": rows}
    path = ROOT / "outputs" / "phase63_actual_retrieval.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps(summary))
    print("wrote", path)
    engine.graph.close(); engine.client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
