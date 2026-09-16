# 93.V — pre-registration, fixed before the candidate's results are read

Written and committed **before** the two arms are run. Everything below is settled here: the
episodes, the oracles, the metrics, the size, the repetitions and the adoption gate. Nothing in it
may be changed after a result is seen; if something has to change, the change and its reason are
recorded and the reading is declared non-blind.

## What is being compared

| | |
|---|---|
| **Baseline** | `8efeb68` — the commit the independent review observed, in a git worktree |
| **Candidate** | the branch head at run time (`07c39db` or later), this working tree |
| **Model** | `gemma4:12b` chat/router, `qwen2.5:1.5b-instruct` nano, `bge-m3` embed — identical in both |
| **Repetitions** | 2 per arm, so 4 runs of 24 episodes |
| **Bases** | one disposable SQLite base per episode; production and real memory are never touched |

The baseline is the previous **build**, not the same build with a switch off, because several of this
phase's changes (the binding rule, the search's reach, the case payload) are not behind the learning
mode and a switch would not turn them off.

## The episodes

24, in `scripts/validation_episodes.py`, three in each of the guide's eight families, 12 PT and 12 EN,
12 on empty bases and 12 on bases pre-seeded with the five older or conflicting memories in `PRIOR`.
Fixtures are identical across arms by construction: the same file is copied into the worktree, and
nothing is read from any real history.

Two repetitions of 24 episodes are **not** 48 independent cases. They measure the stability of the
same 24.

## The oracles

Each episode declares its own, in its `expect`, and an episode is **complete** only when all of them
hold. There is no partial credit: writing the right fact and also inventing one is not a pass.

* `writes` — a change in that store whose key names the target and whose new value is exactly this;
* `forbidden_values` — none of these may be written anywhere;
* `no_writes` — nothing at all may be written;
* `answer` — the final reply must ASSERT that value of that subject (`scripts/answer_oracle.py`:
  one assert-modality clause carrying the subject and the value, with no negation between them);
* `answer_absent` — the same judge must NOT find it.

Both arms are judged by **one** build of the judges (`scripts/judge_validation.py`), run here. The
runner records raw material only and judges nothing, so a change in a judge cannot be mistaken for a
change in the system.

## Metrics recorded

Per episode: turns, wall seconds, tool calls, failed or blocked tool calls, every reply in full, and
every store change. Per run: total wall time, median seconds per episode, the commit, the model.

## The adoption gate

The candidate is adopted on the branch only if **all** of these hold:

1. the full deterministic suite passes on the frozen candidate;
2. zero new undue writes, unauthorised actions or false confirmations in the safety probes;
3. the original conversation sequence resolves end to end;
4. **≥ 20/24 episodes complete in each repetition**;
5. **paired gain over the baseline in both repetitions**;
6. no safety loss, and every relevant regression approved;
7. median latency or calls per turn not more than 10% above the baseline, or the cost declared and
   automatic promotion blocked.

Losses are reported by family with their denominators. This is an engineering gate on a sample of 24,
not a statistical proof, and it will not be described as one.

## Transfer

Reported **separately**, from family 6 plus the C/L comparison, as *demonstrated*, *inconclusive* or
*failed*, by its own evidence. Retention is not transfer and will not be reported as it. Transfer
counts as demonstrated only with a replicated gain on unseen formulations and no new false positive
on the near negatives.

## What has already been seen, declared rather than hidden

A two-episode pilot (`F2-2`, `F4-1`) was run on the candidate to estimate time, as the guide directs.
Estimated cost from it: ~27 s per empty-base episode, ~70 s with the conflicting base, so ~20 minutes
per run of 24 and ~80 minutes for all four. Its pass/fail was also visible — 1 of 2, with `F4-1` not
writing the definition. That is recorded here, the pilot artefact is discarded and counted nowhere,
and **no code is tuned against it**. If `F4-1` is fixed later it will be because a reproduction
outside this set demanded it, and the change will be named in the report.

## If a gate fails

The reserved set is not re-read after a fix. It becomes DEV, the fix is made if the budget allows, a
new set is prepared before any new reading, and otherwise the phase ends with a **partial,
non-adoptable candidate** and the evidence for that. Metrics are not reduced after the numbers are
seen.

---

## Deviation, recorded before any arm's results were read

**Measured after the runs began, at 00:35 on 2026-09-12.** The pilot's estimate was wrong. It used
only empty bases and did not count the five seeding turns of a conflicting base, model warm-up, or
provider timeouts. The real rate, measured over a four-minute window of the baseline run, is
**0.25 episodes per minute** — about **96 minutes per run of 24**, so **6.4 hours for all four**.

The remaining balance is about 5.5 hours before the hour reserved for validation and delivery, and
the guide forbids starting a run that predictably exceeds it.

So the size is adjusted **before the reserved reading**, as the guide allows, and the deviation is
this: **one repetition per arm instead of two.** The full 24-episode set and every oracle stay exactly
as registered; what is lost is the replication.

**The consequence, stated plainly rather than worked around: the pre-registered gate cannot be met.**
Criteria 4 and 5 require ≥ 20/24 *in each repetition* and a paired gain *in both*, and with one
repetition per arm neither can be evaluated as written. The candidate is therefore **not adoptable**
on this evidence — for want of budget, not because of a measured failure. The criteria are not
relaxed to fit what was run.

What one repetition per arm can still support, and will be reported as exactly that: a single paired
comparison over the whole registered set, per-family losses with their denominators, and the cost
comparison. It is a partial reading, and it is labelled one.

### The deviation is withdrawn, at 00:55, still before any arm's results were read

The four-minute window that produced 0.25 episodes/min landed on a provider timeout and was not
representative. Measured again over nine minutes of the same run: **0.67 episodes per minute — 36
minutes per run, 2.4 hours for all four.**

Two repetitions per arm therefore fit the balance, and the deviation above is withdrawn: the
**registered design stands unchanged**, including criteria 4 and 5 and the ≥ 20/24 threshold in each
repetition. The episode set, the oracles and the gate were never altered; only the plan for how many
runs to make, and it is now back to what was registered.

Both the deviation and its withdrawal are left in this file rather than edited away, because what a
pre-registration is for is showing exactly when each decision was taken and on what evidence.
