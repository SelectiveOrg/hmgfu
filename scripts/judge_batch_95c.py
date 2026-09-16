"""95 -- judge the c95c batch (chains L5,L1,E7,E8,E5 x3 + v2 X6 x3) and print, per contract, the
evidence read from the artefacts and the stores, not the verdict alone.  Copy to scripts/ after the
batch (scripts/ is untouched while runs are in progress).

    python scripts/judge_batch_95c.py
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(ROOT, "hmgfu")):
    ROOT = r"C:\Users\you\hmg-fu"
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
import judge_validation_v2 as jv  # noqa: E402


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _events(step, kinds):
    out = []
    for t in step.get("trace") or []:
        if t.get("type") in kinds:
            d = t.get("data")
            try:
                d = json.loads(d) if isinstance(d, str) else d
            except Exception:
                pass
            out.append((t["type"], (d or {}).get("action") or (d or {}).get("reason") or ""))
    return out


def main() -> int:
    print("=== chains c95c (L5 R2, L1 J5, E7 95.9, E8 95.6b, E5 95.4b-ii) ===")
    jv.use_set("chains")
    tally: dict = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "outputs", "validation_chains", "c95c-rep*.json"))):
        payload = _load(path)
        r = jv.summarise(payload)
        print(f"-- rep{payload['rep']} ({payload['head']}) {r['complete']}/{r['n']}")
        for v in r["verdicts"]:
            tally.setdefault(v["id"], []).append(bool(v["complete"]))
            print(f"   {'ok ' if v['complete'] else 'XX '}{v['id']:3} {'; '.join(v['why'])[:120]}"
                  + (f"  | notes: {'; '.join(v.get('notes') or [])[:80]}" if v.get("notes") else ""))
        for ep in payload["episodes"]:
            if ep["id"] == "L5":
                final = [c for s in ep["steps"] for c in (s.get("changes") or []) if "identity" in str(c[1])]
                print("   L5 identity changes:", final[:4], "| reply:", " ".join(ep["steps"][-1]["reply"].split())[:80])
            if ep["id"] == "L1":
                ub, ua = ep.get("utility_before") or {}, ep.get("utility_after") or {}
                print("   L1 utilities before/after:", {k: (ub.get(k), ua.get(k)) for k in sorted(set(ub) | set(ua))})
            if ep["id"] == "E7":
                print("   E7 tools:", [s.get("tools") for s in ep["steps"]], "| widgets:", [(w.get("title"), w.get("props", "")[:60]) for w in ep.get("widgets") or []])
                print("   E7 bash results:", [e for s in ep["steps"] for e in _events(s, {"tool_result"})][:4])
            if ep["id"] == "E8":
                print("   E8 plans:", [(s.get("plan") or {}).get("status") for s in ep["steps"]],
                      "| saydo:", [e for s in ep["steps"] for e in _events(s, {"saydo"})],
                      "| reply0:", " ".join(ep["steps"][0]["reply"].split())[:90])
            if ep["id"] == "E5":
                print("   E5 saydo:", [e for s in ep["steps"] for e in _events(s, {"saydo"})],
                      "| ask reply:", " ".join(ep["steps"][-1]["reply"].split())[:200])
    print("\n=== v2 c95c (X6: discovery -> offered -> run -> report) ===")
    jv.use_set("v2")
    for path in sorted(glob.glob(os.path.join(ROOT, "outputs", "validation_v2", "c95c-rep*.json"))):
        payload = _load(path)
        r = jv.summarise(payload)
        v = r["verdicts"][0]
        tally.setdefault("X6", []).append(bool(v["complete"]))
        ep = payload["episodes"][0]
        print(f"-- rep{payload['rep']} ({payload['head']}) {'ok' if v['complete'] else 'XX'} {'; '.join(v['why'])[:100]}")
        for i, s in enumerate(ep["steps"]):
            res = []
            for t in s["trace"]:
                if t["type"] == "tool_result":
                    try:
                        d = json.loads(t["data"]) if isinstance(t.get("data"), str) else t
                    except ValueError:                       # the artefact truncates long event data
                        d = {"name": "?", "result": str(t.get("data"))[:70], "failed": None}
                    res.append((d.get("name"), str(d.get("result"))[:70], d.get("failed")))
            print(f"   step {i}: offered_has_bash={'bash' in (s['offered'] or [])} tools={s['tools']} ok={s['tools_ok']} results={res}")
    print("\n=== tally (reps complete) ===")
    for k, v in tally.items():
        print(f"   {k:3} {sum(v)}/{len(v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
