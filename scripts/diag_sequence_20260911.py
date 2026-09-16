"""93.C — the whole sequence of the real conversation of 2026-09-11, as a DEV episode.

`reports/codex_latest_conversation_20260911/ANALISE.md` reads one real session; this replays its
SHAPE on a disposable base with explicit fixtures, so the behaviour can be exercised without the
private history and without touching real memory. The guide asks for the sequence, not the sentences:
a behaviour correction, a confirmation, the removal, questions about the plan, teaching a conditional
preference, and finally a request for something unrelated.

Each step declares what must be true afterwards and is judged on the STORES and the TRACE, never on
the wording of the reply:

  1. fixture      an `output_prefix` directive is in force, as it was before the conversation
  2. correction   "stop saying none" must reach the DIRECTIVE mechanism, not become a plan
  3. removal      the prefix must actually stop, and the claim about it must be supported
  4. plan probe   asking about the plan must not leave a permanent task behind
  5. teaching     a conditional preference must leave a policy, not only an episode
  6. task switch  an explicit widget request must not inherit an obsolete plan's scope

    python scripts/diag_sequence_20260911.py [--mode confirm|adapt]
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
from learning_oracle import delta, snapshot  # noqa: E402
from sequence_verdict import failures_of, taught_policy, tool_succeeded  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

PREFIX = "none"
# what the teaching step must leave in the store, checked by value AND by the exception
POLICY_VALUE = "short snippets"
# declared BEFORE any run: the same statement in the two persons the model uses. Equivalence is
# still strict inside each -- an added "or whenever convenient" fails against both.
POLICY_CONDITION = ["unless I ask for the full context",
                    "unless the user asks for the full context"]
STEPS = [
    ("correction", "stop saying none at the start of every reply"),
    ("confirmation", "yes"),
    ("plan_probe", "is that plan still needed?"),
    ("teaching", "I prefer short snippets unless I ask for the full context."),
    ("recall_probe", "what do you know about how I like answers?"),
    # a request unrelated to the plan's memory_search scope, for a type the product actually HAS.
    # 93.R1: the probe used to ask for a "timer" widget, which does not exist -- the call failed every
    # time and the old gate counted the failed call as a creation.
    ("task_switch", "create a note widget titled Timer with the text 20 minutes"),
]


def directive_value(e, kind="output_prefix"):
    for d in e.directives.active():
        if d.get("kind") == kind:
            return d.get("value")
    return None


def main() -> int:
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "confirm"
    os.makedirs(SCRATCH, exist_ok=True)
    db = os.path.join(SCRATCH, f"seq911_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", mode)
    sid = sd.new_session(e, "seq-20260911")

    # fixture: the prefix that was in force before the real conversation started
    e.directives.apply("always start your replies with 'none'", "user_explicit",
                       detected={"kind": "output_prefix", "value": PREFIX,
                                 "instruction": "always start your replies with 'none'",
                                 "fallback_text": ""})
    out = {"mode": mode, "fixture_prefix": directive_value(e), "steps": []}
    print(f"fixture output_prefix = {out['fixture_prefix']!r}")

    for label, msg in STEPS:
        before = snapshot(e)
        with TurnCapture() as cap:
            r = sd.turn(e, sid, msg)
            wait_for_tail(e)
            trace = cap.decision()
            # guide 3: an absent trace is inconclusive, so record whether the router was even GIVEN
            # the envelope contract. "no envelope" then separates "never asked" from "asked, said no".
            contract = any("memory_update" in p for p in cap.payloads)
            router_called = cap.router_called
        after = snapshot(e)
        row = {
            "label": label, "message": msg,
            "changes": [[st, str(k), o, n] for st, k, o, n in delta(before, after)],
            "prefix_after": directive_value(e),
            "envelope": trace["envelope_present"], "action": trace["action"],
            "router_called": router_called, "envelope_contract_sent": contract,
            "proposed": trace["proposed"], "reason": trace["reason"],
            "plan": (e.session_plans.resumable(sid) or {}).get("title"),
            "plan_status": (e.session_plans.resumable(sid) or {}).get("status"),
            "pending_plan": bool(e.session_plans.pending(sid)),
            "tools": r.get("_tools"), "blocked": [t["name"] for t in r.get("tool_trace", [])
                                                  if t.get("blocked")],
            # 93.R1: `_tools` lists every call, failed and blocked included, so success is asked of
            # the trace itself; and the policy is asked of the STORE, not of the envelope.
            "widget_succeeded": tool_succeeded(r.get("tool_trace"), "create_widget"),
            "widget_failures": failures_of(r.get("tool_trace"), "create_widget"),
            "policy_in_store": taught_policy(e.directives.active(), expect_value=POLICY_VALUE,
                                             expect_condition=POLICY_CONDITION),
            # separates "nothing was stored" from "stored, but the exception was dropped"
            "policy_value_only": taught_policy(e.directives.active(), expect_value=POLICY_VALUE),
            "reply": (r.get("response") or "")[:160], "secs": r.get("_secs"),
        }
        out["steps"].append(row)
        print(f"[{label:13}] prefix={str(row['prefix_after'])[:6]:6} "
              f"router={'yes' if row['router_called'] else 'no '} "
              f"contract={'yes' if row['envelope_contract_sent'] else 'NO '} envelope="
              f"{'yes' if row['envelope'] else 'no '} action={row['action']} "
              f"plan={str(row['plan'])[:26]:26} blocked={row['blocked']} changes={len(row['changes'])}",
              flush=True)

    # the four questions the analysis says must be answered by the stores, not the wording
    steps = {s["label"]: s for s in out["steps"]}
    verdict = {
        "prefix_removed": steps["correction"]["prefix_after"] in (None, "") or
                          steps["confirmation"]["prefix_after"] in (None, ""),
        "no_permanent_task_from_a_promise": steps["plan_probe"]["plan_status"] in
                                            (None, "abandoned", "superseded", "done"),
        # 93.R1: the policy must BE in the store, with the value and the exception the user stated.
        "teaching_persisted": bool(steps["teaching"]["policy_in_store"]),
        "widget_not_blocked": not steps["task_switch"]["blocked"],
        "widget_created": bool(steps["task_switch"]["widget_succeeded"]),
    }
    # kept as its OWN metric, never folded into the gate: it separates "perception said nothing" from
    # "perception spoke and the write did not land".
    out["envelope_emitted"] = {s["label"]: bool(s["envelope"]) for s in out["steps"]}
    out["widget_failures"] = steps["task_switch"]["widget_failures"]
    out["policy_stored_without_its_condition"] = bool(
        steps["teaching"]["policy_value_only"] and not steps["teaching"]["policy_in_store"])
    out["verdict"] = verdict
    print()
    for k, v in verdict.items():
        print(f"  {'ok ' if v else 'FAIL'} {k}")
    if out["policy_stored_without_its_condition"]:
        print("  note: the policy WAS stored, but the exception the user stated was dropped")
    if out["widget_failures"]:
        print(f"  note: create_widget failed: {json.dumps(out['widget_failures'], ensure_ascii=False)[:140]}")
    print("versioned:", write_versioned("sequence_20260911", out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
