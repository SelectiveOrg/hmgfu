# Phase 91.V — Answering the independent verification: the regression was mine, and the instrument was also wrong

Date: 2026-09-09. Candidate commit `1e6a7a4` plus the instrument changes recorded below. Nothing adopted, nothing
activated in production, no internal percentage raised.

Source: `reports/codex_verify_phase91/VERIFICACAO.md`, which reviewed my commits `44a30c3` and `69003cb`.

## 1. Reproduced first, and a control established

All ten of the verification's probes were reproduced at HEAD before a line was changed, and a clean control was taken
at `44a30c3` — the commit before correction-by-reference existed. The first control attempt was wrong and had to be
redone: the probe script derives its root two levels above itself, so copying it to the worktree root made it import
the MAIN tree and report the candidate's behaviour as the control's.

| probe | control `44a30c3` | candidate `69003cb` | now |
|---|---|---|---|
| wife's number, one-sentence fiction, explicit correction | pass | pass | pass |
| simple correction by reference | fail (absent) | pass | pass |
| reference after a restatement | fail, colour intact | **colour corrupted** | pass |
| reference after a fact-free turn | pass | **name = "forty two"** | pass |
| reference with a wrong-shaped value | pass | **name = "raining"** | pass |
| fiction / hypothesis across sentences | fail | fail | pass |
| mixed sentence without a comma | fail | fail | pass |

**The honest account of my previous commit: it bought one case and cost three.**

## 2. What was wrong, and what it now is

**V1 — the antecedent.** "Last write" is not "the subject being corrected". Restating a value writes no history row, a
turn with no fact leaves none at all, and the history knows nothing of turns or sessions. The antecedent is now the
**subject of the previous utterance**, and only when the store still holds what that utterance asserted; not unique or
not supported means write nothing.

**V2 — the validations.** The referential candidate returned early, past `name_value_ok` and the rest. It now flows
through the same list as every other candidate.

**V3 — modality scope.** An inherited fiction or hypothesis is now as unreal as an inherited citation — the carry rule
and its "actually" escape already existed; `_unreal` simply did not read them. The contrastive split no longer needs a
comma and decides by clause shape rather than a verb list, which also fixes subject-dropping Portuguese.

That split then cost a case **no unit test of mine caught** — the DEV modality diagnostic did: "used to be X but now Y"
is one claim spanning the coordinator, and cutting it dropped m28 (29/32 → 28/32). A transition frame now uses the
plain splitter; 29/32 restored, three transition cases added to the tests.

**V4 — the judge.** Four counter-proofs now fail as they should: an invention wrapped in doubt is not an abstention; a
third party's answer does not answer for the user (the rule reads the **question**, so "your brother is Amaro" still
passes when the brother was asked about); a stored value that merely contains the expected token is a different value;
history alone does not answer a present-tense question.

**V5 — the errata.** It no longer reconstructs evidence from a field that mixed context and ledger. None of the twelve
archived runs recorded the delivered context, so **no layer is attributable** and that is what it now reports. The
runner records the injected context from now on — and the runs made today are attributable in all cases.

**V6 — a defect the verification did not name, found while fixing V4.** The benches clone the live memory, so a value
that was already there satisfied an expectation the conversation never taught. Write credit now requires the key to
appear in **this run's own ledger deltas**. This made the measure harder: `l12` went back to failing, which is the
truthful outcome.

## 3. Evidence, end to end

| reading | result |
|---|---|
| the verification's ten ledger probes | **10/10** (control 4/10, previous candidate 4/10) |
| the verification's four judge probes | **all four now fail**, as they must |
| suite | **969 passed, 1 xfailed, 0 failed** |
| truth core | **390 PASS, 0 undue changes** |
| DEV modality diagnostic | **29/32, 0 undue writes** (28/32 during the regression, restored) |
| write sets v1–v5, sealed lines | **identical to the baseline** |
| `learn_v1` on the 12B, question in a NEW session | **10/12**, layer attributable in all twelve |
| `conv_v1` on the 12B, re-scored with the current judge | **3/7**, against a ≈3.3/7 historical rep under the *permissive* judge |

The two `learn_v1` failures are not regressions, and both were checked against the control: `l11` is the reply
"Your brother's name is babys." — an invention where abstention was required, which the old judge accepted; `l12`
does not write at the control either, and its earlier pass was the clone's own value plus a permissive judge.

## 4. My own mistakes in this session, since they shaped the numbers

- the antecedent regression above, which the verification caught and I did not;
- the transition frame, which my unit tests missed and the DEV diagnostic caught;
- the value-match flag placed at file level and read at conversation level;
- a `#` comment written into JSON, which invalidated three oracles until I noticed;
- three regression chains started before the code was final and discarded rather than reported.

## 5. Limits, stated

**No claim of zero regressions.** What is demonstrated is zero regressions *observed in the scope tested*: the suite,
the truth core, the five sealed write sets, the DEV diagnostics and two conversation sets on the 12B. Outside that
scope — the full application, the UI, scale, concurrency, any production configuration, and the reserved sets, which
were deliberately not re-run — nothing is claimed.

The oracles' `value_match` flags encode what each file's own `_doc` already declared in prose; no expectation was
changed, and the reserved `learn_r1` stays on **exact** equality, the harder setting.

## 6. Decision

**S0–S2 stay PARTIAL and S3 does not start.** The five requirements are addressed and the probes pass, but the
conversation evidence is two DEV sets on one machine, the reserved set has not been re-run against this candidate, and
the cost pilot the plan requires has not been computed. Adoption remains the user's, and no percentage moves.
