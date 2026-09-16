# Phase 91.X — the two defects from the user's own conversation of 2026-09-09

Both were found by the user, in real use, at `cf89f69`. Neither was caused by the 91.V/W work. They
were fixed sequentially, in the order asked, with no new module and no rule carved for a particular
sentence. Recoverable point before any change: tag `pre-clock-fix-cf89f69`.

## 91.X1 — the clock answered a turn that never asked

Turns 6 and 7 of session `b8616721` were both answered with the local time and nothing else, the
second of them being the user's own complaint about exactly that.

**The attribution was not closed by the earlier probe**, which injected `runtime_context_sufficient`
instead of observing it. `scripts/diag_clock_attribution.py` closes it: it replays the real messages
through a real `AgentEngine` on a throwaway empty base and records the router's OWN classification,
the reply before `runtime_context.ground_reply` and the reply after it. The live router does raise
sufficiency with the full clock key set for a complaint (act `feedback`) and for a fresh sentence
that appears in no report (act `statement`), and the gate then fires.

The gate verified that the clock was SUFFICIENT and that the reply lacked it. It never verified that
the clock was RELEVANT.

**Fixed at two layers.** `_clock_requested` lets the clock ground an answer only for a turn the
router filed as a QUESTION; and the router prompt now states that sufficiency describes a REQUEST, so
mentioning the time, denying having asked, complaining, forbidding it, or using the word in another
sense does not raise it — stated as a rule, with no example sentence.

**The choice was measured, not assumed.** `scripts/diag_clock_router.py` puts 19 labelled PT/EN turns
through the live router: all 11 requests come back `question`, four of them imperative; both
prohibitions come back `instruction`. Battery 13/15 → **19/19, zero turns still overridden**. Two
entries of the failing test had been written from assumption and were corrected by that measurement.

`action_requested` is refused as evidence of a request: it means an action is wanted, not that the
clock is wanted, and `tool_points` raises it after the router runs — observed True for a complaint.
The re-ask no longer says "using ONLY these exact values"; it grounds the date/time and keeps the
rest of the answer, so a mixed request cannot lose its other half.

## 91.X2 — a connector was written as a name

`pet.dog.name = 'but'` from `"but you should know that green is my dog also"`.

**The root cause is not the mould's span but the order of two trims.** `_CLAUSE_CUT` correctly sees
that a new clause begins after "but" and keeps the LEFT side — the bare connector — so the one word
that should never have been there is the one that survived.

The investigation of subject → relation → value found three defects, the reported one being merely
the one that got through: the value swallows a leading connector (for an open slot nothing rejects
it — `"and blue is my favourite colour"` wrote `pref.color='and blue'`); the attribute absorbs a
trailing adverb (`"dog also"` → `pet.dog.name`); and `_looks_like_name` accepted any non-numeric
single token, which is why `'but'` and nothing longer reached the ledger.

`clause_subject` / `clause_attr` / `is_connector` state one grammatical contract in `value_gate.py`
and **replace** two ad-hoc lists that had grown inside `fact_detect` — five openers with a "take the
last word" heuristic, and six trailing adverbs — so the detector lost a line rather than gaining one.
Words that double as denials open a clause only when a comma marks the discourse use, so stripping
one can never turn a denial into a claim.

## What was proven, and what was not

| | 91.X1 | 91.X2 |
|---|---|---|
| test that fails first | `test_v112` verified failing on the pre-change file | `test_v113`, 21 failing → 31 passing |
| frozen candidate | `19fa1cb` | `56191c0` |
| suite | 1007 passed, 1 xfailed | **1038 passed, 1 xfailed** |
| truth core | n=390, undue changes 0, five gates PASS | identical |
| sealed write sets | v1 identical to 91.W | **all five identical to 91.W** (668 items) |
| cost | two spurious chat calls removed over six turns | no model calls added |

**Not proven, and stated as such.** The wall-clock drop in the clock capture (122.0 s → 58.3 s) is
not attributable to the fix: the first capture ran on a cold model; the defensible claim is the call
count. The router still calls a complaint "sufficient" and still varies between runs on a
prohibition — the gate no longer acts on that classification, but the classification was improved,
not made reliable. A genuine request the router files as `statement` now loses the backstop; the
runtime block stays in the prompt, so such an answer is degraded, not falsified. The battery is 19
turns on one model, not a rate. The PT form `"mas o green e o meu cão"` detects nothing at all — a
missing PT mould, not a misattribution. `write_set_v6` (0.736 / 0.379) and `v7` (0.867 / 0.460) are
far from clean; both are identical on the pre-change and post-change arms, so they are pre-existing
and are their own work.

**Zero regressions observed in the scope tested** — the suite, the truth core, seven sealed write
sets and the two live captures. That is the scope; nothing outside it is claimed. Production was not
activated and the real memory was never opened: every run used a throwaway base.
