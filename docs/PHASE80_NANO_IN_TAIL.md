# Phase 80 — The nano off the pre-reply path

Date: 2026-09-06. Branch `phase80-nano-in-tail` from `972abc1` (Phase 79 closed; backup
`bk-20260906-1202-orig37-eff80-agi47-phase79-closed`). Plan committed before code (`92c06e7`).

## Origin

Phase 79 showed the router was never the wall-clock cost of a turn because it has run in parallel with the nano
extraction since 73.2. The pre-reply `retrieve` stage (2.7–3.2 s of a 5.6 s turn) was therefore bounded by the nano.
Lever: run the nano AFTER the reply, in the tail that already ingests the message, and let the stored point receive its
fields there; before the reply, the extraction is the deterministic heuristic plus the model router.

## Built (80.2)

`Sensitizer.extract(..., nano=False)` (heuristic + router, tag `heuristic+router`); `make_query_point(nano=)`; the engine
reads `nano_in_tail`; `turn_tail.enrich_for_ingest` runs the nano once in the tail and keeps the turn's route fields (the
stored point carries `extractor=nano`); `turn_timing.calls_before_reply` and the latency bench report the user-visible
calls; Settings toggle; `heuristic_extract` split into its own module at the 400-line ceiling. Default OFF = today.

## Gates (80.3)

| gate | result |
|---|---|
| G3 stored-point parity (12 script turns) | 12/12: pre-reply `heuristic+router`, stored `nano`, route fields kept — **met** |
| G1 truth no-echo | 17/17 · precision 1.0 (23 kept memories) — met |
| G1 tool precision ×3 | 8/8 · 8/8 · 8/8, grounded 1.0 — met |
| G1 held-out / oracles / routing sample | 25/25 · 6/7 · 13/13 · 28/28 · 18/18; 51/51 · 33/33; routing 10/10 — met |
| G1 say-do ×3 | 5/6 · 5/6 · 4/6 — **not met** (`anaphora` twice; one `read_intent`, one `plan_restart`); the query point and retrieval are identical with and without the nano (probe), so the mechanism is not retrieval; bisect: anaphora alone ON 3/3 (26–30 s each) and OFF 3/3 (14–17 s): the in-suite misses do not reproduce alone, as with the 77 proposal_yes case — model variance in suite context, not the lever; the gate as written (6/6 ×3 in suite) still reads as not met, and the decision does not hinge on it because G2 fails on its own |
| G2 latency ×3 ON vs OFF | ON p50 6.4 · 5.4 · 5.7 s, calls before the reply 3.33 · 3.83 · 3.25; OFF 5.7 s, 4.25 — **not met** (≤ 4.0 s; ≤ 3 on every turn) |

## Finding

With the nano off the path, the retrieve stage still costs 2.6–2.9 s: that is the ROUTER (gemma4:12b, grammar-constrained
JSON, ~2.6 s inside a turn). The nano and the router were each about half of the pre-reply floor, in parallel; removing
one saves ~0.4 s and one call. The bench's counts are the user-visible ones (it runs with `tail_async` on; the tail's nano
was verified running on every turn).

## Decision (80.4)

By the gates: `nano_in_tail` is not promoted (default False); it stays a documented, tested setting. Further p50 gains
need a cheaper router prompt or a single merged pre-reply call — a new pre-registered phase.
