"""Phase 86.3 — the per-turn cost of a deeper retrieval on aggregation questions: for N LongMemEval multi-session questions,
build the session like the agent, then time `engine.retrieve` at the base depth and at the candidate depth on the SAME
store (embeddings only, no chat). Reports retrieve ms and rendered-context chars per depth. Versioned output.
Usage: LME_DEPTHS=10,20 python scripts/diag_lme_depth_cost.py [n]"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import bench_longmemeval_e2 as H  # noqa: E402
from _bench_paths import write_versioned  # noqa: E402
from diag_lme_prod_context import throwaway_db  # noqa: E402
from hmgfu.retrieve import build_llm_context, user_fact_question  # noqa: E402
from hmgfu.utterance import past_cue  # noqa: E402

DEPTHS = [int(x) for x in os.environ.get("LME_DEPTHS", "10,20").split(",")]


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    data = json.load(open(H.DATA, encoding="utf-8"))
    qs = [q for q in data if q["question_type"] == "multi-session" and not str(q.get("question_id", "")).endswith("_abs")][:n]
    rows = []
    for qi, q in enumerate(qs):
        turns = H.session_turns(q); question = q["question"]
        db = throwaway_db(f"depthcost_{qi}.db")
        if os.path.exists(db):
            os.remove(db)
        e = H._make_engine(db, full=False)
        e.settings.set("excerpt_max_chars", 480)
        for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                         "runbooks_enabled": False, "prospective_enabled": False}.items():
            e.settings.set(key, val)
        H.ingest_session_like_agent(e, turns)
        row = {"qi": qi, "n_points": len(e.graph.points)}
        for d in DEPTHS:
            e.retrieve(question, limit=d)                                  # warm (embedding cache)
            t0 = time.perf_counter(); qp, ret, _ = e.retrieve(question, limit=d); ms = (time.perf_counter() - t0) * 1000
            canonical = e.facts.render_lines() + (e.facts.render_history_lines() if past_cue(question) else [])
            ctx, _ = build_llm_context(qp, e.graph, retrieved=ret, token_budget=e.settings.get("token_budget"), canonical=canonical,
                                       superseded=e.facts.superseded_values(), reverted=e.facts.reverted_values(),
                                       echo_free=user_fact_question(qp, e.facts), excerpt_chars=480,
                                       echo_scope=e.settings.get("echo_guard_scope"), echo_pairs=e.facts.active_pairs())
            row[f"ms_d{d}"] = round(ms, 1); row[f"ctx_chars_d{d}"] = len(ctx); row[f"n_retrieved_d{d}"] = len(ret)
        rows.append(row)
        e.graph.close(); e.client.close()
        try:
            os.remove(db)
        except OSError:
            pass
    print(f"\n=== 86.3 depth cost on {len(rows)} multi-session questions (points per session {min(r['n_points'] for r in rows)}–{max(r['n_points'] for r in rows)})")
    summary = {}
    for d in DEPTHS:
        ms = [r[f"ms_d{d}"] for r in rows]; ch = [r[f"ctx_chars_d{d}"] for r in rows]
        summary[d] = {"retrieve_ms_p50": statistics.median(ms), "retrieve_ms_max": max(ms), "ctx_chars_mean": round(statistics.mean(ch))}
        print(f"  depth {d:>2}: retrieve p50 {statistics.median(ms):.0f} ms · max {max(ms):.0f} ms · context {round(statistics.mean(ch))} chars mean (~{round(statistics.mean(ch) / 4)} tokens)")
    print("versioned:", write_versioned("lme_depth_cost", {"depths": DEPTHS, "summary": summary, "rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
