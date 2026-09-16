"""93.Q2 — does the clarification cycle close, and is it the PENDENCY that closes it?

The protocol refuses to ask on silence: a question is raised only when the envelope itself declares an
ambiguity and a write is at stake (`learning_protocol.decide`). What this walks is whether that path
fires with the real model, and whether the chain closes behind it.

The independent review of 93.P found the previous version of this probe could not support the claim it
was making, and re-judging the artefacts on disk (`rejudge_clarification.py`) confirmed every part of
it:

  * `named_answer_wrote = bool(changes)` credited any delta. The writes turned out to be exact, but in
    one run of three the named answer's action was `pass_through` — the ORDINARY ingest wrote it and
    the clarification cycle was not what closed;
  * `applied_in_a_new_session = "project" in reply.lower()` passes on
    `Nimbus is not a project. I don't know what it is.`;
  * the stored reply was truncated at 140 characters, so two of the three "applied" verdicts could
    not be checked at all, in either direction;
  * and the "named answer" was `Nimbus is the name of my current project.` — a COMPLETE statement that
    teaches with no question before it, so the run never isolated use of the pending case.

So there are four arms, and the comparison between them is the measurement:

  pendency        — the ambiguous teaching, the question, a bare answer, then the ELLIPTICAL answer
                    `my current project`, which means nothing unless `Nimbus` was preserved;
  pendency_longer — the same with `the project I am working on`: still carrying no value of its own,
                    but not as bare. The pair separates the pendency from the bareness;
  complete        — the same, but answered with the complete statement;
  control         — the complete statement alone, with no question before it.

If `control` teaches as well as `complete`, then `complete` says nothing about the cycle. Only the
two elliptical arms can, which is why they are here.

Every verdict goes through the shared judges: `learning_oracle` for what was written, `answer_oracle`
for whether a reply actually asserts it.

    python scripts/diag_clarification.py [repetitions]
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from answer_oracle import POSSESSIVE, answered  # noqa: E402
from learning_capture import TurnCapture  # noqa: E402
from learning_oracle import delta, snapshot  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

# no referent: "it" could be anything, which is what an ambiguity IS
AMBIGUOUS = "It is called Nimbus."
CLEAR = "In this project, ACME-7 means Atlas Control Mesh."
PRAISE = "That was a great answer, thank you!"
GREETING = "hello, how are you today?"
# the two answers the arms turn on. The first is a complete statement and teaches on its own; the
# second is an answer, and is intelligible only through the value the question preserved.
COMPLETE = "Nimbus is the name of my current project."
ELLIPTICAL = "my current project"
# 93.Q2: a LONGER elliptical answer. It still carries no "Nimbus", so it too can only teach through
# the preserved value -- but it names the thing as a noun phrase with a verb-free clause of its own.
# Measuring the two apart is what says whether the boundary is the pendency or the bareness.
ELLIPTICAL_LONGER = "the project I am working on"
SUBJECT, VALUE = "Nimbus", "the name of my current project"
ARMS = ("pendency", "pendency_longer", "complete", "control")
FILLER = {"pendency": ELLIPTICAL, "pendency_longer": ELLIPTICAL_LONGER}


def _turn(e, sid, msg):
    before = snapshot(e)
    with TurnCapture() as cap:
        r = sd.turn(e, sid, msg)
        wait_for_tail(e)
        decision = cap.decision()
    changes = delta(before, snapshot(e))
    return {"message": msg, "action": decision["action"], "reason": decision["reason"],
            "proposed": decision["proposed"], "envelope": decision["envelope_present"],
            "question_in_reply": "?" in (r.get("response") or ""),
            "changes": [[a, str(b), c, d] for a, b, c, d in changes],
            # 93.Q2: the WHOLE reply. Truncating it at 140 characters made two of three "applied"
            # verdicts uncheckable in the artefact the claim was published from.
            "reply": r.get("response") or ""}


def _wrote_the_value(step) -> list:
    """The changes that wrote EXACTLY the taught value, whichever adapter wrote them.

    The cycle can legitimately close through the personal-fact adapter (`project.main = Nimbus`) or
    through the definition adapter; what may not vary is the value."""
    return [c for c in step["changes"]
            if " ".join(str(c[3] or "").split()).casefold() == SUBJECT.casefold()]


def run(rep: int, arm: str, answer: str) -> dict:
    db = os.path.join(SCRATCH, f"clarify_{os.getpid()}_{arm}_{rep}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")
    sid = sd.new_session(e, f"clarify-{arm}-{rep}")
    out = {"rep": rep, "arm": arm, "answer": answer, "steps": []}

    if arm == "control":
        # the control has no question to answer, which is the point: whatever it teaches, it teaches
        # without one, and cannot be counted as the cycle closing.
        out["asked"] = False
        out["steps"].append(_turn(e, sid, COMPLETE))
        taught = out["steps"][-1]
    else:
        out["steps"].append(_turn(e, sid, AMBIGUOUS))
        out["asked"] = out["steps"][-1]["action"] == "ask"
        # 93.Q2: a "no" REJECTS the pending case and a "maybe" defers it, so in those reps there is
        # no awaiting case left for a filler to fill and the arm could not measure the cycle even in
        # principle -- at most one rep in three was ever a real trial. The elliptical arms therefore
        # answer "yes", which 93.P3 established cannot fill a blank: the negative is still measured
        # AND the pendency survives to be answered. Reject and defer keep their coverage in the
        # `complete` arm and in v154.
        out["steps"].append(_turn(e, sid, "yes" if arm in FILLER else answer))
        out["wrote_after_bare_answer"] = bool(out["steps"][-1]["changes"])
        out["steps"].append(_turn(e, sid, FILLER.get(arm) or COMPLETE))
        taught = out["steps"][-1]

    out["taught_action"] = taught["action"]
    out["exact_writes"] = _wrote_the_value(taught)
    out["taught_exactly"] = bool(out["exact_writes"])
    # 93.Q2: `pass_through` means the ordinary ingest wrote it and the protocol was not the mechanism.
    # Recorded separately rather than folded into the success gate, so the two can never be conflated.
    out["by_the_protocol"] = taught["action"] in ("commit", "adapt")

    out["steps"].append(_turn(e, sid, PRAISE))
    out["praise_wrote"] = bool(out["steps"][-1]["changes"])
    out["steps"].append(_turn(e, sid, GREETING))
    out["greeting_asked"] = out["steps"][-1]["action"] == "ask"

    other = sd.new_session(e, f"clarify-{arm}-{rep}-new")
    recall = _turn(e, other, "what is Nimbus?")
    out["steps"].append(recall)
    # 93.Q2: BOTH judgements, because the first one was too strict and was corrected after seeing
    # results. `wording` asks for the taught sentence's own content words; `meaning` asks that Nimbus
    # be asserted to be the USER'S project, which is what was actually taught. Reporting both is what
    # keeps the correction honest -- neither number is quietly replaced by the other.
    wording = answered(recall["reply"], subject=SUBJECT, value=VALUE)
    verdict = answered(recall["reply"], subject=SUBJECT, value="project", qualifier=POSSESSIVE)
    out["applied_by_wording"] = bool(wording["ok"])
    out["applied_in_a_new_session"] = bool(verdict["ok"])
    out["applied_why"] = verdict["why"]
    print(f"[{rep}] {arm:9} answer={answer:6} asked={out['asked']} "
          f"taught={out['taught_action']:20} exact={out['taught_exactly']} "
          f"by_protocol={out['by_the_protocol']} applied={out['applied_in_a_new_session']} "
          f"({out['applied_why']})", flush=True)
    return out


def _count(rows, arm, key):
    got = [r for r in rows if r["arm"] == arm]
    return sum(1 for r in got if r.get(key)), len(got)


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3
    os.makedirs(SCRATCH, exist_ok=True)
    answers = (["yes", "no", "maybe"] * 4)[:reps]
    rows = [run(i + 1, arm, ans) for arm in ARMS for i, ans in enumerate(answers)]

    print("\nthe three arms, by what the teaching turn actually did")
    for arm in ARMS:
        exact, n = _count(rows, arm, "taught_exactly")
        proto, _ = _count(rows, arm, "by_the_protocol")
        applied, _ = _count(rows, arm, "applied_in_a_new_session")
        by_wording, _ = _count(rows, arm, "applied_by_wording")
        asked, _ = _count(rows, arm, "asked")
        print(f"  {arm:9} asked {asked}/{n}   wrote the exact value {exact}/{n}   "
              f"of which through the protocol {proto}/{n}   a new session applied it {applied}/{n} "
              f"(by the taught wording alone {by_wording}/{n})")
    longer, nlonger = _count(rows, "pendency_longer", "taught_exactly")
    pend, npend = _count(rows, "pendency", "taught_exactly")
    ctrl, nctrl = _count(rows, "control", "taught_exactly")
    comp, ncomp = _count(rows, "complete", "taught_exactly")
    print("\nwhat that comparison supports:")
    print(f"  the COMPLETE statement teaches {comp}/{ncomp} after a question and {ctrl}/{nctrl} with "
          f"none, so that arm measures the statement, not the cycle")
    print(f"  the ELLIPTICAL answer teaches {pend}/{npend} bare and {longer}/{nlonger} as a longer "
          f"phrase; neither carries the value, so both can only teach through the pendency -- and "
          f"the difference between them is bareness, not the cycle")

    print("\nthe safety negatives (each must be 0)")
    print(f"  praise wrote something: {sum(1 for r in rows if r.get('praise_wrote'))}/{len(rows)}")
    print(f"  a greeting raised a question: {sum(1 for r in rows if r.get('greeting_asked'))}/{len(rows)}")
    bare = [r for r in rows if r["arm"] not in ("control",)]
    print(f"  a bare yes/no/maybe wrote against a fill-in question: "
          f"{sum(1 for r in bare if r.get('wrote_after_bare_answer'))}/{len(bare)}"
          f"   (it answers a different act and cannot fill a blank)")
    if not any(r.get("asked") for r in rows):
        print("\nNOT A MEASUREMENT of the chain: no question was ever delivered, so nothing the "
              "answers did can be attributed to one. The ask path exists (decide() on a declared "
              "ambiguity) but did not fire here.")
    print("versioned:", write_versioned("clarification", {"rows": rows, "reps": reps, "arms": ARMS}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
