# Phase 85 — The reader's context on the corrected ruler (Codex A8)

> **Errata 2026-09-07 (Phase 87, Codex review 3).** The LongMemEval production-arm figures in this document were measured with the `nomic-embed-text` embedder (the throwaway engines' config default) while production embeds with `bge-m3` (live settings, 1024-d vectors). Relative comparisons between configurations on the same embedder stand; no absolute figure here describes production. The harness was fixed (`e538fde`) and the reserved read on the production embedder is in `docs/PHASE87_RULER_PRECISION.md`.

Date: 2026-09-06. Branch `phase85-reader-context` from `6fe800d` (Phase 84 closed; backup
`bk-20260906-1553-orig37-eff80-agi50-phase84-closed`). Plan and gates committed before code (`5435766`).

## Origin

On the faithful harness (Phase 81) the production arm read knowledge-update 0.450 at defaults and 0.600 with the 480-char
window against the base scan's 0.700, and the Phase 78 diagnosis attributed the remaining loss to a residual class it called
"budget" without verifying it. Pre-registered gates: G1 knowledge-update ≥ 0.700 with c = 0 paired losses and no other
value-gold category down; G2 pre-reply latency p50 unchanged ×3 vs a same-day control; G3 truth / held-out / oracles / truth
core / write sets unchanged; G4 suite green, every switch visible. The single-session-preference category is struck (its
golds are rubrics, Phase 81.2).

## 85.1 Exact loss diagnosis

`diag_lme_prod_context.py` now ingests like the agent (it still carried the 77.2 defect) and names each retrieved-but-lost
gold; `diag_lme_other_loss.py` reproduces the residual items. Faithful harness, 480 window, k 10:

| category | base ctx | prod retrieved | prod context | lost to the context policy | named cause |
|---|---|---|---|---|---|
| knowledge-update | 15 | 14 | 12 | 2 | timeline head cut ×2 |
| single-session-user | 17 | 15 | 12 | 3 | timeline head cut ×2, stale-excluded ×1 |
| multi-session | 8 | 9 | 6 | 3 | span miss ×2, echo drop ×1 |
| temporal-reasoning | 6 | 5 | 5 | 0 | — |
| single-session-assistant | 9 | 7 | 6 | 1 | span miss ×1 |

**Not one loss was the budget or the renderer's greedy break** (contexts sat at 2.8–4.3k of 7.2k chars). The named cause
of four losses: the gold-bearing user turns were retrieved with a history reason and rendered by the subject-timeline
branch as a 160-character head cut that ignored the query window.

## 85.2 Fixes at their layer

- `render_injection` fills every section under the budget instead of breaking at the first overflowing section (a real
  defect, byte-identical when nothing overflows; tests v80). It did not fire on this set.
- The subject-timeline branch renders the query-matched window when the window is on (tests v81, failing first).

No setting was added: both are corrections.

## 85.4 Candidates, alone, paired per item (faithful harness, judge v2, 20 / category)

| run | KU | temporal | multi-session | ss-user | ss-assistant | abstention |
|---|---|---|---|---|---|---|
| 81.1 run, 480 window (pre-registered baseline; code of 2026-09-06 12:17Z) | 0.600 | 0.250 | 0.100 | 0.450 | 0.400 | 1.000 |
| A0 control: 480 on the Phase 84 close code, no 85.2 | 0.550 | 0.250 | 0.000 | 0.450 | 0.400 | 1.000 |
| **A: 480 + both 85.2 fixes** | **0.750** | **0.300** | 0.000 | **0.600** | 0.400 | 1.000 |
| B: A + token budget 3000 | 0.650 | 0.300 | 0.000 | 0.600 | 0.400 | 1.000 |
| C: B + k 20 | 0.700 | 0.250 | 0.100 | 0.550 | 0.400 | 0.950 |

Paired, A0 → A: knowledge-update b 4 / c 0, single-session-user b 3 / c 0, temporal b 1 / c 0, every other category
0 / 0 — **the 85.2 fixes alone lose nothing and put knowledge-update above the base scan.** B loses two KU items to A
(more budget dilutes); C recovers the two multi-session sums (they were retrieval-bound) but costs one item in four
categories.

Paired, 81.1 run → A0 (the same 480 configuration, only the code changed): multi-session c 2, knowledge-update b 1 / c 2.
**Those two multi-session flips — which A and B also show against the 81.1 baseline — are the Phase 82–84 write-side
changes' doing** (the ledger lines they add or remove change the reader's prompt), not the context policy. Recorded as an
erratum for Phase 83, whose gate set lacked LongMemEval; it joins every write-side gate set from here.

## Reading of G1

Against the pre-registered baseline (the 81.1 run) the "no category down" clause fails on multi-session. That baseline
runs on code whose write side has since changed, so it does not isolate the change under test; the control A0 reproduces
the pre-registered configuration on the code under test, and against it G1 holds (KU 0.750 ≥ 0.700, c = 0 in every
category). The control corrects the comparison, not the bar; both readings are on record. A ×3, G2 latency ×3 with a
same-day control, and G3/G4 are run before any default moves (ROADMAP 85.5).

## 85.5 Gates and decision

A ×3: knowledge-update 0.750 · 0.650 · 0.650 (mean **0.683**), every other category identical across runs — the reader's noise is ±2 items per
20. G2: 480 window p50 5.4 · 5.4 · 5.2 s (p95 11.3 · 9.4 · 9.5 s; calls before the reply 4.28 · 4.5 · 4.64); defaults control p50 5.5 s (p95 10.5 s, 4.56 calls). G3: truth core 390/390; write sets v1–v4 identical; held-out m1–m5 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles contracts 51/56 (accepted 51/51) · delta 33/35 (accepted 33/33). G4: suite 760, no setting added.

**Decision by the gates: the KU clause (≥ 0.700 on the mean) is missed by 0.017; the `excerpt_max_chars` default stays 0.** The two 85.2
corrections stay (defects fixed, inert at the defaults where they do not fire). The 480 window is the documented one-click option with the
strongest evidence it has had. Percentages unchanged: ~37 / ~80 / ~50.
