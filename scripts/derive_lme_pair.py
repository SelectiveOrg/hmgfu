"""Pair two LongMemEval per-item files (same items, same reader) and report per category: accuracy of each, McNemar
discordant pairs b (B correct, A wrong) / c (A correct, B wrong), net = b − c. Used for 78.4 G3b: A = the 77.2 `prod` arm,
B = the candidate `prod` arm. Items are matched on (cat, qi); an item missing from either file is skipped and counted."""
from __future__ import annotations

import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(path: str, arm: str, exclude_errors: bool = False) -> dict:
    out = {}
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") == arm:
            if exclude_errors and (r.get("error") or not (r.get("reply") or "").strip()):
                continue                                             # 87: a reader infrastructure failure is not an item
            out[(r["cat"], r["qi"])] = int(r["correct"])
    return out


def net_ci(A: dict, B: dict, ks: list, n_boot: int = 2000, seed: int = 20260907) -> tuple:
    """87 (Codex review 3): percentile bootstrap 95% CI of the paired net (b − c) over the items of one category."""
    import random
    rng = random.Random(seed)
    diffs = [B[k] - A[k] for k in ks]
    if not diffs:
        return (0, 0)
    vals = sorted(sum(rng.choice(diffs) for _ in diffs) for _ in range(n_boot))
    return (vals[int(0.025 * n_boot)], vals[int(0.975 * n_boot)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="per-item file A (reference)")
    ap.add_argument("--arm-a", default="prod")
    ap.add_argument("--b", required=True, help="per-item file B (candidate)")
    ap.add_argument("--arm-b", default="prod")
    ap.add_argument("--base", default=None, help="optional: per-item file holding the base arm for the same items")
    ap.add_argument("--exclude-errors", action="store_true", help="87: drop items whose reader failed (timeout / empty) in either file")
    args = ap.parse_args()
    A, B = load(args.a, args.arm_a, args.exclude_errors), load(args.b, args.arm_b, args.exclude_errors)
    base = load(args.base, "base") if args.base else {}
    keys = sorted(set(A) & set(B))
    skipped = len(set(A) ^ set(B))
    cats = sorted({k[0] for k in keys})
    print(f"paired items {len(keys)} (unmatched skipped {skipped})")
    print(f"{'category':>26} {'n':>3} {'A':>6} {'B':>6} {'base':>6}  {'b(B✓A✗)':>8} {'c(A✓B✗)':>8} {'net':>5}  {'net 95% CI':>12}")
    for cat in cats:
        ks = [k for k in keys if k[0] == cat]
        n = len(ks)
        a = sum(A[k] for k in ks) / n; bb = sum(B[k] for k in ks) / n
        bs = (sum(base.get(k, 0) for k in ks) / n) if base else float("nan")
        b_ = sum(1 for k in ks if B[k] and not A[k]); c_ = sum(1 for k in ks if A[k] and not B[k])
        lo, hi = net_ci(A, B, ks)
        print(f"{cat:>26} {n:>3} {a:6.3f} {bb:6.3f} {bs:6.3f}  {b_:>8} {c_:>8} {b_ - c_:>+5}  [{lo:+d}, {hi:+d}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
