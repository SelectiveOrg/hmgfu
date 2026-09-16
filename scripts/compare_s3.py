"""Phase 91.S3 — the paired comparison of a frozen baseline against a frozen candidate on the blind set.

The rule is written here, BEFORE any result is read, and it is the audit's:

  * the unit of independence is the CONVERSATION, not the repetition — a conversation counts once, and repetitions
    are collapsed to "did it hold in every one" so that repeating a run cannot inflate the sample;
  * the comparison is PAIRED: the same conversation, the same synthetic base, the same question, the two arms;
  * the primary reading is the discordant pairs (won / lost), because agreements carry no information about a
    difference — this is McNemar's logic, reported as counts rather than a p-value on 48 items;
  * a family-level table comes with it, since a gain concentrated in one family is not a general gain;
  * INCONCLUSIVE verdicts are reported separately and never counted as either arm's success.

    python scripts/compare_s3.py
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import write_versioned  # noqa: E402

# 91.S3: ONE paired repetition per arm. The budget correction (outputs/evidence_91_W4_pilot.txt) cut the second
# repetition when the measured cost came in 2.2x over the pilot, so "held" below means held in the single run — a
# weaker per-item reading than "held in both", and it is reported as such.
ARMS = {"baseline": ["outputs/evidence_91_S3_base_r1.txt"],
        "candidate": ["outputs/evidence_91_S3_cand_r1.txt"]}


def _verdicts(path: str) -> dict:
    """id -> verdict, read from the run's console record."""
    out = {}
    for line in io.open(os.path.join(ROOT, path), encoding="utf-8", errors="replace").read().splitlines():
        m = re.match(r"^\[([^\]]+)\]\s+(\S+)\s", line)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def _wall_and_calls(after: float) -> tuple:
    """Total seconds and model calls of the versioned runs of this comparison, for the cost line."""
    secs = calls = 0
    for p in glob.glob(os.path.join(ROOT, "outputs/runs/*/conversations.json")):
        if os.path.getmtime(p) < after:
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        if "s3_blind" not in str(d.get("label", "")):
            continue
        for r in d["rows"]:
            secs += r.get("secs", 0) + sum(s.get("secs", 0) for s in r.get("stages", []))
            calls += sum((s.get("timings") or {}).get("model_calls") or 0 for s in r.get("stages", []))
            calls += (r.get("timings") or {}).get("model_calls") or 0
    return round(secs), calls


def main() -> int:
    missing = [p for arm in ARMS.values() for p in arm if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        print("not all passes are present yet:", missing); return 1
    oracle = json.load(io.open(os.path.join(ROOT, "scripts/oracles/s3_blind_v1.json"), encoding="utf-8"))
    family = {c["id"]: c["family"] for c in oracle["conversations"]}
    held, inconclusive = {}, defaultdict(list)
    for arm, paths in ARMS.items():
        reps = [_verdicts(p) for p in paths]
        for cid in family:
            vs = [r.get(cid, "MISSING") for r in reps]
            if any(v.startswith("INCONCLUSIVE") for v in vs):
                inconclusive[arm].append(cid)
            held[(arm, cid)] = all(v == "OK" for v in vs)      # with one repetition: held in that run
    won = [c for c in family if held[("candidate", c)] and not held[("baseline", c)]]
    lost = [c for c in family if held[("baseline", c)] and not held[("candidate", c)]]
    both = [c for c in family if held[("baseline", c)] and held[("candidate", c)]]
    neither = [c for c in family if not held[("baseline", c)] and not held[("candidate", c)]]
    n = len(family)
    print(f"S3 BLIND VALIDATION · {n} conversations · {len(ARMS['baseline'])} paired repetition(s) per arm · frozen arms\n")
    print(f"  baseline holds  {len(both) + len(lost)}/{n}")
    print(f"  candidate holds {len(both) + len(won)}/{n}")
    print(f"\n  DISCORDANT PAIRS (the only ones that carry information about a difference):")
    print(f"    candidate wins  {len(won):2}  {sorted(won)}")
    print(f"    candidate loses {len(lost):2}  {sorted(lost)}")
    print(f"    both hold {len(both)} · neither holds {len(neither)}")
    print(f"\n  by family (baseline -> candidate):")
    for fam in sorted(set(family.values())):
        ids = [c for c in family if family[c] == fam]
        b = sum(1 for c in ids if held[("baseline", c)]); k = sum(1 for c in ids if held[("candidate", c)])
        print(f"    {fam:28} {b}/{len(ids)} -> {k}/{len(ids)}")
    for arm, ids in inconclusive.items():
        if ids:
            print(f"\n  INCONCLUSIVE in {arm} (never counted as a success for either arm): {sorted(ids)}")
    secs, calls = _wall_and_calls(0)
    print(f"\n  cost, both passes: {secs} s of turn time · {calls} model calls")
    print("\n  Reading: with 48 conversations the discordant pairs are the evidence; a difference of a few pairs is not")
    print("  a demonstrated improvement, and a gain confined to one family is not a general gain.")
    print("versioned:", write_versioned("compare_s3", {"won": won, "lost": lost, "both": both, "neither": neither,
                                                       "inconclusive": dict(inconclusive), "n": n,
                                                       "by_family": {f: [sum(1 for c in family if family[c] == f and held[(a, c)])
                                                                        for a in ("baseline", "candidate")]
                                                                     for f in set(family.values())},
                                                       "secs": secs, "model_calls": calls}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
