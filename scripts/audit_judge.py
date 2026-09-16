"""Phase 81.2 — audit the LongMemEval harness judge against the labelled judge set (`scripts/oracles/judge_set_v1.json`):
agreement of judge v1 (77.2: word presence + abstention cues) and judge v2 (81.2: negation window + hedge refusal) with the
author's labels, overall and per kind; every disagreement listed. Deterministic, no model, no DB."""
from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import write_versioned  # noqa: E402

spec = importlib.util.spec_from_file_location("bench_longmemeval_e2", os.path.join(ROOT, "scripts", "bench_longmemeval_e2.py"))
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)


def main() -> int:
    items = json.load(open(os.path.join(ROOT, "scripts", "oracles", "judge_set_v1.json"), encoding="utf-8"))["items"]
    rows = []
    for it in items:
        v1 = bool(H.judge(it["reply"], it["gold"], it["abstention"]))
        v2 = bool(H.judge_v2(it["reply"], it["gold"], it["abstention"]))
        rows.append({**it, "v1": v1, "v2": v2, "v1_ok": v1 == it["correct"], "v2_ok": v2 == it["correct"]})
    n = len(rows)
    kinds = sorted({r["kind"] for r in rows})
    print(f"JUDGE AUDIT n={n} · v1 agreement {sum(r['v1_ok'] for r in rows)}/{n} · v2 agreement {sum(r['v2_ok'] for r in rows)}/{n}")
    for k in kinds:
        rs = [r for r in rows if r["kind"] == k]
        print(f"  {k:>18} n={len(rs):2d}  v1 {sum(r['v1_ok'] for r in rs)}/{len(rs)}  v2 {sum(r['v2_ok'] for r in rs)}/{len(rs)}")
    for r in rows:
        if not r["v2_ok"]:
            print(f"  [v2 DISAGREE] {r['id']} {r['kind']:>16} label={r['correct']} v2={r['v2']} :: {r['reply'][:90]!r}")
    print("versioned:", write_versioned("judge_audit", {"n": n, "rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
