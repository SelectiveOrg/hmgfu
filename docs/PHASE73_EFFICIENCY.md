# Phase 73 — Efficiency: the turn on the critical path

Date: 2026-09-05. Branch `phase73-efficiency` from `8e8c88b`. Programme "Fu 2" row 73: p50 ≤ 5 s and p95 ≤ 12 s per
recall turn on gemma4:12b; ≤ 2 provider calls on a typical turn; recall precision ≥ 0.9 by user-authored evidence;
tokens per turn reported.

## 73.0 — measure before touching anything

`hmgfu/turn_timing.py`: every model call leaves the process through `httpx.Client.post`, so one wrapper at that choke
point (`LedgeredClient`, installed by `instrument_engine` on the Ollama client and every provider client) sees all of
them — kind (chat/embed), model, duration, the token counts Ollama reports, and the thread. `TurnTimer` marks the
stages of a turn (retrieve · prepare · chat · gates · reply · ingest · grade · dream). The summary is persisted with the
turn (`metadata.timings`), emitted as `turn_timings`, returned in the response and shown as a pill in the transcript
(`TimingPill`, cards.jsx; restored from history). No behaviour change; suite 498.

### Anatomy of one turn (read from the ledger of a live greeting, warm model except where noted)

| Where | Call | Model | Cost |
|---|---|---|---|
| retrieve | sensitizer `extract(route=True)` | qwen2.5:1.5b (nano) | ~2.2 s, 1.4k prompt tokens |
| retrieve | `enrich_route` — the router ESCALATES to the main model with a grammar-constrained JSON schema (Phase 57), prompt = route prompt + live tool catalog + active directives + learned exemplars | **gemma4:12b** | 1.85k prompt tokens; 28 s cold (model load), several seconds warm |
| retrieve | query embedding | bge-m3 | 0.25 s warm (2 s cold) |
| chat | the answer (+ tool iterations) | gemma4:12b | 3.9 s for a greeting (1.3k prompt tokens) |
| gates | say-do / grounding / clock re-asks | gemma4:12b | 0 on a clean turn, up to 3 calls otherwise |
| ingest (after the reply is shown) | sensitizer extractions for the user message, the assistant reply, session node, reflections | qwen2.5:1.5b | 4–6 calls, ~1–2 s each |
| ingest | embeddings for each stored node | bge-m3 | 4–5 calls, ~0.25 s each |
| dream (every 8 turns, mini) | contradiction / promotion | qwen2.5:1.5b | ~4.6 s |
| grade | advisory grader (`grader_enabled`) | grader role | 0 here (fail-soft) |

Reading: the user sees the reply after retrieve + chat + gates (36 s on that cold turn); the HTTP call returns only
after ingest + grade + dream (50 s). Two gemma calls happen BEFORE any answer on every turn, and the greeting made
sixteen model calls in total (3 chat · 7 nano · 6 embed, 13.3k tokens).

## 73.1 — baseline (sealed script, 12 turns × 3, warm-up excluded)

`scripts/bench_latency.py`, committed at `6585035` before its first run (n = 36 turns, warm model):

| Class | total p50 | reply p50 | calls/turn | retrieve stage | answer stage | ingest stage |
|---|---|---|---|---|---|---|
| recall | 15.1 s | 10.3 s | 11 | 11.1 s | 1.2 s | 4.1 s |
| tool | 21.7 s | 14.4 s | 13.5 | 10.9 s | 2.6 s | 5.8 s |
| chatter | 29.6 s | 22.7 s | 15.5 | 19.6 s | 3.1 s | 7.0 s |
| fact | 33.6 s | 27.9 s | 13.8 | 32.4 s | 2.5 s | 5.9 s |
| plan | 56.6 s | 50.4 s | 18.7 | 38.8 s | 4.3 s | 6.2 s |
| **all** | **27.4 s (p95 72 s)** | **22.1 s (p95 66 s)** | **13.9** | | | |

Zero of 36 turns used two calls or fewer. The answer stage is 1–4 s; the RETRIEVE stage is 11–39 s, and it is
almost entirely the router escalation on gemma (6.5–70 s per call, mean 16 s).

Probes on a clone (`outputs/probe_router*.txt`):
* The escalation changes the nano's route in 14/14 turns (the 1.5B model labels questions as statements, misses
  `memory_search` / `list_files` / `plan_task`, gets freshness wrong) — it cannot be dropped.
* Its cost is the model size, not the grammar: json-only mode is slower (16–43 s); removing directives and exemplars
  from the prompt saves ~5 s on short turns and nothing on long ones; qwen 1.5B routes in 0.6 s but wrongly.
* Router defect: on "Remember that my favorite drink is ginger tea" gemma emitted the entire 21-tool catalog as
  `requested_tools` and spent 27 s generating it. Fixed structurally: `requested_tools` capped at 3 in the schema
  (`maxItems`, enforced at decode time) and in the sanitiser.

Consequence: the classifier and the answerer are different jobs; the router gets its own provider role
(`router_provider` / `router_model`, default = the chat model), so a smaller model can classify while gemma answers.

## 73.2 — moves (each gated by the baseline, measured alone)

**The root cause of the retrieve stage: the router was thinking.** The candidate-router probe ran gemma4:12b itself
with `think=False` as the reference and it routed every turn in 2.2–3.1 s. Phase 58's dynamic thinking decides
`think` for the ANSWER call only; the classifier call went out with the model default, and gemma4 thinks by default —
6–70 s of hidden reasoning before a grammar-constrained JSON, on every turn. Candidates were all worse on tool
selection (gemma4 e2b 8/14 tools agreement, llama3.1:8b 7/14, phi4-mini 4/14, llama3.2:1b 9/14 with wrong acts;
qwen3.5:2b — a thinking model — hung on constrained JSON), so the router stays gemma4:12b with `think=False`
(`classify_turn`, plus `OllamaClient.chat(think=)` for the fallback path). The router role stays available for a
smaller model later.

Landed before the re-measure:
* (a′) no duplicate model calls: the routing extraction and the query embedding are reused at ingest and for the
  session node; a stored reply is embedded once (−1 nano, −1–2 embeddings per turn, identical results).
* (e) the stuck-loop signature collapsed every digit, so `note1/2/3.txt` were "one identical call" and the third write
  was blocked — the real cause of `plan_restart` ending with two files. Standalone numbers still collapse
  (`sleep 5`/`sleep 500`), digits glued to a word keep their identity.
* Router defect: `requested_tools` capped at 3 (schema `maxItems` + sanitiser).

* (c) `think=False` on every structured or corrective call (slot mapper, grader, directive content, grounding and
  clock re-asks); the Ollama provider drops the flag for models without the capability (cached `/api/show` probe);
  non-Ollama providers never receive it. The answer call keeps dynamic thinking.

### Re-measure 1 (same sealed script, after a′ + b″ + e)

| Class | total p50 | reply p50 | calls/turn | retrieve | answer | ingest |
|---|---|---|---|---|---|---|
| recall | 15.1 → **8.4 s** | 10.3 → **5.2 s** | 11 → 8.1 | 11.1 → 3.8 s | 1.2 → 1.3 s | 4.1 → 3.0 s |
| fact | 33.6 → 9.7 s | 27.9 → 5.4 s | 13.8 → 10.7 | 32.4 → 3.6 s | 2.5 → 2.3 s | 5.9 → 5.2 s |
| tool | 21.7 → 17.9 s | 14.4 → 6.5 s | 13.5 → 10.3 | 10.9 → 4.2 s | 2.6 → 2.7 s | 5.8 → 4.3 s |
| chatter | 29.6 → 14.0 s | 22.7 → 8.0 s | 15.5 → 12 | 19.6 → 4.1 s | 3.1 → 3.8 s | 7.0 → 6.1 s |
| plan | 56.6 → 19.3 s | 50.4 → 8.5 s | 18.7 → 14 | 38.8 → 4.0 s | 4.3 → 7.3 s | 6.2 → 6.5 s |
| **all** | **27.4 → 13.3 s** (p95 72 → 28) | **22.1 → 6.6 s** (p95 66 → 16.5) | **13.9 → 10.5** | | | |

What remains: before the answer, the serial nano extract → router → embedding (~3.8 s); after the reply, the ingest
tail (3–6.5 s) and mini-dreams (3–5 s on some turns) that both the HTTP caller and the next turn's lock wait for.

* (a) the post-reply tail lives in `hmgfu/turn_tail.py` (ingest, reinforce, ontology nodes, grader, mini-dream,
  persistence). Synchronous by default. With the documented setting `tail_async` (default off) the transcript is
  persisted at once, the reply returns, the tail runs on a worker, and the NEXT turn joins the previous tail before it
  reads the graph — the overlap is the user's own reading time, never a half-ingested graph. The tail patches the
  stored metadata with grade and full timings when it finishes (`timings.tail: pending → done`). Known limitation:
  the live grade and timing pills for an async turn appear on restore rather than in the moment.

* (a″) the router escalation, the nano extraction and the query embedding run concurrently (`turn_router.start_route`
  / `merge_route`, `retrieve.make_query_point`): none depends on another's result, so the serial ~3.8 s before the
  answer becomes the slowest of the three. Calls made on worker threads are attributed to the turn through a context
  variable inherited by the workers (`turn_timing.TURN_OWNER`).

### Re-measure 2 (same sealed script, both arms, code with a′ + b″ + c + e + the tail module)

| Arm | total p50 | total p95 | reply p50 | recall total p50 / p95 | calls before reply |
|---|---|---|---|---|---|
| baseline (73.1) | 27.4 s | 72.0 s | 22.1 s | 15.1 s / 27.4 s | 13.9 (all) |
| sync tail | 13.9 s | 24.4 s | 6.3 s | 8.4 s / 9.2 s | 10.8 (all) |
| `tail_async` | **5.7 s** | **12.4 s** | 5.7 s | **4.3 s / 4.5 s** | 4 (tail p50 6.6 s runs while the user reads) |

With `tail_async` the user-visible recall turn meets the Programme targets (p50 ≤ 5 s, p95 ≤ 12 s). The "≤ 2 provider
calls on a typical turn" target is not met: four calls precede the reply (nano extract, router, embedding, answer),
about ten including the tail. Re-measure 3 adds the concurrent routing (a″).

### Re-measure 3 — the reference (fixed learner, retrieval live, concurrent routing; code `2ca4495`)

| Arm | total p50 | total p95 | reply p50 | recall p50 / p95 | fact | tool | chatter | plan | calls before reply |
|---|---|---|---|---|---|---|---|---|---|
| baseline (73.1) | 27.4 s | 72.0 s | 22.1 s | 15.1 / 27.4 s | 33.6 s | 21.7 s | 29.6 s | 56.6 s | 13.9 (all) |
| sync tail | 12.0 s | 16.6 s | 5.9 s | 8.4 / 9.2 s | | | | | 10.1 (all) |
| `tail_async` | **5.8 s** | **8.1 s** | 5.8 s | **4.1 / 4.5 s** | 4.5 s | 5.3 s | 6.5 s | 7.7 s | **4.25** (tail p50 6.2 s in the background) |

Against the Programme row: recall p50 ≤ 5 s met (4.1 s), p95 ≤ 12 s met (8.1 s across all classes), tokens per turn
reported (~5.2k before the reply, ~9.8k with the tail), recall precision by user-authored evidence met (73.3), and
"≤ 2 provider calls on a typical turn" NOT met — four before the reply, with a floor of three while routing stays a
separate call. Baseline → reference: user-visible p50 27.4 → 5.8 s (−79%), p95 72 → 8.1 s.

## 73.4 — `tail_async` becomes the default, gated

The WebSocket turn keeps its event queue open until the tail finishes (the reply is forwarded the moment it is
emitted, so the user still sees it at reply time; the grade and timing pills arrive a few seconds later, live).
Benches join the tail before closing an engine; the fake-provider test harness stays synchronous (the async contract has
its own tests). On the way, a routing gap closed: when the nano extraction failed or produced unparseable JSON, the
router's classification — already computed concurrently — was thrown away with the heuristic fallback; it is now folded
in (`extractor: fallback+router`), so routing no longer depends on the 1.5B model succeeding. Gates on the final code: held-out m1 25/25, m2 6/7 (the known
fixture), m3 13/13; oracles contracts 51/51 and delta 33/33 accepted.

The say-do gate found two more defects, neither caused by the async tail (a sync-tail arm lost the same cases):

* **A same-thread deadlock.** A thread dump taken at the moment of a `database is locked` showed a single thread.
  `DirectiveStore.apply` lifted a tombstone (a DELETE, which opens a write transaction) and, on a restatement, returned
  without committing; the facts INSERT on another connection in the same thread then waited out the busy timeout. Fix:
  commit the lift immediately, and a turn-boundary guard (`db.commit_open_transactions`) that commits and reports any
  store left mid-transaction so the class of bug is visible, not hidden.
* **A hallucinated standing rule.** Both failing replies ended with a made-up suffix. The thinking-free router had
  emitted an `output_suffix` directive on "share with me the link…"; a brand-new kind passed the change gate anywhere,
  was persisted on the clone, and polluted every later reply. Live directives were verified clean. Fix: a new standing
  directive must be stated as standing in the user's own words (`speech_act.has_standing_cue`, EN/PT); changes to an
  active kind, clears and tool rules keep the old rules.

Gates on the fixed code: say-do 6/6 in all six passes (window 3 ×3, window 0 ×3; every claim counter 0; 192–258 s
per pass, down from 400–750 s), tool precision 8/8 with grounding 1.0 and no unasked effects, and the turn-boundary
guard reported no open transaction. `tail_async` stays on.

## 73.5 — close

Latency reference: user-visible p50 27.4 → 5.8 s, p95 72 → 8.1 s, recall 4.1 / 4.5 s, 13.9 → 4.25 model calls before
the reply. Recall precision by the user's own current evidence 0.34 → 1.0 with truth coverage 17/17. Live on the final
server: "Where did I live before?" → "Before 2026-05-21, you lived in Lisbon." in 4.6 s (HTTP 6.6 s), no reverted
value, ledger unchanged; the timing and grade pills render live after the reply. Not met: "≤ 2 provider calls on a
typical turn" — four before the reply, with a floor of three while routing stays a separate call; folding routing into
the answer call is an experiment for a later phase, not a Phase 73 move. Assessment revised to ~37 / ~72 / ~33.

## 73.3 — recall precision by user-authored evidence (M6), and a production finding

The first 73.3 truth run returned 3 memories across 17 queries. The graph was intact and the same query with the config
baseline weights returned 12; with the LEARNED weights it returned 0. Phase 56's weight learner nudges per-component
multipliers from grader outcomes; a turn answered from the canonical ledger cites no memory, so all recalled memories
are graded "unused" and every positive multiplier sinks together — after 270 updates the semantic weight sat at half
its baseline, and the absolute retrieval threshold then rejected even perfect matches. Production retrieval was starved
for about two hours (the ledger kept answering the facts).

Fix at the learner, no database edit: `weights()` re-balances (the positive components keep the baseline's total
mass — learning shifts weight between signals and can never shrink them all, which is what the module's own docstring
promised), and a negative grade counts only in contrast with a cited or implied memory in the same turn. The clone
retrieves 12 again from the same stored multipliers; the live server was restarted on the fix.

The bench now reports `PRECISION_CURRENT` (user-grounded AND carrying no superseded/reverted value) beside the legacy
`PRECISION`, and a `--no-echo` arm excludes assistant/dream-authored memories from the answer context, with CONTEXT
watched for regression. On the fixed learner (×2, deterministic): default arm CONTEXT 17/17, PRECISION 0.423,
PRECISION_CURRENT 0.341 over 123 items; no-echo arm CONTEXT 17/17, both precisions 1.0 over the 15 user-authored
items that remain. Coverage lost nothing, so the arm became product behaviour: `retrieve.user_fact_question` (the turn
is a question that mentions a canonical attribute the ledger holds — decided by the closed slot vocabulary, no phrase
list) switches `echo_free` on in the context builder, for the agent and for the bench's default path alike. The recall
panel still shows every memory; only the ANSWER context is the user's own words.

Still to do: (d) context size if the numbers ask for it.
