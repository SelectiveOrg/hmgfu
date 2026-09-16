"""94.8 — per-case table, baseline vs candidate, three repetitions each. No totals across axes: the
user's rule is that a safety failure is not compensated by successes elsewhere, so each case is its
own row and its own verdict.

    python scripts/aggregate_chains.py outputs/validation_chains
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from judge_validation_v2 import summarise, use_set  # noqa: E402


def main() -> int:
    use_set("chains")
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "outputs", "validation_chains")
    runs = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(out, "*-rep*.json"))):
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        runs[payload["arm"]].append(summarise(payload))
    arms = sorted(runs)
    ids = [v["id"] for v in runs[arms[0]][0]["verdicts"]] if arms else []
    print(f"{'case':5} {'axis':10} " + "  ".join(f"{a:>10}" for a in arms) + "   first reason (candidate)")
    for eid in ids:
        cells = []
        reason = ""
        for arm in arms:
            hits = [v for r in runs[arm] for v in r["verdicts"] if v["id"] == eid]
            n = sum(1 for v in hits if v["complete"])
            cells.append(f"{n}/{len(hits):<8}")
            if arm == "candidate" or len(arms) == 1:      # the column says candidate; make it so
                reason = next((v["why"][0][:60] for v in hits if v["why"]), "")
        axis = next(v["axis"] for v in runs[arms[0]][0]["verdicts"] if v["id"] == eid)
        print(f"{eid:5} {axis:10} " + "  ".join(f"{c:>10}" for c in cells) + f"   {reason}")
    for arm in arms:
        wall = sum(r["wall_secs"] or 0 for r in runs[arm])
        print(f"\n{arm}: reps {[r['complete'] for r in runs[arm]]} of {runs[arm][0]['n']}  "
              f"heads {sorted({r['head'] for r in runs[arm]})}  wall {wall / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
