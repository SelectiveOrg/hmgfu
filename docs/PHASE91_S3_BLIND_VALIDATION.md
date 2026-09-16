# Phase 91.S3 — the blind validation, and what it does and does not show

Date: 2026-09-09. Frozen baseline **`0c65488`** (the state before 91.V) against frozen candidate **`3f313c4`**, on
`scripts/oracles/s3_blind_v1.json` — 48 conversations authored and sealed for this run, sharing no turn, question or
value with any set used before. Each conversation runs on its OWN empty synthetic base, so what is measured is what the
conversation taught, not what a cloned memory already held. The question is always asked in a NEW session.

## The result

| | baseline `0c65488` | candidate `3f313c4` |
|---|---|---|
| conversations that hold | **32/48** | **38/48** |

**Discordant pairs — the only ones that carry information about a difference: 7 won, 1 lost.**
31 hold in both arms, 9 in neither. One case (b45) came back INCONCLUSIVE and is counted for
neither arm, which is the outcome the judge gained in 91.W1 precisely so that an unscoreable reply is not guessed.

| family | baseline | candidate |
|---|---|---|
| abstention | 5/6 | 5/6 |
| correction | 3/6 | 4/6 |
| cross_session_persistence | 4/6 | 4/6 |
| identity_third_party | 4/6 | 6/6 |
| intention_fiction | 5/6 | 5/6 |
| negation | 6/6 | 6/6 |
| reference_correction | 1/6 | 3/6 |
| time | 4/6 | 5/6 |

The gain is **not concentrated in one family**: it appears in identity/third-party, reference-correction, correction
and time. Those are the families the 91.V and 91.W corrections actually touched, which is the coherent place for it to
appear. Nothing moved in negation, abstention, intention/fiction or cross-session persistence.

Raw: `SUMMARY [s3_blind_v1.json [question in NEW session]] ok 38/48 · verdicts {'OK': 38, 'FAIL@write (fact not in ledger)': 7, 'FAIL@reader (evidence delivered, reply wrong)': 1, 'FAIL@reader (should abstain)': 1, 'INCONCLUSIVE (the reply neither states nor denies the value)': 1} · 2618s` · `SUMMARY [s3_blind_v1.json [question in NEW session]] ok 32/48 · verdicts {'OK': 32, 'FAIL@write (fact not in ledger)': 13, 'FAIL@reader (evidence delivered, reply wrong)': 2, 'FAIL@reader (should abstain)': 1} · 2928s`

## Cost, measured

1657 s of turn time and 1022 model calls across the two passes. The pilot had projected ~37 s per conversation from
`learn_v1`; the blind set measured ~73–81 s, a **2.2x underestimate**, because `learn_v1` runs against a clone that
already holds a memory while every blind conversation starts from an empty base and builds its context from nothing.
That correction is written up in `outputs/evidence_91_W4_pilot.txt`, and it is why the design was cut from two paired
repetitions to one.

## What this does not show

- **One repetition per arm.** A single unstable reply now decides a conversation; with two repetitions a result would
  have had to hold twice. This weakens the per-item reading and is the direct cost of the budget correction.
- **48 conversations on one machine, one model set, one diagnostic profile.** Seven-versus-one discordant pairs is a
  consistent direction, not a proven effect size; no interval is claimed and none should be read into it.
- **Empty bases by design.** This measures learning, not interference. The pre-loaded frozen base for the interference
  proof is planned and not run.
- Nothing here speaks to originality, efficiency or AGI readiness. **The historical ~37/80/50 do not move.**

## Decision

**Adopt the candidate for the branch, not for production.** The evidence supports it: 7 discordant wins against 1 loss
on genuinely blind data, a gain spread across the families the work targeted, the suite at 1005 passed, undue changes 0,
the five sealed write sets identical, the ten probes preserved and the judge's own error rate at 0/21 on a balanced
labelled set. Production activation and publication remain the user's decision and are not taken here.

The one loss (`b39`) and the nine cases that fail in both arms are the honest next targets, along with the
interference proof and the second repetition if the stronger per-item reading is wanted.
