"""95 — judge the integrated batch (chains c95b x3 + v2 c958 x3) and print the evidence each contract
needs, read from the artefacts rather than from the verdict alone.

    python scripts/judge_batch_95b.py
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
import judge_validation_v2 as jv  # noqa: E402


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    print("=== chains c95b (L4 grader OFF, E8, E4, E5) ===")
    jv.use_set("chains")
    for path in sorted(glob.glob(os.path.join(ROOT, "outputs", "validation_chains", "c95b-rep*.json"))):
        payload = _load(path)
        r = jv.summarise(payload)
        print(f"-- rep{payload['rep']} ({payload['head']}) {r['complete']}/{r['n']}")
        for v in r["verdicts"]:
            print(f"   {'ok ' if v['complete'] else 'XX '}{v['id']:3} {'; '.join(v['why'])[:110]}")
        for ep in payload["episodes"]:
            if ep["id"] == "L4":
                print("   L4 stale points:", [(p["status"], p["source"], p["text"][:38]) for p in ep.get("stale_points", [])])
                print("   L4 events:", sorted({t["type"] for s in ep["steps"] for t in s["trace"]} & {"router_raw", "fusion", "tools_discovered"}))
            if ep["id"] == "E8":
                plans = [s["plan"].get("status") for s in ep["steps"] if s.get("plan")]
                print("   E8 plans:", plans, "| reply:", " ".join(ep["steps"][0]["reply"].split())[:90])
            if ep["id"] == "E5":
                plan = next((s["plan"] for s in ep["steps"] if s.get("plan")), {})
                print("   E5 plan:", plan.get("status"), [(st["text"][:18], st["status"]) for st in plan.get("steps", [])],
                      "| reply:", " ".join(ep["steps"][-1]["reply"].split())[:100])
    for f in sorted(glob.glob(os.path.join(ROOT, "scratch", "valv2_c95b_*_E4_*.db"))):
        c = sqlite3.connect(f)
        print(f"   E4 rep{f.split('_')[2]} directives:", c.execute("select kind, substr(value,1,50) from directives").fetchall(),
              "tombstones:", c.execute("select count(*) from directive_tombstones").fetchone()[0])
    print("\n=== v2 c958 (X6: discovery -> offered -> run) ===")
    jv.use_set("v2")
    for path in sorted(glob.glob(os.path.join(ROOT, "outputs", "validation_v2", "c958-rep*.json"))):
        payload = _load(path)
        r = jv.summarise(payload)
        v = r["verdicts"][0]
        ep = payload["episodes"][0]
        print(f"-- rep{payload['rep']} ({payload['head']}) {'ok' if v['complete'] else 'XX'} {'; '.join(v['why'])[:100]}")
        for i, s in enumerate(ep["steps"]):
            disc = [t for t in s["trace"] if t["type"] == "tools_discovered"]
            print(f"   step {i}: withheld_has_bash={'bash' in (s['withheld'] or [])} offered_has_bash={'bash' in (s['offered'] or [])} "
                  f"tools={s['tools']} ok={s['tools_ok']} discovered={[json.loads(d['data']).get('names') for d in disc]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
