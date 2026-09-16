"""Phase 91.Z — pair analysis on top of the EXISTING write-set runner.

The review's requirement: "An undetected PT positive cannot validate its negative counterpart." A
negative that leaves the ledger alone proves protection only when the paired positive, in the same
construction, is actually written. Otherwise the pair is VACUOUS: the mould simply never fired.

This adds no runner and no second execution path. It reads the rows `scripts/run_write_set.py`
already versions under outputs/runs/, joins them to the `pair`/`polarity` labels in the oracle, and
reports per pair. Run the arms first, then:

    python scripts/analyse_contrast.py <run_dir_or_write_set.json> [more...]
"""
from __future__ import annotations

import glob
import io
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORACLE = os.path.join(ROOT, "scripts", "oracles", "scope_contrast_v1.json")


def _rows(path: str) -> list:
    if os.path.isdir(path):
        path = os.path.join(path, "write_set.json")
    d = json.load(io.open(path, encoding="utf-8"))
    return d.get("results") or d.get("rows") or []


def main(paths) -> int:
    meta = {i["id"]: i for i in json.load(io.open(ORACLE, encoding="utf-8"))["items"]}
    for path in paths:
        rows = {r["id"]: r for r in _rows(path)}
        label = os.path.basename(os.path.dirname(path) if not os.path.isdir(path) else path)
        pairs = defaultdict(lambda: {"pos": [], "neg": []})
        for cid, r in rows.items():
            m = meta.get(cid)
            if not m:
                continue
            ok = not r["false_writes"] and not r["missed"]
            pairs[m["pair"]]["pos" if m["polarity"] == "positive" else "neg"].append((cid, ok, r))
        print(f"\n=== {label} ===")
        proven = vacuous = broken = 0
        for pair, d in sorted(pairs.items()):
            pos_ok = [c for c, ok, _ in d["pos"] if ok]
            neg_ok = [c for c, ok, _ in d["neg"] if ok]
            neg_bad = [(c, r["false_writes"]) for c, ok, r in d["neg"] if not ok]
            pos_bad = [c for c, ok, _ in d["pos"] if not ok]
            if not pos_ok:
                state, vacuous = "VACUOUS  (no positive recognised: its negatives prove nothing)", vacuous + 1
            elif neg_bad:
                state, broken = "BROKEN   (positive works, a negative still writes)", broken + 1
            else:
                state, proven = "PROVEN   (positive written AND every negative protected)", proven + 1
            print(f"  {pair:22} {state}")
            print(f"      positives written {len(pos_ok)}/{len(d['pos'])}"
                  + (f"  MISSED {pos_bad}" if pos_bad else "")
                  + f" · negatives protected {len(neg_ok)}/{len(d['neg'])}")
            for c, fw in neg_bad:
                print(f"      LEAKS {c}: {json.dumps(fw, ensure_ascii=False)}")
        print(f"  ---- pairs: {proven} proven · {broken} broken · {vacuous} vacuous"
              f"   (a vacuous pair is NEVER counted as protection)")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "outputs/runs/*/write_set.json")),
                                  key=os.path.getmtime)[-1:]
    raise SystemExit(main(args))
