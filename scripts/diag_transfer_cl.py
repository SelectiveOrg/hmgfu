"""Phase 92.E5R — C versus L, measured at the boundary where the arms actually differ.

Recalling a value that was stored is RETENTION, and both arms do it. TRANSFER is reusing the
*interpretation* on a formulation the system does not already handle, for a different value.

Every earlier run of this probe is an INVALID TRIAL for that question, and the reason is kept in
sight rather than tidied away: `classify_turn` built the CONFIRMED INTERPRETATIONS block and then
composed the system message without it, so both arms sent an identical request and no difference
could have been caused by examples the model never saw. The instruments missed it because they all
watched the PRODUCER. This version therefore:

  * captures the REAL system message handed to the model on every turn and records whether the
    example was delivered -- an episode that cannot prove delivery proves nothing;
  * validates the PREPARATION by term, meaning and context. An inverted definition
    (`Cluster Routing Daemon` defined as `CRD-3`) is not successful teaching, and its episode is
    excluded instead of being counted as a failure of transfer;
  * judges every write across the ledger, the assertions and the directives through
    `scripts/learning_oracle.py`, against allowances declared up front, rather than asking whether
    some definition appeared;
  * records a clarifying QUESTION as its own outcome, because asking about a genuinely ambiguous
    wording can be correct behaviour and is not the same as failing to perceive it.

Synthetic bases, invented terms, no real memory.

    python scripts/diag_transfer_cl.py [repetitions] [--teach2]
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from learning_capture import TurnCapture as _Turn  # noqa: E402
from learning_oracle import delta, judge_turn, snapshot  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

TEACH = ("In this project, ACME-7 means Atlas Control Mesh.", "ACME-7", "Atlas Control Mesh")
# a SECOND teaching, in a form the baseline handles, for the (still untested) "one example is too
# little" hypothesis. Its preparation is checked by the same rule: if it lands inverted it does not
# count as teaching.
TEACH2 = ("We call the Cluster Routing Daemon CRD-3 around here.", "CRD-3", "Cluster Routing Daemon")

# (label, message, expected definition or None, allowances for the OTHER stores)
PROBES = [
    ("transfer_dash", "DELTA-9 - Dynamic Ledger Transfer Adapter.",
     ("DELTA-9", "Dynamic Ledger Transfer Adapter"), []),
    ("transfer_qa", "OMEGA-1? Operational Metrics Gateway.",
     ("OMEGA-1", "Operational Metrics Gateway"), []),
    # a preference stated in the shape of a definition: recording the preference is legitimate,
    # defining IOTA-7 is not.
    ("neg_dash_shape", "IOTA-7 - my favourite ticket this week.", None,
     [{"store": "facts", "value": "IOTA-7"}]),
    ("neg_qa_shape", "PSI-3? Never heard of it.", None, []),
    ("neg_opinion", "GAMMA-3 is a nice name, isn't it?", None, []),
]
EXPECTED = {label: expect for label, _m, expect, _a in PROBES}


def teach(e, sid, item) -> dict:
    """One teaching turn, graded by the same oracle that grades the probes."""
    msg, term, meaning = item
    before = snapshot(e)
    with _Turn():
        r = sd.turn(e, sid, msg)
        wait_for_tail(e)
    after = snapshot(e)
    verdict = judge_turn(delta(before, after), expect_definition=(term, meaning),
                         names=after["entities"])
    return {"message": msg, "term": term, "meaning": meaning, "prepared": verdict["definition_ok"],
            "undue": [[str(x) for x in c] for c in verdict["undue"]], "secs": r.get("_secs")}


def run_arm(mode: str, rep: int, teach2: bool = False) -> dict:
    db = os.path.join(SCRATCH, f"transfer_{mode}_{rep}_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", mode)
    sid = sd.new_session(e, f"transfer-{mode}-{rep}")
    out = {"mode": mode, "rep": rep, "turns": [], "teachings": [teach(e, sid, TEACH)]}
    if teach2:
        out["teachings"].append(teach(e, sid, TEACH2))
    out["prepared"] = all(t["prepared"] for t in out["teachings"])
    # what the arm WOULD offer, recorded next to what was actually delivered per turn
    out["examples_block"] = e.sensitizer._learning_examples_text(PROBES[0][1])
    needle = out["examples_block"].split("\n")[0].strip("- ")[:60] if out["examples_block"] else ""
    out["needle"] = needle
    for label, msg, expect, allowed in PROBES:
        before = snapshot(e)
        with _Turn() as t:
            r = sd.turn(e, sid, msg)
            wait_for_tail(e)
            # "not delivered" has two very different causes: the router ran and the block was
            # missing, or the router never ran at all (the pre-router can bypass it). Recording both
            # keeps a bypassed turn from being read as a missing example.
            step, called = t.decision(), t.router_called
            block, taught = t.delivered_block(), t.contains(needle)
            delivered = bool(block)
        after = snapshot(e)
        verdict = judge_turn(delta(before, after), expect_definition=expect, allowed=allowed,
                             names=after["entities"])
        out["turns"].append({"label": label, "message": msg, "expect": expect, "trace": step,
                             "example_delivered": delivered, "delivered_block": block,
                             "taught_example_delivered": taught, "router_called": called, "verdict": verdict,
                             "asked": step["action"] == "ask",
                             "reply": (r.get("response") or "")[:120], "secs": r.get("_secs")})
        mark = "ok " if verdict["correct"] else "MISS"
        print(f"  [{mode:7}#{rep}] {mark} {label:15} "
              f"example={'yes' if delivered else ('no ' if called else 'n/a')} "
              f"def_ok={str(verdict['definition_ok']):5} undue={len(verdict['undue'])} "
              f"action={step['action']}", flush=True)
    return out


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3
    teach2 = "--teach2" in sys.argv[1:]
    os.makedirs(SCRATCH, exist_ok=True)
    arms = {"confirm": [], "adapt": []}
    for rep in range(1, reps + 1):
        print(f"repetition {rep}/{reps}" + (" (two teachings)" if teach2 else ""), flush=True)
        for mode in ("confirm", "adapt"):
            arms[mode].append(run_arm(mode, rep, teach2))

    valid = {m: [a for a in arms[m] if a["prepared"]] for m in arms}
    dropped = {m: len(arms[m]) - len(valid[m]) for m in arms}
    print(f"\nepisodes with VALID preparation: C={len(valid['confirm'])}/{len(arms['confirm'])}  "
          f"L={len(valid['adapt'])}/{len(arms['adapt'])}   (dropped unprepared: {dropped})")
    delivered = sum(1 for a in valid["adapt"] for t in a["turns"] if t["example_delivered"])
    chances = sum(len(a["turns"]) for a in valid["adapt"])
    leaked = sum(1 for a in valid["confirm"] for t in a["turns"] if t["example_delivered"])
    called = sum(1 for a in valid["adapt"] for t in a["turns"] if t["router_called"])
    print(f"router actually called (L): {called}/{chances}")
    taught_seen = sum(1 for a in valid["adapt"] for t in a["turns"] if t["taught_example_delivered"])
    print(f"of those, the TAUGHT example specifically: {taught_seen}/{chances} "
          f"(the rest are later confirmations, selected by the newest case's context)")
    print(f"example DELIVERED to the model: L={delivered}/{chances}  "
          f"C={leaked}/{sum(len(a['turns']) for a in valid['confirm'])}  (C must be 0)")

    summary = {}
    print()
    for label, _msg, expect, _allowed in PROBES:
        row = {}
        for m in ("confirm", "adapt"):
            turns = [t for a in valid[m] for t in a["turns"] if t["label"] == label]
            row[m] = {"correct": sum(1 for t in turns if t["verdict"]["correct"]),
                      "definition_ok": sum(1 for t in turns if t["verdict"]["definition_ok"]),
                      "undue": sum(len(t["verdict"]["undue"]) for t in turns),
                      "asked": sum(1 for t in turns if t["asked"]), "n": len(turns)}
        summary[label] = row
        c, l = row["confirm"], row["adapt"]
        want = "define" if expect else "no definition"
        print(f"{label:15} {want:14} C={c['correct']}/{c['n']} (undue {c['undue']}, asked {c['asked']})"
              f"   L={l['correct']}/{l['n']} (undue {l['undue']}, asked {l['asked']})")

    gained = [k for k, v in summary.items()
              if EXPECTED[k] and v["adapt"]["correct"] > v["confirm"]["correct"]]
    print(f"\nTRANSFER GAINED BY L: {gained or 'none'}")
    if delivered == 0:
        print("NOT A MEASUREMENT: the example was never delivered, so nothing is attributable to L.")
    print("versioned:", write_versioned("transfer_cl", {"arms": arms, "summary": summary,
                                                        "reps": reps, "teach2": teach2,
                                                        "dropped_unprepared": dropped,
                                                        "delivered": [delivered, chances]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
