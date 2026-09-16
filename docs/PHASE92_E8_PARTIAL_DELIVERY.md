# Phase 92 — E8 delivery report (PARTIAL, and why)

Plan: `docs/INTERACTIVE_LEARNING_EXECUTION_V2.md` (E0–E8). B0 = `7e47028`, tag
`B0-learning-protocol-7e47028`. Candidate after this work = `054d621`, tag `E2-integrity-done`.

**This is not a completed execution and does not claim the objective was met.** Two stages are
complete with evidence, one is partial, and the reserved campaign is BLOCKED on a measured budget
finding. Per §9 of the plan, a blockage is delivered as a partial report naming the exact cause and
the pending steps.

## Stage table

| Stage | State | Evidence |
|---|---|---|
| E0 Source, safety, versioned plan | **done** | HEAD verified identical on remote; B0 tagged; effective profile captured; plan and anonymised synthesis versioned; ROADMAP registered |
| E1 Instruments and reproductions | **partial** | 2 of 3 known defects reproduced on synthetic fixtures; DEV24/reserved48/transfer12 **not sealed**; independent judge **not built** |
| E2 Integrity first, baseline S | **done (fixes)** / **partial (baseline)** | both integrity fixes implemented test-first, full suite green; the S measurement on DEV24 was not run because DEV24 does not exist yet |
| E3 State and three adapters | **not started** | — |
| E4 Wire C | **not started** | — |
| E5 Wire L, transfer | **not started** | — |
| E6 Compatibility, cost, freeze | **cost done early** | measured projection below |
| E7 Reserved | **BLOCKED — budget** | see below |
| E8 Delivery | **this report** | — |

## What the effective profile actually is (E0)

Read **after** engine construction, not from config defaults — the plan warned about exactly this and
it was right. Six settings differ from their defaults:

| setting | default | effective |
|---|---|---|
| `embed_model` | nomic-embed-text | **bge-m3** |
| `thinking_mode` | dynamic | always |
| `workspace_dir` | (empty) | set |
| `regulator_enabled` | false | **true** |
| `chat_correction_signal` | false | **true** |
| `observe_first_n` | 0 | 50 |

Any arm that quoted the config defaults would have measured a system nobody runs.

## E2.1 — a router candidate no longer outranks the evidence

**Root cause.** `DirectiveStore.apply` read `detected or detect_output_directive(text) or
detect_tool_rule(text)`. A supplied candidate short-circuited both local detectors, so there was no
arbitration at all. A request for a search *policy* became an `output_prefix` whose literal value was
the word `none`, and `none ` was prepended to later replies, apologies included.

**Fix.** `directive_candidate_supported` requires the candidate to be evidenced by the instruction,
and it holds three ways at once:

- a **literal** format (prefix/suffix) must have its value quoted in the request — this refuses the
  wrong `none` while **keeping** an explicitly requested `none`; banning the word would be a patch;
- a **content spec** (opener/closer) is a description by design (`a short joke`) and is exempt;
- the router legitimately reads formats the local regex cannot (`prefix your answers with the word
  Bom dia` detects nothing locally), so candidates are not rejected wholesale.

**Evidence.** `tests/test_v117_directive_arbitration.py`: 7 of 11 fail before, all pass after. The
policy is now reachable as `tool_rule:memory_search`, so the behaviour is representable at all.

## E2.2 — derived memory is differentiated, not deleted

**Reproduced** on a synthetic base (`scripts/diag_provenance.py`, no personal data, no model calls).
Asked to expand a term the user had defined, the injected context carried the user's own teaching
alongside four unsupported derived lines: two invented expansions, a superseded version, and an
assistant note reading *"Always answer … without checking memory"* — with no item showing its source.

The existing echo guard could not close this: `scope=all` deletes **every** assistant memory (which
the plan forbids — the user may legitimately ask what the system said), and `scope=echoes` only drops
restatements of *ledger values*, so an invented expansion passes untouched.

| arm | invented expansions reaching the model |
|---|---|
| plain question (the common case) | 2/2 |
| echo guard, scope=all | 0/2 — but all assistant memory destroyed |
| echo guard, scope=echoes | 2/2 |

**Fix.** Derived points are routed to their own section, placed **last** so the budget spends on
evidence first, under a heading stating they are derived, unconfirmed, and must never be used to
expand a term the user has defined. Nothing is deleted; macros keep their `[pattern]` tag, because a
macro may indicate *where to look* without asserting a value.

**Limit, stated plainly:** this makes the status *visible and structurally separated*. It is a
contract on what the model is shown, not a guarantee about what a 12B will say. Measuring that is
what E4–E7 were for, and they were not run.

## The blockage: E7 does not fit the authorised budget

Cost measured on this profile and machine, not estimated: `modality_reply_v1` ran 6 conversations ×
4 user messages in 436 s → **18.2 s per user message**. The plan's episodes are 4–8 user messages
(midpoint 6) → **~109 s per episode**.

| run | episodes | projected |
|---|---|---|
| E7 reserved, S vs L, 48 × 2 reps × 2 arms | 192 | **5.81 h** |
| E7 transfer, C/L, 12 × 2 × 2 | 48 | 1.45 h |
| E4/E5 DEV24 for S, C and L | 72 | 2.18 h |
| E4 live pilot | 6 | 0.18 h |
| **subtotal** | | **9.63 h** |
| with the plan's own 25 % margin | | **12.04 h** |
| **authorised** | | **6.00 h** |

**E7 alone is 7.27 h.** The plan says not to start a run that predictably exceeds the balance, and
not to lower a gate to be able to claim full execution. Shrinking the reserved set, dropping to one
repetition, or trimming the episodes would each change a pre-registered gate after the design was
fixed. So the campaign is not started, and this is reported as a blockage.

Almost none of the 6 h has been spent: the work so far is deterministic, and total GPU use is roughly
ten minutes of reproduction runs.

## What remains, and what unblocks it

E1 (seal DEV24 / reserved48 / transfer12, build the independent judge and prove its safety negatives
at zero error), E3 (`learning_protocol.py`, `learning_state.py`, the `learning_cases` table, three
adapters, P = 100 %), E4 (wire C), E5 (wire L and transfer), E6 (freeze), E7 (reserved).

The decision belongs to the user, and there are three honest options:

1. **Raise the budget** to ~12 h and run the design as specified.
2. **Keep 6 h and re-scope the reserved campaign explicitly, before any measurement** — for example
   32 episodes × 2 repetitions × 2 arms (≈ 3.9 h) leaving room for DEV and transfer. This is a
   legitimate design change only if it is fixed *now*, not after seeing results.
3. **Build and validate on DEV only** (E1–E5, ≈ 2.4 h), delivering a candidate that is promising but
   explicitly not reserved-validated.

## Rollback

`git reset --hard B0-learning-protocol-7e47028` restores the pre-phase state. The two integrity fixes
are isolated in `054d621` and can be reverted alone. No database was migrated, no schema added, no
setting changed, and no data repaired.

## Not done, deliberately

No real memory was read or written; the live application was left running on the code it already had
and was **not** restarted, so it does not include these fixes; PA3 was untouched; no model changed;
production was not activated; the known bad live values (`output_prefix=none` among them) were **not**
repaired — that remains separately authorised, and correcting code does not repair stored state.

## Golden rules

| Rule | Status | Evidence |
|---|---|---|
| 1 Source of truth | ✅ | Effective profile read after engine construction; six deviations found |
| 2 Investigate first | ✅ | Both defects reproduced before any edit |
| 3 No symptom patches | ✅ | Refused to ban the word `none`; fixed arbitration and provenance instead |
| 4/5 Modular, no duplication | ✅ | Reused the audit's probe, the existing detectors, the existing section renderer; predicate placed in the module that already owns write gates |
| 6/7 Plan first | ✅ | E0–E8 registered in ROADMAP before product changes |
| 8 Document | ✅ | This report, the anonymised synthesis, the versioned plan |
| 9 Full stack | ⚠️ | Detector → store → injection covered; the turn, API and UI layers belong to E4 and were not reached |
| 10 No hidden features | ✅ | No new flag introduced in this stage |
| 11 Compatibility | ✅ | `directives.py` still at its 400-line ceiling; no signature changed |
| 12 Evidence | ✅ | Failing-first tests, suite 1130 passed, reproductions before and after |
| 13 Right layer | ✅ | Arbitration where candidate and detectors meet; provenance at the single line-building site |
| 14 Protect assets | ✅ | Synthetic bases only; personal audit kept local; third-party files untouched |
| 15 Clean interfaces | ✅ | One new section, ordered last; nothing duplicated or orphaned |

---

# Part 2 — after the independent verification of 92.E2

The verification (`reports/codex_review_92e2/REVIEW.md`) was right on every count, including that my
own headings were too strong. **E1 and E2 are marked PARTIAL**, here and in the ROADMAP.

## Corrections to the first delivery

1. **"E2 done" and "the boundary holds" were overclaims.** The sets are not sealed, the judge did not
   exist, and baseline S was never measured. Suite-green is not stage-complete.
2. **My option 2 arithmetic was wrong.** I offered "32 episodes ≈ 3.9 h" as a fit; the review checked
   it and it lands near 7.7 h once transfer, DEV and pilot are included — still over budget.
3. **The rollback advice was unsafe.** I wrote `git reset --hard`, with third-party files present in
   the tree. That is withdrawn: use a checkout or a separate worktree at the checkpoint, or revert
   the specific commits, preserving other people's work.

## F1 — occurrence of a value is not a request for a format

`directive_candidate_supported` accepted a literal format whenever its value appeared **anywhere** in
the message, so a candidate `output_prefix=none` survived both of these:

| instruction | before | after |
|---|---|---|
| `Always start your replies with the word none.` | `none Answer.` | `none Answer.` (legitimate) |
| `Never start your replies with the word none.` | `none Answer.` | **`Answer.`** |
| `…unsure; none of your guesses should replace evidence.` | `none Answer.` | **`Answer.`** |

`format_request` now requires the format to be **requested**: a prefix/suffix cue standing in
directive context, **not negated**, with the candidate's value in that request's tail. The cues, the
context test and the stop cues are `directives.py`'s own, reached by a local import so the
module-level direction stays one-way — nothing is duplicated and no phrase is hardcoded.

Closing it exposed a **real coverage loss**: `_PREFIX_RE` covered `begin|start|open` but not
`prefix`, so `"always prefix your answers with the word Bom dia"` — a legitimate format only the
router can read — was refused. The verb class is completed (`prefix|preced`, `append|suffix`), which
is the same grammatical class the regex already encodes.

## F2 — a macro is derived too

`source in (assistant, dream) AND type != "macro"` meant the *same* invented expansion was labelled
derived as a message and asserted as fact in `relevantFacts` as a macro. A macro is a consolidation
by construction: it now goes to the derived section and **keeps its `[pattern]` marker**, so it can
still say *where to look* without standing in as proof.

## F3 — the conditional policy

Confirmed still absent, and **not claimed**: `tool_rules_for` matches text, not evidence
sufficiency. That is E4 work.

## E1 — the judge (done)

The existing judge was extended, not replaced. Four learning classes added: a reply that does not
**expand** a term; a **promise** with no write; a **search** that ran unused; a **question**
suggesting a wrong value. Its own gate is met — `judge_learning_v1.json`, 16 labelled cases, **zero
error on the safety negatives**, with clean positives so a judge that flagged everything could not
pass.

The cue sets are the **instrument's**, declared as such in the code: to check a claim of updating
against its receipt, the judge must first recognise the claim. **Still not done: sealing DEV24,
reserved48 and transfer12.**

## E3 — controller and state (done), adapters (pending)

`learning_protocol.py` is a **pure** decision — no database, model or tool inside it, which is what
makes the enumerated table testable. It never decides that something is *true*, only whether the user
authorised a write and which target it reaches; it never accepts an id from a model; and it never
reads a missing field as agreement, so absence is `protocol_unavailable`.

**44/44 on the plan's transition table.** The rows that matter are the refusals: a bare yes cannot
approve a plan, another session's pending question cannot consume this session's answer, a candidate
stored without a **delivered** question earns nothing, generic praise trains no facts, and a moved
revision loses rather than overwrites.

`learning_state.py` records pendencies and receipts — never truth. One active question per session is
enforced by a **partial unique index**, the revision by **compare-and-swap**, and a legacy base never
gains the table while the protocol is off. It follows the caller's transaction, as `AssertionStore`
does.

Suite **1214 passed, 1 xfailed**. Both modules under the 400-line ceiling. **The three store adapters
are pending**, so nothing is wired into a turn yet.

## The full projection (E6), with what the first one omitted

Measured: **18.2 s per user message** on this profile. S episode 109 s; C/L episode 136 s at the
plan's own 1.25× ceiling.

| run | episodes | hours |
|---|---|---|
| E2 baseline S on DEV24 | 24 | 0.73 |
| E4 live pilot | 6 | 0.23 |
| E4 C on DEV24 | 24 | 0.91 |
| E5 L on DEV24 | 24 | 0.91 |
| E5 C/L transfer on DEV | 12 | 0.45 |
| E7 reserved S, 48×2 | 96 | 2.91 |
| E7 reserved L, 48×2 | 96 | 3.63 |
| E7 transfer **preparation** | 24 | 0.91 |
| E7 transfer consultation | 48 | 1.82 |
| E7 **consolidation/dream** | 24 | 0.91 |
| subtotal | | **13.40** |
| retries and discards (10 %) | | 1.34 |
| margin (25 %, plan-mandated) | | 3.68 |
| **total** | | **18.42** |
| **authorised** | | **6.00** |

**Everything before E7 totals 3.22 h and fits the balance.** E7 alone is 10.17 h, or 13.99 h with
retries and margin. So development continues; only the reserved campaign needs a decision, and I have
not changed a repetition count, an episode count or a gate to make it fit.

## Honest pendencies

- E1: DEV24, reserved48 and transfer12 are **not sealed**.
- E2: baseline S is **not measured**.
- E3: the **three store adapters** are not built, so nothing is wired into a turn.
- E4/E5: not started; they fit the budget once the adapters exist.
- E7: needs a budget decision or a re-scope agreed **in advance**.
- The live application still runs the pre-E2 code and was not restarted. The bad live values are not
  repaired; that remains separately authorised.

## Rollback (corrected)

Do **not** use `git reset --hard`: `.claude/launch.json` and `scripts/serve_tailscale.py` are other
people's work in this tree. Use `git checkout B0-learning-protocol-7e47028 -- <paths>` for specific
files, a separate worktree at the tag for comparison, or `git revert` of the four phase-92 commits
(`054d621`, `5f6c230`, `f21bb75` and the doc commits), each of which touches only files this phase
introduced or changed.

---

# Part 3 — self-recall review, adapters, and the L/adapt barrier

Sources: `reports/codex_self_recall_92/REVIEW.md` (new), plus the two earlier reviews. Candidate at
the end of this part: **`54adbe6`**.

**Headline, stated first because it is the acceptance criterion: mode L/adapt is IMPLEMENTED and
unit-tested but NOT WIRED and NOT MEASURED. Transfer is therefore NOT demonstrated, and this work is
NOT a completed learning cycle.** Storing and recalling facts is explicitly not the criterion.

## The two controller gaps the self-recall review found — closed

Both reproduced with its own probe before any change, both in code I wrote.

| gap | before | after |
|---|---|---|
| `evidence_refs=['assistant-reflection:invented-id']` | **commit** | `pass_through` — *"evidence reference does not resolve"* |
| `feedback=confirm` + `ambiguity=contradictory` | **commit** | `ask` — *"unresolved contradictory: nothing is written until it is settled"* |

**Evidence.** The controller is pure and cannot look a reference up, so the caller resolves references
and the controller refuses whatever did not resolve. `evidence_problem` checks the six properties the
plan enumerates — existence, origin, subject, context, modality, revision. Origin carries the
architecture: a user teaching authorises a user fact; a tool observation does so **only when it names
its source**; an assistant reflection **never** does. A reflection may accompany the user's own words;
it just cannot stand alone. That is what keeps self-recall useful without letting the system confirm
itself.

**Conflict.** An unresolved conflict now blocks every path that *writes*, whatever the feedback says.
Refusals still pass — blocking the write is the point, and swallowing a user's "no" would lose
information rather than protect it. Closing this exposed a real ordering bug in my own new guard: it
opened a *second* question while one was pending, violating the one-active-question invariant. Fixed.

Three older fixtures claimed an evidence reference without supplying what resolving it found; they now
supply it. No assertion was weakened.

## E3 adapters — done

`personal_fact` → FactStore's public entry (no synthetic sentence rebuilt to re-run a regex, no
`trusted=True` to bypass a rejection). `domain_definition` → AssertionStore. `behavior_policy` →
DirectiveStore as a **typed** policy.

The hard part is identity. AssertionStore supersedes per `entity_id + relation`, so one shared entity
per project would make each new definition **erase the last**. Identity is `(context, term)`, and both
halves are tested: two terms in one project coexist; the same term in two projects does not collide.
Reads resolve identity exactly as writes did, so a restart finds the same entity rather than guessing
by similarity.

Stores are **injected**, not constructed: AssertionStore is the only one that currently takes a shared
connection, so opening a second FactStore against the same file mid-transaction would contend for the
write lock instead of sharing it. **Pending and not claimed:** extending FactStore and DirectiveStore
to share a connection, which the plan asks for.

## E5 examples — implemented, not wired

Only a human-confirmed commit mints an example. A question, a maybe, a refusal, a pass-through, an
undelivered question and a revoked case each mint nothing. At most two reach the perception step,
filtered by context; revocation makes one ineligible immediately **without deleting the proof**; past
the cap the oldest stop being offered, again without deletion. An example is advisory by construction
— no action, no tool, no canonical write — and text inside one is data, so embedded instructions are
not commands.

## THE BARRIER — for Codex

**What is missing:** nothing calls the protocol from a turn.

```
grep -rn "learning_protocol\|learning_state\|apply_decision\|derive_example" hmgfu/*.py \
  | grep -v "^hmgfu/learning_protocol.py\|^hmgfu/learning_state.py"
```

**Expected vs observed.** Expected, for a C/L comparison: the perception step emits a `memory_update`
envelope, `agent.py` builds a snapshot, resolves evidence, calls `decide`, applies the adapters,
returns an honest receipt, and in `adapt` mode offers up to two examples. Observed: **no output at
all** from that command — zero product call sites. So `decide` is never reached, no envelope is ever
produced, no example is ever offered, and C and L are currently the *same* system.

**Commit / configuration / artefacts.** Candidate `54adbe6` on `phase90-diagnostic-cycle`, pushed.
B0 `7e47028` (tag `B0-learning-protocol-7e47028`). Effective profile: `gemma4:12b` chat and router,
`qwen2.5:1.5b-instruct` nano, **`bge-m3`** embed, `regulator_enabled` and `chat_correction_signal`
true, `thinking_mode` always. Artefacts: `hmgfu/learning_protocol.py`, `hmgfu/learning_state.py`,
tests v117–v124, `scripts/oracles/judge_learning_v1.json`, `scripts/diag_provenance.py`.

**Hypotheses tested, with results.**

| hypothesis | result |
|---|---|
| A router candidate outranks the detectors, so a policy becomes a format | Confirmed; fixed by evidence-based arbitration |
| Presence of a value proves a format was requested | Confirmed false; a request frame is now required |
| Derived summaries reach the answer as user facts | Confirmed; routed to a labelled section, macros included |
| An invented evidence reference can authorise a write | Confirmed; now refused |
| A confirmation can override an unresolved conflict | Confirmed; now blocked |
| One entity per project is enough for definitions | Confirmed false — it would erase each previous definition; identity is (context, term) |

**Stages.** Done: E0; E1 judge; E2 both integrity fixes; E3 controller, state and adapters; E5
examples. Pending: E1 sealing of DEV24/reserved48/transfer12; E2 baseline S; **E4 wiring** (envelope
in the existing call, snapshot, evidence resolution, receipt, visible question, settings flag,
self-recall path); E5 wiring of examples into perception; **the C/L comparison**; E6 freeze; E7
reserved.

**Budget.** GPU consumed this phase: roughly **10–12 minutes** of reproduction runs, out of 6 h
authorised. The barrier is **not** budget: E2 baseline S, the E4 pilot, C and L on DEV24 and the DEV
transfer total **3.22 h and fit comfortably**. The barrier is that the E4 wiring is unbuilt, and it is
a substantial change to the live turn path that should not be half-done.

**Decision needed.** Either (a) authorise continuing into E4 wiring in a further session, after which
the C/L DEV comparison runs inside the existing budget; or (b) re-scope. What must **not** happen is
calling this a completed learning cycle: facts are stored and recalled, and that is precisely the
claim the criterion excludes.

## Implemented / wired / tested / activated

| capability | implemented | wired | unit-tested | live-tested | activated |
|---|---|---|---|---|---|
| Directive arbitration by evidence | ✅ | ✅ (existing path) | ✅ | ❌ | ❌ |
| Provenance boundary for derived memory | ✅ | ✅ (existing path) | ✅ | ❌ | ❌ |
| Learning judge | ✅ | n/a (instrument) | ✅ | ❌ | n/a |
| Controller, state, adapters | ✅ | ❌ | ✅ | ❌ | ❌ |
| Mode L examples | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Transfer (C vs L)** | ❌ | ❌ | ❌ | ❌ | ❌ |

No percentage is invented, and no universal absence of regression is claimed: the suite is 1264
passed, 1 xfailed, which is the scope actually tested.

---

# Part 4 — the C/L comparison, run and answered

The user's acceptance criterion was stated in one sentence and is answered in one: *self-learning
must include mode L/adapt, reusing interpretations learned with human feedback on new formulations;
run the C/L comparison to tell real transfer from merely recovering values; if that capability does
not work, declare it a failure or a barrier — not "done" because facts were stored and recalled.*

**It does not work. It is declared a failure.** Retention and cross-session recall are demonstrated
(Part 3, `2a3c5e5`); transfer is not.

## What was wired first, and how it was verified

Arm L is now wired end to end at `d20a1c7`: a committed case is read back as a confirmed
interpretation and offered to the router in mode `adapt` only, so C and L differ in exactly one
thing. That difference is *verified*, not assumed — `scripts/diag_examples_block.py` prints the block
each mode renders and spies on `start_route`:

```
[confirm] block = ''
[adapt]   block = '- "In this project, ACME-7 means Atlas Control Mesh." was confirmed to define ACME-7 as Atlas Control Mesh (in project terminology)'
reached the router: '- "In this project, ACME-7 means Atlas Control Mesh." ...'
```

## The first comparison was void, and the reason matters more than the result

The first run reported no difference between the arms. It measured nothing. A syntax error in my own
edit to `turn_router.py` was caught by the sensitizer's blanket `except Exception` and logged as
`nano extraction failed (unterminated string literal ...); using heuristic fallback`. Every turn
silently degraded to the heuristic path, the router never ran in either arm, and the empty result
*looked exactly like a negative finding*. Silence of that kind does not merely hide a bug — it
manufactures evidence.

Fixed at the layer that was wrong, with a test that discriminates
(`tests/test_v126_defect_not_degradation.py`): `SyntaxError`, `ImportError` and `NameError` now reach
the caller, because nothing in this path compiles or evaluates model output and a model cannot
provoke one; a reset socket, a timeout or an unparseable payload still degrade to the heuristic
extraction, because there degrading is the correct answer and the turn must not fail.

## The second problem: a probe with no headroom cannot measure transfer

With the router working, both arms committed the original transfer wording. Arm C already succeeded,
so there was nothing left for L to win — a ceiling effect, not a null result.
`scripts/diag_transfer_ladder.py` walked ten definition wordings through the **baseline** and reported
the only two it actually misses, with no false positives on three negatives:

| wording | baseline |
|---|---|
| `BETA-2, that's the Basic Event Transport.` | commits |
| `We call the Cluster Routing Daemon CRD-3 around here.` | commits |
| `DELTA-9 - Dynamic Ledger Transfer Adapter.` | **misses** |
| `Whenever you see EPSILON-4, read Event Pipeline Sync Layer.` | commits |
| `The team's shorthand for Zenith Query Broker is ZETA-8.` | commits |
| `OMEGA-1? Operational Metrics Gateway.` | **misses** |
| `THETA-5 is what we say instead of Threaded Handoff Engine.` | commits |

Those two became the probe. The probe was fixed **before** any C/L number was read from it.

## The third problem: an example that carries a value cannot teach a wording

`_persist` stored `snapshot["proposed_question"]` under `expression`, so a confirmed case remembered
the question the assistant had proposed — or nothing at all on a teaching turn, where no question is
ever asked. The block offered to the router was therefore a value pair, `ACME-7 = Atlas Control
Mesh`, which says nothing about how a definition is phrased. Asking a model to reuse an
interpretation from that is asking it to generalise from evidence it was not given.

The user's own wording is now what is kept; an assistant-proposed question is explicitly not usable
as a confirmed wording; the rendered example stays advisory
(`tests/test_v127_example_carries_wording.py`). This fix produced the single L hit in the run that
followed — and eleven further repetitions showed it was noise.

## The measurement

Paired arms, identical teaching, one manipulated variable, pre-registered probe, no tuning between
runs. Pooled over **14 repetitions per arm**:

| probe | expected | arm C | arm L |
|---|---|---|---|
| `DELTA-9 - Dynamic Ledger Transfer Adapter.` | commit | 1/14 | 2/14 |
| `OMEGA-1? Operational Metrics Gateway.` | commit | 0/14 | 0/14 |
| `IOTA-7 - my favourite ticket this week.` | no definition | 0/14 | 0/14 |
| `PSI-3? Never heard of it.` | no definition | 0/14 | 0/14 |
| `GAMMA-3 is a nice name, isn't it?` | no definition | 0/14 | 0/14 |

2/14 against 1/14 is indistinguishable from noise. No transfer was observed.

**A correction to my own run.** Teaching **two** confirmed wordings did NOT in fact offer two examples, and the claim is corrected here rather than left standing: `eligible_examples` filters by the newest case's `context_ref`, the model assigned the second teaching a different context (`internal naming conventions` against `project terminology`), so the older example was filtered out and the block carried exactly one line in 3/3 repetitions -- the *inverted* one at that. The result was 0/3 in both arms, but the hypothesis "one example is too little evidence to generalise a form" therefore remains **untested**, not refuted. It does not change the verdict, because the router emits no envelope at all on those wordings in both arms, which is upstream of whether any example is offered.

## Where it stops — located, not guessed

The probe records the protocol's own decision, so perception and the gate can be told apart. On the
headroom wordings the router emits **no `memory_update` envelope at all** (`protocol_unavailable`) in
**both** arms. Perception never proposes anything, so there is nothing for the evidence gate to
accept or refuse. The confirmed-interpretation block does not change what this 12B perceives.

That distinction matters for whoever picks this up: the failure is **not** in the controller, the
evidence gate or the store — those refuse and commit exactly as their tables say. It is upstream, in
what the router proposes.

## Limits of this finding

* n = 14 per cell is small. The honest claim is **"transfer not demonstrated"**, not "transfer is
  impossible". A larger campaign is exactly what E7 would be, and E7 is still budget-blocked.
* Only the definition interpretation was probed. Facts and behaviour were not.
* Whether two confirmed examples would help is still open, for the reason above; testing it needs the
  context filter accounted for, since today a newer interpretation in another context silently
  displaces the older ones from the block.
* Changing the model is outside the authorised scope, so "a bigger model would generalise" was not
  tested and is not claimed.
* Two quality defects surfaced in passing and are recorded rather than repaired here:
  `IOTA-7 - my favourite ticket this week.` was committed as a **personal_fact** in 6/6 traced turns
  — correctly *not* a definition, but the whole raw sentence was stored as the value, twice under the
  subject `user_preferences`; and `We call the Cluster Routing Daemon CRD-3 around here.` was stored
  **inverted**, defining `Cluster Routing Daemon` as `CRD-3`.

## Reproduction

```
python scripts/diag_examples_block.py                 # the manipulated variable reaches the router
python scripts/diag_transfer_ladder.py                # where the baseline has headroom
python scripts/diag_transfer_cl.py 8                  # the paired comparison
python scripts/diag_transfer_cl.py 3 --teach2         # two confirmed examples instead of one
```

Artefacts: `outputs/runs/20260910T19*-*/transfer_*.json`, `outputs/runs/20260910T20*-*/transfer_cl.json`.
Commit `d20a1c7` on `phase90-diagnostic-cycle`. Suite **1289 passed, 1 xfailed** — the scope actually
tested, with no universal absence-of-regression claimed.

## Updated status

| capability | implemented | wired | unit-tested | live-tested | activated |
|---|---|---|---|---|---|
| Controller, state, adapters | YES | YES | YES | YES (`2a3c5e5`) | NO |
| Learning turn C (teach -> commit -> recall) | YES | YES | YES | YES | NO |
| Mode L examples | YES | YES | YES | YES | NO |
| **Transfer (C vs L)** | YES | YES | YES | **YES — and it FAILED** | NO |

The capability the user asked about is measured and negative. That is the result, and it is not
dressed up as a completion.

> **SUPERSEDED BY PART 5.** This verdict came from an instrument that could not measure the
> examples: they never reached the model. The conclusion is withdrawn; the runs stay on record as
> invalid trials.

---

# Part 5 — the block was never delivered, and what happened once it was

Part 4 declared transfer a failure. **That conclusion was drawn from an instrument that could not
measure it, and it is withdrawn.** The independent review
(`reports/codex_review_92e5/REVIEW.md`) found the cause, and its probe reproduces here in one
command:

```
.venv/Scripts/python.exe reports/codex_review_92e5/probe.py
{"C_L_requests_identical": true, "example_in_L_request": false, ...}
{"worker_NameError_propagates": false}
```

`classify_turn` built the CONFIRMED INTERPRETATIONS block and then composed the system message as
`runtime + ROUTE_PROMPT + catalog + active + learned` — without it. **Both arms sent an identical
request.** The 1/14 against 2/14 spread could not have been caused by examples the model never saw,
no limit of the 12B was ever demonstrated, and those fourteen repetitions and their GPU cost stay on
record as invalid trials rather than being quietly deleted.

My instruments missed it twice for one reason worth stating plainly: they all watched the
**producer**. `diag_examples_block.py` spied the argument handed to `start_route`; v127 tested
`_learning_examples_text`. Neither watched what `chat` was actually given. That is the same mistake as
the swallowed `SyntaxError` in Part 4, one layer further out.

## What was fixed, tests first

| # | finding | fix | test |
|---|---|---|---|
| F1 | the block never reached the model | `confirmed` joins the system content | v128 captures the final provider boundary: absent in C, present in L, every other input identical |
| F2 | a code defect in the router **worker** still degraded silently — `merge_route` catches `future.result()` | the "our own defect" rule lives once in `turn_router`, imported by the sensitizer; `enrich_route` holds the same line and finally carries `learning_text` | v128; transport failures still degrade, which is the control |
| F3 | `bool(new_definition)` accepted an inverted definition and could not see a write in another store | `scripts/learning_oracle.py` judges term, meaning, context and **every** write across ledger, assertions and directives, against allowances declared up front | v129 (12), including the identity trap: `upsert_entity` mints `definition:<hash8>` and keeps `<context>::<term>` in the entities table |
| F4a | the prompt said `memory_update` was OPTIONAL and to "omit the field entirely" while the grammar REQUIRED it | the paragraph is derived from the **schema**, so the two cannot disagree | v130 |
| F4b | schema and prompt carried the envelope even with the mode **off** — arm S was silently a new perception contract | `router_schema(catalog, learning=False)` is the default; every existing caller keeps the B0 contract | v130 |

Preparation is now validated by term, meaning and context, and an episode whose teaching landed wrong
is **dropped** rather than counted as a failure of transfer — the pilot dropped 1/1 immediately, and
the cause was my own oracle, not the model.

## The measurement, three builds one commit apart

Six repetitions per arm each. Delivery is proven per turn from the captured payload: **L 30/30, 30/30,
25/25 — C 0/30, 0/30, 0/25.**

| build | `DELTA-9 - Dynamic Ledger Transfer Adapter.` | `OMEGA-1? Operational Metrics Gateway.` | undue definitions on the shape-matched negative (L) |
|---|---|---|---|
| `d752425` — paragraph mid-prompt, original wording | C 0/6 → **L 6/6** | C 0/6 → **L 6/6** | 1 |
| `dcf2e39` — paragraph moved to the end, plus a prior I invented | C 0/6 → L 0/6 | C 0/6 → L 0/6 | 0 |
| `d55f226` — position and wording restored to parity | C 0/5 → **L 4/5** | C 0/5 → L 0/5 | 3 |

**Arm C is the column that does not move: 0/16 pooled on each probe, in every build.** Arm L reaches
10/16 and 6/16 on the same wordings, after the same teaching, with the confirmed example as the only
difference — and on `transfer_dash` the delivered block was the *original taught wording* in 6/6 and
23/25 of turns. Transfer is observed.

## Two things that must be said with it

**It is fragile.** At `dcf2e39` I changed two things at once while reconciling the contract: the
paragraph moved to the end of the prompt, and I added *"most messages teach nothing and null is the
expected answer for them"* — a prior the contract never had and for which I had no evidence. The gain
went from 12/12 to 0/12. One sentence of prompt wording moved this capability from working to absent.
That is arguably the most important number in this report, and it is why the position and the absent
prior are now pinned by a test.

**It costs precision.** On `IOTA-7 - my favourite ticket this week.` — a preference wearing the shape
of a definition — arm L wrote a definition **4 times across the campaigns**, twice inverted (defining
the phrase as `IOTA-7`), where arm C never did once. The example transfers the shape as well as the
meaning. A near-negative is not a formality: without it this would read as a clean win.

## Limits

* Two wordings, repeated; that is not fourteen independent wordings. The gain is demonstrated for
  wordings the baseline misses, in DEV, on this 12B and this configuration.
* `_learning_examples_text` still selects by the **newest** case's context and ignores the request
  text, so a later confirmation displaces the taught one — visible in the campaign, where
  `transfer_qa` saw the DELTA-9 example rather than the ACME-7 one in 4/6 repetitions of the first
  build. The plan's contextual selection is declared, not implemented.
* An example minted from an auto-committed turn feeds back into the block. That is inside the design,
  but it is a loop worth naming.
* Nothing here authorises E7 above budget, a model change, or production activation.

## Reproduction

```
.venv/Scripts/python.exe reports/codex_review_92e5/probe.py     # the two findings, before and after
.venv/Scripts/python.exe -m pytest tests/test_v128_provider_boundary.py tests/test_v129_learning_oracle.py tests/test_v130_router_contract_parity.py
.venv/Scripts/python.exe scripts/diag_transfer_cl.py 6          # the paired campaign
```

Artefacts: `outputs/runs/20260910T212808Z-d752425-5db25a/`, `…T214927Z-dcf2e39-36b42b/`,
`…T221034Z-d55f226-2c34d8/`. Suite **1319 passed, 1 xfailed**.

## Updated status

| capability | implemented | wired | unit-tested | live-tested | activated |
|---|---|---|---|---|---|
| Learning turn C (teach → commit → recall) | YES | YES | YES | YES | NO |
| Mode L examples reaching the model | YES | YES | YES | YES | NO |
| **Transfer (C vs L)** | YES | YES | YES | **YES — observed, fragile, with a precision cost** | NO |
| Contextual selection of examples | NO | — | — | — | NO |

**Activation, 2026-09-11 06:33Z.** On the user's explicit instruction, the live app was restarted at
`97d01ac` with `interactive_learning_mode = confirm` on the REAL base, after a full backup
(`hmgfu.db.backup-pre-learning-20260911-063252`). Verified from the running process, not from the
database row: `GET /api/settings` reports the mode. `adapt` stays off — it is the arm measured to
write a wrong definition on a preference shaped like one, and that cost would land in real memory.
