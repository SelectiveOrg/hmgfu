# Phase 91.Z — the second review is accepted, and the general claim is withdrawn

`reports/codex_review_91y/REVIEW.md`. Every finding reproduced before any code change. **No product
code was modified in this step**: the correction it points to is architectural, and the directive
requires approval before that is implemented.

## Corrections to my own 91.Y report

1. **My architecture claim was wrong.** I wrote that the regex path is not wired into the modality
   contract. `FactStore._resolve` **does** call `declarative_text` (`facts.py:85`). The review is
   right; the report is corrected here.
2. **"No coverage traded away" was true only of my own sets.** Three legitimate assertions that X
   wrote are silently dropped by Y: `I know that Green is my dog.`, `I can confirm that Green is my
   dog.`, `I am telling you that Green is my dog.` These are lost X gains.
3. **"A conjunction of two independent classifications" was wrong.** `conversation_act` and
   `freshness` come from the SAME router invocation and are correlated by construction. It is a
   heuristic conjunction, not independent evidence, and the claim of verified intent is withdrawn.

## Where the meaning is actually lost

The contract is wired, and it still fails. Running it directly:

    sentence_modalities("I deny that my dog is called Green.")   -> [("...", "assert")]
    sentence_modalities("I never said that Green is my dog.")    -> [("...", "assert")]
    sentence_modalities("I say she claimed that blue is ...")    -> [("...", "assert")]

Two distinct losses:

- **Granularity.** Modality is assigned per SENTENCE. A denial, doubt or report is a *governing
  clause inside* the sentence, so the embedded proposition is never classified at all.
- **Representation.** `declarative_text` joins the licensed sentences into a **string**. No licence
  travels with the candidate, so every mould re-matches freely across the whole text. Source,
  subject, modality and scope are lost precisely at that string boundary.

`clause_asserted` (91.Y) is a SECOND modality judgement bolted onto ONE mould — `fact_detect.py:284`,
inside `_V_IS_MY_ATTR`. That is the parallel layer the review warns against, and it explains exactly
why the guarantee follows the mould rather than the meaning.

## What that costs, measured on contrast pairs

`scripts/oracles/scope_contrast_v1.json` — 32 cases, 8 pairs, PT and EN, varying word order
(value-first vs attribute-first), length, clause nesting, closed slots and one OPEN slot. Every
negative is paired with a positive in the SAME construction. **A negative whose positive is not
recognised is VACUOUS and proves no protection** — the review's requirement, enforced structurally by
`scripts/analyse_contrast.py`.

| arm | pairs PROVEN | broken | vacuous |
|---|---|---|---|
| baseline `cf89f69` | 1 | 5 | 2 |
| X `99e27ee` | **0** | 8 | 0 |
| Y `e7c9b7d` (current) | **1** | 6 | 1 |

**Y protects one construction out of eight.** `p3_en_long_governor` is VACUOUS under Y: it recognises
no positive there, so its apparent protection proves nothing — the structural form of Finding 2.
`p8_en_report` is BROKEN under Y and VACUOUS under the baseline, because Y made the positive work and
thereby exposed that the negative leaks.

Reproduce:

    .venv/Scripts/python.exe scripts/run_write_set.py --set scripts/oracles/scope_contrast_v1.json
    .venv/Scripts/python.exe scripts/analyse_contrast.py <run_dir>

## The clock, separately — Finding 3 confirmed, with the loop the review could not run

Nine cases through the FULL turn on a throwaway base, recording the reply before and after the gate
(`scripts/diag_clock_attribution.py --review91y`):

- **`Why is my clock showing the wrong time today?` — router question / current / sufficient / all
  six keys, and THE GATE FIRED.** Eligibility failure confirmed: current information is not clock
  information.
- In that single observation the final answer was **not** destroyed — before and after are nearly
  identical, because the re-ask kept answering the diagnostic question. The defect is in eligibility;
  the damage did not materialise here. One observation, not a rate.
- `Porque estas a responder com a hora agora?` and `Why does time seem to pass faster...` were
  protected by **empty `runtime_context_keys`**, not by the act+freshness conjunction.
- The mixed request kept both halves — but again because the router marked it insufficient. Nothing
  deterministic enforces mixed completeness; the review's point stands.
- `What is my timezone?` was answered `South Africa Standard Time`. The system silently identified
  the HOST timezone with the USER's. Recorded as a separate defect, not fixed here.

## The smallest proposal — architectural, therefore NOT implemented

One invariant: **extracting a value may not discard the source, subject, negation, uncertainty or
governing scope that licenses its write.** Enforced at the boundary that already exists, with no
parallel parser and no second filter:

1. **Give the existing classifier propositional granularity.** `sentence_modalities` keeps its
   signature and its modality vocabulary; when a sentence contains a governing clause plus a
   complement, it emits the COMPLEMENT as its own entry, carrying the modality the governor licenses
   — `assert` only for the user's own assertive speech act, otherwise the existing `cite` (report) or
   `hypothesis` (denied/doubted). No new modality is introduced.
2. **Make `_resolve` iterate clauses instead of a joined string.** `facts.py:85` becomes a loop over
   `declarative_clauses(text)`, running the detector per licensed clause. Every mould and every open
   slot then inherits the licence automatically, because a candidate can only be produced from text
   the contract already licensed. This is the consistent enforcement the review asks for, at the
   choke point that already exists.
3. **Delete `clause_asserted` from `_V_IS_MY_ATTR`.** Its judgement folds into (1). The parallel
   layer is removed, not extended.

`declarative_text` is kept as the compatibility view it already declares itself to be, so no caller
breaks.

**Risks, stated in advance.** Changing `_resolve` from one string to N clauses changes what every
mould sees; multi-fact sentences ("my name is X, I live in Y") and the transition frames protected in
91.V3 (m28) are the obvious exposure, and the five sealed write sets plus the truth core are the
instruments that would detect it. The clause split must not re-introduce the comma dependence removed
in 91.V3. This is why it needs approval rather than an immediate edit.

## Limits

- Nothing here fixes anything. The three arms are measurement; no code changed.
- The contrast set is 32 cases on the regex path with no mapper. It is not an end-to-end model
  replay, and the reply level was not re-measured in this step.
- The clock observation is one run per case, one model.
- The bad value already in the real database is untouched; its repair remains separately authorised.
- No production activation, no real memory access, no phase advanced.

---

# Part 2 — the approved work, executed

Approved by the user on 2026-09-10: three steps, sequential, with recoverable checkpoints
(`pre-scope-contract-1c1d7a0`, `z-step1-done`, `z-writeside-done`), and the clock re-ask disabled as
an experimental candidate only.

## Step 1 — propositional granularity (done, `dfabcb5`)

`sentence_modalities` now emits the COMPLEMENT of a governing clause with the status that governor
licenses, resolved recursively so the strictest status in a chain wins. The default is `assert`, so
the three legitimate assertions 91.Y had silently dropped are recovered. A governor disqualifies its
complement when it denies or doubts it, is negated or hedged, marks it as inferred, marks the user as
its receiver, is an abandoned intention, or speaks in another voice.

**Six corrections were forced by instruments, not by design** — each is now in
`tests/test_v115_propositional_scope.py`:

| found by | defect |
|---|---|
| the sealed write sets | the IMPERATIVE has a null subject, so "Remember that ..." was read as somebody else's report — v1 .966→.954, v2/v3/v4 1.000→.983 |
| the same run | a sentence-initial capital is not a proper name ("Please", "Could") |
| probing mixed sentences | a governed status must not use the fiction CARRY-OVER: a denial silenced the NEXT sentence, so "I deny that blue is my favorite color. My dog is called Green." wrote nothing at all |
| my own new test | the PASSIVE makes the user the recipient, not the source — "I was told that ..." |
| the 91.Y modality sets | EPISTEMIC ("I suppose that"), RECEPTION ("I heard that") and PAST INTENTION ("I was about to write that") were missing |
| removing the guard | the intervening-token budget was 3, so "said TO ANY OF YOU that" was invisible; a COPULAR governor predicates truth with an adjective |
| pairing | the affirmative mirror: "It is TRUE that P" was being dropped silently |

## Step 2 — NOT implemented, and the reason is measured

Iterating clauses in `_resolve` instead of the joined string produced **identical writes** on six
adversarial multi-clause probes. It changes what every mould sees, for no demonstrated benefit, so
the smaller change stands. This is a departure from the approved plan and is flagged, not hidden.

## Step 3 — partial, and blocked at a layer boundary

The parallel LOGIC is gone: `clause_asserted` is now a thin delegation to
`utterance.governed_proposition`, so the judgement exists once — the review's actual objection.
Removing the CALL SITE was attempted and **reverted**: every write-level measurement was clean
without it, but five `v114` cases call `detect_facts()` directly, bypassing `_resolve` where the
contract lives. A regression blocks adoption and does not authorise editing the test, so the call
site stays pending a decision on re-siting those assertions to the production path.

## Results

| measurement | before (`e7c9b7d`) | after (`dfabcb5`) |
|---|---|---|
| contrast pairs proven | 1 of 8 | **8 of 8** |
| modality DEV | precision .846 | **.917**, coverage 1.000 |
| modality RESERVED | 1.000 / 1.000 | 1.000 / 1.000 |
| sealed sets v1–v5 | baseline | **identical** |
| truth core | n=390, 0 undue | **identical** |
| suite | 1067 | **1097 passed, 1 xfailed** |

## The clock experiment (Z11)

`CLOCK_REASK_ENABLED`, documented, **default ON** so nothing changes silently; the runtime context
block and all instrumentation are untouched — only the rewrite is withdrawn. Nine cases, two arms,
two repetitions each, same code and configuration:

| | legitimate answered | undue timestamps | turn time |
|---|---|---|---|
| ON rep1 / rep2 | 2/2 · 2/2 | 0/5 · 0/5 | 85 s · 93 s |
| OFF rep1 / rep2 | 2/2 · 2/2 | 0/5 · 0/5 | 78 s · 89 s |

**Disabling the re-ask cost nothing on legitimate requests in this sample**, and the eligibility
defect the review identified never materialised into a bad answer in any run. The repetitions earned
their keep: with the gate ON it fired 2/9 in one run and **0/9** in the next, so it is driven by
whether the model happens to omit the value rather than by the request.

**Two artifacts, named rather than claimed.** The `mixed_complete` difference between arms is NOT a
gate effect — the gate never fired on that turn (`sufficient=false`), so it is model variance plus a
coarse keyword check. The `timezone` row fell into the scorer's mixed branch by mistake and should be
ignored; the substantive timezone point stands from the earlier capture, where the reply gave the
HOST timezone as the user's.

No minimal proposal follows, because the condition set for one — a relevant loss on legitimate
requests — did not occur. The flag stays ON by default and production is not activated.

## Limits

- The contrast set is 32 cases on the regex path with no mapper; the reply level was not re-measured
  for the write side in this part.
- The clock experiment is 9 cases × 2 repetitions on one model. It shows no harm, not the absence of harm.
- `m051` ("My brother told me his dog is called Green.") still writes, from a different mould. It is
  pre-existing and untouched.
- Step 3 remains open and step 2 was deliberately not implemented.
- The bad value already in the real database is untouched; production is not activated; no phase advanced.
