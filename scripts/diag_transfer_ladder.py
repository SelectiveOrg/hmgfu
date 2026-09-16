"""Phase 92.E5b — find a wording with HEADROOM before claiming a C/L comparison means anything.

The first C/L probe came back "no difference", and it was not evidence of anything: arm C already
committed the transfer wording, so there was nothing left for L to win. A comparison can only measure
transfer where the baseline FAILS. This walks a ladder of definition wordings, each one further from
the phrasing the system was taught, through arm C alone, and reports which ones the baseline misses.

Whatever the baseline misses becomes the probe; whatever it already handles is useless for the
question the user asked. Near-negatives run in the same ladder so that a wording the baseline "misses"
for the right reason -- because it is not a definition -- is not mistaken for headroom.

    python scripts/diag_transfer_ladder.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.learning_state import DEFINITION_RELATION  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

TEACH = "In this project, ACME-7 means Atlas Control Mesh."

# (label, message, should_commit) -- a distinct invented term each time, so no rung can be answered
# from a value already in the store.
LADDER = [
    ("apposition",   "BETA-2, that's the Basic Event Transport.", True),
    ("inverted",     "We call the Cluster Routing Daemon CRD-3 around here.", True),
    ("dash",         "DELTA-9 - Dynamic Ledger Transfer Adapter.", True),
    ("instruction",  "Whenever you see EPSILON-4, read Event Pipeline Sync Layer.", True),
    ("possessive",   "The team's shorthand for Zenith Query Broker is ZETA-8.", True),
    ("qa",           "OMEGA-1? Operational Metrics Gateway.", True),
    ("instead_of",   "THETA-5 is what we say instead of Threaded Handoff Engine.", True),
    ("neg_opinion",  "GAMMA-3 is a nice name, isn't it?", False),
    ("neg_question", "What does KAPPA-6 mean again?", False),
    ("neg_third",    "Someone on the forum claimed SIGMA-2 is the Shared Index Gateway.", False),
]


def definitions(engine) -> dict:
    return {a.get("entity_id"): a.get("value") for a in engine.facts.assertions.active()
            if a.get("relation") == DEFINITION_RELATION}


def main() -> int:
    os.makedirs(SCRATCH, exist_ok=True)
    db = os.path.join(SCRATCH, f"ladder_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")     # BASELINE arm: no confirmed examples
    sid = sd.new_session(e, "ladder-confirm")
    sd.turn(e, sid, TEACH)
    wait_for_tail(e)

    rows = []
    for label, msg, should in LADDER:
        before = definitions(e)
        sd.turn(e, sid, msg)
        wait_for_tail(e)
        new = {k: v for k, v in definitions(e).items() if k not in before}
        got = bool(new)
        rows.append({"label": label, "message": msg, "should_commit": should,
                     "committed": new, "correct": got == should})
        mark = "ok " if got == should else "MISS"
        print(f"[{mark}] {label:13} commit={str(got):5} expected={str(should):5} {msg[:52]}")

    headroom = [r["label"] for r in rows if r["should_commit"] and not r["committed"]]
    false_pos = [r["label"] for r in rows if not r["should_commit"] and r["committed"]]
    print(f"\nHEADROOM for L (baseline missed a real definition): {headroom or 'none'}")
    print(f"BASELINE false positives: {false_pos or 'none'}")
    if not headroom:
        print("Without headroom the C/L comparison cannot distinguish transfer from a ceiling effect.")
    print("versioned:", write_versioned("transfer_ladder", {"rows": rows, "headroom": headroom,
                                                            "false_positives": false_pos}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
