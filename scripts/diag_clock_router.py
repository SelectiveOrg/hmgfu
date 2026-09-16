"""Phase 91.X1 — what the LIVE router actually says about turns that ASK for the time and turns
that merely talk about it.

The gate can only be as good as the signal it reads. This battery calls the real router (no full
turn, no injected value) on a labelled set of PT/EN sentences and reports, per sentence, the
classification and whether the candidate precondition `_clock_requested` would let the clock ground
the answer. The label is the ground truth: does this turn ask for a current date/time?

    python scripts/diag_clock_router.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.runtime_context import RuntimeContext, _clock_requested  # noqa: E402
from hmgfu.models import QueryPoint  # noqa: E402

# (asks_for_the_clock, sentence[, added_after_the_first_run])
# 91.Y5: the four turns marked True were added AFTER the first run. They are labelled so the shared
# fifteen can be read on their own -- 13/15 -> 19/19 was never a paired rate on an unchanged set.
CASES = [
    (True,  "what time is it?"),
    (True,  "que horas sao?"),
    (True,  "diz-me a hora local, por favor"),
    (True,  "tell me today's date"),
    (True,  "qual e a data de hoje?"),
    (True,  "what time is it, and what is my dog called?"),          # mixed: still asks
    (True,  "preciso de saber a hora exata agora"),
    (True,  "give me the current time", True),                              # imperative, but it asks
    (True,  "me diga a hora agora", True),
    (True,  "show me today's date", True),
    (True,  "tell me the time please", True),
    (False, "why are you saying the time? you could just ask me what do i mean is okay to ask if you dont understand"),
    (False, "porque estas sempre a dizer as horas? nao te perguntei isso"),
    (False, "I hate it when apps show me the time I did not ask for"),
    (False, "eu nao perguntei as horas"),
    (False, "never show me the time again"),                          # an instruction ABOUT the clock
    (False, "nao me digas mais as horas"),
    (False, "but babys is also babys"),
    (False, "the time we spent together was great"),                  # 'time' in another sense
]


def main() -> int:
    clone = os.path.join(SCRATCH, f"clock_router_{os.getpid()}.db")
    if os.path.exists(clone):
        os.remove(clone)
    open(clone, "wb").close()
    e = sd.fresh_engine(clone, None)
    rt = RuntimeContext.capture()
    rows, wrong = [], []
    try:
        for asks, text, *rest in CASES:
            added = bool(rest and rest[0])
            ex = e.sensitizer.extract(text, runtime_context=rt, route=True, nano=False)
            d = ex if isinstance(ex, dict) else dict(ex)
            # mirror retrieve.py:50-64 exactly -- a QueryPoint missing a field the gate reads makes this
            # battery measure the diagnostic instead of the product (91.Y5: it did, until this line)
            q = QueryPoint(conversation_act=d.get("conversation_act", "statement"),
                           freshness=d.get("freshness", "none"),
                           action_requested=bool(d.get("action_requested")),
                           runtime_context_sufficient=bool(d.get("runtime_context_sufficient")),
                           runtime_context_keys=list(d.get("runtime_context_keys") or []))
            # the gate would ground only when the router called the clock sufficient AND the
            # precondition says the turn asked for it
            grounds = q.runtime_context_sufficient and _clock_requested(q)
            # 91.Y5: the error kinds are reported SEPARATELY and never averaged. The old single "ok" was
            # permissive -- a classifier answering sufficient=False for everything scored full marks on
            # it, which proves nothing about recall of real clock requests.
            kind = ("false_override" if (not asks and grounds) else
                    "lost_grounding" if (asks and q.runtime_context_sufficient and not grounds) else
                    "no_signal" if (asks and not q.runtime_context_sufficient) else "correct")
            rows.append({"asks": asks, "text": text, "act": q.conversation_act, "added": added,
                         "action_requested": q.action_requested, "freshness": d.get("freshness"),
                         "sufficient": q.runtime_context_sufficient,
                         "keys": q.runtime_context_keys, "grounds": grounds, "kind": kind})
            if kind != "correct":
                wrong.append(rows[-1])
            print(f"{kind:14} asks={str(asks):5} grounds={str(grounds):5} act={q.conversation_act:11} "
                  f"fresh={str(d.get('freshness')):10} suff={str(q.runtime_context_sufficient):5} | {text[:56]}")
    finally:
        try:
            e.graph.close()
        except Exception:
            pass
    over = [r for r in rows if r["kind"] == "false_override"]
    lost = [r for r in rows if r["kind"] == "lost_grounding"]
    nosig = [r for r in rows if r["kind"] == "no_signal"]
    asks_n = sum(1 for r in rows if r["asks"])
    shared = [r for r in rows if not r["added"]]
    print("")
    print(f"FALSE OVERRIDES  (did not ask, grounded anyway) : {len(over)}/{len(rows) - asks_n}   {[r['text'][:26] for r in over]}")
    print(f"RETAINED         (real request, still grounded) : {sum(1 for r in rows if r['asks'] and r['grounds'])}/{asks_n}")
    print(f"LOST GROUNDINGS  (router said sufficient, gate refused) : {len(lost)}   {[r['text'][:26] for r in lost]}")
    print(f"NO ROUTER SIGNAL (request the router never called sufficient; the gate is not the mechanism) : {len(nosig)}   {[r['text'][:26] for r in nosig]}")
    print(f"SHARED 15 only   : false overrides {sum(1 for r in shared if r['kind'] == 'false_override')}/{sum(1 for r in shared if not r['asks'])} "
          f"- retained {sum(1 for r in shared if r['asks'] and r['grounds'])}/{sum(1 for r in shared if r['asks'])}")
    print("freshness seen per label: " + str({str(lbl): sorted({str(r["freshness"]) for r in rows if r["asks"] is lbl}) for lbl in (True, False)}))
    print("versioned:", write_versioned("clock_router", {"rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
