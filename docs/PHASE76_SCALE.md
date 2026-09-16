# Phase 76 — Scale + consolidation: the recall curve to 100k and dreams as budgeted maintenance

Date: 2026-09-05. Branch `phase76-scale` from the Phase 75 close (`d040704`). Plan committed before code (`a1fbdfd`).

## 76.0 — Baseline, measured before any move

`scripts/bench_scale.py` extended (`--sizes`, `--dim`, `--edges-per-point`, `--profile`; defaults reproduce Phase 30.5).

| points | (a) dim 64, no edges — Phase 30.5 reproduction, p95 ms | (b) dim 1024 (bge-m3), 4 edges/point, p95 ms |
|---|---|---|
| 500 | 11 | 158 |
| 1k | 15 | 198 |
| 2.5k | 30 | 379 |
| 5k | 56 | **643** |
| 10k | 111 | 1,248 |
| 20k | 247 | 2,499 |
| 50k | 613 (Phase 30: 575) | 6,477 |
| 100k | 1,311 | 12,746 |

(a) is unchanged since Phase 30 — retrieval cost per point did not grow with Phases 47–75 when no edges exist. (b) is
the real picture: with bge-m3's 1024 dimensions the 500 ms budget is crossed at ~5,000 points (the live database holds
1,741 today). Profile at 100k: `active_points()` 5 ms · **raw cosine over all points 11,151 ms** · semantic top-60
11,430 ms — the pure-Python cosine scan is the cost (~110 µs per pair); channels and the per-edge path-κ are noise
beside it. A second scale fact, read from `ingest.py`: the duplicate check and the relation-candidate step each scan
all active points per ingest — O(n) per message, O(n²) to fill a graph — so at 100k every ingest costs two full scans.

## 76.2 — One measured move: a vectorised scan (numpy, optional)

Chosen by the profile, not by preference. `hmgfu/vecindex.py`: `scores` / `top_k` / `best` with the same ranking as
`fu_math.cosine` point by point, as one float32 matrix product; numpy is an **optional dependency** (import-guarded;
README install line; `HMGFU_VECTOR_INDEX=0` forces the pure path as a documented A/B switch); without it the old path
runs unchanged. The four O(n) scans go through it: retrieval's semantic channel, ingest's duplicate check, hex
assignment, relation candidates. The store records every written or deleted point id (`graph.dirty`) and bumps
`graph.version`; the index applies the dirty ids incrementally (append/overwrite rows) and rebuilds fully only past 25%
dirty.

**Two defects the measurement caught in the first version, fixed at their cause.** (1) Equivalence: B0/B1/B2 reproduced
exactly but F read 0.700 instead of 0.717 with identical graphs (156 points · 542 edges · 8 macros) — the sealed corpus
has repeated identical filler lines, hence identical embeddings and EXACT ties at the top-60 boundary, and
`argpartition` chose different tied members than Python's stable `sorted`; fixed with a stable argsort (ties resolve by
input order, as before), and a latent shortcut that returned scores in matrix order instead of the caller's order was
removed. (2) The first index rebuilt the whole matrix on every write — 2.7 s per query at 100k in the bench, once per
turn in production — fixed by the incremental maintenance above. Float32 rounding (~1e-7) can still reorder two
distinct embeddings closer than that; measured, documented, not hidden.

Re-measurement (equivalence, scale curve, gates, suite): 

| points | pre-index p50 / p95 ms | vector scan p50 / p95 ms | first query after the bulk writes (index sync) |
|---|---|---|---|
| 500 | 149 / 158 | 109 / 128 | 97 ms |
| 1k | 193 / 198 | 89 / 99 | 108 ms |
| 5k | 640 / 643 | 80 / 94 | 193 ms |
| 10k | 1,227 / 1,248 | 90 / 98 | 370 ms |
| 20k | 2,491 / 2,499 | 150 / 437 | 757 ms |
| 50k | 6,301 / 6,477 | 214 / 753 | 2,070 ms |
| 100k | 11,699 / 12,746 | **393–411 / 1,406–2,307** | 3,042–4,549 ms |

Per-channel profile at 100k, steady state: active_points 7 · class filter 48 · semantic top-60 (vector) 153 · entity
159 · goal 8 · recent 16 · dense 46 ms ≈ the p50; the pure scan it replaced: 12,143 ms. The p95 is not a channel: it
is the process holding 100k points as Python objects (~2.4 GB of floats) beside the 400 MB matrix. Equivalence after
the fixes: B0/B1/B2 0.717, **F 0.717** with the same per-family numbers as 74.8b; truth 17/17 · 1.0; held-out 25/25 ·
6/7 · 13/13 · 28/28; oracles 51/51 · 33/33; suite 548.

**76.2 closes** with the one move the plan allowed: the p50 half of the gate is met at 100k (393 ms), the p95 half is
not (1.4–2.3 s) and is written down as such. Follow-ups on record, not done here: an inverted entity index (159 → ~5
ms) and a columnar embedding store (the p95's real cause) — the latter is a store redesign, a phase of its own.
The production graph today holds 1,741 points (p95 ~100 ms either way); the move matters from ~5k on.

## 76.3 — Dreams as budgeted Fu-R maintenance (built; ablation running)

The dream loop keeps its seven stages and gains `DreamBudget` (seconds · model calls from the Phase 73 ledger ·
`region_only`) and a region — points written or accessed since the last dream report plus their strong neighbours —
so the proposing stages (macros, super-macros, wormholes, contradictions, rebalance, insights) each stop at the budget
and work the touched frontier first; decay and promotion (derived state) always run; the report summary records
budget, region size, time, calls and what the budget cut, with no change to the stored row. Settings `dream_budget_s`
(0 = unbudgeted, today's behaviour) and `dream_region_only` (False) — promoted only by the ablation.
`scripts/bench_dream_ablation.py`: dreams OFF vs ON (one production `engine.dream()`, nano off) on the relational F
engine and the truth clone — recall (Hit@12 / truth), context truth, and context TOKENS per question, paired; then the
same with a 30 s region-only budget. Decision rule, pre-registered: default path only if recall is unchanged (paired CI
including 0) AND tokens per question fall by a reported x%. Result: relational (60 q): Hit@12 OFF 0.717 → ON **0.683** (paired ON−OFF CI [−0.083, 0.0]), context truth 0.867 → 0.850, tokens/question 395.6 → 396.9 (**+0.3%**), macro lines in the contexts 20 → 32; truth (17 q, live clone): 17/17 → 17/17, tokens 271.5 → 270.2 (**−0.5%**), macro lines 0 → 2. Budgeted arm (30 s, region only): identical recall; the budget is recorded in the report — relational 2.2 s / 2 calls over 156 pts, truth 17.2 s / 1 call over a 94-point region. Dream contents: 6 macros + 1 wormhole (relational), 6 macros + 1 promotion + 10 rebalances + hygiene (truth). **Verdict: off the default path** — `full_dream_every_n_turns` defaults to 0; manual and API dreams, and the budget/region machinery, remain.


## 76.1 — Quality at scale (in progress)

`scripts/haystack_corpus.py` (deterministic filler, vocabulary disjoint from the sealed corpus; seed 76, first 1k lines
sha acaa6594ce78) and `scripts/bench_relational_scale.py`: one database — the 159 corpus messages through the real path
at their observed time, 100k filler lines as plain points with real bge-m3 embeddings (ingest is O(n) per message, so
the haystack cannot go through ingest at 100k; the filler is retrieval noise, not knowledge) — evaluated at 0 · 1k ·
10k · 100k filler by masking active points (the 74.5 ablation pattern), B2 vs F Hit@12 with paired CI and F's retrieval
latency per size. Gate: F ≥ B2 − 0.05 at every size; F(100k) ≥ F(159) − 0.10.

**Measured (100k filler seeded in 5,012 s, alone; evaluation on the full database):** filler 0 → B2 0.717 · F 0.717; 1k → 0.633 · 0.650 (CI [−0.033, 0.067]); 10k → 0.633 · 0.633 (CI [−0.05, 0.05]); **100k → B2 0.633 · F 0.617 (CI [−0.05, 0.0])**; relational family 0.643 in both arms at every size; context truth F 0.867 / 0.80 / 0.78 / 0.77 vs B2 0.85 / 0.72 / 0.72 / 0.70; F retrieval p50 116 / 74 / 80 / 718 ms (p95 at 100k 8.5 s incl. the index build on a real ingested graph). **Gate MET, marginally: F ≥ B2 − 0.05 at every size (100k: 0.617 ≥ 0.583) and F(100k) 0.617 = F(159) − 0.10 exactly.** The haystack costs both arms 0.08–0.10 absolute, almost all of it in the FIRST 1k noise lines (temporal questions) and flat from 1k to 100k — the retrieval-at-scale confound E.2 could not measure, now a number; the relational family is untouched by scale.

## Close

Final code on `phase76-scale`; suite 549; every prior gate identical (held-out 25/25 · 6/7 · 13/13 · 28/28, oracles 51/51 · 33/33, truth 17/17 · 1.0). Assessment row 76: efficiency ~72% → ~80% by the measured curve; originality and readiness unchanged.
