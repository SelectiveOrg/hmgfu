# 93.Q / 93.V — delivery: what was fixed, what was measured, what is still open

Candidate: **`39e9c5c`** (frozen for the reading; this document and the roadmap entry follow it).
Baseline: **`8efeb68`**, the commit the independent review observed, run in a git worktree.
Model, identical in both arms: `gemma4:12b` chat/router, `qwen2.5:1.5b-instruct` nano, `bge-m3` embed.

Nothing here was activated. Production, real memory, `.env` and PA3 were not touched, and no weights
were changed or swapped.

---

## 1. The pre-registered gate

Registered in `docs/PREREGISTRATION_93V.md` and committed **before** either arm ran (`9446bb9`), with
a size deviation and its withdrawal both left in the file rather than edited away.

| # | Criterion | Result |
|---|---|---|
| 1 | full deterministic suite on the frozen candidate | **1578 passed, 1 xfailed** |
| 2 | zero new undue writes / unauthorised actions / false confirmations | **truth core 390/390, undue changes 0**, receipts 164/164, provenance 100%, fault injection 100% recovered |
| 3 | the original conversation sequence end to end | **5/5 gates** (prefix removed, no permanent task from a promise, teaching persisted, widget not blocked, widget created) |
| 4 | ≥ 20/24 episodes complete in each repetition | **20/24** and **22/24** |
| 5 | paired gain over the baseline in both repetitions | **+1** and **+2** |
| 6 | no safety loss | safety episodes 4/4 runs; clarification negatives 0/12 praise, 0/12 greeting, 0/9 bare answer |
| 7 | cost within 10%, else declared and automatic promotion blocked | p50 per turn **10.8 / 10.2 s** vs baseline **11.0 / 10.4 s** (no increase); **tool calls up 12→16 and 10→12**, above 10% → **declared, automatic promotion blocked** |

**The gate is met, with criterion 7 taking its "declare and block" branch.** The candidate is
adoptable on the branch. Activation in production stays the user's decision and was not performed.

### The 24 episodes, by family

| family | base r1 | base r2 | cand r1 | cand r2 |
|---|---|---|---|---|
| 1 behaviour correction and removal | 1/3 | 1/3 | 1/3 | 1/3 |
| 2 yes / no / maybe, praise, pendencies | 3/3 | 3/3 | 3/3 | 3/3 |
| 3 plan and task change | 3/3 | 3/3 | 3/3 | 3/3 |
| 4 teaching and correction across sessions | 1/3 | 1/3 | 1/3 | **3/3** |
| 5 conditional preferences, composite answers | 2/3 | 3/3 | **3/3** | 3/3 |
| 6 formulation transfer, with near negatives | 3/3 | 3/3 | 3/3 | 3/3 |
| 7 recall, provenance, temporal history | 3/3 | 3/3 | 3/3 | 3/3 |
| 8 self-description, receipts, permissions | 3/3 | 3/3 | 3/3 | 3/3 |
| **total** | **19/24** | **20/24** | **20/24** | **22/24** |

### What this reading does NOT support, said plainly

* **The gain is small and not robust.** +1 and +2 episodes out of 24. Family 4 moved from 1/3 to 3/3
  between the candidate's two repetitions on the same set, so a two-episode swing is within this
  instrument's own variance. Do not read the totals as a stable effect size.
* **Five of eight families are at ceiling in both arms**, so most of the set had no headroom to detect
  a difference. The set is too easy in families 2, 3, 6, 7 and 8 and should be strengthened before the
  next reading.
* Two repetitions of 24 episodes are not 48 independent cases.
* This is an engineering gate on a sample of 24, not a statistical proof, and the strategic percentage
  targets are **not** recalibrated by it.

---

## 2. Transfer, reported separately — **inconclusive**

Family 6 is 3/3 in every run of both arms, so there is no headroom in which a gain could appear: a
strong baseline is not a demonstration, as the guide says. Worse for the claim, the artefacts show
the definition write firing inconsistently (2 of 6 family-6 episodes in the baseline, 3 of 6 in the
candidate) while the *answers* were correct 3/3 throughout — so most of those correct answers came
from **episodic recall**, not from a stored definition being reused for a new formulation. Episodic
memory is useful and is not the adoption of a policy.

**Verdict: inconclusive.** Not failed — nothing here shows transfer breaking — and certainly not
demonstrated. A reading that could decide it needs formulations the episodic route cannot answer.

---

## 3. What was fixed this phase, each with its reproduction

| id | defect, as reproduced | fix | tests |
|---|---|---|---|
| 93.Q1 | `_bound` accepted a context sharing any four-letter word and a subject present anywhere in the message or in the global entity set. The review's four controlled cases: the correct proposal committed and **so did three wrong ones**. | binding travels with the CLAUSE carrying the value; a known entity resolves a reference but never authorises one; every content word of a context must be present | v149 (8) |
| 93.Q3 | *"I don't have a specific location recorded"* said while the location WAS stored and merely unretrieved | `hmgfu/recall_state.py`: four states, classified from judgements the turn already makes; three of them may never be said as absence; exactly one warrants a search | v150 (10) |
| 93.Q2a | an elliptical answer could never fill the blank its own question left — `protocol_unavailable: a proposal carries no evidence reference`, because evidence was only sought in the current message | a delivered pending case is a second place evidence may live; the value keeps a reference into the turn that stated it, the subject must still be bound here, the modality is re-read from the case's own utterance | v152 (12) |
| 93.Q2b | a bare "no" or "maybe" **erased** the case it answered — rejected and deferred cases came back with `needs None, question None, proposals []` | `_persist` writes only what the turn produced; fourth instance of *an optional field is an omitted field* | v154 (9) |
| 93.Q2c | the router was told to expect a yes/no to a question that asked for a NAME | the case's `needs` travels with the question; the wording was chosen by measuring four candidates against the real router (0/3 → 2/3, no proposals on unrelated turns) | v153 (7) |
| 93.Q4 | `memory_search` inherited `retrieval_limit`, the per-turn INJECTION budget, so a deliberate search saw no further than the automatic pass that had already missed | the tool's own `limit` is passed down; the two numbers are different quantities | v156 (4) |

Instrument work, which is not a fix to the product but is why the numbers mean anything: the
clarification judge (`scripts/answer_oracle.py`, v151), the re-judge of the nine artefacts already on
disk (`scripts/rejudge_clarification.py`), the four-arm clarification probe, and the three-condition
self-recall arms (`scripts/self_recall_arms.py`, v155).

### Self-recall, before → after the reach fix (same settings, same seeding)

| condition | before | after |
|---|---|---|
| `in_context` | 3/3 correct, **0** searches, 0 wasted | 3/3 correct, **0** searches, 0 wasted |
| `related_only` | **0/3** correct, searched 3/3, claimed absence 2/3 | **3/3** correct, answered 3/3, claimed absence **0/3** |
| `truly_absent` | 3/3 correct | 3/3 correct, invented 0/3, no denial of the user's speech |
| full chain (search → evidence → used, not already present) | **0** | **2** |

### Clarification, four arms

| arm | taught exactly | through the protocol |
|---|---|---|
| `pendency` (bare "my current project") | 0/3 | 0/3 |
| `pendency_longer` ("the project I am working on") | **2/3** | **2/3** |
| `complete` (after a question) | 3/3 | 3/3 |
| `control` (**no question at all**) | 3/3 | 3/3 |

The control is the finding: the complete statement teaches just as well with no question, so the
earlier 3/3 measured the statement and never measured the cycle. The review was right.

---

## 4. Mistakes of my own, corrected in the open

* The first `rejudge_clarification.py` looked only for `definition.meaning` and reported **0/27**. The
  runs had written the right value through the personal-fact adapter. Same class of instrument error
  it existed to catch; corrected in place with the reason written down.
* `answer_oracle` first required every content word of the taught sentence and scored *"it is listed in
  my records as your primary project"* as not an answer. Corrected **after seeing results**, said so in
  the code, and both numbers are reported: over all 69 recorded clarification runs, applied by the
  taught wording **5**, by meaning **24**.
* The `truly_absent` judge failed replies that searched, invented nothing and asked — which
  `recall_state` itself calls honest. Corrected, with the line held: *"you never told me"* stays a
  failure everywhere, because a search that can miss does not establish the other person's act.
* A size deviation was decided on a four-minute sample that had landed on a provider timeout, and
  withdrawn nine minutes later. Both are left in the pre-registration.
* **Two of the four episodes the candidate "failed" were my oracle's errors, not the system's** (F1-1
  and F1-2 above), and I had written the second of them into the backlog as a product defect before
  reading the artefacts properly. Both are left counting against the candidate in the gate.
* I was one step from reporting `behavior_policy` as a barrier because one field was null, when the
  adjacent field held the correct answer.
* `scripts/serve_tailscale.py`, someone else's file, was swept into a commit by a broad `git add` for
  the second time and removed from the index again in `57c8503`. The file on disk is untouched.

---

## 5. Still open — the causal backlog, in order

1. ~~**F4-1 / F4-2: a definition is taught, answered correctly, and never written.**~~ **Closed in
   93.W (`2124d3a`), after this reading and without touching it.** `diag_definition_write` localised it
   to **0/6, "no envelope" every time** — the protocol refused nothing because nothing reached it. A
   single-variable bisect on the router call then showed the cause: with an **empty** tool catalogue the
   same sentence and schema produced the correct `domain_definition` proposal, and with the **real**
   22-tool, 3,793-character catalogue it produced `memory_update: null`. The learning contract sat ahead
   of the catalogue; the same words now go last, nearest the message. Taught **1/3 → 2/3** against the
   real router with undue proposals on the negatives unchanged at **0/3**, and the end-to-end probe
   **0/6 → 6/6**, each through the protocol. Suite 1585 passed, 1 xfailed.
   **The reserved set was not re-read**, so the gate above stands as measured on `39e9c5c` and this
   improvement is *unmeasured against it*. It also makes transfer newly **measurable** rather than
   measured: a reliably written definition is the precondition the inconclusive verdict lacked.
2. **F1-2 is my oracle's fault too, and the system was right.** The artefacts show the candidate
   superseding the conflicting prior correctly in all four runs:
   `directives.response_style: 'long, detailed explanations with full background' -> 'respostas em
   português'`. My `writes` expectation demanded the exact string `'responde sempre em português'` —
   the **whole sentence** — which is the very thing this project treats as a defect when it is stored.
   The episode asked for the wrong thing.
3. **F1-1 is my oracle's fault as well.** `directives.response_style: None -> 'short snippets'` then
   `'short snippets' -> None` in all four runs: the rule was taught, then dropped, exactly as the
   episode's two messages asked. `forbidden_values` matched the legitimate teaching step.

   **So family 1's true score is 3/3, not 1/3** — in both arms — and the reserved reading therefore
   **understated both** of them by two episodes per repetition. The gate was scored against the
   candidate with these counted as failures, which is the conservative direction, and **it is left that
   way**: correcting an oracle and re-reading the same reserved set is precisely what the
   pre-registration forbids. The corrected oracles belong to the new set, and this diagnosis is why
   they will differ.
4. **The bare two-word elliptical answer still produces no envelope.** The deterministic contract
   accepts it (v152); the router does not emit it.
5. **The reserved set is too easy** in five families and should be strengthened before the next
   reading — not after seeing which episodes failed.
6. **Tool calls per run rose** (12→16, 10→12). p50 latency did not, and failed or blocked calls fell
   from 7/3 to 2/0, but the call count is a real cost and blocks automatic promotion by criterion 7.
7. ~~**`behavior_policy` still returns null.**~~ **Withdrawn — measured, and it is not a defect.**
   *"Always answer me with short snippets."* yields `memory_update: null` **and** a correct
   `directive: {kind: response_style, value: "short snippets"}`; with a condition it yields
   `condition: "unless I ask for the full context"`, extracted verbatim. Response style is the
   directive mechanism's job, so null is the right answer there and the turn reaches the right
   mechanism. I nearly reported this as a barrier on the strength of the null alone; looking at the
   whole router output rather than one field of it is what stopped me.
8. **A fresh reserved set is now required.** 93.W changed behaviour after the reading, so the next
   reading needs a new set, prepared and registered before anything is read from it.

---

## 6. Cost of this execution

| | |
|---|---|
| Authorised | 12 h elapsed, 10 h local GPU, granted after `8efeb68` (committed 19:56) |
| Elapsed | ~7 h 20 m, to 03:15 |
| Local GPU | ~4 h 30 m (four validation runs ≈ 2.4 h, four clarification campaigns, three self-recall campaigns, the router wording measurement, the sequence probe) |
| Remaining | ~4 h 40 m elapsed, ~5 h 30 m GPU, with the last hour reserved |
| External spend | none |

## 7. Activation and rollback

**Not activated.** To adopt, on the user's decision only:

```bash
# the candidate is already on the branch; nothing needs to be moved to use it
cd /c/Users/you/hmg-fu && git log --oneline -1        # expect 39e9c5c or later
```

Learning stays off until switched on per base, and only on a test base:

```bash
# enable the protocol in a DEV base (never the real one)
python -c "from hmgfu.agent import AgentEngine; e=AgentEngine('dev.db'); e.settings.set('interactive_learning_mode','confirm')"
```

Rollback is a checkout, because nothing was migrated and no schema changed destructively:

```bash
git checkout 8efeb68 -- hmgfu/          # the reviewed build, file for file
```

The `learning_cases` table is created lazily and an older build simply ignores it; no data conversion
happened in either direction.

Recovery checkpoint: **`8efeb68`** (baseline, also checked out in the worktree
`C:/Users/nora/hmgfu-baseline-93v` during this phase) and **`39e9c5c`** (the frozen candidate).
