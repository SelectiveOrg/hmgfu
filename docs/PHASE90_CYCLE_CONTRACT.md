# Phase 90.B — The memory cycle: responsibility → module → state

Date: 2026-09-07. One page, read from the code (Rule 1), no new component. The user's cycle: **message → structured information →
related memory → retrieval → reply**. Dreaming (`dream.py`) is maintenance; no row below depends on it.

Legend — **live**: implemented and on the production path today · **built, OFF**: implemented, reachable only through a setting that is
off · **proposed**: written in a plan/proposal, no code · **gap**: a responsibility with no owner (found in the 2026-09-07 live analysis).

| # | responsibility | module · function | state | test that covers it | note |
|---|---|---|---|---|---|
| 1 | Read the turn: intent, act, tools, memory need | `sensitizer.extract` (+ `turn_router` model router; `heuristic_extract` fallback) | live | v41, v50, routing/decision oracles | pre-router hooks 79.3 (`pre_router`) and 89 (`knn_router`) are built, OFF |
| 2 | Embed the turn once | `agent.embed` → `embed_memo.EmbedMemo` | live | v85 | shared across the retrieval worker and any router |
| 3 | Write CLOSED profile slots from the user's own declaratives (regex) | `facts.FactStore.apply_all` → `_apply_one`; moulds `slots.py`, `fact_moulds.py`; gates `value_gate.py`; modality/time `utterance.py` | live | truth core (390), write sets v1–v7, v72 | **gap G1**: a value stated without the slot's alias ("here's the updated link: <url>") never reaches a slot — the live defect D1 |
| 4 | Write closed slots the regex missed (model-backed) | `fact_spans.apply_spans` + `registry_span_extractor`, called from `turn_tail._ingest_and_learn` | built, OFF (`fact_mapper_mode=spans`) | v83, write sets (84.3/84.5) | production runs the single-slot fallback mapper (`slots.registry_mapper`) only when the regex already found a slot |
| 5 | Supersede / retract with valid time and known time | `assertions.AssertionStore.assert_` (valid_to = new valid_from), `retract`, `active(at, known_at)`; `fact_reconcile` | live | v72, v82 truth core (scoped retraction, temporal) | corrections phrased as a new value work; corrections phrased as "actually we are working on X" need row 3 first (D4) |
| 6 | Keep provenance: fact → episode → span | `facts.link_source`, `assertions.link_episode` (`source_span`) | live | truth core provenance_100 | |
| 7 | Store the episode (user turn, assistant reply) with the routing extraction | `agent.ingest`, `turn_tail._ingest_and_learn`, `chat._store_assistant_reply` (trivia/echo gates) | live | v52, v50 | the assistant reply is embedded (a second embed per turn) |
| 8 | Relate: entities, topics, session node, reflections, Fu edges | `taxonomy.upsert_session_node`, `store_reflection`, `fu_edges` via `graph` | live | relational oracle | the reflection store is where "the user provided a new car location link" survived while the ledger did not (D1) |
| 9 | Retrieve for the question: ledger first, then points by cosine + Fu expansion + history | `retrieve.make_query_point`, `retrieve_memory`, `expand_through_fu`, `_history_memories`, `query_depth.depth_for` | live | truth 17, held-out, LME | `retrieval_limit_aggregate` (86.1) built, OFF — the user's pending decision |
| 10 | Render what the reader sees: ledger lines, history, timeline, excerpts | `context_render.render_injection`, `excerpt_for_query`, `retrieve.build_llm_context` | live | v80, LME 85/87 | 480-char excerpt window (`excerpt_max_chars`) built, OFF — the user's pending decision |
| 11 | Reply with tools when the route asks | `agent._tool_loop`, `tool_loop`, `toolsys`, receipts opened per call | live | say-do, tool precision | |
| 12 | Say = do: a promise becomes execution or is corrected | `saydo.enforce` (one re-ask; `PLAN_CORRECTION`) | live | v41, v88 | 90.2 added: a promise that stays a promise is marked in the reply |
| 13 | A step is done only with proof | `receipts.verify_step` (files: write receipt + hash; widgets: the requested one; generic: THIS turn + the requested action), `session_plans` persist | live | v47, v74, v88 | 90.2 closed the "any action" hole (D3) |
| 14 | Numbers/URLs in the reply trace to evidence | `grounding.verify_grounding`, `ungrounded_claims` | live | v41, v87 | 90.1 fixed the markdown/punctuation tokenisation (D2) |
| 15 | Learn from the turn (tools, routes, runbooks, bandit) | `learning_hooks`, `runbooks` (OFF), `bandit` (OFF), `grader` (setting) | live / built OFF | 75.x benches | costs nano calls in the tail |
| 16 | Time to a usable memory | the tail (`turn_tail.finish_turn`, sync by default; `tail_async` OFF) — `tail_ms` measured by `bench_latency` | live | 73.2 | in the live session the tail took 5–6 s per turn (ingest 4.7–6.5 s) |

## What the live analysis says about this table

- Rows 3–5 are the **update contract**. Today it accepts a value only when the sentence carries the slot's alias (row 3) or when the OFF
  span extractor is on (row 4). The two live misses (D1 "the updated link", D4 "we are actually working on HMG") both fall in that gap.
  Whether the fix is a broader mould, the span extractor ON, or a reference-resolution step ("the updated link" = the link we were talking
  about) is what 90.A must decide from evidence — not assumed here.
- Rows 12–14 are the **honesty gates**; two of them had tokenisation/matching defects that hid correct behaviour (D2) or faked completion
  (D3). Both fixed in 90.1/90.2 with regression tests; no new mechanism.
- Row 16 is the **cost**: the cycle needs 4 model calls (embed, router, reply, tail nano); the live turn made 10–16. The extra calls are rows
  7 (reply embedding), 8 (reflection/title/summary nanos), 15 (grader/learning) and the mini-dream. Measured, not changed (user's direction).

## Contract example (the proposal's): "Gosto de A" then "Ultimamente prefiro B"

Row 3 writes `pref.X = A` (declarative, first person, closed slot). The second sentence is a relative recent preference: row 5 would record
B with `valid_from` from "ultimamente" only if `utterance.valid_from_of` maps it — it does not give a date, so the store records B as the
current value with the recording time as known time, keeping A in history (`fact_history`, `assertions.valid_to`). Nothing infers "odeio A"
(no negative polarity without a negation cue — `utterance.sentence_modalities`). Covered by: v72 (temporal), truth core family C
(history), write sets (values). Not covered: the "relative preference" reading itself — that is a 90.C family, DEV.
