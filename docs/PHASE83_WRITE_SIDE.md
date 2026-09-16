# Phase 83 — The write side on unseen messages

Date: 2026-09-06. Branch `phase83-write-side` from `237eee0` (Phase 82 closed; backup
`bk-20260906-1342-orig37-eff80-agi50-phase82-closed`). Plan and gates committed before code (`81c0916`).

## Origin

The reserved `write_set_v5` (Phase 81.4) read precision 0.727 / coverage 0.458 on 300 unseen PT/EN messages, against
0.97–1.00 on the four sets the write side had been fitted on. Five failure families were on record. Discipline: v5 became a
regression set (its misses the cases to fix), and the phase was to be MEASURED once on a new reserved set `write_set_v6`
with pre-registered gates — **G1 precision ≥ 0.90 and coverage ≥ 0.75**, G2 v1–v4 unchanged, G3 held-out / oracles / truth
core unchanged, G4 suite green, no setting added, `fact_detect.py` under 400 lines.

## Built (83.1–83.5, every case failing-test-first)

| step | change | tests |
|---|---|---|
| 83.1 predicates are not values | `hmgfu/value_gate.py`: preposition/adverbial heads, determiner + pronoun/ordinal, state adjectives alone or before a tail, PT infinitive phrases; hedges ("maybe …, or maybe …"); third-party possessors ("my neighbour's dog") | v75 (16 negatives) |
| 83.2 value boundary | articles before any token, trailing adverbs/idioms, PT locative tails, single-token trailing dot, initial alias | v75 (10 cases) |
| 83.3 unseen moulds | `hmgfu/fact_moulds.py` holds ALL mould tables (the 62–77.5 tables moved out of `fact_detect`, which stays the algorithm) plus introductions, aliases, relocation/home frames, job/company frames, birthdays, preference frames, value-inferred slots, species frames, appositions, colon lists, topic prefixes; modality idioms fixed at `utterance.py` | v76 (87 cases) |
| 83.4 sequences | relocation chains across sentences and value chains in one sentence write only the LAST value | v77 |
| 83.5 retirements | we-forms, named-value retirements (company, alias), negated EN copula, "n't" visible to the negation window | v77 |

Regression while building: v1–v4 identical throughout (0.966 / 0.986 / 1.000 / 1.000); v5 0.727 / 0.458 → **0.976 / 0.985**.

## Measured (83.6): the reserved v6, run ONCE

| set | n | precision | coverage |
|---|---|---|---|
| v5 (regression, after the fixes) | 300 | 0.976 | 0.985 |
| **v6 reserved** (sealed `89dfa7f`, `outputs/evidence_83_6_write_set_v6.txt`) | 300 | **0.743 [0.650, 0.829]** | **0.364 [0.299, 0.431]** |
| v6 en / pt | 150 / 150 | 0.727 / 0.760 | 0.374 / 0.355 |

**G1 not met.** The second reserved set reads the same ceiling as the first: coverage 0.36 (v5: 0.46), precision 0.74
(v5: 0.73). The v5-family fixes were in-sample for v6 too.

Failure anatomy (nothing patched against v6):
- **False writes (27):** 17 are open-slot predicates minted by the generic "my X is Y" mould (`open.guess: Manica`,
  `open.advice: patience`, `open.plano`, `open.schedule`, `open.club: Benfica`, `open.cerveja: Laurentina`); 3 are modality
  frames ("in the game I'm building, my name is Kevin"; "the sign reads: my name is Lídia"); 7 are predicate values through
  typed slots ("my name is comum", "my birthday is coming up") or an imperative ("call my sister Carla").
- **Misses (137):** every slot family has 5–18 unseen phrasings — "you can put me down as X", "I answer to X", "X is where
  I hang my hat", "I'm a pharmacist by trade", "I clock in at EDM", "I blow out candles on 14 March", "you'll always find me
  in lilac", "pour me a ginger tea any day", "everything I ship is written in Ruby", "say hi to Bolinha, my dog", "dad's
  name is Gil", "I drive a Nissan Navara", "I'm on Africa/Valencia time", "Occupation: baker", "Favourite colour: charcoal".

## What the two reserved sets establish

Deterministic sentence moulds do not generalise to unseen phrasing: every new set exposes as many new moulds as the last one
closed. The honest write-side figures on unseen first-person messages are **precision ~0.73–0.74, coverage ~0.36–0.46**.
The lever is structural, not another mould table:

1. **Open-slot regex writes are the systematic precision leak.** Precision on v6 would read 0.886 without them — a
   hypothesis to pre-register for v7, not a change measured on v6.
2. **Coverage needs a model-backed grounded mapper** (`slots.map_to_slot` exists: constrained decoding over the closed slot
   schema, value must be literally in the text), measured against a reserved set with the same discipline — Phase 84.

## Gates and closure (83.7)

G2 v1–v4 unchanged; G3 truth core 390/390 with 0 undue changes (`outputs/evidence_83_7_truth_core.txt`), held-out m1–m5 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles contracts 51/56 (accepted 51/51) · delta 33/35 (accepted 33/33); G4 suite 744 passed, no setting added, `fact_detect.py` 386 lines. By the pre-registration
the phase promotes nothing and re-reads nothing upward: percentages stay ~37 / ~80 / ~50. The write-side line of the
assessment now carries two reserved measurements instead of one in-sample figure.
