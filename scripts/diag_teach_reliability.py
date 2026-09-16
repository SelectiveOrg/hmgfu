"""93.F — how often does teaching a definition actually land, and did phase 93 change that?

The transfer campaign dropped 5 of 12 episodes for invalid preparation where phase 92 dropped 1 of
12. That is a loss worth repairing, but 7/12 against 11/12 is not, on its own, outside chance — so it
is measured before anything is changed, and measured PAIRED against the one file the phase touched in
the perception path.

Each repetition is a fresh disposable base and a single teaching turn. The verdict comes from
`learning_oracle`: the right term, the right meaning, in a context, written to the store — not "some
definition appeared". The arms differ only by `hmgfu/turn_router.py`, swapped between the phase's
start commit and the working tree, so a difference is attributable to the contract and not to the
rest of the phase.

    python scripts/diag_teach_reliability.py [repetitions] [--baseline <commit>]
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402

TEACH = ("In this project, ACME-7 means Atlas Control Mesh.", "ACME-7", "Atlas Control Mesh")
ROUTER = os.path.join(ROOT, "hmgfu", "turn_router.py")


def one_run(rep: int) -> dict:
    """One teaching turn on a fresh base, in a fresh process-local engine."""
    import bench_say_do as sd
    from learning_capture import TurnCapture
    from learning_oracle import delta, judge_turn, snapshot
    from hmgfu.turn_tail import wait_for_tail

    db = os.path.join(SCRATCH, f"teachrel_{os.getpid()}_{rep}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")
    sid = sd.new_session(e, f"teachrel-{rep}")
    before = snapshot(e)
    with TurnCapture() as cap:
        r = sd.turn(e, sid, TEACH[0])
        wait_for_tail(e)
        trace = cap.decision()
    after = snapshot(e)
    verdict = judge_turn(delta(before, after), expect_definition=(TEACH[1], TEACH[2]),
                         names=after["entities"])
    return {"rep": rep, "ok": verdict["definition_ok"], "action": trace["action"],
            "proposed": trace["proposed"], "envelope": trace["envelope_present"],
            "changes": [[a, str(b), c, d] for a, b, c, d in delta(before, after)],
            "secs": r.get("_secs")}


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8
    if "--child" in sys.argv:                       # one arm, inside its own process
        rows = [one_run(i + 1) for i in range(reps)]
        print("__RESULT__" + json.dumps(rows))
        return 0

    baseline = sys.argv[sys.argv.index("--baseline") + 1] if "--baseline" in sys.argv else "742dea6"
    os.makedirs(SCRATCH, exist_ok=True)
    saved = os.path.join(SCRATCH, "turn_router_working.py")
    shutil.copyfile(ROUTER, saved)
    arms = {}
    try:
        for arm in ("candidate", "baseline"):
            if arm == "baseline":                   # only the router differs between the arms
                blob = subprocess.run(["git", "show", f"{baseline}:hmgfu/turn_router.py"],
                                      cwd=ROOT, capture_output=True, text=True, check=True).stdout
                open(ROUTER, "w", encoding="utf-8", newline="").write(blob)
            out = subprocess.run([sys.executable, os.path.abspath(__file__), str(reps), "--child"],
                                 cwd=ROOT, capture_output=True, text=True)
            line = next((l for l in out.stdout.split("\n") if l.startswith("__RESULT__")), "")
            rows = json.loads(line[len("__RESULT__"):]) if line else []
            arms[arm] = rows
            hit = sum(1 for x in rows if x["ok"])
            print(f"[{arm:9}] taught correctly {hit}/{len(rows)}"
                  f"  (no envelope: {sum(1 for x in rows if not x['envelope'])})", flush=True)
    finally:
        shutil.copyfile(saved, ROUTER)              # the working tree is restored whatever happens

    c = sum(1 for x in arms.get("candidate", []) if x["ok"])
    b = sum(1 for x in arms.get("baseline", []) if x["ok"])
    n = reps
    print(f"\ncandidate {c}/{n}  vs  baseline({baseline}) {b}/{n}")
    print("A difference of one or two at this size is not a finding; it says what to measure next.")
    print("versioned:", write_versioned("teach_reliability", {"arms": arms, "reps": reps,
                                                              "baseline": baseline}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
