"""93.W — the clearest defect left: a definition is taught, answered correctly, and not written.

From the 93.V artefacts. `In this project, ACME-7 means Atlas Control Mesh.` produced **zero** store
changes in the candidate's first repetition and **one** in the second — same sentence, same empty
base, different outcome — and in both the new session answered correctly, from episodic memory. Until
that write is reliable, "learned" and "remembered" cannot be told apart, which is also why transfer
cannot be measured.

So this asks the same teaching N times on a fresh base each time and separates the two possible
causes, which need different fixes:

  * **no envelope** — the router did not propose anything, so nothing reached the protocol;
  * **envelope refused** — it proposed, and the decision table said no. Then the reason is the finding.

It records the envelope and the decision verbatim, because "it did not write" is a symptom shared by
both and has already been mistaken for the second when it was the first (93.R4).

    python scripts/diag_definition_write.py [repetitions]
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from learning_capture import TurnCapture  # noqa: E402
from learning_oracle import definition_written, delta, snapshot  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
TERM, MEANING = "ACME-7", "Atlas Control Mesh"


def run(rep: int) -> dict:
    db = os.path.join(SCRATCH, f"defwrite_{os.getpid()}_{rep}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")
    sid = sd.new_session(e, f"defwrite-{rep}")
    before = snapshot(e)
    with TurnCapture() as cap:
        r = sd.turn(e, sid, TEACH)
        wait_for_tail(e)
        decision = cap.decision()
    after = snapshot(e)
    changes = delta(before, after)
    wrote = definition_written(changes, TERM, MEANING, names=after.get("entities"))
    row = {"rep": rep, "envelope": decision["envelope_present"], "action": decision["action"],
           "reason": decision["reason"], "proposed": decision["proposed"],
           "wrote_the_definition": bool(wrote),
           "changes": [[a, str(b), c, d] for a, b, c, d in changes],
           "reply": (r.get("response") or "")[:160]}
    row["cause"] = ("no envelope" if not decision["envelope_present"]
                    else "written" if wrote else f"refused: {decision['reason'][:60]}")
    print(f"[{rep}] envelope={row['envelope']!s:5} action={row['action']:22} "
          f"wrote={row['wrote_the_definition']!s:5} {row['cause']}", flush=True)
    return row


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 6
    os.makedirs(SCRATCH, exist_ok=True)
    rows = [run(i + 1) for i in range(reps)]
    wrote = sum(1 for r in rows if r["wrote_the_definition"])
    causes = Counter(r["cause"] for r in rows)
    print(f"\nthe definition was written {wrote}/{reps}")
    print("why not, when not:")
    for cause, n in causes.most_common():
        print(f"  {n}x  {cause}")
    if any(not r["envelope"] for r in rows):
        print("\nAn absent envelope is a PERCEPTION result, not a protocol one: nothing reached the "
              "decision table, so no guard refused anything. Those runs say nothing about the "
              "protocol and must not be counted against it.")
    for r in rows:
        if r["envelope"] and not r["wrote_the_definition"]:
            print(f"\nrefused with a proposal on the table (rep {r['rep']}):")
            print(f"  {json.dumps(r['proposed'], ensure_ascii=False)[:400]}")
            print(f"  reason: {r['reason']}")
    print("versioned:", write_versioned("definition_write", {"rows": rows, "reps": reps}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
