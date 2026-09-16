# Phase 84 — The structural write side

Date: 2026-09-06. Branch `phase84-write-structural` from `ab9519c` (Phase 83 closed; backup
`bk-20260906-1437-orig37-eff80-agi50-phase83-closed`). Plan and gates committed before code (`bc3dede`).

## Origin

Two reserved sets (v5, v6) had shown the deterministic write side's ceiling (precision ~0.73, coverage ~0.36–0.46 on unseen
first-person messages) and that mould tables do not carry from one set to the next (Phase 83, G1 not met). Planning found
a harness fact: production BINDS a model mapper (`agent.py`: `registry_mapper`, nano role) that runs pre-reply on every
unresolved declarative message, while the write-set benches measured the regex-only path. Pre-registered gates: G1 on a
reserved v7 in the production configuration — precision ≥ 0.85 and coverage ≥ 0.60; G2 pre-reply latency p50 unchanged;
G3 held-out / oracles / truth core / v1–v4 unchanged; G4 suite green, every switch visible.

## 84.1 The production write side as it is

`run_write_set.py --mapper` binds the same mapper production binds; every fact change now names its path (`regex` |
`mapper` | `spans`). Result: **production equals the regex-only figure** — the nano mapper adds 0 writes on v1–v5 and one
right / two wrong on v6. Probed directly, its raw outputs are hallucinations ("I drive a Nissan Navara" → `pet.name: Rex`)
that the grounding guards catch. Production has paid a pre-reply nano call for nothing.

## 84.2 Open-slot regex writes gated

Setting `open_slot_regex_writes` (default on = today; Settings toggle; bench `--open-slots off`). On DEV: v6 precision
0.743 → 0.897 with coverage unchanged; v5 0.976 / 0.985 → 0.980 / 0.980.

## 84.3 The span-extractor contract

The chat model (gemma4:12b) under the old single-slot contract answers `none` on almost everything; the contract, not the
model, made the mapper inert. Amended (Rule 7): the model lists every first-person fact as `{attribute in the user's own
words, value verbatim}` (`hmgfu/fact_spans.py`) and the deterministic side does the rest — slot from the closed vocabulary,
value grounded in the text, `value_gate` for predicates and hedges, third-party possessors and third-party SENTENCES dropped,
closed slots only, the regex's writes win, cardinality, modality. DEV (open slots off):

| configuration | v6 P / C | v5 P / C |
|---|---|---|
| regex-only | 0.897 / 0.364 | 0.980 / 0.980 |
| spans, nano (qwen2.5:1.5b) | 0.627 / 0.682 (78 false writes) | 0.777 / 0.980 (53 false writes) — **dropped** |
| spans, chat (gemma4:12b), first run | 0.885 / 0.537 | 0.971 / 0.980 |
| spans, chat, after 7 deterministic-side fixes | **0.914 / 0.547** | **0.980 / 0.980** |

The chat model's false writes were read one by one; seven were deterministic-side gaps (article in the value, a URL taken
as a car, an origin phrase as the home city, a proper name as a job → employer, "o nome do meu gato" as the user's name, a
second pet overwriting the first, a PT past cue) and were fixed there with tests (v79).

## 84.4 Where the call lives

The extractor runs in the turn TAIL (`turn_tail`, after the reply, provenance linked); `fact_mapper_mode=spans` also turns
the legacy pre-reply mapper off. G2 measured alone, same day: spans p50 **5.7 · 5.8 · 5.7 s**, calls before the reply
4.19–4.33; defaults control **5.7 s**, 4.31 — **G2 holds**. Cost: p95 10.4–11.1 s vs 9.6 s, max 14–20 s vs 10 s — the tail's
chat call can overlap the next turn's pre-reply calls on one GPU.

## 84.5 The reserved v7, run once

| configuration on v7 (300, sealed `0928fbf`) | precision | coverage |
|---|---|---|
| regex-only (today without the mapper) | 0.862 [0.787, 0.925] | 0.441 [0.367, 0.513] |
| production today (fallback nano mapper, open slots on) | 0.864 [0.789, 0.925] | 0.446 [0.374, 0.517] |
| **candidate** (spans/chat in the tail, open slots off) | **0.947 [0.904, 0.982]** | **0.592 [0.518, 0.662]** |

**G1: precision met; coverage 0.592 against the 0.60 bar — not met, by 0.008.** The interval covers the bar, the point
estimate does not, and the pre-registration reads the point estimate. **By the rule the defaults do not move.** The
candidate is the documented one-click option (three Settings rows: `fact_mapper_mode`, `fact_mapper_role`,
`open_slot_regex_writes`). On unseen messages it reads +0.08 precision and +0.15 coverage over production; the regex path
is now the larger source of false writes (2 of 7), and 84 misses remain across every family.

## Closure (84.6)

G3 truth core 390/390 with 0 undue changes; held-out m1–m5 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles contracts 51/56 (accepted 51/51) · delta 33/35 (accepted 33/33); v1–v4 unchanged.
G4 suite green (one test updated to read the three fields of a change record, which now also carries `path`). Percentages:
by the pre-registration nothing moves by default — originality ~37 %, efficiency ~80 %, AGI-memory readiness ~50 %. What
the phase leaves on record: the structural write side exists, is measured on a reserved set, and is one honest decision
away from the default; the pre-reply nano mapper that production runs today is inert and costs a call.
