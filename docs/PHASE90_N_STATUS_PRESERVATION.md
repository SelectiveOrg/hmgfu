# Phase 90.N — Where a proposal becomes an activity, and what actually stops it

Date: 2026-09-08. One hypothesis: **preserve the status of information all the way to the reply**, without turning a
proposal, a wish or a hypothesis into a fact. The 90.M close attributed the remaining defect (s06) to the reader; this
phase was asked to check that attribution instead of trusting it.

## 1. The trace (90.N1) — four layers, verbatim

`scripts/diag_episode_status.py --trace` (an arm on the EXISTING diagnostic, not a new script);
`outputs/evidence_90_N1_trace.txt`. The candidate layers were written down from the code **before** the run
(`outputs/evidence_90_N1_candidates.txt`), so the conclusion could not be chosen after seeing the answer.

```
L1 MESSAGE    'We should work on Mapiko.'
L2 POINT      type=task · layer=L0_raw · source=user · title 'Prioritize Project Tasks'
              summary "The conversation aims to prioritize tasks related to the project 'Mapiko'"
              content 'We should work on Mapiko.'                     <- the user's words are intact
L3 DELIVERED  [Active projects and goals] '- We should work on Mapiko.  (just now)'
L4 REPLY      'Your main project is **HMG**, ...'
```

## 2. The finding (90.N2) — the conversion is **not** only in the reader

| layer | what it does | verdict |
|---|---|---|
| pre-reply nano (`sensitizer.extract`, on by default) | assigns the point's `type`; `EXTRACT_PROMPT` does not constrain it by modality | **types the proposal `task`** — the deterministic `heuristic_extract` returns `message` for all seven probes |
| `retrieve.py:318` | files `goal/project/task` into `activeProjects` | **files the proposal there** |
| `context_render.py:77` | renders that section as **"Active projects and goals"** | **the heading is itself a status claim** |
| `retrieve_channels.goal_candidates` | gives that type a dedicated retrieval budget | raises the odds it reaches the reader |
| `turn_tail.enrich_for_ingest` | would do the same in the tail | not on the live path (`nano_in_tail=False`) |
| the reader | reads a verbatim proposal under a heading that says it is active | the last link, and stochastic |

A storage classification (`type`) is consumed downstream as an **activity claim**. The user's words never change; the
frame around them does.

## 3. Two iterations, and the measurement that reversed my own reading

**Iteration 1 — refuse the false claim.** One predicate in `ingest.ingest_memory`, beside the authorship guard (Phase 48)
and the speech-act gate (Phase 62) and in the same shape, reusing 90.L's modality contract: a USER message with **no
assertive clause** is an episode, never `goal/project/task`.

**Iteration 2 — deliver it with its status instead of losing it.** The same gate also **tags** the point `_intent` (the
keyword mechanism the store already uses for `_question` and `_ephemeral`), `organise_for_injection` routes tagged points
to their own section, and one entry joins the existing `_SECTION_ORDER` table:

```
Active projects and goals:
- We are working on Kuvala.  (just now)

Proposals, wishes and plans the user has voiced (NOT current state and NOT active work — the user proposed,
wanted or planned these; never present them as what the user does or has):
- We should work on Mapiko.  (just now)
```

The tag is narrower than the type gate **on purpose**: a past, fiction or citation clause also lacks an assertion and is
not a proposal. That was a real bug in my first attempt at iteration 2, found by sweeping the modalities before trusting
the tag, and it is now covered by three negative tests.

### The A/B measurement (90.N5), designed before it ran

`outputs/evidence_90_N5_design.txt` fixed the cases, the arms, the two metrics and the adoption rule **before** any run.
Five wish/proposal cases (PT and EN), **4 repetitions each, 20 runs per arm**, fresh clone and sessions every time;
arm A = iteration 1 only (a worktree at the iteration-1 commit), arm B = iterations 1 + 2.

| metric | arm A (iteration 1) | arm B (iterations 1+2) |
|---|---|---|
| **1. a value presented as the user's CURRENT state when it must not be** | **8/20** | **0/20** |
| 2. the value is surfaced in the reply at all | 20/20 | 13/20 |
| OK by the full oracle rule | 9/20 | 10/20 |

Arm A's 8 failures are **not spread**: they are 4/4 on s03 and 4/4 on s06 — exactly the two cases the tag reaches — and
the replies are flat assertions: *"Your main project is Mapiko."* for "I want to work on Mapiko." and for "We should work
on Mapiko.". **Iteration 1 alone does not fix this phase's defect. Iteration 2 does (0/20).**

This reverses what a single run had suggested, and it is why the single-run readings (14/16 -> 13/16 -> 12/16) were not
used to decide: the cases that flipped there included mixed sentences that neither iteration touches.

### The verdict of my own rule, not reinterpreted

The rule said: adopt only if iteration 2 does not raise metric 1 **and** raises metric 2. Metric 1 went 8 -> 0; metric 2
went 20/20 -> 13/20. **By the rule as written, the verdict is DO NOT ADOPT** (`outputs/evidence_90_N5_verdict.json`).

The rule was built on a premise that the same experiment disproved — that iteration 1 had already brought metric 1 to
zero (it had, in one run; it does not, in twenty). A rule written on a false premise still stands as written: I am not
rewriting it after seeing the numbers. **The decision goes to the user**, with the trade stated plainly:

- **iteration 1 only**: the proposal is always mentioned, and is called the user's main project in 40% of runs;
- **iterations 1+2**: the proposal is never called current, and goes unmentioned in 35% of runs.

My recommendation is to adopt iteration 2, because metric 1 is the phase's target — never convert a proposal into a
fact — and metric 2 is a cost, not a correctness property. But that is the user's call, not mine to make by loosening a
gate.

## 4. Regressions for the state measured (chain_90z, production defaults, candidate OFF)

| reading | baseline (90.M4) | now |
|---|---|---|
| suite | 824 | **856 passed, 1 warning in 282.70s (0:04:42)** |
| truth core | 390 PASS, undue changes 0 | **TRUTH CORE n=390 · undue changes 0 · provenance_100 PASS · injections_recovered_100 PASS · receipts_100 PASS · scoped_retraction_100 PASS · sequences_100 PASS** |
| write sets v1-v5 (sealed lines) | .966/.966 · .986/1.000 · 1.000 · 1.000 · .976/.985 | **identical, line for line** |
| modality diagnostic (deterministic) | 29/32, 0 undue writes | **identical line for line — the ledger was not touched** |
| conv_v1 x3 | SUMMARY [conv_v1.json [question in NEW session]] ok 10/21 · verdicts {'OK': 10, 'FAIL@write (fact not in ledger)': 9, 'FAIL@reader (evidence delivered, reply wrong)': 2} · 854s | **SUMMARY [conv_v1.json [question in NEW session]] ok 11/21 · verdicts {'OK': 11, 'FAIL@write (fact not in ledger)': 9, 'FAIL@reader (evidence delivered, reply wrong)': 1} · 800s** |
| conv_v2 x1 | SUMMARY [conv_v2.json [question in NEW session]] ok 14/24 · verdicts {'OK': 14, 'FAIL@write (fact not in ledger)': 9, 'FAIL@reader (should abstain)': 1} · 908s | **SUMMARY [conv_v2.json [question in NEW session]] ok 13/24 · verdicts {'OK': 13, 'FAIL@write (fact not in ledger)': 9, 'FAIL@reader (evidence delivered, reply wrong)': 1, 'FAIL@reader (should abstain)': 1} · 1354s** |
| ledger deltas (conv_v1 / conv_v2) | 15 / 25 | **15 / 25** |

Two chains were **stopped on purpose** and their numbers discarded rather than reported: 90y, because its conversation
runs would have straddled a code change, and the first 90z, because I had found and fixed the tag bug. A third stop was
housekeeping: 22 GB of stale bench clones in `scratch/` were starving the disk and making the suite crawl; cleaning them
(they are gitignored throwaway clones by design) took it back to 4:42.

## 5. The cost, stated

Every consumer of the `goal/project/task` type was read (`outputs/evidence_90_N3_sweep.txt`):

- **Intended**: a proposal no longer competes in the goal retrieval channel and no longer renders under a heading that
  claims it is active.
- **Real cost**: `fu_math` boosts task/goal/project points for a task-intent query, so a proposal ranks slightly lower on
  "what should we do next?"; the edge label between topic-sharing points is no longer `goal_related`. No scoring path
  reads either as a status.
- **Measured cost of iteration 2**: the wish goes unmentioned in 7 of 20 runs.
- **In plain terms**: "Let's work on Mapiko" stops counting as active work until something is asserted — the same trade
  as 90.L, and the sequence test proves the promotion still happens the moment the user says the work started.
- **New surface, documented (Rule 10)**: one more section in the injected context, after `activeProjects` in the priority
  order, so under a tight budget it yields before identity, timeline and active work.

## 6. Open, named, not touched

- **The cue's reach** (`outputs/evidence_90_N3_reach.txt`): the gate inherits 90.L's speaker-anchored cue, so impersonal
  proposals ("Seria bom trabalhar no X"), morphological variants ("podíamos", "devêssemos") and explicit performatives
  ("Proponho", "Sugiro") still type normally. Fixable only in the `_INTENT` cue, which also feeds the WRITE side.
- **A probe limit, stated rather than patched after the fact**: the diagnostic's wish vocabulary does not contain "goal"
  or "expressed", so a correct reply like "you've expressed your goal of moving over to work on Mapiko" is scored as a
  false current claim. It affects arm A's count in the direction of *fewer* failures than reported only if such phrasing
  appears — it does not in the eight flagged replies, which are flat "Your main project is Mapiko.".
- The **session digest** (`type=session`) whose own summary asserts "the conversation aims to prioritize tasks related to
  the project 'Mapiko'" — a second, independent path to the same failure, for non-user sources.
- Unchanged from 90.M: the activity-form mould, the Zélia fallback, the `open_slot_regex_writes` contradiction.
