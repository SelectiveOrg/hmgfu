"""Phase 62 — replay the user's OWN statements from PA3 into the closed fact-slot ledger.

The original importer (`import_pa3.py`) copied PA3's *extracted* fact tables, which the autopsy
showed were fragmented and polluted (56 live names, the favorite language under 8 keys), and it
skipped user sentences like "btw i live in valencia city spain". This script goes back to the
ground truth: every `conversations` row with role='user', in chronological order, run through the
SAME resolver the live turn uses (`FactStore._resolve`: speech-act gate → regex → slot normaliser →
optional model mapper). Later statements supersede earlier ones exactly as they would have live,
and `fact_history` keeps the whole chain with the verbatim words and original dates.

Read-only on PA3. Writes only canonical_facts/fact_history of the TARGET db (default: a clone).

  .venv/Scripts/python scripts/import_pa3_user_facts.py --target scratch/x.db [--pa3 PATH] [--mapper] [--dry]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hmgfu.facts import FactStore, _DECLARATIVE_CUE  # noqa: E402
from hmgfu.models import now_iso  # noqa: E402

PA3_DB = r"C:\Users\you\PriorAgent\data\agent.db"
# PA3 sessions used for scripted memory tests (fake identities); never the user's truth
_TEST_MARKERS = ("Amara Silva", "Nimbus", "Zorblatt", "ORCA-7", "INC-4417", "Benchmark Newname", "Betinho",
                 "Fátima", "Fatima", "test session", "Sebastian")


def user_rows(pa3: str) -> list:
    c = sqlite3.connect(pa3)
    rows = c.execute("SELECT created_at, content FROM conversations WHERE role='user' "
                     "AND length(content) BETWEEN 6 AND 600 ORDER BY created_at").fetchall()
    c.close()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="hmg-fu db to write canonical facts into")
    ap.add_argument("--pa3", default=PA3_DB)
    ap.add_argument("--mapper", action="store_true", help="also run the model slot-mapper on cue-matched rows")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    from hmgfu.agent import AgentEngine
    target = args.target
    if args.dry:                               # M0.3: a dry run never opens (or migrates) the real target
        import shutil, sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from _bench_paths import throwaway_db
        target = throwaway_db("import_pa3_dry_copy.db")
        if os.path.exists(args.target):
            shutil.copyfile(args.target, target)
        print(f"DRY RUN on a copy: {target}")
    eng = AgentEngine(db_path=target)          # graph needed to demote stale nodes at the end
    store = eng.facts
    if not args.mapper:
        store.bind_mapper(None)
    rows = user_rows(args.pa3)
    print(f"{len(rows)} PA3 user rows; replaying through the closed-slot resolver "
          f"({'with' if args.mapper else 'without'} model mapper)")
    applied, skipped_test = [], 0
    for ts, text in rows:
        if any(m.lower() in text.lower() for m in _TEST_MARKERS):
            skipped_test += 1
            continue
        if not _DECLARATIVE_CUE.search(text):
            continue
        det = store._resolve(text)
        if not det:
            continue
        # chronology guard: never let an OLDER PA3 statement overwrite a NEWER value already in
        # this ledger (e.g. the name confirmed in hmg-fu on 2026-07-04 vs a 2026-05 test alias)
        current = next((f for f in store.active() if f["key"] == det["key"]), None)
        if current and (current["updated_at"] or "") > ts:
            continue
        if args.dry:
            applied.append((ts[:16], det))
            continue
        res = store.apply(text, source="user_explicit")
        if res:
            # keep the ORIGINAL date on the ledger (the replay is not "now")
            with store._lock:
                store._db.execute("UPDATE canonical_facts SET updated_at=? WHERE key=?", (ts, res["key"]))
                store._db.execute("UPDATE fact_history SET updated_at=? WHERE id=(SELECT MAX(id) FROM "
                                  "fact_history WHERE key=?)", (ts, res["key"]))
                store._db.commit()
            applied.append((ts[:16], res))
    for ts, r in applied:
        print(f"  {ts}  {r}")
    print(f"\napplied {len(applied)} statements, skipped {skipped_test} test-identity rows")
    if not args.dry:
        from hmgfu.facts import supersede_stale_nodes
        print("graph nodes carrying superseded values demoted:", supersede_stale_nodes(store, eng.graph))
    print("CURRENT LEDGER:")
    for f in store.active():
        print(f"  {f['key']:28s} = {f['value']!r:40s} (prev {f['prev']!r}) {f['updated_at'][:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
