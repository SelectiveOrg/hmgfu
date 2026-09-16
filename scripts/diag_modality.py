"""Phase 90.L — can the EXISTING contracts tell a durable state assertion from a correction, a bare activity, a proposal, an
intention, a negation, a third party, a question? Runs the deterministic write side (no model call) over the DEV set
`scripts/oracles/modality_v1.json` and prints, per case: the sentence modality the store assigns (`utterance.sentence_modalities`),
whether the third-party guard fires, whether the hedge guard fires, what the regex detector produces, and the canon value the ledger
ends up with — against the expectation fixed before the run. Diagnostic only: nothing is changed and no reserved set is touched."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import write_versioned  # noqa: E402
from hmgfu.facts import FactStore  # noqa: E402
from hmgfu.fact_detect import detect_facts  # noqa: E402
from hmgfu.utterance import sentence_modalities  # noqa: E402
from hmgfu.value_gate import _HEDGE, third_party_sentence  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOT = "project.main"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", default=os.path.join(ROOT, "scripts", "oracles", "modality_v1.json"))
    ap.add_argument("--prior", default="My main project is Kuvala.", help="the message that seeds the slot before each case")
    args = ap.parse_args()
    data = json.load(open(args.oracle, encoding="utf-8"))
    rows = []
    for c in data["cases"]:
        store = FactStore(os.path.join(tempfile.mkdtemp(), "f.db"))
        store.apply_all(args.prior, "user_explicit")                       # the slot already has a value: a write must be evidenced
        before = {r["key"]: r["value"] for r in store.active()}.get(SLOT)
        mods = sentence_modalities(c["text"])
        dets = detect_facts(c["text"])
        store.apply_all(c["text"], "user_explicit")
        after = {r["key"]: r["value"] for r in store.active()}.get(SLOT)
        got = after if after != before else None                            # the canon CHANGE this message caused
        ok = (got or "").lower().startswith((c["expect_canon"] or "").lower()) if c["expect_canon"] else got is None
        rows.append({"id": c["id"], "class": c["class"], "lang": c["lang"], "text": c["text"], "expect": c["expect_canon"],
                     "got": got, "ok": bool(ok), "modalities": [m["modality"] for m in mods],
                     "third_party": third_party_sentence(c["text"]), "hedged": bool(_HEDGE.search(c["text"])),
                     "regex_dets": [(d.get("key"), d.get("value")) for d in dets], "why": c["why"]})
        print(f"[{'OK ' if ok else 'BAD'}] {c['id']} {c['class']:16} {c['lang']} · modality {'+'.join(m['modality'] for m in mods):22} "
              f"3p={int(third_party_sentence(c['text']))} hedge={int(bool(_HEDGE.search(c['text'])))} · regex {[(d.get('key'), d.get('value')) for d in dets]}")
        print(f"      {c['text'][:88]!r}\n      expect {c['expect_canon']!r} · got {got!r}   ({c['why']})")
    ok_n = sum(r["ok"] for r in rows)
    print(f"\nMODALITY DIAGNOSTIC [{os.path.basename(args.oracle)}] {ok_n}/{len(rows)}")
    by = {}
    for r in rows:
        b = by.setdefault(r["class"], [0, 0]); b[0] += r["ok"]; b[1] += 1
    for cls, (o, n) in sorted(by.items()):
        print(f"  {cls:18} {o}/{n}")
    wrong_write = [r for r in rows if r["expect"] is None and r["got"]]
    missed = [r for r in rows if r["expect"] and not r["ok"]]
    print(f"  writes that must not happen: {len(wrong_write)} {[(r['id'], r['got']) for r in wrong_write]}")
    print(f"  writes that must happen and did not: {len(missed)} {[r['id'] for r in missed]}")
    print("  modalities seen:", dict(Counter(m for r in rows for m in r["modalities"])))
    print("versioned:", write_versioned("modality_diagnostic", {"rows": rows, "oracle": os.path.basename(args.oracle)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
