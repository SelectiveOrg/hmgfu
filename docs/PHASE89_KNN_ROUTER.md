# Phase 89 — A nearest-exemplar router with a model fallback

Date: 2026-09-07. Branch `phase89-knn-router` from `1c1b4b4` (Phase 88 closed). Plan and gates committed before code.
Accountability format per the Codex "ciclo curto" proposal §6 (adopted for closes on 2026-09-07); complexity balance per the user's
simplicity constraint of the same day.

## 1. The question this phase answers

Can the model router call (gemma4:12b, ~1.5–1.8 s per turn, one of the 4.3 model calls before the reply) be removed on the turns whose
route the turn's own embedding already decides — the k nearest labelled exemplars agreeing and close — with the model as the fallback,
at no cost to decision correctness and with a visible latency gain?

## 2. The single change

`hmgfu/knn_router.py` (exemplar base from the two sealed sets, embeddings cached per embedder, k-agreement + minimum similarity, never a
directive turn; `make_knn_pre_router` bound through the 79.3 hook), settings `knn_router_enabled` (OFF) / `knn_router_k` / `knn_router_min_sim`
with Settings rows; bench `--knn` / `--knn-combined`. Deviation from the plan, stated: production's learned `route_exemplars` were NOT added
to the base (the two sealed sets only), so the base is fixed and auditable. A second, unplanned change fell out of the root-cause work before
G2: `hmgfu/embed_memo.py` shares the turn's in-flight embedding across threads (retrieval's worker embed || the router), replacing the 89.1
one-entry memo that could not; it stays regardless of the router (it removes a duplicate provider call whenever two callers embed the same
text in the same turn).

## 3. Cases run and infrastructure errors

| step | set | n | infra errors |
|---|---|---|---|
| 89.2 DEV kNN alone, LOO, k 3 | decision_v1 / routing_v1 | 100 / 84 × min_sim 0.80, 0.85, 0.90 | 0 |
| 89.2 DEV diagnostic grid (LOO) | the 184-exemplar base | k 1–3 × min_sim 0.60–0.85 | 0 |
| 89.2 RESERVED, once each | decision_v2 (sealed `51b9b23`, md5 559e484a93ac, 0 texts shared with the base) | 100 model · 100 kNN+model | 0 |
| 89.3 latency ×3 + same-day control | sealed 12-turn script × 3 reps | 36 × 4 runs | 0 |
| 89.3 G3 / G4 | truth 17, say-do ×3, tool ×3, held-out m1–m5, oracles, truth core, write sets v1–v5, suite | — | see §4 |

## 4. Results, paired, with two complete examples

**Why so few claims (DEV diagnostic, `outputs/evidence_89_2_knn_neighbourhood.txt`).** With bge-m3 the leave-one-out nearest-neighbour
similarity over the 184 exemplars is p50 0.733 / p75 0.812 / p90 0.896, and the nearest neighbour carries the same full decision only
119/184 times: the embedding tracks the TOPIC ("my favourite colour is amber" sits next to "what is my favourite colour?"), not the routing
decision. The grid: k 1 @ 0.80 claims 53 at 0.887 correct; k 2 @ 0.75 claims 28 at 0.964; k 2 @ 0.80 13/13; k 3 @ 0.70 26 at 0.962.
DEV choice for the one reserved run: **k 2, min_sim 0.75**.

**G1 — reserved `decision_v2`, once (`outputs/evidence_89_2_reserved_*.txt`, `_pair.txt`).**

| arm | correct | kNN claims |
|---|---|---|
| model router (gemma4:12b) | 92/100 = 0.920 | — |
| kNN (k 2, 0.75) + model fallback | 94/100 = 0.940 | 16/100 claimed, **16/16 correct** (the model was right on 15 of those 16) |

Paired net **+2 [95 % CI +0, +5]** (b 2, c 0; flips e006 "Onde está o meu carro, pelo link que te dei?" and e099 "Can you forget things on
request?", both model-router misses that the fallback path got right on the second run — the kNN did not claim either, so the +2 is model
variance, not the kNN). **G1 met.** Example claimed turn: e032 "Corre o bash e mostra a pasta actual." → nearest exemplars in the "run bash"
family, decision `action_requested, tools [bash], instruction` — correct, no model call. Example unclaimed turn: e015 "My lucky number is 11."
— nearest neighbours are recall questions about slots (topic match), disagreement → the model router runs.

**G2 — latency ×3 + same-day control (`outputs/evidence_89_3_latency_*.txt`, `_pair.txt`).**

| run | overall p50 | control same day | Δ | claimed (proxy) | claimed p50 vs control on the same turns |
|---|---|---|---|---|---|
| 1 | 5.6 s | 5.7 s | −0.2 | 8/36 | 4.2 vs 7.3 s |
| 2 | 5.6 s | 5.7 s | −0.2 | 8/36 | 5.1 vs 7.3 s |
| 3 | 6.0 s | 5.7 s | **+0.2** | 9/36 | 6.0 vs 6.6 s |

Embed calls 1.00 per turn in every run (the shared in-flight embedding held). On the 25 claimed turns p50 4.9 s vs 6.6 s (−1.6 s): the
claimed-turn half of G2 is met. The overall p50 is unchanged within the run-to-run spread (±0.2 s) and one run is higher: **the pre-registered
"never higher overall" is NOT met; G2 NOT MET.** Mechanism: with ~17 % of turns claimed and ~1.6 s saved on each, the expected mean saving is
~0.3 s, and on the unclaimed 83 % the model router now starts only after the embedding lands (the kNN must wait for it), costing ~0.2 s —
the two cancel at the median. No extra latency reading with the route source exposed was run: it would sharpen which turns were claimed, not
the overall verdict (simplicity constraint, point 4).

**G3 / G4 (kNN ON where the runner has a settings hook; `outputs/evidence_89_3_{truth,saydo,tool,heldout,suite}.txt`).** Truth 17/17
(precision 0.778 / current 0.722, unchanged); say-do 6/6, 6/6, **4/6** — the pre-registered "6/6 ×3" not met strictly; the two failing turns of
rep 3 (anaphora turn 2, plan_restart) would NOT have been claimed by the kNN (offline claim check, top-2 cosine 0.619 / 0.681 < 0.75:
`outputs/evidence_89_3_saydo_claim_check.txt`), so the model router ran on both exactly as with the router OFF, and the suite has recorded 5/6
and 4/6 runs at defaults in phases 77, 79 and 80 — bench variance, not the router. Tool precision **7/8 ×3** (`outputs/evidence_89_3_tool.txt`): the same case every time — weather_pt "qual é o tempo hoje?" — rounds 0, no tool, reply "O tempo hoje é 2026-09-07T17:24…" (the clock). The offline claim check (`outputs/evidence_89_3_saydo_claim_check.txt`) shows the kNN CLAIMED this turn at k 2 / 0.75: its two nearest exemplars are "What's today's date?" (0.832, decision_v1) and "What time is it now?" (0.800, routing_v1) — `tempo` read as time, not weather — both without a tool, so the search was never offered. A real misroute by the router (the case passed 8/8 in every earlier run at defaults), not bench variance; the provider timeouts around it are secondary. Held-out m1 25/25, m2 6/7 (`wrong_file_is_not_evidence`, a standing failure at defaults since Phase 84; the runner has no settings hook), m3 13/13, m4 28/28, m5 18/18; truth core 390/390, every gate PASS; write sets v1–v4 identical to the prior record (0.966/0.966, 0.986/1.000, 1.000/1.000, 1.000/1.000), v5 0.976/0.985; suite **772 passed**. **G3 NOT met (tool precision 7/8 ×3 — a real kNN misroute on weather_pt; say-do 4/6 once — bench variance); G4 met.**

**Reserved-set family check (Codex proposal §E, adopted; `scripts/diag_reserved_similarity.py`, `outputs/evidence_89_4_reserved_similarity.txt`).**
n 100 vs 184 exemplars: nearest-exemplar cosine p10 0.623 · p50 0.732 · p90 0.855 · max 0.934; 0 literal duplicates; **5/100 flagged at ≥ 0.90** as paraphrases of base turns (e001, e062, e044, e080, e010). Of the 16 turns the kNN claimed, one (e080 "Deixa isso por agora." ~ "Let's leave it for now.") is among them; the other 15 claims and both flips are not. The reserved verdict stands as read; the rule for the next reserved set (conv_v2) is authoring by family plus this control before sealing.

## 5. Cost

Before the reply, per turn: unchanged at ~4.1–4.3 model calls (router + reply, embedding; the nano in the tail); on a claimed turn one
chat-role call fewer. The exemplar base costs one embedding per exemplar per embedder, once (cached under scratch/). No cost after the reply.
Time to a usable memory: unchanged (the router does not touch the write side).

## 6. Decision

**Keep the nearest-exemplar router OFF (= today); removal deferred** — the user's direction (2026-09-07): the priority is the mechanism that
makes the memory work, not cleaning experimental code that is off; experiments are preserved for comparison, and removal happens only on
proven interference or risk. OFF, the router costs nothing (no base built, no embedding waited on), so there is no interference today. **A risk IS
proven for the ON state** (G3): the router claimed "qual é o tempo hoje?" as a clock question (nearest exemplars "What's today's date?" /
"What time is it now?"), the search tool was never offered and the agent answered with the clock — 3 of 3 repetitions. The mechanism: the
k-agreement test compares the four decision fields, and two exemplars about a different TOPIC that happen to share a decision (question, no
tool, no memory) pass it; a topic-level ambiguity (`tempo`) is invisible to it. Whether that proven-when-ON risk justifies removal is the
user's call; this close keeps the code OFF and preserved. G1 met, G2 not met, G3 not met: the lever cannot move the median because the embedding does not separate routing decisions well enough to claim more than ~1 turn in 6,
and every unclaimed turn pays the wait for the embedding. The finding that matters for efficiency is the one the phase started from and did
not change: the model router call itself (~1.5–1.8 s) is the pre-reply cost, and the way to remove it is not a cheaper router beside it but
fewer decisions before the reply — a candidate for the next plan, presented for approval, not started here.

## 7. Complexity balance (simplicity constraint, point 6)

| item | before 89 | after 89 | proposal |
|---|---|---|---|
| model calls per turn (latency script) | 4.31 (control) | 4.06–4.28 with the router ON; 4.31 OFF | unchanged in production (OFF) |
| pre-reply decision paths | model router (default); 79.3 pre-router (OFF); 79.6 bypass-skips-nano (OFF); 80.2 nano-in-tail (OFF) | + kNN router (OFF) | all stay OFF and preserved for comparison; removal deferred (no interference: an OFF path builds nothing and waits on nothing) |
| modules in `hmgfu/` | 78 | 80 (`knn_router.py`, `embed_memo.py`) | `embed_memo.py` is live (removes a duplicate provider call on any two same-text embeds in a turn; 40 lines, tested); `knn_router.py` inert while OFF |
| settings | 78 | 81 | unchanged; documented and visible (Settings rows, README) |
| scripts | — | +3 (`diag_knn_neighbourhood.py`, `derive_router_pair.py`, `derive_latency_pair.py`) | the two pairing tools are reusable for any router / latency comparison (`net_ci` reused, not duplicated) |
| observed benefit | — | −1.6 s on ~17 % of turns; 0 at the median; +2 [0, +5] decision correctness on the reserved set (not attributable to the kNN: it claimed neither flip) | none that reaches the user; the balance is information for a later simplification pass, not a work item on the critical path |

## 8. Closure

Percentages unchanged by the rule (no gate set fully passed): originality ~37 %, efficiency ~80 %, AGI-memory readiness ~50 %.
