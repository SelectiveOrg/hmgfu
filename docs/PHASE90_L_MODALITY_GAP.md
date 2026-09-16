# Phase 90.L — Activity, correction, proposal, intention, focus change: what the existing contracts do, the gap, and the smallest proposal

Date: 2026-09-08. Diagnostic only so far; **nothing implemented when this page was written**. Candidate OFF, no reserved set, no
model call in the measurement.

## 1. The taxonomy, fixed before measuring

`scripts/oracles/modality_v1.json` (DEV, 32 PT/EN cases, all aimed at one slot — `project.main` — so only the modality varies).

| store? | class | rule (never a phrase) |
|---|---|---|
| **yes** | durable state assertion | the user states the slot's value now, evidenced by the slot's own noun ("project" / "projecto") |
| **yes** | correction | a change-of-state marker the store already recognises ("actually" / "na verdade"; "used to be … now"; "since <year>") |
| **yes** | decision to change focus | an explicit change of the slot's value ("from now on my project is X") |
| **no** | proposal | deontic ("we should work on X", "devíamos trabalhar no X") |
| **no** | intention | volitive or future ("I want to work on X now", "vou trabalhar no X", "I plan to…") |
| **no** | negation | adds no value; a retraction only through the existing retraction contract |
| **no** | third party, question, hypothesis, fiction, citation, dated past | the existing guards |
| **ambiguous → no** | bare current activity | "we are working on X" with no scope or change marker. An activity now is **not** evidence that it is the user's MAIN project: the honest outcome is an episode and no canon write |

## 2. What the existing contracts actually do (`outputs/evidence_90_L1_modality.txt`, deterministic)

**27/32.** The five failures are all *missing* writes; **there is not one write that should not have happened**:

| class | result |
|---|---|
| proposal, intention, negation, third party, question, hypothesis, fiction, citation, past, bare activity | **all correct — nothing written** (18 cases) |
| state assertion | 1/3 · correction 1/3 · focus change 2/3 |

Misses: m02 `O meu projecto principal é o Mapiko.`, m27 `A partir de agora o meu projecto é o HMG.` (both PT), m03
`The project I work on is Mapiko.`, m05/m06 the corrections phrased as an activity.

## 3. The gap, in two parts — and the honest reading of the safety

**A. The modality contract does not distinguish intention or proposal from assertion.** `sentence_modalities` labels 26 of the 32
cases `assert`, including every proposal ("we should work on X") and every intention ("I want to work on X now", "vou trabalhar no
X"). The set is `("assert", "cite", "hypothesis", "fiction", "past", "question")` — there is no deontic or volitive class, and the
function's last branch is `else: m = "assert"`.

Nothing is written for them **today only because no regex mould produces a value for those forms**. The safety is a side effect of
the mould set, not a contract. That is exactly how the 90.J defect happened: as soon as another path (the model extractor) proposed
a value for a sentence the moulds ignore, it was written. Any future mould, or the extractor, re-opens it.

**B. Two coverage gaps, of different kinds.**
- *Spelling*: `projecto` (European Portuguese) is not normalised to `projeto`, so `normalise_key("projecto principal")` →
  `open.projecto_principal`. `_MORPH` already carries exactly this kind of pair (`favourite`→`favorite`, `colour`→`color`).
  This explains m02 and m27 and has nothing to do with modality.
- *Form*: there is no mould for "the project I work on is X" (m03) or for an activity clause carrying a correction marker (m05,
  m06). Adding one would be a coverage decision with a risk the taxonomy names: an activity is not a main project.

## 4. The smallest proposal

**Implement A only.** One class in the existing enum, one cue regex in the same shape as the existing `_HYPO` / `_FICTION` cue
families, anchored to the speaker ("I/we/eu/nós + should/want to/going to/plan to…" or a clause-initial "let's/vou/quero/devíamos"),
placed before the final `else`. `declarative_clauses` already keeps only `assert`, so **every consumer inherits the protection for
free**: the regex store, the model extractor's `apply_spans`, and anything added later. No new module, no new setting, no phrase list
for one expression, no change to any write path.

What it buys: intention and proposal can never become facts, by contract rather than by the accident of which moulds exist.

**Do not implement B now.**
- The *form* gap would add a mould for the activity sentence. The taxonomy says bare activity must not be written, and the only
  activity sentences that should write are the corrections — which need the change-of-state marker to be read together with a mould
  that does not exist. That is a coverage hypothesis with its own risk (activity → main project), and it is the "growing list of
  special phrases" the user ruled out. It stays as a named, measured gap.
- The *spelling* pair (`projecto` → `projeto`) is a one-token normalisation of the same kind already in `_MORPH`, not a phrase
  list; it is presented here for the user's decision and is **not** implemented as part of this goal.

**Known limitation of A, stated up front:** a sentence like "I want to tell you my name is X" is an intention sentence and will stop
writing. That is the price of the contract; the taxonomy prefers a missed write to an invented fact.

## 5. What was implemented (A only), and the evidence

`hmgfu/utterance.py`: `intent` joins `MODALITIES`; one cue (`_INTENT`) anchored to the speaker ("I/we/eu/nós" + should / want to /
going to / plan to / could…) or clause-initial in Portuguese, where the subject is dropped ("vou", "quero", "devíamos", "let's"),
placed after the interrogative test and before the date/transition tests, with one guard: a speech-act idiom whose complement IS the
assertion keeps the sentence an assertion ("I want to **tell** you my name is X", "quero **dizer**, o meu nome é X"). Nothing else
changed — `declarative_clauses` already returns only `assert`, so the regex store, the model extractor's `apply_spans` and anything
added later inherit the contract. Two iterations, as budgeted: the first put the speech-act guard after the verb instead of after the
whole cue and wrongly silenced "I want to tell you my name is X".

| reading | before | after |
|---|---|---|
| test v96 (written first, failing) | — | **4/4**: every proposal and intention is `intent` and leaves `declarative_clauses` empty; assertions, corrections, focus changes and the speech-act idioms stay `assert`; the write path writes nothing for an intention and still writes the assertion; question / hypothesis / past still decide first |
| suite | 812 | **816** |
| DEV modality diagnostic | 27/32, 0 undue writes, modalities `assert 26` | **27/32, 0 undue writes**, modalities `assert 18 · intent 8` |
| truth core | 390 PASS | **390 PASS** |
| write sets v1–v5, production | 0.966/0.966 · 0.986/1.000 · 1.000 · 1.000 · 0.976/0.985 | **identical**, and the false-write lists diff to nothing |
| conv_v1 ×3 / conv_v2 ×1, production defaults | 12/21 · 13/24 | 11/21 · 14/24 — the two flips are both `FAIL@reader` in the past-vs-present family, and **the ledger deltas are identical in both arms** (15 = 15, 25 = 25): the write side wrote exactly the same facts, so this is reader variance, not an effect of the change |

## 6. Decision

**Keep it.** The canon behaviour is unchanged everywhere it was measured — that is the point of a safety contract: it does not add
writes, it removes a class of possible wrong ones. What changed is that a proposal or an intention is now refused *by the contract*
rather than by the accident of which regex moulds exist, so the next path that proposes a value for "we should work on X" or "I want
to work on X" cannot turn it into a fact — the failure mode that produced the 90.J defect.

**Not implemented, and why** (both stay open for the user): the activity-form mould (the taxonomy resolves bare activity as
no-write, and the corrective activity case would need a mould whose risk is precisely activity → main project); the `projecto` →
`projeto` spelling pair (a one-token normalisation of the kind `_MORPH` already carries — the user's call).
