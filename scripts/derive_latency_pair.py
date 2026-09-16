"""Phase 89.3 — pair latency runs (the kNN router ON ×n) with a same-day defaults control, turn by turn (same script text and
repetition): overall p50 per run vs the control, the CLAIMED turns (no router call: one fewer chat-role call than the control on
the same text) and their p50 against the control's p50 on the same turns, and the embed-call count (one per turn = the memo held).
Inputs: the versioned `latency.json` files `bench_latency.py` writes."""
from __future__ import annotations

import argparse
import json
import statistics


def rows_of(path: str) -> list:
    return json.load(open(path, encoding="utf-8"))["rows"]


def p50(xs):
    return statistics.median(xs) / 1000.0 if xs else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", required=True)
    ap.add_argument("--run", action="append", required=True, help="latency.json of a kNN-ON run (repeatable)")
    args = ap.parse_args()
    ctl = {(r["rep"], r["text"]): r for r in rows_of(args.control)}
    print(f"control: n {len(ctl)} · total p50 {p50([r['total_ms'] for r in ctl.values()]):.1f}s · embed calls/turn "
          f"{statistics.mean((r['calls'] or {}).get('embed', 0) for r in ctl.values()):.2f}")
    all_claimed, all_ctl_same = [], []
    for path in args.run:
        rows = rows_of(path)
        paired = [(r, ctl.get((r["rep"], r["text"]))) for r in rows]
        paired = [(r, c) for r, c in paired if c is not None]
        exact = any("route_source" in r for r in rows)                      # 89.3: the response exposes the route source
        claimed = ([(r, c) for r, c in paired if r.get("route_source") == "knn"] if exact else
                   [(r, c) for r, c in paired if (r["calls"] or {}).get("chat", 0) < (c["calls"] or {}).get("chat", 0)])   # proxy: one chat-role call fewer
        emb = statistics.mean((r["calls"] or {}).get("embed", 0) for r in rows)
        tot = p50([r["total_ms"] for r in rows]); ctl_tot = p50([c["total_ms"] for _r, c in paired])
        line = (f"run {path.split('runs')[-1][:28]}: n {len(rows)} · total p50 {tot:.1f}s (control on the same turns {ctl_tot:.1f}s, "
                f"Δ {tot - ctl_tot:+.1f}s) · embed calls/turn {emb:.2f} · claimed {len(claimed)}/{len(paired)} ({'route_source' if exact else 'PROXY: chat calls < control'})")
        if claimed:
            pc, pcc = p50([r["total_ms"] for r, _c in claimed]), p50([c["total_ms"] for _r, c in claimed])
            line += f" · claimed p50 {pc:.1f}s vs control {pcc:.1f}s (Δ {pc - pcc:+.1f}s) · classes {sorted({r['cls'] for r, _c in claimed})}"
            all_claimed += [r["total_ms"] for r, _c in claimed]; all_ctl_same += [c["total_ms"] for _r, c in claimed]
        print(line)
    if all_claimed:
        print(f"ALL claimed turns ({len(all_claimed)}): p50 {p50(all_claimed):.1f}s vs control {p50(all_ctl_same):.1f}s · Δ {p50(all_claimed) - p50(all_ctl_same):+.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
