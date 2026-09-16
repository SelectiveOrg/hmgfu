# Phase 91.Y — the review was right, and what the correction cost

`reports/codex_review_91x/REVIEW.md` found a real regression I introduced in 91.X2. It is confirmed,
corrected, and measured here against sets written before the fix.

## The regression, reproduced and larger than reported

Re-running the reviewer's own `probe.py`: seeded `My dog is called Rex.`, then four denials and
doubts all went from NO WRITE to overwriting the ledger with `Green`. A **fifth** case,
`"I was told that Green is my dog."`, also flipped — that one is a SOURCE failure, not a negation.

## Where the meaning was lost

`utterance.declarative_clauses` — the modality contract (assert/cite/hypothesis/fiction/past/
question/intent) — is wired into `fact_spans.py`, the SPAN path, and **not** into `detect_facts`, the
regex path. The regex path carries the six dimensions through per-mould guards instead:

| dimension | regex-path guard |
|---|---|
| source | `third_party_attr`, `_REPORTED` |
| subject | `utterance_subject`, possessor |
| relation | `normalise_key` |
| value | `_clean_value`, `is_attribute_value`, `name_value_ok` |
| modality | `hedged`, `_NEG_NEAR`, `_COMPLEMENT` |
| time | `_SINCE`, `_PAST`, `valid_from` |

The sibling mould `_MY_IS` runs that whole chain. **`_V_IS_MY_ATTR` runs almost none of it.** Before
91.X2 its greedy span produced junk that later filters rejected, so it was protected by ACCIDENT, not
by contract. `clause_subject` removed the accident and exposed a hole older than my change. The
defect is mine; the gap is not new.

## The correction — one hypothesis, at the common contract

`clause_asserted` is the write-side counterpart of the modality contract: a subordinate proposition
is asserted by the USER only when the clause governing it is an assertive speech act of their own. It
is an **allow-list of that frame, not a deny-list of attitudes**, so an unfamiliar governing verb
fails CLOSED. Bare discourse connectors are excluded from the judgement, so `"Actually Green is my
dog"` stays a claim. It is the same discipline as `_INTENT`'s `_SPEECH_ACT` guard, which already
keeps `"I want to tell you that my name is X"` an assertion.

No phrase list of the reported sentences, no context-erasing cut, no parallel module: the cases run
through the EXISTING `run_write_set.py` in the EXISTING oracle format, which already supported the
`prior` setup turns the cross-turn cases need.

## Measured against criteria fixed before implementing

`modality_dev_v1.json` — 35 cases, PT/EN, combining assertion, negation, doubt, intention, citation,
third parties and cross-turn corrections:

| arm | false writes | precision | coverage |
|---|---|---|---|
| baseline `cf89f69` | 4 | 0.667 | 0.727 |
| HEAD `99e27ee` (the regression) | **12** | 0.478 | 1.000 |
| candidate `aec1ecf` | **2** | **0.846** | **1.000** |

All ten regression cases fixed with no coverage traded away.

`modality_reserved_v1.json` — SEALED, authored with the DEV set, sharing no sentence with it, run
**once**:

| arm | false writes | precision | coverage |
|---|---|---|---|
| baseline `cf89f69` | 2 | 0.750 | 0.750 |
| HEAD `99e27ee` | 7 | 0.533 | 1.000 |
| candidate `aec1ecf` | **0** | **1.000** | **1.000** |

8 positives all written, 15 negatives all silent, on sentences the fix never saw.

**C5, the reply level** (`modality_reply_v1.json`, live engine, throwaway base, question asked in a
NEW session): **6/6**. Written, retrieved and asserted agree — the denial, citation, doubt and
third-party turns leave `Rex` intact and the reply says Rex; the assertion control writes and answers
`Green`. 436 s for six conversations.

**C4, existing regressions**: suite **1067 passed, 1 xfailed**; truth core **n=390, undue changes 0,
five gates PASS**; the five sealed write sets **identical to the 91.W/91.X baseline**. No model call
added on the regex path.

## The clock — intent, not the shape of a question

`conversation_act == "question"` says the turn asks, not what it asks. `freshness` is a separate
router field meaning the turn wants a CURRENT value; the gate now requires both — a conjunction of
two independent classifications. Measured before implementing: all 11 requests `current`, all 8
non-requests `none`.

The old score was permissive, exactly as the review says: `ok = (grounds == asks) or (asks and not
sufficient)` gave full marks to a classifier answering `sufficient=False` for everything. **13/15 →
19/19 was never a paired rate and is withdrawn.** The battery now reports the error kinds separately:

    FALSE OVERRIDES  0/8      RETAINED 10/11      LOST GROUNDINGS 0      NO ROUTER SIGNAL 1
    SHARED 15 only: false overrides 0/8, retained 6/7

That correction paid for itself at once: the first run after the change showed RETAINED 0/11 and 10
LOST GROUNDINGS — caused by the DIAGNOSTIC, which built a QueryPoint without `freshness` while
`retrieve.py:58` populates it. The old permissive metric would have printed 19/19 and hidden it.

## Limits, declared

- **Two DEV false writes survive and are NOT fixed here.** Both are pre-existing, present in the
  baseline, and come from other moulds: `"Maybe Green is my dog."` → `pet.dog.name="Maybe Green"`
  (a pet-species mould with no hedge guard) and `"My brother told me his dog is called Green."` →
  `brother_told_me_his_dog` (an open-slot mould). They are a separate hypothesis, deliberately not
  bundled into this change.
- **The PT negatives pass for the wrong reason.** The PT form `"o Green é o meu cão"` is not detected
  at all, so those cases do not exercise the contract. The PT positives that do pass use the
  `chama-se` mould. PT coverage of this contract is therefore untested, not proven.
- **`"I was going to say that…"`** is refused by the allow-list, while the existing 90.L rule treats a
  speech-act complement as an assertion. The two readings differ on past intention; the boundary is
  recorded, not resolved.
- The clock battery is 19 turns on one model. `freshness` separating the classes cleanly there is an
  observation, not a rate, and the mixed request is answered by the model from the prompt block, not
  by the gate.
- The review's remaining point stands: no deterministic check enforces that a re-ask preserves the
  non-clock half of a mixed answer. The prompt asks for it; nothing verifies it.
- Zero regressions **observed in the scope tested**. Nothing outside that scope is claimed, no
  internal percentage is raised, production is not activated, and the real memory was never opened.
- **The erroneous `pet.dog.name` already in the real database is not repaired by any of this.** That
  remains a separate, separately authorised action.
