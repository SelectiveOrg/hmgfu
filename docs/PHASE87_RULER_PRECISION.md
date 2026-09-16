# Phase 87 — Ruler precision: the production embedder, reserved items, paired intervals

Date: 2026-09-07. Branch `phase87-ruler-precision` from `8203015` (Phase 86 closed). Plan and gates committed before code
(`eff9f2e`), amended after Codex's third review (`e538fde`, Rule 7).

## Origin

Phases 83–86 each produced a measured gain and each missed its pre-registered bar narrowly, on 20-item categories whose
reader noise is ±2 items. The plan was a finer read (40 items). Codex's third review, verified in code, changed the plan
in four places: (1) **the LongMemEval harness embedded with nomic while production embeds with bge-m3** — the live
settings table persists `embed_model = bge-m3` and the live vectors are 1024-d, while every throwaway engine started from
the config default; the bench's own WARN said so on every run and its header printed "bge-m3" as fixed text. Every
absolute LME figure since 77.2 is superseded; relative comparisons on the same embedder stand. (2) Timeouts and empty
replies were folded into "wrong". (3) Items 1–40 include the 20 used to choose the candidates. (4) Supersession closed the
old validity at the recording time even when the new statement dated the change.

## Fixed at their layer (`e538fde`)

- `_bench_paths.production_model_settings()` reads the live settings read-only; `_make_engine` applies `embed_model` /
  `embed_provider` to every throwaway engine; the header prints the EFFECTIVE embedder. Clone-based benches (latency,
  truth, router agreement) always inherited bge-m3.
- `answer()` records the reader's failure kind per item; counted as wrong (conservative) and reported apart; the pairing
  tool gained `--exclude-errors` and a bootstrap 95 % CI on the paired net.
- `AssertionStore.assert_`: `valid_to` of the superseded value = the new value's `valid_from` when given (test in v72).
- The decision reads on a RESERVED read: items 41–80 of each category (abstention has 30 and is dropped from it).

## 87.1r The reserved read (bge-m3, judge v2, k 10; items 41–80; 152 items)

| configuration | knowledge-update (32) | multi-session (40) | ss-user (24) | temporal (40) | ss-assistant (16) |
|---|---|---|---|---|---|
| D0r defaults | 0.312 | 0.075 | 0.292 | 0.025 | 0.188 |
| **D1r `excerpt_max_chars=480`** (vs D0r) | **0.625** (+10 [+5, +15]) | **0.425** (+14 [+8, +21]) | 0.458 (+4 [+1, +8]) | 0.125 (+4 [+1, +8]) | 0.250 (+1 [−2, +5]) |
| **D2r 480 + `retrieval_limit_aggregate=20`** (vs D1r) | 0.594 (−1 [−3, 0]) | **0.500** (+3 [0, +7]) | = | = | = |

Reader failures: 0 / 1 / 1 of 152 (counted wrong). On the production embedder and on items never used to choose
anything, the 480 window gains in every category and the interval excludes zero in four of five; depth 20 adds a small
multi-session gain at no cost elsewhere.

## Reading of the gates

G1a: the paired clause (no category net ≤ −3) is met; the absolute clause (knowledge-update ≥ 0.700) is not — 0.625 on a
reserved set whose defaults read 0.312, a bar calibrated on the nomic dev read where the base scan gave 0.700. G1b
(multi-session net ≥ +3, no other ≤ −3): met by the letter, at the bar, with an interval touching zero. **By the letter
of the pre-registration neither default moves on Claude's authority.** The recommendation — `excerpt_max_chars = 480`,
optionally `retrieval_limit_aggregate = 20` — is recorded with this evidence for the user's decision; latency was held for
both (85.5, 86.3, same code).

## 87.1 The dev read (items 1–40, bge-m3) — for the record

D0 → D1: abstention 0.967 → 0.967 (net +0 [+0, +0]); knowledge-update 0.250 → 0.575 (net +13 [+7, +20]); multi-session 0.025 → 0.200 (net +7 [+3, +12]); single-session-assistant 0.175 → 0.475 (net +12 [+7, +18]); single-session-user 0.350 → 0.500 (net +6 [+0, +12]); temporal-reasoning 0.100 → 0.350 (net +10 [+4, +16]). D1 → D2: abstention 0.967 → 0.967 (net +0 [+0, +0]); knowledge-update 0.575 → 0.575 (net +0 [+0, +0]); multi-session 0.200 → 0.250 (net +2 [-2, +6]); single-session-assistant 0.475 → 0.475 (net +0 [+0, +0]); single-session-user 0.500 → 0.500 (net +0 [+0, +0]); temporal-reasoning 0.350 → 0.325 (net -1 [-3, +0]). It does not decide.

## Closure

Percentages: nothing moves by the rule — originality ~37 %, efficiency ~80 %, AGI-memory readiness ~50 %. What the phase
leaves on record: the ruler now measures the production embedder, reports reader failures apart and carries intervals;
the reader's context window is the first change with an unambiguous reserved gain; the write side of Phase 84 still
awaits its own LME reading (the extractor per ingested turn is a harness extension).
