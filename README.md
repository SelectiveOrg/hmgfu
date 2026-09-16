# HMG-Fu — Hex Memory Grid prototype

A working prototype of the **HMG-Fu relational memory algorithm**: memory as a living field of
points connected by *Fu intervals* on a hexagonal grid — with ontological density, energy
propagation, wormholes, contradictions, healthy forgetting, and a dream loop that reorganises
the field. Theory: [docs/THEORY.md](docs/THEORY.md). Plan & status: [ROADMAP.md](ROADMAP.md).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![Models](https://img.shields.io/badge/models-local%20via%20Ollama-orange.svg)

Everything runs on your own machine: no API keys, no cloud, no telemetry. The memory lives in one
SQLite file next to the code, and the models are served by a local Ollama.

**Branches** — `stable-v4` is the version to start from. `main` is history; other branches are work
in progress.

All models run **locally via Ollama**:

| Role | Default model | Override env var |
|------|---------------|------------------|
| Main mind (chat) | `gemma4:12b` | `HMGFU_CHAT_MODEL` |
| Memory sensitizer (nano) | `qwen2.5:1.5b-instruct` | `HMGFU_NANO_MODEL` |
| Nano-produced grader | `gemma-cpu:latest` | `HMGFU_GRADER_MODEL` |
| Dream worker (nano) | `qwen2.5:1.5b-instruct` | `HMGFU_DREAM_MODEL` |
| Embedder | `nomic-embed-text` | `HMGFU_EMBED_MODEL` |

## Setup

```bash
git clone https://github.com/SelectiveOrg/hmg-fu.git
cd hmg-fu
python -m venv .venv
source .venv/Scripts/activate        # Git Bash (Windows: .venv\Scripts\activate)
pip install fastapi "uvicorn[standard]" websockets httpx pytest anyio cryptography
pip install numpy   # optional (Phase 76.2): one matrix product instead of a pure-Python cosine scan — needed past ~2k memories
```

## The UI's third-party files

`web/vendor/` is not in the repository: it holds four minified third-party builds, each under its own
licence, and they are gitignored so this tree stays first-party. The API serves fine without them, but
the Cowork UI renders blank until they are there. Put these four in `web/vendor/`:

| File | What it is |
|------|------------|
| `react.production.min.js` | React (production build) |
| `react-dom.production.min.js` | React DOM (production build) |
| `babel.min.js` | Babel standalone — the `.jsx` files are compiled in the browser |
| `lucide.min.js` | Lucide icons |

Any CDN copy works (unpkg, jsDelivr, cdnjs); the app loads them by these exact names.

## Run

```bash
# Cowork UI (chat + resizable canvas + live/compressed memory hex + trace/layers)
python -m hmgfu.api                  # → http://127.0.0.1:8777

# Terminal chat
python -m hmgfu.cli                  # commands: :dream :stats :why :quit

# Tests (no Ollama needed — fake embedder)
python -m pytest tests/ -q
python scripts/bench_live_system.py   # full live-corpus clone + gemma4:12b action/recall gates

# Live end-to-end smoke (needs Ollama running; uses a throwaway smoke_live.db)
python scripts/smoke_live.py
```

## How a chat turn works (THEORY §24)

1. The message becomes a **QueryPoint** (nano extracts entities/topics/intent, embedder embeds).
2. **Retrieval Ψ**: six channels (semantic, entity, goal, recent, dense-identity, wormhole) →
   §30 activation score → **Fu expansion** through strong edges. Pure local math, milliseconds.
3. The winners are compressed into a token-budgeted **memory injection** for `gemma4:12b`.
4. The reply comes back; the user message (and valuable replies) are **ingested**: sensitized,
   embedded, densified, placed on the hex grid, wired with **FuEdges**, energy **propagated**,
   macros updated.
5. Used memories/edges are **reinforced** (§25). Every few turns a **mini dream loop** runs;
   the full **dream loop** (🌙 button, `:dream`, or `POST /api/dream`) consolidates macros,
   creates wormholes, resolves contradictions, decays noise, and promotes stable memories.

The Cowork canvas is resizable on desktop (drag the separator or use its arrow keys) and remains
full-width on mobile. The Memory · Hex field widget keeps the live activation/inspection view and
adds **Λ Compression**, which restores the original design-system macro absorption, growth, and
expand/compress-all animations against live graph data.

## API

| Endpoint | Purpose |
|----------|---------|
| `POST /api/chat` `{message, explicit?}` | Plain memory cycle + gemma reply + retrieval trace |
| `POST /api/agent/chat` `{message, explicit?}` | **Agentic** cycle: tools offered/used, tool trace, grade card, forced-finalization flag |
| `POST /api/ingest` `{content, source?, type?}` | Ingest a memory without chatting |
| `GET /api/retrieve?q=` | Dry-run retrieval with injected-context preview |
| `GET /api/memory/search?q=&limit=` | Hybrid memory search (frontend surface) |
| `GET /api/memory/timeline?limit=&type=&before=` | Chronological memory feed |
| `GET /api/graph` | All points + edges + stats (feeds the hex UI) |
| `GET /api/tools` / `GET /api/tools/search?q=` | Tool gallery with usage stats + earned utility |
| `GET /api/skills` | Installed skills (file, tools, summary) |
| `GET /api/providers` | Provider availability + per-role routing |
| `GET/PUT /api/settings` | Runtime settings (chat/nano/dream/grader/embed models, grader producer, toggles) |
| `GET /api/connectors` | Connector configuration status (never returns secrets) |
| `POST /api/connectors/{name}/connect` | Connect MCP providers or start Google gog remote OAuth |
| `POST /api/connectors/google/connect/finish` | Finish Google login with the pasted redirect URL |
| `POST /api/dream` | Run the full dream loop, returns the DreamReport |
| `GET /api/reports` | Past dream reports |
| `GET /api/learning` | Self-tuning state: learned score-weight multipliers vs config baseline, routing-exemplar stats, every learned parameter |
| `GET /api/health` | Ollama reachability, configured models, graph stats |

## Agentic layer (v2)

- **Tools/skills are HMG points** — tool selection is the same §30 retrieval as memory;
  used tools gain utility and Fu edges; grading tunes them. `create_skill` lets the agent
  write, validate (AST) and hot-install new `skills/*.py` capabilities.
- **Guards** (from PA3 lessons): 2-strike per-tool block, stuck-loop signature detection,
  no-progress cutoff, forced finalization with tools disabled — never a dead reply.
- **Grader** (`grader_producer`: `nano` or `main`, switchable live): grades recalled
  memories cited/implied/unused → utility EMA → density; detects corrections (ingested as
  user-explicit facts, contradictions marked); extracts playbook pattern-memories.
- **PA3 import**: `python scripts/import_pa3.py` (read-only source, idempotent, re-embeds).
- **Agent smoke**: `python scripts/smoke_agent.py` (after import; server stopped).
- **Complete live benchmark**: `python scripts/bench_live_system.py`. It online-clones the live
  SQLite database, audits every node, then runs the full real-`gemma4:12b` memory/proactivity suite
  only against the clone. Current evidence: 33/33 mandatory checks, including English/Portuguese
  exact-clock and action/directive cases.
- **Runtime time + multilingual routing**: every turn captures one authoritative local/UTC clock
  snapshot and injects that same structured data into sensitization, routing, and the main answer.
  Gemma classifies intent against the live tool registry (new skills appear automatically); HMG
  tool scores and user-feedback reinforcement remain the adaptive learning path. There is no
  natural-language action phrase table. Current correctness-first routing adds a material local
  model latency cost; the measured complete suite took 894.7 s.

## Governed facts: closed slot schema + write gate (Phase 62)

The 2026-09-03 autopsy (`PriorAgent/reports/hmg_memory_reassessment/ANALYSIS.md`) found
both memory systems failing on the WRITE side: fact keys minted by an extractor fragmented one
attribute into many spellings (so a correction retired only its own spelling), and questions /
assistant replies were stored as facts. Phase 62 closes that at the choke points:

- **Closed slot vocabulary** ([hmgfu/slots.py](hmgfu/slots.py)): 25 slots (`identity.name`,
  `identity.alias`, `identity.location`, `pet.name`, `pref.language`, `pref.color`, …) with PT/EN
  aliases. Every fact write passes `normalise_key`; unknown attributes become a cleaned
  `open.<attr>` key (stored, shown in the UI, **never rendered into the prompt**). A bare
  "my favourite is java" resolves by value class. A model mapper (`registry_mapper`, nano role,
  schema-constrained to the slot enum) is consulted only for declarative statements the regex
  left unresolved — it can never mint a key.
- **Speech-act gate** ([hmgfu/speech_act.py](hmgfu/speech_act.py)): a question or request is
  never a fact/person/canon — at ingest (type forced to `message`, keyword `_question`, layer
  L1), at `FactStore.apply`, and in the identity section of the injection.
- **Ledger** (`canonical_facts` + append-only `fact_history`): one live value per slot; a
  correction supersedes across spellings; re-stating the same value is a no-op; every historical
  value is demoted from recall (`superseded_values`). `GET /api/facts` returns `key` (slot id),
  `label`, `slot` (bool), `value`, `prev`, `verbatim`, and `history`.
  **Contract change:** keys are slot ids (was the raw regex attribute); `call me X` → `identity.alias`.
- **Legacy repair**: `hygiene.retype_stored_questions` runs at startup (idempotent);
  `scripts/import_pa3_user_facts.py --target <db>` replays PA3 `conversations` role=user rows
  chronologically through the same resolver (chronology guard, test identities skipped, original
  dates kept, stale nodes demoted).
- **Dream clock**: `turn_count` persists across restarts (`learned_params` `state:turn_count`) and
  the mini-dream tension trigger fires only when unresolved tension grew (`state:tension_seen`).
- **Truth bench** (`scripts/bench_recall_truth.py`, ground truth in `scripts/truth_set.json` with
  provenance): clones the live DB, checks the injected context carries the user's CURRENT value
  and no superseded one (`--answer` also runs gemma; `--weights lean` is an experiment arm).
  Every memory change is gated on it.

## A nearest-exemplar router, measured and kept off (Phase 89)

The turn's own embedding can decide the route when the k nearest labelled exemplars agree and are close, with the model router as the fallback
(`knn_router_enabled`, OFF). On a reserved decision set authored after the build the combined router matched the model's correctness (0.940 vs
0.920, the kNN's 16 claims all correct), but latency ×3 against a same-day control did not move the median: with bge-m3 the embedding tracks the
topic, not the decision, so only ~1 turn in 6 is claimable, and the unclaimed turns wait for the embedding before the model router starts. The
setting stays OFF and is preserved for comparison; what stays live is `hmgfu/embed_memo.py` (one embedding per turn text across threads). Full
record with the complexity balance: `docs/PHASE89_KNN_ROUTER.md`.

## The write side on the production ruler (Phase 88)

The LongMemEval harness can now ingest exactly as the agent does with the span extractor on (per user turn, in the tail's order, provenance linked,
cost counted). Read once on the reserved items with the production embedder, the Phase 84 write-side candidate is neutral on this reader —
knowledge-update equal, multi-session +1, single-session-user +1, nothing down — because LongMemEval's user turns almost never state a durable
first-person fact the regex missed (3 ledger writes in 152 sessions; 0.71 s per turn, paid after the reply). No default moves; the three documented
options (480 window, depth 20, write-side candidate) now share one evidence base and none has a measured cost on the reader. Full record:
`docs/PHASE88_WRITE_SIDE_RULER.md`.

## Ruler precision: the production embedder (Phase 87)

Codex's third review found the LongMemEval harness embedding with `nomic-embed-text` while production embeds with `bge-m3`; verified against the
live settings and the live vectors, fixed at the harness (throwaway engines take production's model settings; the header prints the effective
embedder), with reader failures reported apart and bootstrap intervals on paired nets. The reserved read on the production embedder (items
41–80, never used to choose anything) gives the first unambiguous reader gain: the 480-character window lifts every category (knowledge-update
0.312 → 0.625, multi-session 0.075 → 0.425, intervals excluding zero in four of five); depth 20 on aggregation questions adds multi-session +3
at no cost. By the letter of the pre-registration no default moved on Claude's authority; the adoption of `excerpt_max_chars = 480` (and optionally
`retrieval_limit_aggregate = 20`) is the user's decision with the evidence in `docs/PHASE87_RULER_PRECISION.md`.

> **Errata 2026-09-07.** The LongMemEval figures quoted in the Phase 77–86 sections below were measured with `nomic-embed-text`; production embeds with `bge-m3`. Relative comparisons stand; the production-embedder reserved read is in `docs/PHASE87_RULER_PRECISION.md`.

## Retrieval depth for aggregation questions (Phase 86)

Cross-session sums ("how many days did I take social media breaks in total?") were retrieval-bound; a deeper recall for every question diluted
the rest. Now a deterministic aggregation cue (EN/PT) lifts the recall limit for that turn only (`retrieval_limit_aggregate`; one rule for the
agent and the harness). Measured alone, three runs against three: multi-session 0.0 → 0.083 with every other category
identical or inside the reader's noise; latency held (480 + depth 20: p50 5.3 · 5.5 · 5.4 s (p95 10.2 · 8.9 · 7.9 s). Decision by the gates: not all pass (G1 False, G2 True, G3 True) → the default stays 0; depth 20 is the documented one-click option. Full record: `docs/PHASE86_RETRIEVAL_DEPTH.md`.

## The reader's context on the corrected ruler (Phase 85)

The Phase 78 diagnosis's "budget" residual was never the budget: re-rendering every retrieved-but-lost gold on the faithful harness named the
causes — four golds sat beyond a 160-character head cut in the subject-timeline branch, the rest were span misses, one echo drop, one stale
exclusion. Two renderer defects were fixed (the greedy break that dropped later sections whole; the timeline head cut when the query window is
on), byte-identical where they do not fire. Measured alone, paired per item, three times, with a same-code control: the fixes lose nothing and
lift knowledge-update from 0.550 to a mean of 0.683 with the 480 window (single run 0.750, above the base scan). The pre-registered bar of
0.700 on the mean is missed by 0.017, so the 480 window stays the documented one-click option and no default moves. Two facts on record: the
reader's own noise is two items per twenty, and the Phase 82–84 write-side changes cost two multi-session items on this harness — LongMemEval
joins every write-side gate set. Full record: `docs/PHASE85_READER_CONTEXT.md`.

## The structural write side (Phase 84)

Measured first: production's pre-reply nano mapper is inert (zero writes on five sets, hallucinated raw outputs caught by
the guards) and costs a call. Built, all visible in Settings and off by default: `open_slot_regex_writes` (the open-slot
mould is the precision leak), and a span-extractor contract (`hmgfu/fact_spans.py`) where the model lists every first-person
fact as {attribute in the user's words, value verbatim} and the deterministic side keeps grounding, predicates, third
parties, closed slots, cardinality and modality — running in the turn tail so the pre-reply path is untouched (p50 5.7 s
against a 5.7 s same-day control). On the reserved v7, run once: candidate precision 0.947 / coverage 0.592 against
production's 0.864 / 0.446. The coverage bar of 0.60 was missed by 0.008, so by pre-registration the defaults stay and
the candidate is the documented one-click option. Full record: `docs/PHASE84_STRUCTURAL_WRITE.md`.

## The write side on unseen messages (Phase 83)

The five failure families of the reserved `write_set_v5` were fixed at their cause, failing-test-first (`hmgfu/value_gate.py`
for predicate-shaped values, hedges and third parties; `hmgfu/fact_moulds.py` holding every sentence mould; sequences and
retirements), and v5 went from 0.727 / 0.458 to 0.976 / 0.985 — then the NEW reserved `write_set_v6`, run once, read
precision 0.743 / coverage 0.364 against the pre-registered 0.90 / 0.75. The fixes were in-sample again. Two reserved sets
now agree: deterministic moulds give ~0.73 precision and ~0.36–0.46 coverage on unseen first-person messages; the open-slot
mould is the precision leak and the approach itself is the coverage ceiling. Nothing promoted; the structural write side
(gated open-slot writes; a grounded model mapper measured on a reserved v7) is Phase 84. Full record: `docs/PHASE83_WRITE_SIDE.md`.

## Truth and execution core (Phase 82)

Codex's P1, built failing-test-first: a named negation retires a value only inside its own slot (a user named Bento keeps
their name when the dog Bento is corrected; a cat Bento survives too); the canonical row, its history and its assertion
are ONE transaction on ONE connection with rollback (fault-injected), construction reconciles and reports the two views,
and `active(at=, known_at=)` separates when a fact held from when it was learned; every assertion points at its episode
with the exact offsets of the value in the message; receipts prove the REQUESTED outcome — the directory-normalised path,
the on-disk hash equal to the observed one, the named widget, and never a read for a write. A 390-case deterministic
adversarial suite (`scripts/bench_truth_core.py`) found two more real defects on its first run (species-crossing sweep;
SQLite's ASCII-only `lower()` on accented values) and passes fully after them. Full record: `docs/PHASE82_TRUTH_CORE.md`.

## Measurement fidelity (Phase 81)

Codex's second review asked for the ruler before any more optimisation. The LongMemEval production arm now ingests like the
agent (assistant turns never reach the fact ledger — the 77.2 / 78.4 prod figures are superseded: KU 0.450 at defaults,
0.600 with the 480-char window, zero paired losses); the reply judge was audited on 66 labelled replies (v1 39/66 →
v2 63/66, declared per run with `LME_JUDGE`); run manifests carry the dirty-diff and effective-settings hashes with
exclusive file names and nearest-rank quantiles. Two RESERVED sets were sealed and run once: `write_set_v5` (300 unseen
PT/EN messages) reads precision 0.727 / coverage 0.458 against 0.97–1.00 on the sets the write side was tuned on, and
`decision_v1` (100 turns with author-adjudicated admissible routes) reads router correctness 0.94. Full record:
`docs/PHASE81_MEASUREMENT_FIDELITY.md`.

## The nano off the pre-reply path (Phase 80)

`nano_in_tail` (default off) moves the nano extraction into the post-reply tail: before the reply the extraction is the
deterministic heuristic plus the model router; the stored memory still receives the nano's fields (verified 12/12).
Measured: truth, tool precision, held-out and oracles held; say-do read 5/6 · 5/6 · 4/6 and the script-wide p50 stayed at
5.4–6.4 s — because the router call itself is the other half of the pre-reply floor (~2.6 s in a turn). By pre-registration
the setting stays off. Full record: `docs/PHASE80_NANO_IN_TAIL.md`.

## Router cost (Phase 79)

The last unmet efficiency clause was two calls per turn (4.25 today). A sealed routing set (84 PT/EN turns, reference routes
by gemma4:12b) showed no installed small model routes like gemma (agreement 0.07–0.43 vs a 0.95 bar). A deterministic
pre-router (`hmgfu/pre_router.py`, built only from existing detectors) decides plain recall questions and plain fact
statements without a model call, 14/84 of the set at 1.000 agreement — and it exposed and fixed a production write defect
(a Portuguese negated copula overwrote the user's name). Measured: the router was never the wall-clock cost (it runs in
parallel with the nano extraction since 73.2); with `bypass_skips_nano` the claimed turns run in ~1.5 s at 2 calls instead
of ~4.5 s at 4, with the user's words as the ingested summary instead of a nano paraphrase that is often invented. The
script-wide p50 gate was not met (unclaimed classes dominate the median), so by pre-registration both settings stay OFF —
`router_bypass_enabled` and `bypass_skips_nano` in Settings → Memory recall. Full record: `docs/PHASE79_ROUTER_COST.md`.

## Long-form excerpts (Phase 78)

The 77.2 attribution said the production CONTEXT POLICY, not retrieval, loses long evidence: every memory was cut to its first
200 characters. `hmgfu/context_render.py` now renders the query-matched sentence window of a memory when `excerpt_max_chars`
is set (default **0** = today's head cut, byte-identical); `echo_guard_scope` (`all` = today | `echoes`) is the scoped echo
guard. Pre-registered gates, measured: truth no-echo held (17/17 · 1.0) with the window; relational Hit@12 0.717 and
context truth identical; the deterministic attribution keeps 0.75–1.00 of what retrieval found (today 0.47–0.60) — below
the 0.90 bar because the residue is the 1800-token budget; LongMemEval production arm at 480 characters, paired against
77.2: knowledge-update **0.30 → 0.55**, every answerable category up. **The default did not move** (one gate short, as
pre-registered); `excerpt_max_chars = 480` is the documented, one-click option in Settings → Memory recall. The `echoes`
scope fails the truth gate on the live corpus (0.525) and is not recommended. Full record: `docs/PHASE78_EXCERPTS.md`.

## Retrieval mode (Phase 77.1)

`retrieval_mode` = `fu` (the experimental package: six channels, composite Fu score, expansion) or `cosine` (the strong
control of Phase 74 as product: vector top-k over the same episodic pool, the relevance floor, the same context policy).
The default is decided by a pre-registered rule, not by preference: the cheaper mode wins at parity, the other needs
≥ 0.05 on a sealed primary metric. `scripts/bench_relational.py` arm `p2` is the product cosine mode and must reproduce
B2; `scripts/bench_recall_truth.py --mode cosine|fu` measures the truth set in either mode.

## One read path, novel phrasing, an alarm that needs no turn (Phase 77.3 / 77.5 / 77.6)

**77.3 — one read path over assertions.** The rendered fact lines come from the ASSERTION store (active · supported ·
slot relations); every canonical clear or negated value retires its assertion; canonical rows written before Phase 72 are
backfilled once at construction; `canonical_facts` stays as the projection the provenance helpers read. `supported()` is
the justification gate — wired, and producer-less today (no product path writes justifications yet), said so. Sealed
`heldout_m5` 17/18 before → 17/18 after (the miss was the precision case 77.5 fixed) → 18/18.

**77.5 — novel phrasing on the write side.** Sealed `write_set_v4.json` (84 PT/EN paraphrases) read **P 0.692 / C 0.450**
before; the 42 misses were eight classes fixed at the layer each lives in (detector forms whose attribute is resolved by
the slot schema, sentence modality, value trimming, a store gate that lets a NAME slot take only a name-shaped value, the
rules for a relative's attribute) → **P 1.000 / C 1.000**, v1–v3 identical, no item named in code, no setting added.

**77.6 — prospective alarm.** Due time-reminders fire WITHOUT a turn: `hmgfu/prospective_alarm.py` ticks every
`prospective_tick_s` seconds (default 30; 0 idles it), fires what is due and writes a notification; the next turn
delivers it as a PROSPECTIVE block, or the UI polls `GET /api/prospective/notifications`, shows a bell pill and
acknowledges (`POST /api/prospective/notifications/ack`). Condition reminders still need a message. Settings now show
"Prospective memory" (`prospective_enabled`, `prospective_tick_s`). Bench: 200 synthetic triggers on a frozen clock —
0 false fires, 0 late, 0 misses; live idle ticker — 0 notifications. Full record: `docs/PHASE77_CORE_VALIDATION.md`.

**77.2 — external protocol, honestly.** LongMemEval sample (20 items × 7 categories, arms base · prod fu · prod cosine, paired): the
production path reads far below a plain top-10 scan of full turns in every answerable category, in both modes. Deterministic attribution:
retrieval finds the gold about as often as the scan; the context policy (200/160-character excerpts, assistant-source exclusion, 1800-token
budget) then loses about half of it. Recorded as a finding; a long-form excerpt policy is planned as the next phase, behind its own gates.

**77.4 — claim-level abstention.** The answer-side signal is the best of three tried (test F1 0.708, never abstains on the truth set) and
still fails the pre-registered gate; on the reader path it changes no verdict. `claim_gate_enabled` stays OFF as a documented control.

## Scale and consolidation (Phase 76)

**Vector scan (76.2).** With bge-m3's 1024 dimensions the pure-Python cosine scan crossed the 500 ms budget at ~5k
memories (12.7 s per query at 100k). `hmgfu/vecindex.py` computes the same ranking — tie order included — as one
matrix product when numpy is installed (`pip install numpy`, optional), maintained incrementally from the store's
dirty set: 100k points p50 393 ms (p95 1.4–2.3 s, the cost of 100k Python objects, documented). `HMGFU_VECTOR_INDEX=0`
forces the old path. Results identical on every sealed set; quality curve to 100k in `docs/PHASE76_SCALE.md`.

**Dreams as budgeted maintenance (76.3).** The dream loop takes a budget (seconds, model calls) and a region (what
changed since the last dream) — settings `dream_budget_s`, `dream_region_only` — and records what it cut. The
pre-registered ablation (one full dream on the relational and truth benches) found recall down on the relational set
(0.717 → 0.683, macro crowding) and no token saving, so the scheduled full dream is **off by default**
(`full_dream_every_n_turns` 0); manual and API dreams remain.

## AGI properties (Phase 75)

**Procedural runbooks (75.1, opt-in).** A finalized plan leaves one runbook — the task, the user's own request, the
steps with the tools and files that fulfilled them (from the receipts), the outcome. When a later request resembles a
runbook's task (`runbook_match_floor`, cosine 0.62; ranked by memory scoring's relevance) and no plan is active, up to
two runbooks are offered beside the tool schemas so the model reuses the proven sequence instead of inventing one; a
runbook followed to `done` gains utility and absorbs the request that led to its reuse (multilingual self-growth).
Off by default (`runbooks_enabled`): the sealed bench (`scripts/bench_runbooks.py`, `scripts/oracles/runbooks_v2.json`)
measured Hit@1 0.889 (EN 1.0 · PT 0.667) with zero false surfacing, under the pre-registered 0.9 gate. `GET /api/runbooks`
lists them; a `runbook` pill shows when one was offered. See `docs/PHASE75_AGI_PROPERTIES.md`.

**Prospective memory (75.2).** "Lembra-me amanhã às 9 de ligar ao João", "remind me to send the invoice when Nelson
replies": a deterministic PT/EN detector (no model call) stores a trigger by time (resolved against the turn's local
clock) or by condition (the salient words of the clause); at turn start, due triggers fire into the prompt, a pill and a
`prospective_fired` event, marked fired with the turn as receipt. "Remind me what I said" is recall, not a trigger; a
cancel cue cancels the latest pending one. Setting `prospective_enabled`; `GET /api/prospective`,
`POST /api/prospective/{id}/cancel`. Sealed held-out `heldout_m4` 28/28 on its single run.

**Calibrated abstention (75.3, negative).** Two pre-registered retrieval-side signals (similarity floor, lexical
coverage) were calibrated on a dev split of LongMemEval's abstention + knowledge-update items and reported on test:
F1 0.58 / 0.67 with 10 and 46 of 77 answerable control questions wrongly abstained. Neither separates "topic present,
detail missing"; nothing is wired. Abstention needs claim-level verification, a later phase.

**Self-recall (75.4).** The agent's own reflections come back on a recurring problem (20/20 on the sealed set) and
never enter the answer to a question about the user — after closing a degraded-path hole: the heuristic fallback now
classifies the conversation act, so the echo-free rule holds even when the router is down.

**Outcome-driven bandit (75.5, opt-in).** A bounded Thompson-sampling bandit (`hmgfu/bandit.py`, state in
`learned_params`, visible at `/api/learning`) decides at one real site — offer a matched runbook or not — and is paid by the
plan's receipts-verified outcome. Off by default (`bandit_enabled`): exploration costs real plans early on.

**Utility estimator (75.6).** `scripts/bench_utility_g.py` estimates Fu-R's G(f) and I_Fu offline (remove one part, re-read,
bootstrap CI; "unknown" when the interval includes zero). On the relational set every part reads 0.0 ± CI: the reader
answers from the recalled memories alone — the utility-side view of the Phase 74 parity.

## Relational bench: does the Fu package earn its complexity? (Phase 74)

A pre-registered test of the theory's one falsifiable claim — relational recall beats semantic recall — on a sealed
synthetic diary (`scripts/oracles/relational_v1.json`, generator `scripts/relational_corpus.py`, 159 messages, 60
questions with gold ids), four arms on the same corpus (`scripts/bench_relational.py`): plain cosine, cosine + ledger,
cosine + provenance / fixed revision (the strong control, B2), and production Fu retrieval with B2's context policy (F).
**Verdict: the gate ("F beats B2 by +0.10 on relational Hit@k, CI excluding 0") is not met — F is below B2 on three
runs (0.65 vs 0.72), answer accuracy is at parity, cost identical. Honest claim: good provenance engineering.** The Fu
package (expansion, wormholes, learned weights) is an experimental arm from here. The bench found and fixed two write-side
false positives and an ungated read-side exclusion (Fu-R's "revision erases independent facts"), made `min_score` a
relevance floor, and located the loss in the scoring rule: the edge-κ term rewarded clusters of self-similar memories
whatever the question (74.7: path-κ is query-relative), then in dream macros dated by the dream instead of their
content (74.8: a macro is as recent as its newest member; `ingest(..., timestamp=)` carries the observation time for
imports and replays). With both corrections F reaches parity with the strong control (0.717 = 0.717; relational family
+0.036) — the verdict stands. Ablation switch: `--ablate noexpand|no_wormhole|no_dense_recent_goal|
semantic_entity_only|semantic_only|no_macros|no_edge_kappa`. See `docs/PHASE74_RELATIONAL.md`.

## Efficiency: the turn on the critical path (Phase 73)

Every model call is ledgered at the HTTP choke point and every turn carries stage timings (`hmgfu/turn_timing.py`,
`TimingPill` in the transcript). The sealed 12-turn latency script (`scripts/bench_latency.py`, ×3) went from a
user-visible p50 of 27.4 s (p95 72 s, 13.9 model calls per turn) to **5.8 s (p95 8.1 s, 4 calls before the reply)**.
What did it: the grammar-constrained router ran with the model's native thinking on (6–70 s per route; `think=False`
brings it to 2–3 s — Phase 58's dynamic thinking still governs the answer call), no duplicate extraction or
embedding per turn, the router / nano extraction / query embedding run concurrently, a fixed stuck-loop signature that
had been blocking legitimate writes, `think=False` on every structured or corrective call, and the post-reply tail
(ingest, grader, mini-dream — `hmgfu/turn_tail.py`) running after the reply with the next turn joining it first
(`tail_async`, on by default; the WebSocket keeps the turn open until `turn_end` so the late pills still arrive).
Two production findings on the way, both fixed at their layer: the retrieval weight learner had sunk every multiplier
on ledger-answered turns (it now re-balances, and "unused" needs a cited contrast), and a same-thread SQLite deadlock
in the directive store. Recall precision by the user's own current evidence: 0.34 → 1.0 on user-fact questions, with
truth coverage 17/17, by keeping assistant-authored memories out of the answer context. See
`docs/PHASE73_EFFICIENCY.md`.

## Assertions with time and modality (Phase 72 — M3)

The fact ledger is no longer a flat slot table. Every user sentence gets a **modality** (`assert / cite / hypothesis /
fiction / past / question`, `hmgfu/utterance.py`): quoted or reported speech, fiction (carried over one sentence until
a reality cue), hypotheticals and dated past clauses never become the user's facts; "since 2022 I live in Tete" is
current with a `valid_from`. Accepted facts are written as **bitemporal assertions** (`hmgfu/assertions.py`: entity,
relation, value, polarity, modality, `valid_from/valid_to`, source episode) alongside the canonical ledger, in the same
transaction. A new value supersedes the old one instead of overwriting it, so "where did I live before?" is answered
at query time from the same store (HISTORY lines in the context; a `history` toggle in the memory panel). Two entities
of one kind in one message become `pet.dog.name` and `pet.dog.name.2`; "Teca, not Bento" retracts the named value.
Write precision/coverage is measured on sealed PT/EN write sets with a bootstrap CI (`scripts/run_write_set.py`);
the last fresh held-out set gave precision 0.948, coverage 0.932 before fixes — see `docs/PHASE72_ASSERTIONS.md`.

## Receipts: "done" means the world changed (Phase 71 — M2)

Every executed action leaves a receipt (`hmgfu/receipts.py`, table `receipts`): opened before dispatch, closed with
the observed effects (files + sha256, widget ids, exit codes). A plan step is `done` only when its post-condition holds
in the world — the files it names exist and were written by an unconsumed receipt, a widget step has a widget receipt —
checked identically by `update_plan` and by the end of the turn; a receipt is consumed by exactly one step. Done plus
failed is `partial`. A crash between effect and receipt leaves an UNKNOWN OUTCOME the model must verify before
repeating; cancellation cancels pending receipts; rewriting identical content is idempotent. External gate: Codex's
four M2 checks pass (delta oracle 26/26 accepted).

## Immutable evidence and scoped authority (Phase 70 — M0 + M1 of the audit plan)

Codex's resumed audit wrote 35 new adversarial checks against Phase 69 (3 passed) and an M0–M7 plan
(`docs/PHASE68_PLANO_MELHORIAS.md`). Phase 70 executes M0 and M1 (`docs/PHASE70_M0_M1.md`):

- **Evidence**: every bench/oracle run lands in `outputs/runs/<utc>-<sha7>/` with a manifest; benches refuse the
  production DB (`guard_scratch`); `scripts/run_oracles.py` compares the two frozen audit oracles with
  `scripts/oracles/expected.json`; a sealed held-out set (`scripts/run_heldout.py`) is run once, not tuned.
- **Authority**: `hmgfu/authority.py` decides per call from a DECLARED effect (`x-effect` on every tool; undeclared =
  effect) and an authorization RECORD bound to the plan (who approved, with which words, when). Resume never mints
  approval; "do not create…" closes the turn; an approved plan authorizes only the tools (and files) its steps name;
  shell is read-only only under a small allow-list grammar, with `list_files`/`read_file` as the native reads; the
  alias is resolved once; the HTML materializer is a dispatched `write_file` with a receipt in the trace.
- External gate: delta oracle 3/35 → 22/22 accepted (13 deferred to M2/M3/M5); contracts oracle intact 51/51.

## One authority boundary, evidence-bound claims, honest write side (Phase 69)

An independent re-audit (Codex, `docs/PHASE68_REAUDITORIA.md`) ran 56 deterministic contract checks against the
Phase 67 code: 12 held. The response (`docs/PHASE69_AUDIT_RESPONSE.md`) fixed 36 accepted gaps and re-ran the same
oracle as an external check: **51/56** (the five left are documented: two use the old single pet slot, three ask a
lexical gate for semantic entity binding). What changed:

- **`hmgfu/authority.py`** is the ONE place that decides whether an effect may happen this turn: canonical effect list,
  alias resolved before the check, fail-closed shell classifier (`ls`/`git status` pass, anything unknown confirms),
  and authority = the user's request or a user-approved plan — a plan the model declares grants nothing. The tool
  loop, the code-block materializer, say-do and the benches all ask it.
- **Plan truth**: "stop/cancel" abandons an active plan; a step completes only on evidence that fits it; "done" claims
  need executed work; all-failed plans are `failed`; "Sim, podes avançar" approves.
- **Claims bound by type**: "deleted" needs a retraction or remove effect, "created" an effect, "updated" a write,
  "noted" the ledger or the episode; failed tools are not action; promises about remembering are not proposals;
  grounding runs on the final reply and a number carries its unit.
- **Write side**: the ledger learns only from asserted, present, first-person clauses (questions, quoted speech,
  hypotheticals and past clauses are vetoed per sentence); species pet slots; last value wins; compound values;
  update forms bind only to a fitting subject; supersession respects the attribute; retired values demote evidence.
- **Provenance and lifecycle**: directive tombstones (a retired rule never comes back at startup), raw user words in
  recall with summaries marked derived, canonical facts on empty retrieval, session delete cascades to its plan.
- **UI**: say-do and grounding feedback pills, blocked tools stay blocked after a restore, failed steps render as failed.

## Say-do fidelity: claims are contracts, plans outlive the turn (Phase 67)

Live case (docs/PHASE67_SAY_DO_ANALYSIS.md): "I'll take a look…" with no action; "I've updated your link" with
no ledger write; a recall-only memory that left "it's not clickable" without a referent. Now:

- **Say-do gate** (`hmgfu/saydo.py`, setting `saydo_gate_enabled`): a promise with no tool this turn is either
  executed now (read-only intents: look/check/read/search) or turned into a **proposal**; a claim of a write
  ("I've updated…") must match a committed transaction (ledger write, directive change, successful side-effect
  tool) or is corrected visibly. The report is stored per turn (`metadata.saydo`) as the agent's self-grade.
- **Session plans** (`hmgfu/session_plans.py`, table `session_plans`): `plan_task(status="proposed")` asks first;
  "yes/sim" activates, "no/não" abandons (deterministic, only while a proposal is pending); active plans are
  **pinned** at the top of the system prompt and resume after reconnects and restarts; steps auto-complete only
  with evidence of work. One execution path — no background worker universe.
- **Permission first** (67.10): a *suggestion* ("you can maybe create a widget…", `speech_act.is_suggestion`)
  closes the side-effect gate; the blocked call is turned into a proposal by the harness, and `plan_task` on such
  a turn is forced to `proposed` — the model cannot reopen the gate by declaring a plan. After approval, a promise
  or a bare "continue" with no tool triggers the **approved re-ask** (execute now, never re-propose or apologise);
  `plan_task` while a plan is approved returns the current step instead of re-planning; a sparse widget call with
  no props gets them built from the ledger.
- **Recent-turn window** (`recent_turns_window`, default 3, Settings): the last N session turns injected
  verbatim — the guaranteed anaphora window for a recall-based memory; `bench_say_do.py --window N` measures it.
- **Self-instructed recall** (`plan_step_recall`): picking up a plan step recalls memory for the step and returns it
  inside the plan tool's result; an executed intent recalls first.
- **Update form** in the resolver ("here's the updated link: URL" → the single URL-valued slot), **workspace
  scoping** (the workspace block only when files/code are referenced), **memory-grounded widget content** (the
  referent is the user's message plus the pinned plan, so "yes please" still grounds the widget; note text and
  table rows are filled from the ledger, idempotently).
- Measured by `scripts/bench_say_do.py` (intent-claim-without-action, false-execution-claim, approval honoured,
  plan resumed after restart, workspace misattribution).

## Harnessed tool use (Phase 66)

A live weather question cost four tool rounds and produced a fabricated "26°C" (research and case in
[docs/PHASE66_HARNESS_RESEARCH.md](docs/PHASE66_HARNESS_RESEARCH.md)). The harness now enforces what a
small model cannot be trusted to do by itself:

- **Answer grounding gate** (`hmgfu/grounding.py`, setting `grounding_gate_enabled`): after a tool round,
  every number/unit and URL in the reply must trace to a tool result, the memory context, the runtime
  clock (a clock reading grounds only a time-shaped claim, never a bare number) or the user's words; one tools-off re-ask, then the value is flagged "(unverified: …)" and a
  `grounding` event reaches the UI.
- **Argument grounding** (`hmgfu/deixis.py`): for tools that declare `x-search-query-arg` (brave_web_search)
  the query is completed with the user's city (when the request is local and no place was named) and the
  local date (when time-bound). Plus an explicit exemplar in the agent prompt.
- **Unknown-tool auto-resolution**: an invented tool name is resolved semantically against the tool points
  (confident top hit only) and rerouted with a `_rerouted` marker — no wasted round.
- **Standing tool rules are directives**: "from now on always use brave search for weather" becomes a
  `tool_rule:<tool>` directive (one row per tool), rendered on every turn, migrated from existing memories
  at startup (tagged `_tool_rule`, kept in recall on action turns), and enforced like a user-named tool.
- **Minimal action**: a plain question sees `question_max_tools` tools and `question_max_iterations`
  rounds (both in Settings); widgets/files/skills are blocked unless asked, router-requested or planned.
- **Measured** by `scripts/bench_tool_precision.py` (hallucinated-tool, argument-grounding, answer-grounding,
  unasked-effect rates, rounds per question; `--chat-model` for the model-tier arm).

## Recall precision and use (Phase 65)

Live sessions showed recalled memories that were mostly noise and a model that "preferred" `memory_search`.
Root causes and the general fixes (all measured on the truth bench, none by weight tuning):

- **Memory tools are offered, never forced.** The router pins `memory_search` on most identity questions;
  the tool loop used to force it ("ACTION REQUIRED"). Memory is already injected, so `memory_search`,
  `memory_timeline` and `memory_zoom` are now excluded from forced actions. "Tell me without any search"
  is honoured. A turn that refers to the user themselves (`speech_act.refers_to_self`) never has its
  recalled context discarded on a router `needs_memory=False`.
- **A user's question is never an answer.** Every stored user/system interrogative carries `_question`
  (startup hygiene, idempotent) and leaves the recall pool, like skills and session breath.
- **Provenance at render.** User-authored points are injected as the user's verbatim words (the nano
  summary is a lossy rewrite). Assistant replies are stored WITHOUT the enforced opener/closer, so
  trivia and jokes no longer become memories.
- **Strict heuristic grader.** "cited" needs two distinctive tokens the user's question did not already
  contain; questions/session points are never cited (this had been pumping junk utility).
- **Measured, not promoted:** `--assistant-factor 0.6` (worse) and `--dormant-chatter` (negligible)
  remain experiment flags on `bench_recall_truth.py`; `PRECISION` (share of recalled items that are
  user-grounded, `taxonomy.is_user_grounded`) is reported on every run.

## Self-tuning layer (Phase 56)

All learned state is bounded, persisted in the `learned_params`/`route_exemplars` tables, visible
at `GET /api/learning`, and gated by the `learning_enabled` setting (off → exact config-baseline
behaviour; deleting the rows restores stock):

- **Score-weight learning** (`hmgfu/learning.py`): grader memory grades (cited/implied/unused)
  adapt per-weight multipliers over `MEMORY_SCORE_WEIGHTS` within [0.5×, 1.5×] — retrieval and
  tool ranking improve with experience instead of staying hand-tuned.
- **Semantic feedback polarity**: the router judges praise/complaint by meaning in any language
  (`feedback_polarity`); the old lexical cue lists survive only as the offline fallback.
- **Routing-exemplar memory** (`hmgfu/route_memory.py`): a semantic-recovery rescue confirmed by
  successful execution is stored (deduped, capped at 50) and injected as per-turn learned
  few-shots — the router learns from its own misroutes.
- **Wormhole gate calibration** (`WormholeCalibrator`): dream near-miss statistics relax the
  most-binding gate (hard bounds) after dry dreams and tighten back toward the baseline when
  over-firing; adaptations appear in the dream report insights.
- **Scheduled full dream** (`full_dream_every_n_turns`, default 40, 0 = off): the macro/wormhole
  self-organisation stage now runs automatically in a background thread — production evidence
  showed it had been manual-only (56/59 dreams were minis).
- **Layer stratification invariant** (`taxonomy.episodic_repair_layer` / `layer_cap`): episodic
  content never presents as identity — hygiene demotes existing pollution (startup + every full
  dream) and the promotion gate caps new content at the project layer.

## All configuration flags

Everything lives in [hmgfu/config.py](hmgfu/config.py) with THEORY § references; the values
below are overridable via environment (no hidden switches):

| Env var | Default | Meaning |
|---------|---------|---------|
| `HMGFU_CHAT_MODEL` | `gemma4:12b` | main chat model |
| `HMGFU_ROUTER_MODEL` | = chat model | turn classifier (Phase 73.2 `router` role; runs with native thinking OFF — a grammar-constrained JSON never needs it) |
| `HMGFU_NANO_MODEL` | `qwen2.5:1.5b-instruct` | high-frequency sensitizer model |
| `HMGFU_GRADER_MODEL` | `gemma-cpu:latest` | advisory nano-produced grader model |
| `HMGFU_DREAM_MODEL` | `qwen2.5:1.5b-instruct` | dream-loop model |
| `HMGFU_EMBED_MODEL` | `nomic-embed-text` | embedding model |
| `HMGFU_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `HMGFU_OLLAMA_TIMEOUT_S` | `300` | chat timeout |
| `HMGFU_NANO_TIMEOUT_S` | `45` | nano timeout |
| `HMGFU_DB_PATH` | `<repo>/hmgfu.db` | SQLite path |
| `HMGFU_TOKEN_BUDGET` | `1800` | injected-context token budget |
| `HMGFU_MINI_DREAM_EVERY_N_TURNS` | `8` | mini dream cadence |
| `HMGFU_API_HOST` / `HMGFU_API_PORT` | `127.0.0.1` / `8777` | server bind |
| `HMGFU_REGULATOR_ENABLED` | `0` (OFF) | Phase 61a memory-lifecycle Regulator (TEMP/CANDIDATE/FACT/SUPERSEDED). Absorbing correction in prod — **enable deliberately**; the settings UI toggle requires explicit confirmation and auto-engages the observation window. Also a persisted setting (`regulator_enabled`). |
| `HMGFU_CHAT_CORRECTION_SIGNAL` | `0` (OFF) | route correction detection to the strong chat model, deferred to the GPU-free drain (P-AUDIT-3b flip). Persisted setting `chat_correction_signal`. |
| `HMGFU_OBSERVE_FIRST_N` | `0` (off) | post-flip observation window: log the first N drained corrections' source + lifecycle-ledger to `observation_log.jsonl` for spot-audit. Persisted setting `observe_first_n` (UI auto-sets 50 on toggle-on). |

**Precedence (WRITTEN rule, `config._env_is_set` / `reconcile_flags`):** for these three flags, **if the `HMGFU_*` env var is set it WINS** and the persisted setting is ignored; otherwise the persisted setting applies; otherwise the default (OFF). This is the *inverse* of `HMGFU_EMBED_MODEL`, where a persisted value silently shadowed the env during the bge-m3 migration and caused a dimension-mismatch — the lesson is that the precedence must be explicit per key, not assumed.

## Architecture — modular & self-growing

No module may exceed **400 lines** (frontend: 300) — enforced by `tests/test_architecture.py`,
which fails the build the moment a file balloons (the PA3 4,800-line-conductor lesson,
docs/PA3_LESSONS.md refusal #2). Where new things go:

| You want to add… | Put it in… | Nothing else changes |
|---|---|---|
| A new **capability for the agent** | `skills/<name>.py` exporting `TOOLS` + `execute()` (or let the agent `create_skill` it) | auto-discovered, becomes an HMG tool-point |
| A new **built-in tool** | schema in `hmgfu/tool_builtins.py` + one branch in `toolsys._execute_inner` | |
| A new **endpoint group** | `hmgfu/routes/<area>.py` with an `APIRouter`, listed in `routes.ALL_ROUTERS` | `api.py` untouched |
| A new **widget type** | `WIDGET_TYPES` in `sessions.py` + a renderer case in `web/app/Canvas.jsx` | LLM can create it immediately |
| A new **provider** | class in `hmgfu/providers.py` + registry entry | selectable per role via settings |
| A new **turn event** | emit in `agent.py`, handle in `web/app/events.jsx` | |
| A new **formula/weight** | `hmgfu/fu_math.py` / `hmgfu/config.py` with a THEORY § reference | |

Layering: `models → fu_math/hexgrid → store → (sensitizer/providers) → ingest/retrieve/propagate/dream
→ agent/grader → routes → web`. `runtime.py` holds the single engine instance for all routers.

## Robustness guarantees

- **One SQLite connection policy** (`hmgfu/db.py`, Phase 72.6d): every store opens the database in WAL mode with a
  30 s busy timeout, so a long write on one connection makes another wait instead of failing with
  "database is locked". The `-wal/-shm` side files sit next to `hmgfu.db` and are gitignored.
- Nano output is parsed in three tolerant stages; on any failure a **deterministic heuristic
  fallback** extracts signals — ingestion never crashes because a 1.5B model rambled
  (every point records which `extractor` produced it).
- Energy propagation is **provably non-amplifying** (per-hop factor clamped ≤ 0.95).
- Decay never deletes: weak memories go **dormant** and re-awaken when their entities are
  mentioned again; well-connected hubs are exempt from dormancy (centrality guard).
- Contradiction losers are only auto-superseded by explicit user statements; everything else
  is surfaced as tension in the injected context.

## Contributing

Issues and pull requests are welcome. Two conventions this codebase keeps, both visible in the
history: a change starts with a test that fails for the reason being fixed, and no module grows past
400 lines (300 for the front end) — `tests/test_architecture.py` enforces the second one.

```bash
python -m pytest tests/ -q     # the whole suite runs without Ollama
```

## License

[MIT](LICENSE) © 2026 Selective.
