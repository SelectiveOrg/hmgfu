"""Phase 90.J — pair two conversation runs (the versioned `conversations.json` files) per conversation: each arm's OK count, McNemar b/c,
paired net with a bootstrap 95 % CI (`derive_lme_pair.net_ci`, reused), per-family table, the flips item by item, and — for the
extractor question — the chat-role calls per user turn in each arm (the extractor exercised = +1 chat call per declarative turn)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from derive_lme_pair import net_ci  # noqa: E402


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d.get("label", ""), d["rows"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="conversations.json of arm A (reference)")
    ap.add_argument("--b", required=True, help="conversations.json of arm B (candidate)")
    ap.add_argument("--reps", type=int, default=None, help="pair by (id, rep) when both runs have the same reps; default: by id, first rep")
    args = ap.parse_args()
    la, ra = load(args.a); lb, rb = load(args.b)
    key = (lambda r: (r["id"], r["rep"])) if args.reps else (lambda r: r["id"])
    A = {key(r): r for r in ra}; B = {key(r): r for r in rb}
    ks = sorted(set(A) & set(B))
    a = {k: int(A[k]["verdict"] == "OK") for k in ks}; b = {k: int(B[k]["verdict"] == "OK") for k in ks}
    bb = sum(1 for k in ks if b[k] and not a[k]); cc = sum(1 for k in ks if a[k] and not b[k])
    lo, hi = net_ci(a, b, ks)
    print(f"A [{la[:60]}]: {sum(a.values())}/{len(ks)}\nB [{lb[:60]}]: {sum(b.values())}/{len(ks)}")
    print(f"paired: b(B ok, A fail)={bb} c(A ok, B fail)={cc} net {bb - cc:+d} [95% CI {lo:+d}, {hi:+d}]")
    fam = defaultdict(lambda: [0, 0, 0])
    for k in ks:
        f = A[k]["family"]; fam[f][0] += a[k]; fam[f][1] += b[k]; fam[f][2] += 1
    for f, (x, y, n) in sorted(fam.items()):
        print(f"  {f:40} A {x}/{n}  B {y}/{n}")
    for k in ks:
        if a[k] != b[k]:
            print(f"  FLIP {k}: A={A[k]['verdict'][:24]} | B={B[k]['verdict'][:24]}")
    # the extractor exercised: chat-role calls per user turn (stages) in each arm
    def chat_calls(rows):
        n = c = 0
        for r in rows:
            for st in r.get("stages", []):
                calls = ((st.get("timings") or {}).get("calls") or {})
                if calls:
                    n += 1; c += calls.get("chat", 0)
        return (c / n) if n else float("nan"), n
    ca, na = chat_calls(ra); cb, nb = chat_calls(rb)
    print(f"chat-role calls per user turn: A {ca:.2f} (n {na}) · B {cb:.2f} (n {nb}) · Δ {cb - ca:+.2f} (the tail extractor = +1 per declarative turn)")
    spans_writes = sum(1 for r in rb for st in r.get("stages", []) if st.get("ledger_delta"))
    print(f"B turns with a ledger delta: {spans_writes} · A: {sum(1 for r in ra for st in r.get('stages', []) if st.get('ledger_delta'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
