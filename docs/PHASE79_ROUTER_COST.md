# Phase 79 — Router cost

Date: 2026-09-06. Branch `phase79-router-cost` from `20b0a9b` (Phase 78 closed; backup
`bk-20260906-1022-orig37-eff80-agi47-phase78-closed`). Plan committed before code (`84dab19`).

## Origin

The efficiency target has one unmet clause: at most two provider calls before the reply (today 4.25). The pre-reply
`retrieve` stage costs 2.7–3.2 s of a 5.6 s turn, and it is the turn ROUTER: a grammar-constrained classification on
`gemma4:12b` (2.2–3.1 s in a turn, 1.6 s in isolation) running in parallel with the nano extraction and the embedding.
The router has had its own provider role since 73.2 but still defaults to the chat model; no smaller model had been
measured against it.

## Sealed routing set (79.1)

`scripts/oracles/routing_v1.json`: 84 PT/EN turns across the classes the router decides on; the reference route per turn
recorded ONCE by `gemma4:12b` (`scripts/bench_router_agreement.py --record`, route p50 1578 ms, oracle md5 b0ccb67f08b4),
committed before any candidate. Agreement is measured against that reference on the decision fields (`action_requested`,
`requested_tools`, `conversation_act`, `needs_memory`), with learned routing exemplars fixed to none.

## Lever (a): a smaller router model (79.2) — not achievable with the installed models

| candidate | decision agreement | route p50 |
|---|---|---|
| gemma4:e2b-it-qat | 0.429 | ~1.0 s |
| qwen3.5:2b | 0.190 | ~1.0 s |
| qwen2.5:1.5b-instruct | 0.107 | ~0.5 s |
| phi4-mini | 0.167 | ~0.9 s |
| llama3.2:1b | 0.071 | ~0.5 s |

All far below the pre-registered 0.95: the small models drop `memory_search` on recall, invent `brave_web_search`, mislabel
acts. Recorded; only lever (b) proceeds.

## Lever (b): a deterministic pre-router (79.3)

`hmgfu/pre_router.py` decides, without a model call, the two classes whose reference routes are uniform on the sealed set:
a plain question about the user's own ledger attribute (→ the recall route) and a plain first-person fact statement (→ the
statement route). Built only from detectors that already exist (`speech_act`, `fact_detect`, `slots`, `utterance`);
everything else — a tool named, an effect, a standing rule, an imperative opener, a negation or correction, chatter, world
questions — falls through to the model router. Setting `router_bypass_enabled` (default OFF, Settings → Memory recall);
the extraction carries `route_source` (bypass | model). On the sealed set it claims 14/84 with decision agreement 1.000,
after one refusal rule added in-sample (negation words); the out-of-sample check is the gate set below.

**A production write defect found by the first bypass disagreement and fixed at the detector:** "Isso está errado, o meu
nome não é esse" used to WRITE `identity.name = esse` over the real name (the Portuguese copula form swallowed "não" into the
attribute). A negation ending the attribute now marks the detection negated; PT demonstratives are never values. Write sets
v1–v4 identical after the fix; m5 18/18; `tests/test_v66_pt_negated_copula.py`.

## Gates (79.4)

| gate | result |
|---|---|
| G1 bypass agreement (sealed set) | claimed 14/84, decision 1.000 (in-sample after the negation refusal); coverage limits: "Como me chamo?", a bare "I" |
| G2 with the pre-router ON | say-do 6/6 · 5/6 · 6/6 · 6/6 · 6/6 · 6/6 (the miss on a turn the pre-router does not claim); tool 8/8 ×3; held-out 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles 51/51 · 33/33; truth 17/17 · 1.0 |
| G3 with the pre-router ON | total p50 5.8 · 5.2 · 5.9 s, calls 4.25 · 4.0 · 4.08 — **not met**: the router runs in parallel with the nano since 73.2, so the nano extraction is the critical path |
| 79.6 amendment (pre-registered before its run): `bypass_skips_nano` | claimed turns: **recall p50 1.5 · 1.5 · 1.4 s at 2 calls** (from 4.3–4.6 s at 4), fact 3.2–4.1 s at 3; script-wide p50 5.1 · 5.2 · 5.0 s (clause not met: 8 of 12 script turns are unclaimed classes); say-do 6/6 ×3 and tool 8/8 ×3 with both ON |
| ingest quality on claimed turns | heuristic vs nano: keyword Jaccard 0.27, entity 0.29; the nano's summaries are often fabrications on these turns ("… their name is 'John Doe'"); the heuristic keeps the user's words |

## Decision (79.5)

By the gates, as pre-registered: neither setting is promoted. `router_bypass_enabled` and `bypass_skips_nano` stay OFF,
documented and one click away in Settings → Memory recall. With both on, a plain recall question or a plain fact statement
runs in about 1.5 s with two calls instead of about 4.5 s with four, and is ingested with the user's own words as its summary;
every other class of turn is untouched. No installed small model can replace gemma as the router (agreement 0.07–0.43).
A future pre-registration should state the latency gate per claimed class — a new gate, not a rescue of this one.
