"""Phase 73.1 — latency / provider-call baseline for one agent turn, on a CLONE, under the project venv.

A FIXED 12-turn script (4 recall questions on real slots, 2 fact statements, 2 read-only tool turns, 2 chatter,
2 plan turns), repeated `--reps` times on fresh engines (the model stays warm: one untimed warm-up turn per engine
absorbs the cold model load, which is a property of the host, not of the turn). Every turn's `timings` (73.0:
stages, model calls by role, tokens) is collected from the agent response; the report gives p50/p95 per turn class
for total and time-to-reply, provider calls per turn by role, tokens per turn, and the mean stage breakdown.
Versioned output (M0.1); `guard_scratch` refuses the production database; `environment_warnings` are printed.

The fact statements RESTATE values that already hold on the clone (they change nothing) — the clone is disposable
anyway, but the script must stay valid as a live replay too.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, guard_scratch, throwaway_db, write_versioned  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402

WARMUP = "Hello."
SCRIPT = [
    ("recall", "What is my name?"),
    ("recall", "Where do I live?"),
    ("recall", "What is my favorite color?"),
    ("recall", "What's my favorite drink?"),
    ("fact", "My favorite color is chartreuse."),
    ("fact", "Remember that my favorite drink is ginger tea."),
    ("tool", "What files are in the workspace right now?"),
    ("tool", "What time is it now?"),
    ("chatter", "Thanks, that's helpful."),
    ("chatter", "Obrigado, era só isso."),
    ("plan", "Plan how you would organise my notes into three files, but do not create anything yet."),
    ("plan", "Actually, cancel that plan."),
]



# 79.4: --set key=value (repeatable) → applied to every engine this bench builds (clone only)
EXTRA_SETTINGS: dict = {}


def apply_extra_settings(engine) -> None:
    for key, raw in EXTRA_SETTINGS.items():
        cur = engine.settings.get(key)
        if isinstance(cur, bool):
            val = str(raw).strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, int):
            val = int(raw)
        elif isinstance(cur, float):
            val = float(raw)
        else:
            val = raw
        engine.settings.set(key, val)


def parse_set_args(items) -> None:
    for item in items or []:
        key, _, val = item.partition("=")
        EXTRA_SETTINGS[key.strip()] = val.strip()

TAIL_ASYNC = None      # 81.3: the EFFECTIVE tail mode of the measured engines, labelled in the summary


def fresh_engine(clone: str, workspace: str):
    global TAIL_ASYNC
    from hmgfu.agent import AgentEngine
    e = AgentEngine(db_path=clone)
    apply_extra_settings(e)                                  # 79.4: candidate configuration on the clone
    TAIL_ASYNC = bool(e.settings.get("tail_async"))
    e.settings.set("workspace_dir", workspace)
    e.settings.set("full_dream_every_n_turns", 0)          # scheduled dreams are measured separately (73.2)
    return e


def pct(values, q):
    """81.3: nearest-rank quantile (p50 of two values = the larger, never the smaller; p95 of 12 = the 12th) — reported with n and max."""
    import math
    if not values:
        return None
    s = sorted(values)
    k = max(1, min(len(s), int(math.ceil(q * len(s)))))
    return round(s[k - 1], 1)


def summarise(rows):
    by_class = {}
    for r in rows:
        by_class.setdefault(r["cls"], []).append(r)
    out = {}
    for cls, rs in sorted(by_class.items()):
        totals = [r["total_ms"] for r in rs]
        replies = [r["reply_ms"] for r in rs if r["reply_ms"] is not None]
        calls = [r["model_calls"] for r in rs]
        out[cls] = {"n": len(rs), "total_p50_ms": pct(totals, 0.5), "total_p95_ms": pct(totals, 0.95),
                    "reply_p50_ms": pct(replies, 0.5), "reply_p95_ms": pct(replies, 0.95),
                    "calls_mean": round(statistics.mean(calls), 2) if calls else None,
                    "calls_by_role_mean": {k: round(statistics.mean(r["calls"].get(k, 0) for r in rs), 2)
                                           for k in ("chat", "nano", "embed", "other")},
                    "tokens_mean": round(statistics.mean(r["tokens"]["prompt"] + r["tokens"]["eval"] for r in rs)),
                    "stages_mean_ms": {k: round(statistics.mean(r["stages"].get(k, 0.0) for r in rs), 1)
                                       for k in ("retrieve", "prepare", "chat", "gates", "ingest", "grade", "dream")}}
    all_total = [r["total_ms"] for r in rows]
    all_reply = [r["reply_ms"] for r in rows if r["reply_ms"] is not None]
    out["_all"] = {"n": len(rows), "total_p50_ms": pct(all_total, 0.5), "total_p95_ms": pct(all_total, 0.95),
                   "reply_p50_ms": pct(all_reply, 0.5), "reply_p95_ms": pct(all_reply, 0.95),
                   "calls_mean": round(statistics.mean(r["model_calls"] for r in rows), 2),
                   "tail_p50_ms": pct([r.get("tail_ms", 0.0) for r in rows], 0.5),
                   "turns_with_le_2_calls": sum(1 for r in rows if r["model_calls"] <= 2),
                   "before_reply_mean": round(statistics.mean(r["calls_before_reply"] for r in rows if r.get("calls_before_reply") is not None), 2)
                   if any(r.get("calls_before_reply") is not None for r in rows) else None,
                   "turns_with_le_3_before_reply": sum(1 for r in rows if (r.get("calls_before_reply") or 99) <= 3),
                   "n_turns": len(rows), "total_max_ms": max(r["total_ms"] for r in rows), "quantile_method": "nearest-rank"}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--db", default=None, help="source DB to clone (default: live config.DB_PATH)")
    ap.add_argument("--set", action="append", default=[], help="79.4: key=value applied to the clone settings (repeatable)")
    ap.add_argument("--only", default=None, help="comma-separated classes (recall,fact,tool,chatter,plan)")
    ap.add_argument("--tail-async", action="store_true", help="73.2(a) arm: tail on a worker; total_ms = user-visible, tail_ms measured")
    args = ap.parse_args()
    parse_set_args(args.set)
    only = set(args.only.split(",")) if args.only else None
    rows = []
    t0 = time.time()
    for rep in range(1, args.reps + 1):
        clone = throwaway_db(f"bench_latency_{rep}.db")
        clone_live(clone, args.db)
        workspace = tempfile.mkdtemp(prefix="bench_latency_ws_", dir=SCRATCH)
        guard_scratch(clone, workspace)                                          # M0.2
        e = fresh_engine(clone, workspace)
        if args.tail_async:
            e.settings.set("tail_async", True)
        sid = e.sessions.ensure_session(None)
        e.agent_chat(WARMUP, session_id=sid)                                     # warm-up: cold model load excluded
        for cls, text in SCRIPT:
            if only and cls not in only:
                continue
            r = e.agent_chat(text, session_id=sid)
            tw = time.time()
            from hmgfu.turn_tail import wait_for_tail
            waited = wait_for_tail(e)                                            # async arm: measure the tail separately
            tail_ms = round((time.time() - tw) * 1000, 1) if waited else 0.0
            t = r.get("timings") or {}
            row = {"rep": rep, "cls": cls, "text": text, "total_ms": t.get("total_ms"), "reply_ms": t.get("reply_ms"),
                   "model_calls": t.get("model_calls", 0), "calls": t.get("calls", {}), "calls_ms": t.get("calls_ms", {}),
                   "calls_before_reply": t.get("calls_before_reply"),                    # 80.2
                   "tokens": t.get("tokens", {"prompt": 0, "eval": 0}), "stages": t.get("stages", {}),
                   "tail_ms": tail_ms,
                   "tools": [x.get("name") for x in r.get("tool_trace") or []], "reply": (r.get("response") or "")[:160]}
            rows.append(row)
            print(f"  [rep {rep}] {cls:8s} total {row['total_ms']/1000:6.1f}s reply {((row['reply_ms'] or 0)/1000):6.1f}s tail {tail_ms/1000:5.1f}s "
                  f"calls {row['model_calls']:2d} {row['calls']} tokens {row['tokens']}  {text[:40]!r}")
        e.graph.close()
        shutil.rmtree(workspace, ignore_errors=True)
    summary = summarise(rows)
    a = summary["_all"]
    print(f"\nLATENCY n={a['n']} · total p50 {a['total_p50_ms']/1000:.1f}s p95 {a['total_p95_ms']/1000:.1f}s · "
          f"reply p50 {a['reply_p50_ms']/1000:.1f}s p95 {a['reply_p95_ms']/1000:.1f}s · calls/turn {a['calls_mean']} · "
          f"turns ≤2 calls {a['turns_with_le_2_calls']}/{a['n']} · calls BEFORE reply mean {a['before_reply_mean']} · "
          f"turns ≤3 before reply {a['turns_with_le_3_before_reply']}/{a['n']} · n {a['n_turns']} · max {a['total_max_ms']/1000:.1f}s · "
          f"quantiles nearest-rank · tail {'async' if TAIL_ASYNC else 'sync'}")
    for cls, s in summary.items():
        if cls == "_all":
            continue
        print(f"  {cls:8s} total p50 {s['total_p50_ms']/1000:5.1f}s p95 {s['total_p95_ms']/1000:5.1f}s · reply p50 "
              f"{(s['reply_p50_ms'] or 0)/1000:5.1f}s · calls {s['calls_mean']} {s['calls_by_role_mean']} · tok {s['tokens_mean']} · "
              f"stages {s['stages_mean_ms']}")
    summary["elapsed_s"] = round(time.time() - t0, 1)
    summary["arm"] = "tail_async" if args.tail_async else "sync"
    print("versioned:", write_versioned("latency", {"summary": summary, "rows": rows}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
