# Phase 88 — The write side on the production ruler

Date: 2026-09-07. Branch `phase88-write-side-ruler` from `410c778` (Phase 87 closed). Plan and gates committed before code (`ba37838`).

## Origin

The Phase 84 write-side candidate (`fact_mapper_mode=spans`, `fact_mapper_role=chat`, `open_slot_regex_writes=false`) was the last open candidate
without a LongMemEval reading, and the Phase 85 erratum requires one for every write-side change: the ledger lines a write path adds or removes
change the reader's prompt. The harness could not read it: `ingest_session_like_agent` ran the regex ledger per user turn, never the tail's
span extractor.

## 88.1 Harness extension

`ingest_session_like_agent(engine, turns, extractor=None)` applies the span extractor after the regex write of every USER turn when the prod
engine's `fact_mapper_mode` is `spans` — the tail's semantics: regex first, the extractor adds only slots the regex did not write, provenance
linked to the turn's point, `open_slot_regex_writes` honoured; the extractor's calls, seconds and writes are counted per run. Without an extractor
the path is byte-for-byte Phase 81.1's. Test v83.

## 88.2 The reading (reserved items 41–80, production embedder bge-m3, judge v2, k 10, 480 window on both)

| category | W0: 480 window (Phase 87 D1r) | W1: 480 + write-side candidate | paired net [95 % CI] |
|---|---|---|---|
| knowledge-update (32) | 0.625 | 0.625 | 0 [0, 0] |
| multi-session (40) | 0.425 | 0.450 | +1 [−2, +5] |
| single-session-user (24) | 0.458 | 0.500 | +1 [0, +3] |
| temporal-reasoning (40) | 0.125 | 0.125 | 0 |
| single-session-assistant (16) | 0.250 | 0.250 | 0 |

The extractor ran on every user turn — 1,691 calls, 1,196 s (0.71 s per turn; production pays it in the tail, after the reply) — and wrote **3
ledger lines across 152 sessions**. LongMemEval's user turns are long, task-oriented and almost never state a durable first-person fact the regex
missed, so on this reader the candidate is neutral by construction: it does not harm and barely helps.

## Gates and decision (88.3)

G1 met (no category down; knowledge-update and single-session-user net ≥ 0). G2 reported (0.71 s per user turn, tail-side; the pre-reply p50 held
in 84.4). G3 unchanged — a harness-only change: truth core 390/390, write sets v1–v4 identical, the Phase 84 reserved-v7 figures stand. G4 suite 766.
**No default moves: Phase 84's own verdict (v7 coverage 0.592 against 0.60) stands, and this phase adds that adopting the candidate costs nothing on
the reader.** The user's decision on the three documented options — the 480 window, depth 20 on aggregation questions, the write-side candidate —
now has a complete, production-embedder, reserved-item evidence base.

## Closure

Percentages unchanged by the rule: originality ~37 %, efficiency ~80 %, AGI-memory readiness ~50 %. What the phase leaves on record: the LME
harness can read any write-side configuration exactly as the agent runs it; the write-side candidate's value is on the write-side sets (v7 precision
0.947 / coverage 0.592 against production's 0.864 / 0.446), not on LongMemEval, where the user's own facts are rarely stated in plain first person.
