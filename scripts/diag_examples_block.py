"""Phase 92.E5b — is arm L actually DIFFERENT from arm C at the point where it is supposed to differ?

The C/L comparison is only interpretable if the one manipulated variable really reaches the router.
An empty examples block would make L identical to C, and a null result would then say nothing about
transfer -- the same trap the swallowed SyntaxError had already sprung once. So this prints, for one
taught turn: the committed cases, the block each mode renders, and whether the block reaches the
prompt the router is given.

    python scripts/diag_examples_block.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
PROBE = "BETA-2, that's the Basic Event Transport."


def main() -> int:
    os.makedirs(SCRATCH, exist_ok=True)
    db = os.path.join(SCRATCH, f"exblock_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "adapt")
    sid = sd.new_session(e, "exblock")
    sd.turn(e, sid, TEACH)
    wait_for_tail(e)

    rows = e.facts._db.execute("SELECT id, state, payload_json FROM learning_cases").fetchall()
    print(f"cases: {len(rows)}")
    for cid, st, payload in rows:
        print(f"  {cid} {st} {json.dumps(json.loads(payload or '{}'), ensure_ascii=False)[:220]}")

    for mode in ("confirm", "adapt"):
        e.settings.set("interactive_learning_mode", mode)
        block = e.sensitizer._learning_examples_text(PROBE)
        print(f"\n[{mode}] block = {block!r}")

    e.settings.set("interactive_learning_mode", "adapt")
    seen = {}
    original = None
    from hmgfu import turn_router
    original = turn_router.start_route

    def spy(chat, parse, text, time_ctx, catalog_text, directives, exemplars, schema, learning_text=""):
        seen["learning_text"] = learning_text
        return original(chat, parse, text, time_ctx, catalog_text, directives, exemplars, schema, learning_text)

    turn_router.start_route = spy
    try:
        sd.turn(e, sid, PROBE)
        wait_for_tail(e)
    finally:
        turn_router.start_route = original
    print(f"\nreached the router: {seen.get('learning_text')!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
