# Phase 93 — integrated learning and operational self-knowledge

Executing `reports/codex_latest_conversation_20260911/EXECUTION_GUIDE.md` after its `ANALISE.md` of
the real conversation of 2026-09-11. Authorised: up to 12 h elapsed and 10 h local GPU.

**Not done, and not authorised by this guide:** the real application was not restarted, `adapt` was
not activated in production, real memory was not touched, the model was not changed, PA3 was not
touched. The `confirm` activation of 2026-09-11 06:33Z stands as the user separately authorised it;
nothing here extends it. Third-party changes (`.claude/launch.json`, `scripts/serve_tailscale.py`)
are preserved untouched and untracked — one of them was swept into a commit by a `git add scripts/`
and untracked again in `25bfca7`, which is recorded rather than quietly amended.

## Start state, verified rather than assumed

HEAD `742dea6` on `phase90-diagnostic-cycle`, pushed. Live app serving at `confirm`
(`GET /api/settings`). Suite before any change: 1336 passed, 1 xfailed.

## What the analysis asked, and what was done

### 93.A — receipts name the operation, and a "yes" has one addressee

`transactions_of` collapsed a directive change to a boolean, so removing `output_prefix` — tombstone
in the ledger, prefix gone from the replies — was reported as a **false execution claim**. The
summary now carries `operations` of `(op, target)` and each claim class is supported only by an
operation of its own kind. The trap the analysis named is what most of the tests defend: widening
`remove` to accept "a directive changed" would have let any write prove any removal. The learning
protocol's effects join the same summary, and an effect that did not apply is not an operation.
Summaries built by hand keep the pre-93 rule, so no existing caller changed behaviour
(**v132, 10 tests**).

`begin_turn` runs before the learning turn, so a plan proposal silently consumed a "yes" that a
delivered question was waiting for — which is how *stop saying none* became an approved plan while
nothing was learned. With both pending, **neither** is consumed and the turn asks which one. No
phrase picks a winner. An undelivered question, another session's question and the protocol being off
are not second addressees (**v133, 8 tests**).

### 93.B — an obsolete plan stops holding the user's next request hostage

Two defects, both reproduced without a model:

* `authorization()` returned `approved_plan` whenever a plan record existed, so a stale plan's scope
  narrowed the turn even when the user had just asked directly — `create_widget` blocked as "outside
  the approved plan's scope (memory_search)". A plan scopes the **model's unprompted work**, not the
  user's next request.
* `plan_task` answered `already_active` to an explicit new task. The user may switch; the old plan is
  marked **superseded with its reason and turn**, not dropped.

The discriminator is the USER's own request, not `_turn_effects_allowed` — which is also true when
the router or the plan pinned a tool, and using it cost a regression in `test_v38` that said so.
Guards that survived: a prohibition still wins, no-request-and-no-plan still authorises nothing, and
the model re-planning around its own work is still refused (**v134, 8 tests**).

A promise about something the turn had **already done** was becoming a permanent task, because
`acted` read only the tool trace while the prefix removal happens deterministically outside it. The
transaction summary answers that now — planning still does not count as doing, and a promise on a
turn that genuinely did nothing still becomes a proposal the user can refuse (**v136, 8 tests**).

### 93.C — a standing rule about HOW to answer finally has somewhere to live

The absence of `learning_cases` was diagnosed, not assumed. The DEV replay
(`scripts/diag_sequence_20260911.py`) records, per turn, whether the router was even **given** the
envelope contract: it was, on every turn, and it answered `null` anyway. A raw capture of the
router's own output finished it — for *"I prefer short snippets unless I ask for the full context"*
the model returns `memory_update=null` and classifies the turn as an **instruction**. It recognised a
standing rule and had nowhere to put it:

* the directive vocabulary was `output_prefix`, `output_suffix`, `conversation_opener`,
  `conversation_closer`, `tool_rule:<tool>` — none of them is "how replies should be written";
* nothing anywhere could hold the **exception**. A policy stored without "unless I ask for the full
  context" is not the policy the user stated.

So `response_style` joins the vocabulary in both fields the model uses, and a policy may carry a
`condition`: schema, prompt, sanitiser, an additive column, the render (value plus the stated
exception, never the raw sentence, so no unstated exception leaks in) and the protocol adapter, which
no longer files every policy under `tool_rule:memory_search`. With that, the same 12B emits the
directive for **all three wordings probed, Portuguese included** (**v135, 14 tests**).

This is a contract fix, not a rule for a sentence: the class that had no representation is
"a standing rule about how to answer, with an exception".

### 93.D — the assistant reads its own state

`hmgfu/operational_state.py` compiles what is in force from the stores that already hold it: active
directives with their conditions, the plan and whether it is only proposed, the question this session
is waiting on **and that a bare yes answers that one**, and what the previous turn actually changed —
from the transaction summary, not from the reply. No extra model call. Every line is read at build
time, an unreadable source says `unavailable` rather than reading as "nothing", and the block states
that it authorises nothing (**v137, 9 tests**).

## Evidence, end to end

The original sequence, replayed on a disposable base with explicit fixtures — behaviour correction,
confirmation, removal, questions about the plan, teaching a conditional preference, then an unrelated
request:

| check | before (HEAD `742dea6`) | after |
|---|---|---|
| the prefix is actually removed | ok | ok |
| no permanent task from the assistant's promise | **FAIL** | ok |
| the teaching leaves a trace | **FAIL** | ok |
| the widget request is not blocked by the old plan | **FAIL** | ok |
| the widget is created | ok | ok |

**5/5, in 3 of 3 repetitions** — but under a verdict the independent review showed to be permissive,
and two of its gates have since been corrected (93.R1 below). Under the strict verdict the sequence is
**5/5 again**, for reasons that are now measured rather than assumed.

Suite: **1336 → 1380 passed, 1 xfailed**. Module ceilings held by compaction and by relocating the
directive rendering to `directive_render.py` — never raised.

### 93.E — transfer, measured on this build, with the loss it came with

`scripts/diag_transfer_cl.py 6`, paired arms, delivery proven per turn from the captured payload
(**L 15/15, C 0/20**), artefact `outputs/runs/20260911T075832Z-20c1938-e38a3f/`:

| probe | expected | arm C | arm L |
|---|---|---|---|
| `DELTA-9 - Dynamic Ledger Transfer Adapter.` | commit | 0/4 | **1/3** |
| `OMEGA-1? Operational Metrics Gateway.` | commit | 0/4 | **1/3** |
| three near negatives | no definition | 4/4 clean | 3/3 clean |

L is ahead of C on both probes with no leakage, which is consistent with phase 92's finding, but
n = 3–4 per cell is far too small to call anything demonstrated. **Inconclusive at this size.**

**A correction to my own claim.** I first reported this as a regression introduced by the phase:
5 of 12 episodes dropped for invalid preparation, against 11 of 12 landing in phase 92. A paired A/B
that swaps ONLY `hmgfu/turn_router.py` between this build and the phase's start commit says
otherwise — **candidate 5/8, baseline `742dea6` 5/8**, with the same three missing envelopes in each
(`scripts/diag_teach_reliability.py`, artefact `outputs/runs/20260911T080534Z-1941e2b-447f59/`). The
difference between campaigns was sampling, not the phase. The claim is withdrawn.

**What is real, and older than this phase:** teaching a definition lands about five times in eight,
and the failure is binary and upstream. When an envelope appears it is ALWAYS correct
(`domain_definition`, `ACME-7`, `Atlas Control Mesh`, committed); when it fails there is no envelope
at all. The router is called exactly once either way, with no warning and no transport failure — it
simply answers `memory_update: null` on three of six identical turns. So it is neither a missing
contract (93.C closed that) nor a degraded call, but a perception decision on a knife edge.

### The regression this phase introduced, and how it was found

The first transfer campaign after 93.C returned **0/0**: every episode dropped. Bisected against the
phase's start state by swapping only `turn_router.py` — at `742dea6` the same teaching returns a
`domain_definition` proposal; with the 93.C router it returned `memory_update=null`. Three iterations,
each with a measured gain:

1. the proposal-level `required` was ruled out (still null without it);
2. describing `response_style` in prose made `behavior_policy` a magnet — *"My dog is called Green."*
   came back as a `behavior_policy` and a definition as nothing. Fixed contrastively: the paragraph
   now says what each kind is FOR;
3. the model then wrote the definition as `value = "ACME-7 means Atlas Control Mesh"` — the whole
   clause. **The new oracle caught that; the old `bool(new_definition)` would have passed it.** The
   contract now says the value is the meaning alone, never the sentence stating it.

After the three: definition → `domain_definition` with `value` "Atlas Control Mesh"; style →
`response_style` with `value` "short snippets"; fact → `personal_fact`.

## 93.R — what the independent review of 93.F corrected

**The instruments were permissive, and two conclusions were too strong.** Verified here before
changing anything:

* `teaching_left_a_trace` accepted any delta OR the mere presence of an envelope, so a refused
  proposal, a wrong value or a policy stripped of its exception all passed;
* `widget_created` looked for the tool's NAME in `_tools`, which `bench_say_do` fills from the whole
  trace — failed and blocked calls included. Re-reading the stored artefacts shows the probe had been
  asking for a **`timer` widget, a type the product does not have**: every one of those calls failed,
  and the earlier "widget created" claims are **withdrawn**. The artefacts cannot settle it either
  way, because they store only tool names, not outcomes;
* the A/B swaps only `turn_router.py` inside the current tree, unrandomised, with misses that are not
  paired. It supports **"no aggregate difference in this sample"**, not "no regression in this phase".
  That sentence is corrected wherever it appeared;
* the six test files are **54 tests**, not the 57 I wrote.

**A defect the stricter judge found immediately.** The conditional policy was being stored **without
the exception the user stated** — `response_style = "short snippets"` with an empty condition, in
**6 of 6** runs. The cause is the lesson of 92.E4 repeating itself: `condition` was an OPTIONAL field
in the directive contract, and an optional field is an omitted field. Making it required — with `""`
as the valid answer for a rule stated without an exception — took it to **4–5 of 6**. A related
rendering defect went with it: the template assumed the connective and produced "unless unless …", so
the exception is now rendered as the user's own words without assuming how they phrased it.

**Attribution by session (93.R2).** `record_operations` kept one list on an engine that serves every
session, so an operation performed in session A appeared in session B's block as something B had just
done. Reproduced without a model, then fixed: effects are recorded per session and turn; an effect
from elsewhere is still shown, because a directive is global and still in force, but labelled as
another conversation's with its session and turn (v139, 7 tests).

Under the corrected verdict the sequence is **5/5**, with the first `create_widget` attempt failing
for missing props and the retry succeeding — recorded, not hidden.

## 93.R3 — the frozen replay overturns the 93.F barrier

93.F concluded that the remaining candidates were "properties of the model call, and changing the
model is out of scope". That is now **wrong, and withdrawn**. `scripts/diag_frozen_replay.py` captures
the request the router actually sent — messages, options, schema, with a sha256 — and calls the model
again with exactly those bytes:

| arm | sample 1 | sample 2 | distinct requests sent |
|---|---|---|---|
| **frozen** (same bytes) | envelope 8/8 | envelope 0/8 | 1 |
| clock line rewritten | 5/8 | 4/8 | 8 |
| whole fresh turns | 2/8 → 5/8 after the fix below | 3/8 | 8 |

**The model call is deterministic.** Two independent captures each answered the same way eight times
running — once always with an envelope, once never. The outcome is a function of the request, not of
chance in the call. Everything earlier read as "a perception decision on a knife edge" is context
sensitivity, which is inside the contract and inside scope.

**And the context that varies is one line.** A diff of the router's system message across fresh turns
of the same sentence shows the ONLY difference is the runtime clock, down to the second:
`{"now_local":"2026-09-11T11:15:09+02:00",...}` against `...:15:22...`. Seconds cannot bear on "is
this turn teaching me something", so the CLASSIFIER now receives the block with seconds removed, while
the ANSWER path keeps full precision — when the user asks the time, the value spoken is still exact,
and `unix_seconds` stays for relative-time reasoning (v140, 4 tests).

**What that fix is and is not.** It is justified by mechanism: an irrelevant token that changes every
second stops changing, so two turns in the same minute send identical bytes. Its effect on the
envelope rate is **not demonstrated** — fresh went 2/8 → 5/8 in one paired sample and 3/8 in the next,
which n=8 cannot separate. No rate is claimed for it.

## The barrier, in the format the guide asks for

**Minimal reproduction**

```
.venv/Scripts/python.exe scripts/diag_teach_reliability.py 8              # candidate vs 742dea6
.venv/Scripts/python.exe scripts/diag_teach_reliability.py 8 --baseline HEAD
```

**Expected vs observed.** Expected: the same teaching, on the same fresh base, with the same settings,
produces the same classification. Observed: `In this project, ACME-7 means Atlas Control Mesh.` yields
a correct `domain_definition` proposal that commits in **five runs of eight**, and **no envelope at
all** in the other three. The split is binary — there is no case of a wrong kind, a wrong term or a
wrong meaning. The router is called exactly once in both outcomes, with no warning and no transport
failure, at `temperature=0.0`.

**Commit and artefacts.** `1941e2b` (and `742dea6` for the baseline arm);
`outputs/runs/20260911T080534Z-1941e2b-447f59/` and `…T081142Z-af0d412-9ba50c/`.

**Hypotheses tested**

| # | hypothesis | result |
|---|---|---|
| 1 | the phase introduced it | **falsified** — 5/8 on this build, 5/8 at the start commit, same three misses |
| 2 | the router call fails or times out and degrades silently | **falsified** — one call, no warning, a parsed reply that simply says `memory_update: null` |
| 3 | the contract is missing (93.C) | **falsified** — the contract is delivered on every turn (`envelope_contract_sent=yes`) |
| 4 | the prompt offers `null` as the easy default; stating both sides would balance it | **no gain** — 3/8 against 5/8, within noise at this size. Reverted rather than kept on a hope |

**Superseded by 93.R3.** This section said the remaining candidates were properties of the model call.
The frozen replay shows the call is deterministic and the varying input is the clock, so the barrier
as stated here is withdrawn. What remains open is narrower and stated there: which request bytes
decide the envelope, and whether any contract-level change moves the rate — a question n=8 cannot
answer.

**Decision needed.** Either accept a perception that teaches reliably about five times in eight and
design around it — a confirmation question when the turn looks like teaching and no envelope came
back would make the miss visible to the user instead of silent — or authorise a measurement campaign
large enough to test candidates properly. The first is inside the current contract and is the
recommendation; the second needs an explicit budget.

## What is NOT claimed

* **The guide's validation gate (93.V) has not been run.** The 24 PT/EN episodes across the eight
  families, two repetitions per arm, with the paired gate and the safety probes, are **not built**.
  Nothing here should be read as the candidate being adoptable under that gate; what is demonstrated
  is the reproduced sequence and the unit-level contracts (v132-v137 are **54** tests, not the 57 I first wrote).
* **The old 92.E7 is not claimed as met.** This phase did not replace it with a smaller set.
* Self-recall (93.D, second half) is not verified: that an internal recall request reaches
  `memory_search`, respects permissions and is consumed, is still pending.
* Contextual selection of learned examples (92.E5R-R8c) is still open — selection is by the newest
  case's context and ignores the request text.
* **Teaching a definition lands ~5 times in 8, and that is NOT a regression of this phase** — the
  paired A/B measures the same rate at the phase's start commit. It is the first item of the backlog,
  and it is older than this work.
* Transfer is **inconclusive at this sample size**, not demonstrated and not refuted.
* The matrix diagnostic still shows model variance: on one run of the final build the definition step
  wrote nothing and only 1 of 2 recalls was backed by a write. That variance is real and is reported
  rather than averaged away.
* No percentages are raised. The strategic targets (originality, efficiency, AGI-readiness, learning)
  are **not recalibrated** by this work.

## Reproduction

```
.venv/Scripts/python.exe -m pytest tests/test_v132_receipts_name_the_operation.py tests/test_v133_one_yes_one_addressee.py tests/test_v134_task_switch.py tests/test_v135_conditional_policy.py tests/test_v136_promise_after_a_real_action.py tests/test_v137_operational_state.py
.venv/Scripts/python.exe scripts/diag_sequence_20260911.py     # the whole sequence, on a disposable base
.venv/Scripts/python.exe scripts/diag_learning_matrix.py       # facts, definitions, behaviour, correction
.venv/Scripts/python.exe scripts/diag_transfer_cl.py 6         # C vs L
```

Artefacts under `outputs/runs/2026091*`. Checkpoint for recovery: `742dea6` (the state before this
phase); the phase's own commits are `d120b29`, `b001e3c`, `25bfca7`, `f58757f`.

## Activation and rollback, for the user to decide

Nothing was activated. To adopt on the live app: stop the serving process, `git pull` on the branch,
start it again — the settings row is unchanged, so it stays at `confirm`. To roll back: the same, at
`742dea6`. The real base was backed up before the earlier activation
(`hmgfu.db.backup-pre-learning-20260911-063252`).
