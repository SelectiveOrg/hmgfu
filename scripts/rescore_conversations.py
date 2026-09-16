"""Phase 91.S0 — re-score ARCHIVED conversation runs with the corrected evaluator, as a versioned errata.

The audit reproduced five defects in the judging (`reports/codex_execution_audit_20260909/ANALISE_E_PLANO.md` §3), so
every conversation score produced before the fix is an unvalidated measure. This script reads the recorded answers of a
run — the replies, the injected context and the final ledger are all stored in `outputs/runs/<id>/conversations.json` —
and applies the corrected `judge()` to them offline.

It never re-runs the model: the original numbers stay exactly where they are, and the errata is written beside them.
Ambiguous cases are listed, not silently converted into product changes.

    python scripts/rescore_conversations.py outputs/runs/<id>/conversations.json [--oracle scripts/oracles/x.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import write_versioned  # noqa: E402


def _runner():
    spec = importlib.util.spec_from_file_location("run_conversations", os.path.join(ROOT, "scripts", "run_conversations.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="outputs/runs/<id>/conversations.json from the archived run")
    ap.add_argument("--oracle", default=None, help="the oracle used by that run (default: read from its label)")
    args = ap.parse_args()
    R = _runner()
    data = json.load(io.open(args.run, encoding="utf-8"))
    label = str(data.get("label", ""))
    oracle_path = args.oracle or os.path.join(ROOT, "scripts", "oracles", label.split()[0].strip("[]"))
    _oracle = json.load(io.open(oracle_path, encoding="utf-8"))
    for _c in _oracle["conversations"]:                # 91.V4: the file-level contract reaches every conversation
        _c.setdefault("value_match", _oracle.get("value_match", "exact"))
    convs = {c["id"]: c for c in _oracle["conversations"]}
    rows, changed = [], []
    for r in data["rows"]:
        c = convs.get(r["id"])
        if c is None:
            continue
        # the row records the FINAL ledger for the expected keys; rebuilding it from the deltas alone would ignore
        # whatever the cloned memory already held and would report a write failure that never happened
        ledger = dict(r.get("ledger_final") or {})
        if not ledger:
            for s in r.get("stages", []):
                ledger.update(s.get("ledger_delta") or {})
        # 91.V5: the OLD `allowed_in_context` mixed the injected context with the ledger — the very defect being
        # corrected — so it cannot show what reached the reader. Where the run did not record the context separately,
        # the layer attribution is INDETERMINATE and is reported as such, never reconstructed from a contaminated field.
        recorded_context = r.get("injected_context")
        written = {k for s in r.get("stages", []) for k in (s.get("ledger_delta") or {})}
        j = R.judge(c, r.get("reply") or "", recorded_context or "", ledger, None, written)
        if recorded_context is None:
            # the run stored no separate context, so DELIVERY is unknown and no layer can be attributed. The reply's
            # CONTENT is still judged and reported; the verdict is not reconstructed from the contaminated old field.
            j["verdict"] = "INDETERMINATE (context not recorded)"
        row = {"id": r["id"], "family": r.get("family"), "old_verdict": r.get("verdict"), "new_verdict": j["verdict"],
               "content_ok": j["answer_ok"], "context_recorded": recorded_context is not None,
               "answer_ok": j["answer_ok"], "stated": j["stated_in_reply"], "stated_forbidden": j["stated_forbidden"],
               "abstained": j["abstained"], "reply": (r.get("reply") or "")[:180]}
        rows.append(row)
        if row["old_verdict"] != row["new_verdict"]:
            changed.append(row)
    indet = sum(1 for r in rows if str(r["new_verdict"]).startswith("INDETERMINATE"))
    old_ok = sum(1 for r in rows if r["old_verdict"] == "OK")
    new_ok = sum(1 for r in rows if r["new_verdict"] == "OK")
    print(f"run     {os.path.basename(os.path.dirname(args.run))}  ({label})")
    print(f"oracle  {os.path.relpath(oracle_path, ROOT)}")
    content_ok = sum(1 for r in rows if r.get("content_ok"))
    print(f"ORIGINAL score PRESERVED: {old_ok}/{len(rows)}")
    if indet == len(rows):
        print(f"RE-SCORING IS NOT A SCORE HERE: none of the {len(rows)} runs recorded the delivered context, so no layer")
        print(f"    can be attributed. On CONTENT alone, the corrected judge accepts {content_ok}/{len(rows)} replies.")
    else:
        print(f"re-scored with the corrected judge: {new_ok}/{len(rows)} OK · {indet} indeterminate · content ok {content_ok}/{len(rows)}")
    if indet:
        print(f"{indet} case(s) INDETERMINATE: the run recorded no separate context, so a LAYER cannot be attributed.")
        print("    The reply content is still judged; the runner also truncates replies at 400 characters and keeps"
              " no prompt, so nothing is claimed about what the artefacts do not hold.")
    print(f"old verdicts {dict(Counter(r['old_verdict'] for r in rows))}")
    print(f"new verdicts {dict(Counter(r['new_verdict'] for r in rows))}")
    if changed:
        print(f"\n{len(changed)} case(s) change verdict — errata, not a rewrite of history:")
        for r in changed:
            print(f"  {r['id']:32} {r['old_verdict']}  ->  {r['new_verdict']}")
            print(f"      reply: {r['reply']!r}")
    else:
        print("\nno verdict changes")
    print("\nversioned:", write_versioned("rescore_conversations",
                                          {"run": args.run, "oracle": oracle_path, "old_ok": old_ok,
                                           "new_ok": new_ok, "n": len(rows), "rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
