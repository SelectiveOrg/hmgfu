"""Phase 89.2 — pair two routing-agreement runs on the SAME decision set (e.g. the model router vs kNN+model on the reserved
decision_v2) and report: each arm's correctness, the McNemar cells (b = B right where A wrong, c = A right where B wrong), the
paired net b − c with a percentile-bootstrap 95 % CI (reusing `derive_lme_pair.net_ci`), and the correctness of the kNN's own
claims in arm B. Inputs: the versioned `routing_agreement.json` files the bench writes."""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from derive_lme_pair import net_ci  # noqa: E402


def load(path: str) -> dict:
    d = json.load(open(path, encoding="utf-8"))
    rows = {r["id"]: r for r in d["rows"]}
    return {"label": d.get("label"), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="routing_agreement.json of arm A (the model router)")
    ap.add_argument("--b", required=True, help="routing_agreement.json of arm B (kNN + model)")
    args = ap.parse_args()
    A, B = load(args.a), load(args.b)
    ids = sorted(set(A["rows"]) & set(B["rows"]))
    if len(ids) != len(A["rows"]) or len(ids) != len(B["rows"]):
        print(f"WARN: arms differ in items (A {len(A['rows'])}, B {len(B['rows'])}, shared {len(ids)})")
    a_ok = {i: int(bool(A["rows"][i].get("decision"))) for i in ids}
    b_ok = {i: int(bool(B["rows"][i].get("decision"))) for i in ids}
    b_cell = sum(1 for i in ids if b_ok[i] and not a_ok[i]); c_cell = sum(1 for i in ids if a_ok[i] and not b_ok[i])
    lo, hi = net_ci(a_ok, b_ok, ids)
    print(f"A [{A['label']}]: {sum(a_ok.values())}/{len(ids)} = {sum(a_ok.values())/len(ids):.3f}")
    print(f"B [{B['label']}]: {sum(b_ok.values())}/{len(ids)} = {sum(b_ok.values())/len(ids):.3f}")
    print(f"paired: B right/A wrong b={b_cell} · A right/B wrong c={c_cell} · net {b_cell - c_cell:+d} [95% CI {lo:+d}, {hi:+d}]")
    knn = [i for i in ids if (B["rows"][i].get("route") or {}).get("_source") == "knn"]
    if knn:
        ok = sum(b_ok[i] for i in knn)
        print(f"kNN claims in B: {len(knn)}/{len(ids)} · correct {ok}/{len(knn)} = {ok/len(knn):.3f} · the model on the same turns in A: {sum(a_ok[i] for i in knn)}/{len(knn)}")
        wrong = [i for i in knn if not b_ok[i]]
        if wrong:
            print("  wrong kNN claims: " + ", ".join(f"{i} ({B['rows'][i].get('class')})" for i in wrong))
    else:
        print("kNN claims in B: none")
    flips = [i for i in ids if a_ok[i] != b_ok[i]]
    if flips:
        print("flips: " + ", ".join(f"{i}({'+' if b_ok[i] else '-'})" for i in flips))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
