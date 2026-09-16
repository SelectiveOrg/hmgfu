"""Phase 81.2 follow-up — author adjudication of a STRATIFIED sample of stored LongMemEval replies.

`--draw N` reads a per-item JSONL that carries `reply`, `gold` and `judge` (runs from 81.2 on), draws N items stratified by
category × judge verdict (seeded), and writes a sheet `<peritem>.sample.jsonl` with the fields to read plus an empty
`author` label. The author fills `author` with correct | wrong | decline | contradiction by READING each reply (the label
is never produced by a model). `--score` reads the filled sheet and reports the judge's agreement with the author per
category and per verdict, and lists every disagreement — the ruler for the LME numbers, on real replies.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import write_versioned  # noqa: E402


def draw(peritem: str, n: int, seed: int) -> str:
    rows = [json.loads(l) for l in open(peritem, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if "reply" in r]
    strata = {}
    for r in rows:
        strata.setdefault((r["cat"], int(r["correct"])), []).append(r)
    rng = random.Random(seed)
    per = max(1, n // len(strata))
    picked = []
    for key in sorted(strata):
        pool = strata[key]; rng.shuffle(pool)
        picked.extend(pool[:per])
    rest = [r for r in rows if r not in picked]; rng.shuffle(rest)
    picked.extend(rest[:max(0, n - len(picked))])
    out = peritem + ".sample.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in picked[:n]:
            f.write(json.dumps({"cat": r["cat"], "qid": r["qid"], "gold": r.get("gold"), "reply": r.get("reply"),
                                "judge": r.get("judge"), "judge_verdict": int(r["correct"]), "author": ""}, ensure_ascii=False) + "\n")
    print(f"drew {min(n, len(picked))} of {len(rows)} stored replies into {out} (strata {len(strata)})")
    return out


def score(sheet: str) -> int:
    rows = [json.loads(l) for l in open(sheet, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r.get("author")]
    if not rows:
        print("no author labels yet"); return 1
    def agree(r):
        return (r["judge_verdict"] == 1) == (r["author"] == "correct")
    n_ok = sum(1 for r in rows if agree(r))
    print(f"AUTHOR ADJUDICATION n={len(rows)} · judge agrees with the author on {n_ok}/{len(rows)} = {n_ok / len(rows):.3f}")
    by_cat, by_verdict = {}, {}
    for r in rows:
        by_cat.setdefault(r["cat"], []).append(agree(r)); by_verdict.setdefault(r["judge_verdict"], []).append(agree(r))
    print("  by category: " + " · ".join(f"{c} {sum(v)}/{len(v)}" for c, v in sorted(by_cat.items())))
    print("  by judge verdict: " + " · ".join(f"{'judged correct' if k else 'judged wrong'} {sum(v)}/{len(v)}" for k, v in sorted(by_verdict.items())))
    kinds = {}
    for r in rows:
        if not agree(r):
            kinds.setdefault(("judge says correct" if r["judge_verdict"] else "judge says wrong", r["author"]), []).append(r)
    for (jv, au), rs in sorted(kinds.items()):
        print(f"  [DISAGREE] {jv} / author {au}: {len(rs)}")
        for r in rs[:6]:
            print(f"      {r['cat']:>26} gold={str(r['gold'])[:40]!r} reply={str(r['reply'])[:110]!r}")
    print("versioned:", write_versioned("lme_author_adjudication", {"n": len(rows), "agree": n_ok, "rows": rows}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peritem"); ap.add_argument("--draw", type=int, default=0); ap.add_argument("--seed", type=int, default=20260906)
    ap.add_argument("--score", default=None, help="a filled sample sheet")
    a = ap.parse_args()
    if a.draw and a.peritem:
        draw(a.peritem, a.draw, a.seed); return 0
    if a.score:
        return score(a.score)
    ap.print_help(); return 2


if __name__ == "__main__":
    raise SystemExit(main())
