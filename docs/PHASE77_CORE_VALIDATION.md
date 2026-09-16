# Phase 77 — Finish and validate the core

> **Errata 2026-09-07 (Phase 87, Codex review 3).** The LongMemEval production-arm figures in this document were measured with the `nomic-embed-text` embedder (the throwaway engines' config default) while production embeds with `bge-m3` (live settings, 1024-d vectors). Relative comparisons between configurations on the same embedder stand; no absolute figure here describes production. The harness was fixed (`e538fde`) and the reserved read on the production embedder is in `docs/PHASE87_RULER_PRECISION.md`.

Date: 2026-09-06. Branch `phase77-core-validation` from `3df886c` (backup `bk-20260906-0153-orig37-eff80-agi45`). Plan
committed before code (`0ecd561`). Origin: Codex's review of `3df886c`; its four factual points were verified in the code
first — the justification store was written but never read on the answer path; there was no retrieval-mode switch; write
precision on fresh phrasing was 0.948; prospective triggers fired only when a turn arrived. Priorities adopted in Codex's
order; nothing new is added before the core closes.

## 77.1 — A real retrieval-mode switch (measured)

`retrieval_mode` = `fu` (channels + composite score + Fu expansion) | `cosine` (the Phase 74 strong control as product:
vector top-k over the episodic pool, relevance floor on similarity, the same context policy). One entry point
(`retrieve_memory(..., mode=)`), enum-checked setting, bench arm `p2`, truth-bench `--mode`.

| measurement | fu | cosine |
|---|---|---|
| relational Hit@12 (sealed, 60 q) | 0.717 (relational family 0.679) | **P2 0.717** — identical to B2 per family and in context truth |
| truth set (17 q, no-echo) | 17/17 · precision 1.0 (32 grounded items) | 17/17 · precision 1.0 (15 grounded items) |
| context truth at 100k filler (76.1 curve) | 0.767 | 0.700 |

Pre-registered default rule: the cheaper mode wins at parity; the other needs ≥ 0.05 on a sealed primary metric.
Relational Hit@12 is parity; context truth at 100k is +0.067 for `fu` → **`fu` stays the default by the rule**, and
`cosine` is the documented, tested control one setting away. Codex's point #3 is now effected in code. Held-out
25/25 · 6/7 · 13/13 · 28/28, oracles 51/51 · 33/33, suite 551.

## 77.3 — One read path over assertions (measured)

Sealed `scripts/oracles/heldout_m5.json` (18 cases: retraction, cascade, entity, validity, modality, supersession,
precision, restatement) committed before the code and run BEFORE (canonical read path): 17/18 — the miss is the
precision case "My dog Rex is 4 years old" → `pet.dog.name = 4 years old`, found by the probe and left for 77.5.

Change: `render_lines` renders the ACTIVE, SUPPORTED assertions (query-time validity, one row per entity,
`supported()` as the justification gate); every canonical clear or negated value now retires its assertion; canonical
rows written before Phase 72 are backfilled once at construction so nothing that rendered yesterday stops rendering;
`canonical_facts` stays as the projection the provenance helpers read. Honest scope: no product path writes
justifications yet (the slot vocabulary has no derived attributes), so `supported()` passes everything directly
asserted — wired, producer-less, and said so.

After the change m5 read **15/18**: the assertion view exposed two divergences the canonical table had hidden — a
correction without plurality ("my cat is Luna" → "my cat is Sol") left both pet entities active, and the Portuguese
named negation never superseded the old name. One cause: a canonical write that replaces a value never superseded
that value's assertion when it lived on another entity. Fixed at the cause (`AssertionStore.supersede_value`); m5
back to **17/18** with only the sealed precision case failing; m3 13/13 throughout; facts/assertions/slots/echo-free
suites 80/80. Gates on the wired code (`outputs/evidence_77_3_gates.txt`, head b15cd77): held-out m1 25/25 · m2 6/7
(the pre-existing case) · m3 13/13 · m4 28/28 · m5 17/18; frozen oracles contracts 51/51 accepted · delta 33/33
accepted; truth no-echo CONTEXT 17/17 · precision 31/31 = 1.0; write sets v1–v3 unchanged (0.966/0.966 · 0.986/1.000 ·
1.000/1.000); full suite 558 (`outputs/pytest_full_77_4.txt`, after the facts split and the 77.4 gate code).

## 77.5 — Novel phrasing on the write side (measured)

Sealed `scripts/oracles/write_set_v4.json` (84 PT/EN messages of NEW phrasing for every slot family, the v3 miss
classes and the 77.3 probe class) committed before any code (`f4d49f4`) and run once as the before-record:

| set | before 77.5 | after 77.5 |
|---|---|---|
| v4 (sealed, n=84) | **P 0.692 [0.529, 0.839] · C 0.450 [0.310, 0.597]** | **P 1.000 [1.000, 1.000] · C 1.000 [1.000, 1.000]** |
| v1 (n=111) | 0.966 / 0.966 (errata-adjusted 1.000 / 1.000) | identical, same three errata items |
| v2 (n=90) | 0.986 / 1.000 (errata v068 1.000 / 1.000) | identical |
| v3 (n=83) | 1.000 / 1.000 | identical |

The 42 failing items were root-caused into eight classes before any code and each class was fixed at the layer it
lives in (detector forms whose attribute is resolved by the slot schema; sentence modality; value trimming; a store gate
that lets a NAME slot take only a name-shaped value; the open-key and mapper rules for a relative's attribute). No item
is named in code; no setting was added. Held-out after: m1 25/25, m2 6/7 (the same case as in every run since the set
was sealed), m3 13/13, m4 28/28, m5 18/18 — the 77.3 precision leftover ("My dog Rex is 4 years old") now writes
nothing. Evidence: `outputs/evidence_77_5_v4_before.txt`, `outputs/evidence_77_5_write_sets_after.txt`,
`outputs/evidence_77_5_heldout_after.txt`; tests `tests/test_v62_write_paraphrase.py`.

Honest scope: the write set measures the deterministic path (no model mapper, as v1–v3 did). Known limit: a bare
capitalised nationality after "sou" / "I am" still passes the strict name gate, as it did for "eu sou".

## 77.6 — Prospective alarm (built, measured, seen in the browser)

Before: a reminder set for 09:00 fired only when the user's next message arrived. Now `hmgfu/prospective_alarm.py`
runs a daemon ticker (single-flight, like the scheduled full dream) that evaluates the pending TIME triggers against the
host clock every `prospective_tick_s` seconds (default 30; 0 idles it without a restart) and fires what is due: the
trigger is marked fired with no turn (`fired_turn` NULL) and a notification row is written under the same lock.
Delivery is whichever comes first — the next turn renders undelivered notifications as a PROSPECTIVE block, emits
`prospective_fired` and marks them delivered, or the UI polls `GET /api/prospective/notifications` every 20 s, shows a
bell pill in the transcript header and acknowledges them (`POST /api/prospective/notifications/ack`). Condition triggers
need a message and are never fired by the ticker.

Honest correction to the plan's wording: the WebSocket lives per turn (the client closes it at `turn_end`), so an
out-of-turn push has no socket to reach — poll plus next-turn delivery is the mechanism, not a WS push.

| evidence | result |
|---|---|
| `tests/test_v63_prospective_alarm.py` | 6 tests: fires exactly what is due, never twice, never a condition trigger; delivered once by turn or by ack; turn fire wins when the turn arrives first; ticker thread single-flight with an injected clock; setting bounded; both routes through `TestClient` |
| `scripts/bench_prospective_alarm.py` | frozen walk n=200, tick 30 s: fired 200, false fires 0, late fires 0, misses 0, condition triggers untouched; live idle 12 s: 12 ticks, 0 fired, 0 notifications → PASS |
| browser, throwaway clone | ticker fired a seeded due trigger with no turn open; header "1 reminder due" → click → card + ack 200 → pill gone; Settings shows the new "Prospective memory" section |

Settings surfaced (Rule 10): `prospective_enabled` (75.2 had no UI toggle) and `prospective_tick_s`. The Settings row
helpers moved to `web/app/SettingsRows.jsx` at the 300-line frontend ceiling; behaviour unchanged.

## 77.2 — LongMemEval, production arms (measured; a finding, not a gate)

Pre-registered sample: first 20 items of each of the 7 categories (deterministic), arms `base` · `prod` (fu) ·
`prodcos` (cosine), k = 10, nano off, one repetition, paired per item, McNemar per category.

| category | base | prod (fu) | prodcos | prod vs base b / c |
|---|---|---|---|---|
| knowledge-update | 0.700 | 0.300 | 0.400 | 1 / 9 |
| temporal-reasoning | 0.450 | 0.050 | 0.050 | 0 / 8 |
| multi-session | 0.300 | 0.000 | 0.050 | 0 / 6 |
| single-session-user | 0.800 | 0.300 | 0.350 | 1 / 11 |
| single-session-assistant | 0.550 | 0.200 | 0.250 | 0 / 7 |
| single-session-preference | 0.000 | 0.000 | 0.000 | 0 / 0 |
| abstention | 1.000 | 0.950 | 0.950 | 0 / 1 |

**Finding.** The production path reads far below the plain base arm in every answerable category, in both retrieval
modes — and prod ≈ prodcos, so the gap is not fu versus cosine. It is the production CONTEXT POLICY after retrieval:
assistant-source memories are excluded from the injected context (the echo-loop guard), every excerpt is cut to 200
characters (user) or a summary / 160 characters (others), and the budget is 1800 tokens — a policy built for short chat
memories, applied to long LongMemEval turns whose answer usually sits past the cut or in an assistant turn. The base
arm injects ten full turns. `scripts/diag_lme_prod_context.py` attributes each miss deterministically to retrieval or
to the context policy (`outputs/evidence_77_2_diagnosis.txt`):

| category | gold in base ctx | gold in prod RETRIEVED (full text) | gold in prod CTX | retrieved, cut by the policy | gold only in assistant turns |
|---|---|---|---|---|---|
| knowledge-update | 15 | 14 | 8 | 6 | 1 |
| temporal-reasoning | 6 | 5 | 3 | 2 | 1 |
| multi-session | 8 | 8 | 4 | 4 | 9 |
| single-session-user | 17 | 15 | 7 | 8 | 0 |
| single-session-assistant | 10 | 8 | 4 | 4 | 6 |
| single-session-preference | 0 | 0 | 0 | 0 | 0 |

Production retrieval finds the gold about as often as the base cosine scan (parity — the Phase 74 verdict on an external
set); the context policy then loses roughly half of it, and the injected context is about five times shorter than the
base arm's. Where the gold sits only in assistant turns, the assistant-source exclusion alone explains the loss. Changing the policy is a product decision with its own
gates; it is recorded as the next step, not patched inside this phase.

## 77.4 — Claim-level abstention (measured; gate not met; stays OFF)

The answer-side check: the reply's salient words that are neither in the question nor anywhere in the evidence;
gate `claim_gate_enabled` (OFF) with a dev-chosen floor; one corrective re-ask, then an explicit no-record statement.
Measured on the 75.3 split with the same controls (`outputs/evidence_77_4_claim_phase1.txt`):

| signal | floor (dev) | dev F1 | TEST F1 | false abstention KU test | controls false (truth / relational) |
|---|---|---|---|---|---|
| 75.3 cosine (question-side) | 0.62 | 0.667 | 0.579 | 3/31 | 2/17 · 8/60 |
| 75.3b coverage (question-side) | 0.70 | 0.375 | 0.667 | 4/31 | 7/17 · 39/60 |
| **77.4 claim (answer-side)** | 0.10 | 0.316 | **0.708** | 7/31 | **0/17 · 10/60** |

The claim signal is the best of the three and the only one that never abstains on the truth set — and it still fails the
pre-registered gate (test F1 ≥ 0.8, false abstention ≤ 1/77 on the controls). Verdict as pre-registered: abstention is not
achievable at this layer either; the gate stays OFF as a documented, tested control. The signal is bimodal (median 0.0
on abstention items, 1.0 on answerable ones): a word-level check separates paraphrase from wholesale invention, but the
relational controls, whose answers legitimately combine words from several memories, look unsupported to it. The next
layer would be a span or entailment check, not attempted here. Phase 2 (paired reader accuracy base vs gate on TEST)
ran alone after the gate set with `--floor 0.1`: reader on the test items, paired — base abstention 0.958 and
knowledge-update 0.452; with the gate, abstention 0.958 and knowledge-update 0.452 (24 gated items). The gate changes no
verdict: the fixed reader already declines on 23 of 24 abstention items from the production context alone. Inert on
this path; the OFF default is confirmed by both phases (`outputs/evidence_77_4_claim_phase2.txt`).
