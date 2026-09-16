"""93.R5 — self-recall end to end: intent, tool, result, and whether the result was USED.

The review is right that the absence of a symbol called `self_recall` proves nothing: what has to be
shown is the chain. A cache of searches does not demonstrate it, and neither does a tool appearing in
a trace. So this maps four things for one turn and reports them separately:

  1. **intent**    — did the reply merely SAY it would look something up? An intent is a proposal, not
                     a search, and it is recorded on its own so it can never be mistaken for one.
  2. **search**    — did `memory_search` actually run, unblocked and unfailed?
  3. **evidence**  — did what came back contain the value the question needs?
  4. **consumed**  — does the final answer contain that value, and was it NOT already sitting in the
                     injected context? If the context already carried it, the answer proves retrieval,
                     not recall on request, and the run says so instead of claiming the chain.

The fact is seeded as an EPISODIC point on a disposable base, never as a canonical fact, so the only
routes to it are the injected context or a search — and the run distinguishes them.

    python scripts/diag_self_recall.py [repetitions]
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
from answer_oracle import answered  # noqa: E402
from self_recall_arms import ARMS, judge, names_a_venue, seeds_the_value, settings_for  # noqa: E402
from sequence_verdict import tool_succeeded  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

# an invented fact that exists ONLY as an episodic memory on the throwaway base
SECRET = "Kestrel Pier"
SEED = f"Remember this: we agreed the launch party will be at {SECRET}, on the old waterfront."
# 93.P5: a SECOND memory about the same event, more recent and closer to the question's wording.
# With a narrow retrieval budget the top match is this one, and the venue -- still perfectly
# findable by a search -- is left out of the injected context. Both memories are real and the
# question is the natural one; nothing here is arranged to make the model fail.
DECOY = "The launch party will have live music, a photo booth and a long table for the team."
ASK = "where did we agree to hold the launch party?"
INTENT = ("let me check", "i'll check", "i will check", "let me search", "i'll look", "let me look")
NOISE_TURNS = int(os.environ.get("SELF_RECALL_NOISE", "10"))
# declared, not hidden: the narrow retrieval budget that creates the condition being tested
RETRIEVAL_LIMIT = int(os.environ.get("SELF_RECALL_RETRIEVAL_LIMIT", "1"))
RECENT_WINDOW = int(os.environ.get("SELF_RECALL_RECENT_WINDOW", "0"))
NOISE = ["The weather has been grey all week here.",
         "I finally replaced the kitchen tap yesterday.",
         "My sister is learning to sail on the estuary.",
         "The bus route changed again this month.",
         "I have been reading about lighthouse keepers.",
         "The neighbour's cat sits on my doorstep every evening.",
         "I need new running shoes before the autumn.",
         "The bakery on the corner closes at four now.",
         "I watched a documentary about deep sea vents.",
         "The office coffee machine broke twice this week.",
         "I am thinking of repainting the hallway.",
         "The ferry timetable is different on Sundays."]


def _seed(engine, arm: str = "related_only") -> str:
    """Say it the way a user would, in its own session, so it is stored and indexed like any memory.

    A first version wrote the point directly with `save_point(... embedding=[])`; the row existed and
    `memory_search` could never find it. That was a defect of the PROBE, and it is recorded here
    because an instrument that seeds unreachable evidence proves nothing about recall."""
    other = sd.new_session(engine, "selfrecall-seed")
    # 93.Q4: `truly_absent` is the SAME conversation with one thing missing -- the turn that names
    # the venue. Everything else, the decoy included, is said in every arm, so the two compared arms
    # differ in whether the evidence exists and in nothing else.
    if seeds_the_value(arm):
        sd.turn(engine, other, SEED)
        wait_for_tail(engine)
    sd.turn(engine, other, DECOY)
    wait_for_tail(engine)
    # 93.Q4: in the two narrow-budget arms, one more memory ABOUT THE PLACE and carrying no venue.
    # Without it the single retrieved memory was the one naming the venue, and `related_only` was
    # `in_context` under another name. Both arms get it, so they still differ in one thing only.
    if arm != "in_context":
        from self_recall_arms import DECOY_ABOUT_THE_PLACE
        sd.turn(engine, other, DECOY_ABOUT_THE_PLACE)
        wait_for_tail(engine)
    # 93.R5: with only this memory on the base, retrieval hands it to the model before it can ask for
    # it, and the run measures retrieval rather than recall-on-request. Unrelated turns push it out of
    # the window that is injected, so the chain has something to do. `noise=0` keeps the easy case.
    for i, line in enumerate(NOISE[:int(settings_for(arm).get("noise", NOISE_TURNS))]):
        sd.turn(engine, other, line)
    wait_for_tail(engine)
    return other


class _Capture:
    """The messages the ANSWERING model was given, so 'already in the context' is a fact, not a guess."""

    def __init__(self, engine):
        self.engine = engine
        self.prompts = []

    def __enter__(self):
        from hmgfu import tool_loop
        self._original = tool_loop.run_tool_loop

        def spy(engine, messages, *a, **kw):
            self.prompts.append("\n".join(str(m.get("content") or "") for m in messages))
            return self._original(engine, messages, *a, **kw)

        tool_loop.run_tool_loop = spy
        return self

    def __exit__(self, *exc):
        from hmgfu import tool_loop
        tool_loop.run_tool_loop = self._original
        return False

    def context_had(self, needle: str) -> bool:
        return any(needle in p for p in self.prompts[:1])   # the FIRST prompt: before any tool ran


def run(rep: int, arm: str = "related_only") -> dict:
    db = os.path.join(SCRATCH, f"selfrecall_{os.getpid()}_{arm}_{rep}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")
    # 93.P5: the chain can only be exercised where retrieval does NOT already hand the fact over.
    # The earlier runs proved the opposite condition -- automatic retrieval answered 4/4 and 2/2,
    # which is a success of retrieval, not evidence about the tool path. So the probe NARROWS the
    # retrieval budget with the product's own visible settings, and says so: the conclusion is
    # scoped to that configuration and claims nothing about the default one.
    # 93.Q4: each condition declares its own settings, and `in_context` deliberately leaves the
    # defaults alone -- that IS the condition where retrieval answers before anything is asked.
    conf = settings_for(arm)
    for key in ("retrieval_limit", "recent_turns_window"):
        if key in conf:
            e.settings.set(key, conf[key])
    _seed(e, arm)
    sid = sd.new_session(e, f"selfrecall-{arm}-{rep}")
    with _Capture(e) as cap:
        r = sd.turn(e, sid, ASK)
        wait_for_tail(e)
        in_context = cap.context_had(SECRET)
    trace = r.get("tool_trace") or []
    reply = r.get("response") or ""
    searched = tool_succeeded(trace, "memory_search")
    evidence = any(t.get("name") == "memory_search" and SECRET in str(t.get("result") or "")
                   for t in trace)
    # 93.Q4: the answer is judged the same way a clarification reply is -- the venue must be
    # ASSERTED of the party, not merely mentioned somewhere in the paragraph.
    verdict = answered(reply, subject="launch party", value=SECRET)
    row = {"rep": rep, "arm": arm, "intent_only_said": any(k in reply.lower() for k in INTENT),
           "search_ran": searched, "evidence_had_the_value": evidence,
           "answer_has_the_value": bool(verdict["ok"]), "answer_why": verdict["why"],
           "value_already_in_context": in_context, "settings": conf,
           "tools": [t.get("name") for t in trace], "reply": reply, "secs": r.get("_secs")}
    row.update(judge(arm, searched=searched, value_in_context=in_context,
                     answered_ok=row["answer_has_the_value"], reply=reply,
                     invented=(not seeds_the_value(arm) and names_a_venue(reply, known={SECRET}))))
    # the chain only counts when the search is what brought the value in
    row["chain_demonstrated"] = bool(searched and evidence and row["answer_has_the_value"]
                                     and not in_context)
    print(f"[{rep}] {arm:13} search={row['search_ran']!s:5} needed={row['search_was_needed']!s:5} "
          f"wasted={row['unnecessary_search']!s:5} answered={row['answer_has_the_value']!s:5} "
          f"claimed_absence={row['claimed_absence']!s:5} correct={row['correct']}", flush=True)
    return row


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4
    os.makedirs(SCRATCH, exist_ok=True)
    rows = [run(i + 1, arm) for arm in ARMS for i in range(reps)]

    print("\nthe three conditions, judged each by what IT required")
    for arm in ARMS:
        got = [r for r in rows if r["arm"] == arm]
        n = len(got) or 1
        def _n(key):
            return sum(1 for r in got if r.get(key))
        print(f"  {arm:13} correct {_n('correct')}/{n}   searched {_n('search_ran')}/{n} "
              f"(needed {_n('search_was_needed')}/{n}, wasted {_n('unnecessary_search')}/{n})   "
              f"answered {_n('answer_has_the_value')}/{n}   "
              f"claimed absence {_n('claimed_absence')}/{n}   settings {got[0]['settings']}")
    chain = sum(1 for r in rows if r["chain_demonstrated"])
    answered_n = sum(1 for r in rows if r["answer_has_the_value"])
    from_context = sum(1 for r in rows if r["value_already_in_context"])
    said_only = sum(1 for r in rows if r["intent_only_said"] and not r["search_ran"])
    print(f"\nacross all {len(rows)} runs: answered {answered_n}; of those the value was ALREADY in "
          f"the injected context {from_context}")
    print(f"full chain (intent -> search -> evidence -> used, and not already present): {chain}")
    print(f"turns that only SAID they would look, without searching: {said_only}")
    print("`related_only` and `truly_absent` ran under identical settings, so the only difference "
          "between them is whether the venue was ever said. `in_context` is the condition where "
          "retrieval answers on its own, and its settings are stated above rather than implied.")
    print("An answer is not recall: retrieval already puts memories in the prompt, and this run "
          "separates the two rather than crediting the search for both.")
    print("versioned:", write_versioned("self_recall", {"rows": rows, "reps": reps}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
