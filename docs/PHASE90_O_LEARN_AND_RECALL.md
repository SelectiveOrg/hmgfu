# Phase 90.O — Learning and correcting in natural language, and recalling it in another session

Date: 2026-09-09. Candidate frozen at **`9834f73`** (= `ddeb130` + eight lines in `fact_moulds.py` + `pytest.ini` +
two oracles + one test). Every experimental flag is OFF; nothing is activated in production.

## 1. What is actually active (asked for first, `outputs/evidence_90_O1_active.txt`)

`fact_mapper_mode=fallback`, `knn_router_enabled`, `nano_in_tail`, `bypass_skips_nano`, `router_bypass_enabled` — all
off. The branch is 334 commits ahead of `main` (main sits at Phase 28), so the live agent runs none of this. **Stated
plainly because it is easy to miss: the 90.L / 90.M / 90.N changes are not behind a setting — any run of this branch
exercises them.**

## 2. The scenario, as a DEV oracle and not a new runner

`scripts/oracles/learn_v1.json`: 12 conversations, 7 EN and 5 PT, each one **teach → correct → change subject →
question in a NEW session**, and every question a genuine paraphrase (checked: they share only the attribute noun with
the turns). Six families: correction-then-paraphrase, third party, negation, intention-vs-fact, past-vs-present,
ambiguity. `run_conversations.py --question-in-new-session` already provided everything needed, including per-turn
latency and model calls.

## 3. The blocker, and the single hypothesis that explained it

Three conversations failed, all at the write side, all the same shape: **an alternation inside an existing mould that
stops one form short of a frame the store already reads elsewhere.**

| slot | already read | missing |
|---|---|---|
| `identity.company` | "I work at X **as a Y**" (compound) · "I no longer work at X" (retraction) | the plain positive "I work at X." |
| `identity.location` | "I am living in X" · "residing in X" · "my home **has been** X" | "I **have lived** in X since 2022" |

So the fix completes two existing alternations. No new mould, no new module, no per-sentence patch. The PT branch
refuses the project idiom ("trabalho no **projeto** X"); EN separates the two by preposition already ("work at" vs
"work on").

**Two iterations, as budgeted.** The first used a global `re.IGNORECASE`, which breaks `_NAME`'s capitalisation
contract and captured "Mapiko now"; the neighbouring `_NAME` moulds scope it to the cue with `(?i:...)`, and so does
this one now. Test **v100 written first: 7 failed / 13 passed before, 20 passed after.** The 13 that passed before are
the negatives — third party, intention, proposal, question, dated past, fiction, citation, negation, and four
project-vs-employer ambiguities — and they still pass.

## 4. Measured against the control

| state | accuracy on learn_v1 | undue values in a reply | median turn | model calls / turn |
|---|---|---|---|---|
| control `9b8fc5c`, same live memory | 9/12 | 0 | 9.9s | 5.39 |
| control `9b8fc5c`, empty memory (confounded, kept for the record) | 8/12 | 0 | 8.9s | 5.92 |
| candidate `ddeb130` (90.N) | 9/12 | 0 | 11.5s | 5.44 |
| **candidate + frame completion** | **12/12** | **0** | **10.0s** | **5.44** |

The corrected control scores the **same 9/12 as the 90.N candidate**, and fails on exactly the same three
conversations (l08, l09, l10): on this set the whole improvement is the frame completion, and 90.N moves nothing
either way. The completion is regex, so it costs **exactly the same 5.44 model calls per turn**. Regressions at the frozen
candidate: TRUTH CORE n=390 · undue changes 0 · provenance_100 PASS · injections_recovered_100 PASS · receipts_100 PASS · scoped_retraction_100 PASS · sequences_100 PASS; MODALITY DIAGNOSTIC [modality_v1.json] 29/32, writes that must not happen: 0 []; write sets v1–v5 identical to the sealed baseline, line for line; conv_v1 `SUMMARY [conv_v1.json [question in NEW session]] ok 3/7 · verdicts {'OK': 3, 'FAIL@write (fact not in ledger)': 3, 'FAIL@reader (evidence delivered, reply wrong)': 1} · 262s`
(one rep against a 10/21 three-rep baseline, with the same 5 ledger writes per rep).

## 5. A confound I introduced, found, and corrected

`config.DB_PATH` derives from the package root, so a run started **inside a git worktree** clones that worktree's own
database — empty — instead of the live memory. I did not pass `--db`. This invalidated the control arm above (its
latency and call figures are not comparable, though the three shared write failures are mould gaps proved
deterministically without any database) and, more seriously, **the 90.N5 A/B whose conclusion I had already reported**.

Re-run with both arms on the same live memory:

| metric (rule fixed before any run) | arm A — iteration 1 only | arm B — iterations 1+2 |
|---|---|---|
| **1. a value presented as the user's current state when it must not be** | **0/20** | **0/20** |
| 2. the value is surfaced in the reply at all | 11/20 | 13/20 |
| OK by the full oracle rule | 11/20 | 10/20 |

**The earlier claim is retracted.** "Iteration 1 alone does not fix the defect, iteration 2 does" was an artefact of the
empty database: with a realistic memory *neither* arm produces a false current claim. What iteration 2 actually buys is
that the proposal is surfaced more often (11/20 → 13/20), which is what the pre-registered rule required — so the rule now
says **ADOPT**. The margin is two runs in twenty and the composite OK is a tie (11 vs 10); that is a weak effect
and it is reported as one.

The cause is fixed for good: an arm in a worktree must be given `--db` explicitly, and `pytest.ini` now scopes
collection to `tests/` so a worktree can no longer make the suite report ~100 collection errors that look like
breakage.

## 6. Reserved validation

`scripts/oracles/learn_r1.json` — 12 conversations, the same six families, **no value, no turn and no question shared
with the DEV set**, four of eight slots deliberately in common so it tests the same capability with different material.
Authored once, sealed by the commit that froze the candidate, run once:

    SUMMARY [learn_r1.json [question in NEW session]] ok 7/12 · verdicts {'OK': 7, 'FAIL@reader (evidence delivered, reply wrong)': 2, 'FAIL@write (fact not in ledger)': 3} · 664s

**DEV said 12/12. The reserved set says 7/12** — and that gap is what a reserved set is for
(`outputs/evidence_90_O6_reserved_analysis.txt`, analysed and *not* tuned against):

| case | failure | attribution |
|---|---|---|
| r04 | **an undue write**: "My wife's lucky number is 88." overwrote the user's 14, and the reply stated it | the third-party guard is **slot-dependent** — the same sentence about a *drink* writes nothing. Pre-existing, untouched by this phase |
| r12 | nothing written for "I stayed in Inhambane." | another incomplete alternation in the location frame, the same family this phase completed |
| r06 | "My favourite sport is handball." stored `open.favorite_sport` | the registry has no `pref.sport`; my oracle asserted one. The value was stored and recalled correctly — counted as a failure by the criterion fixed beforehand, and left counted |
| r03 | reply gave the superseded employer | the ledger was **right** (Namuli then Chire — the completed frame working twice); the reader ignored it |
| r10 | reply was an apology about tools | the ledger was **right** (Chire) |

None of the five is caused by the frame completion; in r03 and r10 the frames it completed wrote correctly and the
failure is downstream. But the candidate does **not** hold 12/12 on unseen material, and saying so is the point of
having run this once.

## 7. Adoption decision

0. **The reserved result governs the headline.** The capability asked for — learn, correct, change subject, recall in
   another session from a paraphrase — is at **7/12 on unseen material**, not the 12/12 the DEV set showed. The next
   three blockers are named and ordered: the slot-dependent third-party guard (it produces an undue write, the most
   serious kind of error here), the remaining location alternations, and a reader that answers with a superseded value
   it was not given. None is fixed here: a reserved set is spent once, and the two-iteration budget went to the frame
   completion.
1. **Frame completion — recommend adopting.** The evidence is clean: 9/12 → 12/12 on the DEV set, every sealed write
   set identical, truth core unchanged, no extra model call, and 13 negatives (third parties, intentions, proposals,
   questions, dated pasts, fiction, citation, negation and the project-vs-employer ambiguity) still silent.
2. **90.N iteration 2 — the pre-registered rule now says ADOPT, on a weak margin.** It does no harm
   (0/20 false current claims either way) and surfaces the wish slightly more often. Adopting it is defensible;
   dropping it is also defensible. The decision stays with the user, as it did before, and the reason I now recommend
   it is different from the reason I gave yesterday — that one was wrong.

Nothing is activated in production. No internal target (originality, efficiency, AGI readiness) is raised here: this
phase produced no measurement that speaks to them, and Fu originality remains pending a specific comparison.
