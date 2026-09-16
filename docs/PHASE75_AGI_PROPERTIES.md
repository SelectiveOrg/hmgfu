# Phase 75 — AGI properties: procedural, prospective, metamemory, self, outcome-driven

Date: 2026-09-05. Branch `phase75-agi-properties` from `720c435`. Programme "Fu 2" row 75. Plan committed before code
(`000c75a`). Baseline on the branch point: suite 528 · oracles 51/51 · 33/33 · held-out 25/25 · 6/7 · 13/13 · truth 17/17 · 1.0.

Rules of the phase: one property = one step = one commit with its own bench; every step re-runs the oracles, held-out,
truth and the suite; new behaviour sits behind a documented setting and is promoted only by its pre-registered gate;
production DB never touched; what cannot be measured offline is written down as such (BEAM: no offline sample).

## 75.1 — Procedural runbooks (built, measured; gate not met → ships opt-in)

**What it is.** When a session plan finalizes (`done` / `partial` / `failed`), `hmgfu/runbooks.py` derives ONE runbook
point: the task title, the user's own request that produced the plan (in the user's language), the steps in order
with the tools that fulfilled each and the files touched (from the receipts each step consumed, Phase 71), and the
outcome. Runbooks are procedural, not episodic: taxonomy class `skill`, a SPECIAL type (never decayed as an episode,
never clustered into macros), excluded from the memory panel and from user-grounded precision. At turn start, when no
plan is active and the request is not a question about the user, runbooks whose task resembles the request are
offered beside the tool schemas ("RUNBOOKS — proven sequences … propose ITS steps as the plan"). A runbook shown at
proposal time is recorded on the new plan (`runbook_hint`); when that plan finalizes, the runbook's utility moves with
the outcome (followed-and-done → up, failed → down) and a runbook followed to `done` absorbs the request that led to
its reuse (the Phase 56 tool-phrase rule, same cap and novelty threshold) — multilingual self-growth in use.

**Matching.** Floor on cosine(request, runbook task) — a similarity floor, the 74.5 rule (`runbook_match_floor`,
0.62); rank by memory scoring's own relevance definition (0.75 · cosine + 0.25 · literal overlap); at most two shown.

**Visible surface (Rule 10).** Settings `runbooks_enabled` (default OFF) and `runbook_match_floor`; `GET /api/runbooks`;
WS event `runbooks` → `RunbookPill` in the transcript. Tests: `tests/test_v55_runbooks.py` (5).

**Sealed sets, before any run.** `scripts/oracles/runbooks_v1.json` (12 executed plans · 36 paraphrased later
requests, PT/EN · 12 unrelated requests incl. user-fact questions; generator `scripts/runbooks_corpus.py`, sha
a889a09a12af) and `runbooks_v2.json` (same, each plan with its ORIGINAL request — 6 PT, 6 EN; sha 55b1b2521fd5).
Harness `scripts/bench_runbooks.py`. Gate pre-registered in the ROADMAP: Hit@1 ≥ 0.9, PT and EN ≥ 0.8, false
surfacing ≤ 1/12 at the configured floor.

| Run | set | Hit@1 | PT | EN | false surfacing | note |
|---|---|---|---|---|---|---|
| 1 (`2cd66a8`) | v1 | 0.750 | 0.250 | 1.000 | 0/12 | title + steps only; cross-lingual cosine 0.44–0.65 under the floor |
| 2 (`51d8baf`) | v2 | 0.861 | 0.583 | 1.000 | 0/12 | + the user's original request in the task text |
| 3 (rank by relevance) | v2 | **0.889** | 0.667 | 1.000 | **0/12** | floor on cosine, rank 0.75 cos + 0.25 overlap |
| 3 | v1 | 0.750 | 0.250 | 1.000 | 0/12 | no request available — the cross-lingual ceiling |

Floor sweep (v2): 0.50 → 0.89 with 5 false surfacings; 0.55 → 0.89 / 1; 0.60–0.65 → 0.89 / 0; 0.70 → 0.75 / 0.
The remaining misses are three Portuguese paraphrases under the similarity floor and one Portuguese widget request
that prefers the other widget runbook whose original request is Portuguese.

**Verdict.** Gate NOT met (0.889 < 0.9; PT 0.667 < 0.8). As pre-registered, `runbooks_enabled` stays OFF by default:
the feature ships opt-in, fully wired, with its measured recall and zero false surfacing. The mechanism that closes
the cross-lingual gap is the phrase learning on reuse, which a one-shot bench cannot show; a later bench with a
reuse sequence (request → follow → re-request in the other language) is the right test of it.

**Regression gates on the 75.1 code path:** held-out 25/25 · 6/7 · 13/13; oracles 51/51 · 33/33; truth 17/17 · precision 1.0; tool-precision 8/8, hallucinated 0, arg/answer grounded 1.0; say-do 5/6 on the first pass (`plan_restart` re-proposed instead of executing — the prompt on that path is unchanged with the feature OFF; the case is re-run ×3 and reported below); suite 533.

Say-do `plan_restart` ×3 re-run: SAYDO_RESTART_75_1


## 75.2 — Prospective memory: triggers by time or condition (built, measured)

**What it is.** The user asks, in their own words, to be reminded; `hmgfu/prospective.py` detects it deterministically
(PT/EN, no model call) and stores a trigger: kind `time` — a due instant resolved against the turn's LOCAL clock from a
relative span ("in 45 minutes", "daqui a 3 horas", "em 2 dias"), a day word ("tomorrow", "amanhã", "tonight", "next
week", weekdays in both languages) and/or a clock ("às 18h30", "at 3pm"; a clock already past today rolls to tomorrow;
a day without a clock means 09:00) — or kind `condition` — the salient, accent-stripped words of the condition clause
("when Nelson replies", "assim que o Dário me responder"). The cue must open the clause ("remind me", "lembra-me",
"avisa-me", "don't let me forget", …); a WH word after it ("remind me what I said…") is recall, never a trigger; a bare
"remind me to call João" with no time and no condition sets nothing (the model is told nothing and can ask); a cancel
cue cancels the most recent pending trigger.

**Firing.** At turn start, right after the runtime clock is captured: time triggers whose due ≤ now and condition
triggers whose words the current message carries (at least half of them) fire — injected as a PROSPECTIVE block that
tells the model to deliver them now, emitted as `prospective_fired` with a transcript pill, marked `fired` with the
turn as receipt. A trigger never fires on the turn that set it. Setting a trigger emits `prospective_set` and a
short prompt block so the reply confirms it; cancelling emits `prospective_cancelled`.

**Visible surface (Rule 10).** Setting `prospective_enabled`; `GET /api/prospective` (all statuses) and
`POST /api/prospective/{id}/cancel`; `ProspectivePill` (set / due / cancelled). Table `prospective_triggers`
(id, session, kind, due, condition, keywords, text, status, created/fired turn and time, source utterance).
Tests: `tests/test_v56_prospective.py` (6 — detection PT/EN, negatives, due resolution at a frozen clock, firing
never on the setting turn, store lifecycle, the turn hook's blocks and events).

**Sealed set, run once.** `scripts/oracles/heldout_m4.json` (28 utterances: 12 time · 5 condition · 2 cancel · 9
negatives incl. recall questions, future-tense statements, a bare reminder and a question about reminders) committed
at `854dfd9` before the runner existed; runner family `prospective` in `scripts/run_heldout.py --set m4`.

| Family | result |
|---|---|
| time | 12/12 |
| condition | 5/5 |
| cancel | 2/2 |
| negative | 9/9 |

Detect precision 1.0 and recall 1.0 on the sealed set (gate: ≥ 0.95 / ≥ 0.85). Zero false trigger sets on the 12-turn
latency script. Firing with a frozen clock covered by the unit tests. Regression gates on the wired code: held-out m1 25/25 · m2 6/7 · m3 13/13 · m4 28/28; oracles 51/51 · 33/33; truth 17/17 · precision 1.0; suite 539. Gate met; `prospective_enabled` is promoted to ON by default in the follow-up commit (kept out of this one so a running say-do experiment on the previous code stays clean).

**Honest scope.** The detector covers relative spans, day words, weekdays and clocks; dates ("on the 12th", "no dia 3
de Outubro") and recurring reminders ("every Monday") are not parsed — a request using them sets nothing and the
model can ask. The set is 28 utterances written by the same hand as the detector, sealed before running; it
measures the vocabulary the plan named, not the long tail of phrasing.

## 75.3 — Calibrated abstention (measured twice, pre-registered; gate not met; nothing wired)

**Question.** Can the system say "my memory has no record of this" from a retrieval-side signal, calibrated offline,
without guessing? Pre-registered before any number: the 30 LongMemEval abstention items (the asked detail is not in the
sessions) and the 72 knowledge-update items (answerable), split dev/test by the parity of the first hex digit of
md5(question_id); the floor chosen on dev only; reported on test; two must-not-abstain controls (truth set 17 queries
on a live clone, relational set 60 questions); gate test F1 ≥ 0.8 and ≤ 1/77 false abstentions on the controls.
Production retrieval throughout; nano off; the E.2 harness reused for ingestion (`scripts/bench_abstention.py`).

| signal | dev floor | dev F1 | test F1 (P / R) | false abstain, answerable test | controls false (truth / relational) |
|---|---|---|---|---|---|
| similarity — max cosine(question, recalled memory) | 0.62 | 0.667 | 0.579 (0.786 / 0.458) | 3/31 | 2/17 · 8/60 |
| coverage — share of the question's salient words in the recalled context | 0.7 | 0.375 | 0.667 (0.778 / 0.583) | 4/31 | 7/17 · 39/60 |

Evidence distributions overlap (similarity: abstention median 0.62 vs answerable 0.71; coverage: 0.67 vs 1.0 with
abstention items reaching 1.0). **Why:** LongMemEval's abstention questions name things that ARE in the sessions ("which
did I do first, fixing the fence or buying cows from Peter?" — the fence is there); neither signal sees that the asked
detail is missing, and lexical coverage additionally collapses on Portuguese questions over English memories (the
controls). **Verdict:** gate not met by both signals; `abstention_floor` is not introduced, nothing is wired, the LLM leg
is not run (a gate that abstains on 10–46 of 77 answerable controls has nothing worth measuring downstream). BEAM: no
offline sample — not measured, not approximated. What abstention needs is claim-level verification — does the context
STATE the asked attribute/value — the target-bound-claims direction (M5, grounding gate), a later phase.
`hmgfu/abstention.py` (pure functions) and the bench stay as the measured experiment.

## 75.4 — Self-recall (measured; gate met; a degraded-path hole closed)

**What was measured.** Reflections — the agent's own reasoning, stored in the tail as `reflection` nodes
(source=assistant) since Phase 27 — must come back when the same problem recurs and must never enter the answer
context of a question about the user. Sealed `scripts/oracles/selfrecall_v1.json` (10 problems: request + reflection +
2 later paraphrases PT/EN; 6 user-fact questions with their facts), harness `scripts/bench_selfrecall.py` (production
`store_reflection`, production retrieval, `build_llm_context`).

| run | recall on recurrence | in answer context | leaks into user-fact answers |
|---|---|---|---|
| first | 1.000 (20/20) | 0.900 | **5/6** — echo-free applied on 0/6 |
| after the fix | 1.000 | 0.900 | **0/6** — echo-free applied on 6/6 |

**The hole.** `user_fact_question` (the M6 echo-free rule) reads `conversation_act == "question"`, which only the
router sets; the heuristic fallback (`sensitizer.heuristic_extract`) set `intent` from a "?" but never the act. So
whenever the router was degraded, every question-only gate was silently off and assistant/reflection echoes could
leak into answers about the user. Fix at that layer: the fallback classifies the act with the predicate the harness
already trusts (`speech_act.is_interrogative`) — no second phrase list. Gates after the fix: held-out 25/25 · 6/7 ·
13/13 · 28/28, oracles 51/51 · 33/33, truth 17/17 · 1.0, suite 541 passed. Nothing else changed: self-recall was already
there; 75.4 measured it and closed what the measurement exposed.

## 75.5 — Outcome-driven bandit (built at one real decision site; default OFF)

`hmgfu/bandit.py`: bounded Thompson sampling — Beta(α, β) per (site, arm) persisted in `learned_params` (bounded at
α + β ≤ 500 with fading so an arm can be re-learned), `snapshot` for `/api/learning`, `reset`, inert when
`bandit_enabled` is off. Rewards are outcomes the system already proves, never the model's self-assessment.

**The site.** Offer a matched runbook or let the model plan alone (`runbooks.runbooks_for_turn`): the arm chosen at
turn start rides on the plan proposed that turn (`plan["bandit"]`) and is paid when that plan finalizes from its
receipts-verified status (done 1 · partial 0.5 · failed 0). The planned second site — tool order when the top two
candidates are within ε — is not built: the tool schemas reach the model as a set, and no per-turn reward isolates order,
so a bandit there would learn noise. Recorded rather than faked.

**Gate.** Offline convergence met (`tests/test_v57_bandit.py`: with true payoffs 0.8 / 0.3 and seed 75 the last ten of
forty pulls are ≥ 8/10 the better arm; persistence, bound, visibility, reset and the off-switch covered; `test_v55` +1
for the arm-on-plan flow). The live half of the gate (tool 8/8, say-do 6/6 with the bandit ON) is vacuous by
construction — the site fires only when a runbook matches and the live clone holds no runbook — and is therefore not
claimed. **Default stays OFF**: runbooks are opt-in (75.1), and a Beta(1, 1) start skips the runbook about half the
time until twenty to forty plan outcomes have been seen — a real cost for a personal agent that runs a few plans a
week. That is a product decision, written here, not a measurement.

## 75.6 — Fu-R utility G(f) and I_Fu, estimated offline (measured; "unknown" everywhere at n = 60)

`scripts/bench_utility_g.py` (committed before its run): on the sealed relational set with the reader fixed, U = answer
accuracy; each package part removed in turn (its derived copies too): ledger lines, history lines, provenance exclusion,
both, echo-free, Fu expansion. Cheap estimator: the grader's deterministic cited-count per reply.

U (answer accuracy, 60 questions × 1 rep, reader gemma4:12b think=False) is 0.583 for full, no_ledger, no_history, no_provenance, no_echofree, no_expansion and 0.600 for no_both; G(f) = 0.0 for every part with a 95% CI including 0 (ledger [−0.067, 0.067], provenance [−0.05, 0.05], history/echo-free/expansion exactly 0), I_Fu(ledger, provenance) = 0.017 [−0.033, 0.083] — all 'unknown' by the pre-registered rule; the cheap estimator (grader cited-count) correlates 0.633 with U across the 7 variants (n = 7 — weak). Reading: on this corpus the reader answers from the recalled memories alone and none of the deterministic parts changes its accuracy — consistent with the Phase 74 parity verdict; the estimator says 'unknown' where it cannot tell, which is the honest output. 420 reader calls, 463 s.

**What this says.** The estimator works as specified — it prints "unknown" whenever the interval includes zero — and on
this corpus it finds no part of the deterministic package that changes the reader's accuracy. That is the same fact
Phase 74 found from the retrieval side (parity with the strong control), now from the utility side. G and I_Fu are
definitions with a procedure, not results; a corpus where a part carries the answer (relation-only questions, a reader
that cannot bridge on its own) is what would give them a non-zero reading.

## Close

Final code `678ef06`, suite 544. Close gates run ALONE (no concurrent LLM bench): say-do **6/6 · 6/6 · 6/6** (intent_no_action 0, false_exec_claim 0, misattributed 0 in all three) · tool-precision **8/8**, hallucinated 0.00, arg/answer grounded 1.0, unasked effects 0.00 (`outputs/evidence_75_close_gates.txt`, head `678ef06`). Run alone, the plan_restart case is 3/3 — the earlier 4/7 came under concurrent LLM benches (the confound the coverage rule now forbids). Assessment row 75: originality ~37% (unchanged), efficiency ~72%, AGI-memory readiness ~35% → ~45%.
