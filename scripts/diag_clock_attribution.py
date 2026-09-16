"""Phase 91.X1 — close the attribution of the clock override with the REAL router, not an injected classification.

The independent diagnosis reproduced the mechanism by injecting `runtime_context_sufficient=True`. That proves the
GATE behaves as described; it does not prove the live router actually produced that classification for the user's two
messages. This script closes the gap: it replays those messages through a real `AgentEngine` on a THROWAWAY database
and records, per turn,

    the router's own classification (conversation_act, runtime_context_sufficient, runtime_context_keys),
    the reply BEFORE `ground_reply` and the reply AFTER it,
    whether the gate fired and with which values.

The before/after capture wraps `runtime_context.ground_reply` from OUTSIDE — this script monkeypatches its own import
for the duration of the run. No product module is modified, and the real memory is never opened.

    python scripts/diag_clock_attribution.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

# the user's own turns, verbatim from the transcript (session b8616721, turns 5-7), plus the controls that must keep
# working: a legitimate clock request, and a mixed request that asks for the time AND something else.
TURNS = [
    ("setup", "do you know baby's?"),
    ("t6_ambiguous", "but babys is also babys"),
    ("t7_complaint", "why are you saying the time? you could just ask me what do i mean is okay to ask if you dont understand"),
    ("control_legit", "what time is it?"),
    ("control_mixed", "what time is it, and what is my dog called?"),
    ("control_mention", "I hate it when apps show me the time I did not ask for"),
]


# 91.Z6: the eight cases from reports/codex_review_91y/REVIEW.md Finding 3. The reviewer ran the router
# only and explicitly did not run the answer/re-ask loop; these go through the FULL turn so the reply
# BEFORE and AFTER the gate is observed, including whether a mixed answer keeps its non-clock half.
REVIEW91Y = [
    ("weather_today", "What is the weather in Valencia today?"),
    ("clock_diagnosis", "Why is my clock showing the wrong time today?"),
    ("current_project", "What is my current main project?"),
    ("timezone", "What is my timezone?"),
    ("complaint_pt", "Porque estas a responder com a hora agora?"),
    ("time_philosophy", "Why does time seem to pass faster as we get older?"),
    ("legit_request", "What time is it right now?"),
    ("legit_request_pt", "Diz-me a data de hoje, por favor."),
    ("mixed_complete", "What time is it, and what is my dog called?"),
]


def main() -> int:
    import hmgfu.runtime_context as rc
    captured = []
    original = rc.ground_reply

    calls = {"n": 0}

    def counting(provider):
        """Count the chat calls the gate makes, so an invocation is visible even when the re-ask
        returns identical text (91.AA4: `fired` used to mean only that the text changed)."""
        real = provider.chat

        def chat(*a, **k):
            calls["n"] += 1
            return real(*a, **k)
        provider.chat = chat
        return provider

    def spy(engine, reply, user_message, query, runtime, system):
        resolve = engine.registry.resolve
        engine.registry.resolve = lambda role: (counting(resolve(role)[0]), resolve(role)[1]) if role == "chat" else resolve(role)
        before_calls = calls["n"]
        try:
            out = original(engine, reply, user_message, query, runtime, system)
        finally:
            engine.registry.resolve = resolve
        reasked = calls["n"] > before_calls
        captured.append({"message": user_message[:120], "before": (reply or "")[:400], "after": (out or "")[:400],
                         "reasked": reasked,          # 91.AA4: an invocation happened
                         "changed": out != reply,      # 91.AA4: and the text actually differs
                         "fired": reasked,             # kept for existing readers: now means INVOKED
                         "sufficient": bool(getattr(query, "runtime_context_sufficient", False)),
                         "keys": list(getattr(query, "runtime_context_keys", []) or []),
                         "act": getattr(query, "conversation_act", None),
                         "action_requested": getattr(query, "action_requested", None)})
        return out

    rc.ground_reply = spy      # agent.py imports the symbol at call time, so this patch is seen

    turns = REVIEW91Y if "--review91y" in sys.argv else TURNS
    clone = os.path.join(SCRATCH, f"clock_attr_{os.getpid()}.db")
    if os.path.exists(clone):
        os.remove(clone)
    open(clone, "wb").close()             # a THROWAWAY empty base; the real memory is never opened
    e = sd.fresh_engine(clone, None)
    sid = sd.new_session(e, "clock-attribution")
    rows = []
    try:
        for label, msg in turns:
            r = sd.turn(e, sid, msg)
            wait_for_tail(e)
            cap = captured[-1] if captured else {}
            rows.append({"label": label, "message": msg, "final_reply": (r.get("response") or "")[:400],
                         "secs": r.get("_secs"), **{k: cap.get(k) for k in
                                                    ("sufficient", "keys", "act", "action_requested", "reasked", "changed", "fired", "before", "after")}})
            print(f"\n[{label}] {msg!r}")
            print(f"   router: act={cap.get('act')} sufficient={cap.get('sufficient')} keys={cap.get('keys')} action={cap.get('action_requested')}")
            print(f"   gate re-asked: {cap.get('reasked')} - text changed: {cap.get('changed')}")
            print(f"   BEFORE: {(cap.get('before') or '')[:180]!r}")
            print(f"   AFTER : {(cap.get('after') or '')[:180]!r}")
    finally:
        rc.ground_reply = original
        try:
            e.graph.close()
        except Exception:
            pass
    reasked = [r for r in rows if r.get("reasked")]
    changed = [r for r in rows if r.get("changed")]
    print(f"\nATTRIBUTION: the gate RE-ASKED on {len(reasked)}/{len(rows)} turns {[r['label'] for r in reasked]}; "
          f"the TEXT CHANGED on {len(changed)}/{len(rows)} {[r['label'] for r in changed]}")
    print("versioned:", write_versioned("clock_attribution", {"rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
