"""Phase 70 M0.4 — run the two FROZEN external audit oracles and compare with scripts/oracles/expected.json.

The oracle scripts (Codex, Phase 68/69) are never edited. This runner only decides what counts as a regression:
every 'accepted' check must pass; 'superseded'/'downgraded'/'deferred' are reported, not counted. Output is written
to an immutable run directory (M0.1). Exit code 1 on any regression (or on an unexpected new pass? no — new passes
are reported so expected.json can be promoted deliberately).

Usage: .venv/Scripts/python scripts/run_oracles.py [--only contracts|delta]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _bench_paths import write_versioned  # noqa: E402

EXPECTED = json.load(open(os.path.join(ROOT, "scripts", "oracles", "expected.json"), encoding="utf-8"))
ORACLES = {
    "contracts": (["scripts/audit_phase68_contracts.py"], "outputs/phase68_contracts.json", "phase68_contracts"),
    "delta": (["scripts/audit_phase69_delta.py", "--mode", "contracts"], "outputs/phase69_reaudit_delta_contracts.json", "phase69_delta"),
}


def run(name: str) -> dict:
    argv, out, key = ORACLES[name]
    subprocess.run([sys.executable, *argv], cwd=ROOT, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data = json.load(open(os.path.join(ROOT, out), encoding="utf-8"))
    results = {r["case"]: bool(r["passed"]) for r in data["results"]}
    exp = EXPECTED[key]
    accepted = exp["accepted"]
    regressions = [c for c in accepted if not results.get(c, False)]
    not_counted = {**exp.get("superseded", {}), **exp.get("downgraded", {}), **exp.get("deferred", {})}
    unexpected_pass = [c for c in not_counted if results.get(c)]
    unknown = [c for c in results if c not in accepted and c not in not_counted]
    return {"oracle": name, "total": len(results), "passed": sum(results.values()),
            "accepted": len(accepted), "accepted_passing": len(accepted) - len(regressions),
            "regressions": regressions, "unexpected_pass": unexpected_pass, "unknown_cases": unknown,
            "not_counted": not_counted}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(ORACLES), default=None)
    args = ap.parse_args()
    reports = [run(n) for n in ORACLES if not args.only or n == args.only]
    ok = True
    for r in reports:
        status = "OK " if not r["regressions"] else "REGRESSION"
        ok = ok and not r["regressions"]
        print(f"[{status}] {r['oracle']}: {r['passed']}/{r['total']} pass; accepted {r['accepted_passing']}/{r['accepted']}"
              f"{'; REGRESSED: ' + ', '.join(r['regressions']) if r['regressions'] else ''}"
              f"{'; newly passing (promote deliberately): ' + ', '.join(r['unexpected_pass']) if r['unexpected_pass'] else ''}"
              f"{'; UNKNOWN cases: ' + ', '.join(r['unknown_cases']) if r['unknown_cases'] else ''}")
    print("versioned:", write_versioned("oracles", {"reports": reports}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
