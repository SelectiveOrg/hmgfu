# Phase 86 — Retrieval depth for aggregation questions

> **Errata 2026-09-07 (Phase 87, Codex review 3).** The LongMemEval production-arm figures in this document were measured with the `nomic-embed-text` embedder (the throwaway engines' config default) while production embeds with `bge-m3` (live settings, 1024-d vectors). Relative comparisons between configurations on the same embedder stand; no absolute figure here describes production. The harness was fixed (`e538fde`) and the reserved read on the production embedder is in `docs/PHASE87_RULER_PRECISION.md`.

Date: 2026-09-06/07. Branch `phase86-retrieval-depth` from `261d25b` (Phase 85 closed). Plan and gates committed before code (`5bd6ea6`).

## Origin

Phase 85's candidate C (k 20 for every question) recovered the two multi-session sums and cost one item in each of four other categories: the
cross-session aggregation questions are retrieval-bound, the others are diluted by depth. 19 of the 20 LongMemEval multi-session questions
aggregate ("how many … in total", "how much total", "how many different", "combined").

## Built (86.1)

`hmgfu/query_depth.py`: `is_aggregation(text)` — a deterministic EN/PT cue (how many / how much / total / in total / combined / altogether /
quantos / quantas / quanto / no total / ao todo …), never a first-person statement — and `depth_for(text, settings)` → `retrieval_limit_aggregate`
when the cue fires and the setting is on, else `retrieval_limit`. One rule, two callers: the agent's retrieve and the LongMemEval harness's
production arm. Setting `retrieval_limit_aggregate` (0 = off; Settings row). Tests v82: the cue fires on the count/sum questions, on no fact
statement of the seven write sets, on the routing set only where "how many / quantos" appears.

## Measured (86.2–86.3), alone, paired per item, faithful harness, judge v2

| run | KU | temporal | multi-session | ss-user | ss-assistant | abstention |
|---|---|---|---|---|---|---|
| candidate A ×3 (Phase 85: 480 window + renderer fixes) | 0.750 / 0.650 / 0.650 | 0.300 | 0.000 | 0.600 | 0.400 | 1.000 |
| depth 30 | 0.650 | 0.300 | 0.050 | 0.600 | 0.400 | 1.000 |
| **depth 20 ×3** | 0.7 / 0.65 / 0.7 | 0.3 | **0.1 / 0.1 / 0.05** | 0.6 | 0.4 | 1.0 |

Nine pairings (each depth-20 run against each A run): knowledge-update: A mean 0.683 → depth-20 mean 0.683 (runs [0.7, 0.65, 0.7], mean net +0 items, max |net| 2); temporal-reasoning: A mean 0.3 → depth-20 mean 0.3 (runs [0.3, 0.3, 0.3], mean net +0 items, max |net| 0); multi-session: A mean 0.0 → depth-20 mean 0.083 (runs [0.1, 0.1, 0.05], mean net +1.67 items, max |net| 2); single-session-user: A mean 0.6 → depth-20 mean 0.6 (runs [0.6, 0.6, 0.6], mean net +0 items, max |net| 0); single-session-assistant: A mean 0.4 → depth-20 mean 0.4 (runs [0.4, 0.4, 0.4], mean net +0 items, max |net| 0); abstention: A mean 1.0 → depth-20 mean 1.0 (runs [1.0, 1.0, 1.0], mean net +0 items, max |net| 0).

Latency (G2, alone, same day): 480 + depth 20: p50 5.3 · 5.5 · 5.4 s (p95 10.2 · 8.9 · 7.9 s; calls before the reply 4.31 · 4.28 · 4.5); defaults control p50 5.3 s (p95 9.2 s, 4.39 calls). Aggregation-turn cost: depth 10: retrieve p50 124 ms · max 184 ms · context 3943 chars mean (~986 tokens) · depth 20: retrieve p50 126 ms · max 155 ms · context 5757 chars mean (~1439 tokens).

## Gates and decision (86.4)

G1 multi-session (mean net ≥ +2): not met; other categories within the noise floor: met. G2: held.
G3: truth core 390/390; write sets v1–v4 identical; held-out m1–m5 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles contracts 51/56 (accepted 51/51) · delta 33/35 (accepted 33/33). G4: suite 764; the setting visible.

**Decision by the gates: not all pass (G1 False, G2 True, G3 True) → the default stays 0; depth 20 is the documented one-click option.**
