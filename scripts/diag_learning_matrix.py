"""Phase 92.E5R — priority 4, end to end: FACTS, DEFINITIONS and BEHAVIOUR, and a correction that wins.

The live evidence so far covered one kind (a definition) and one answer (explicit teaching). The
directive asks for facts, definitions and behaviour, with yes/no/maybe/corrections, persisting across
sessions. This walks the whole matrix on a THROWAWAY synthetic base and judges every step with
`scripts/learning_oracle.py`, so each one is graded on what was actually written across the ledger,
the assertions and the directives -- not on whether something appeared.

What it can and cannot force is stated rather than blurred: a teaching turn is under the user's
control, so those steps are deterministic; a yes/no/maybe answer requires the protocol to have ASKED,
which depends on the model judging the turn ambiguous. So the ambiguous step reports what actually
happened -- question asked, or committed, or nothing -- instead of pretending to have driven it. The
enumerated answer table is proved deterministically elsewhere (v120, 44 transitions).

    python scripts/diag_learning_matrix.py [--mode confirm|adapt]
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
from learning_capture import TurnCapture  # noqa: E402
from learning_oracle import definition_written, delta, snapshot  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

DOG_FIRST, DOG_CORRECTED = "Blue", "Green"
TERM, MEANING = "ACME-7", "Atlas Control Mesh"
PREFIX = "Ready:"

STEPS = [
    ("fact", f"My dog is called {DOG_FIRST}.", {"store": "facts", "value": DOG_FIRST}),
    ("correction", f"Actually, my dog is called {DOG_CORRECTED}.",
     {"store": "facts", "value": DOG_CORRECTED}),
    ("definition", f"In this project, {TERM} means {MEANING}.",
     {"definition": (TERM, MEANING)}),
    ("behaviour", f'From now on, always start your replies with "{PREFIX}".',
     {"store": "directives", "value": PREFIX}),
    # not forced: whether the protocol ASKS here is the model's judgement, and the step reports it
    ("ambiguous", "It is called Nimbus.", None),
]

ASK = [("fact", "what is my dog called?", DOG_CORRECTED),
       ("definition", f"what does {TERM} stand for?", MEANING)]
# what must be IN THE STORES for the answer to count as learned rather than retrieved: the CURRENT
# value, so the corrected name is what has to be there, not the one that was superseded.
RECALL_EXPECT = {"fact": {"store": "facts", "value": DOG_CORRECTED},
                 "definition": {"definition": (TERM, MEANING)}}


def _norm(v):
    return " ".join((v or "").split()).casefold()


def matched(changes, expect, names) -> bool:
    """Did this step write what it was supposed to, judged over every store?"""
    if not expect:
        return True
    if "definition" in expect:
        return definition_written(changes, expect["definition"][0], expect["definition"][1], names=names)
    return any(store == expect["store"] and _norm(expect["value"]) in _norm(new)
               for store, _key, _old, new in changes)


def main() -> int:
    mode = "adapt"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    os.makedirs(SCRATCH, exist_ok=True)
    db = os.path.join(SCRATCH, f"matrix_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", mode)
    sid = sd.new_session(e, "matrix-teach")

    out = {"mode": mode, "steps": [], "recall": []}
    for label, msg, expect in STEPS:
        before = snapshot(e)
        with TurnCapture() as cap:
            r = sd.turn(e, sid, msg)
            wait_for_tail(e)
            step_trace = cap.decision()
        after = snapshot(e)
        changes = delta(before, after)
        ok = matched(changes, expect, after["entities"])
        out["steps"].append({"label": label, "message": msg, "expected": expect, "wrote": ok,
                             "trace": step_trace,
                             "changes": [[st, str(k), o, n] for st, k, o, n in changes],
                             "reply": (r.get("response") or "")[:140], "secs": r.get("_secs")})
        print(f"[{label:11}] wrote={'yes' if ok else 'NO '} envelope="
              f"{'yes' if step_trace['envelope_present'] else 'no '} action={step_trace['action']} "
              f":: {msg[:46]}", flush=True)
        for st, k, o, n in changes:
            print(f"              {st}: {str(k)[:48]} {str(o)[:28]!r} -> {str(n)[:40]!r}")

    # the correction must WIN, not coexist: the old value may survive only as history
    live = snapshot(e)
    stale = [f"{k}={v}" for k, v in live["facts"].items() if _norm(DOG_FIRST) == _norm(v)]
    out["correction_wins"] = not stale
    print(f"\ncorrection wins (no live fact still says {DOG_FIRST}): {not stale}  {stale or ''}")

    # a NEW session: nothing is carried in the conversation, only what was written -- and the
    # question is asked of the STORES as well, since an answer can come from episodic retrieval.
    empty = {"facts": {}, "assertions": {}, "directives": {}, "entities": {}}
    live_changes = delta(empty, live)
    sid2 = sd.new_session(e, "matrix-recall")
    for label, question, expected in ASK:
        r = sd.turn(e, sid2, question)
        wait_for_tail(e)
        said = _norm(expected) in _norm(r.get("response"))
        # A REPLY IS NOT A WRITE. The definition step showed exactly why: the assistant answered
        # "Understood, I've noted that ACME-7 refers to ..." and stored nothing, and a later session
        # still answered correctly -- from the raw conversation, not from anything learned. Scoring
        # the answer alone would have called that success, which is the failure class the judge
        # (92.E1) exists to catch.
        stored = matched(live_changes, RECALL_EXPECT[label], live["entities"])
        out["recall"].append({"label": label, "question": question, "expected": expected,
                              "answered": said, "backed_by_a_write": stored,
                              "reply": (r.get("response") or "")[:160]})
        print(f"[recall {label:9}] answered={'yes' if said else 'NO '} "
              f"backed_by_a_write={'yes' if stored else 'NO '} :: {(r.get('response') or '')[:70]}")

    wrote = sum(1 for s in out["steps"] if s["expected"] and s["wrote"])
    want = sum(1 for s in out["steps"] if s["expected"])
    recalled = sum(1 for x in out["recall"] if x["answered"])
    backed = sum(1 for x in out["recall"] if x["answered"] and x["backed_by_a_write"])
    print(f"\nTAUGHT AND WRITTEN: {wrote}/{want}   RECALLED IN A NEW SESSION: {recalled}/{len(ASK)}"
          f" (BACKED BY A WRITE: {backed}/{len(ASK)})   CORRECTION WINS: {out['correction_wins']}")
    print("The ambiguous step is reported, not forced: see its row above for what the protocol did.")
    print("versioned:", write_versioned("learning_matrix", out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
