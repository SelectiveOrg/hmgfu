# PA3 → HMG-Fu v2: what we copy, simplify, and refuse to repeat

Source: `PriorAgent/project_arq/` (12-area architecture map) + read-only inspection of
`data/agent.db`. PA3 stays untouched; this repo re-implements the *concepts*, smaller.

## What we copy (proven in PA3)

| PA3 mechanism | Here |
|---|---|
| One dispatch entry point for tools, every hook fail-soft, results = JSON strings | `toolsys.execute_tool` |
| `classify_tool_result` — `blocked:true` is NOT a failure; guards armed only on real failures | `agent.py` |
| 2-strike per-tool block per turn + stuck-loop signature detection + forced finalization | `agent.py` loop guards |
| Turn grading with selectable producer (`TURN_CLASSIFIER` nano vs main) + grader card to UI | `grader.py` + settings |
| Usefulness EMA on recalled memories (cited=1.0 / implied=0.6 / unused=0.0) feeding rank | grader → `utility` EMA → ρ |
| Deterministic explicit-correction fast-path BEFORE the flaky grader | contradiction/supersede path on `user_explicit` ingest |
| Provider abstraction with per-role routing (`NANO_*_PROVIDER/MODEL` cascades) | `providers.py` + `settings.py` roles |
| Skills = `skills/*.py` exporting `TOOLS` + `execute()`, AST-validated install (`learn_skill`) | `create_skill` tool |
| Recall degrades, never blocks; memory writes never break the turn | already v1 invariants |
| Windows: subprocess via `subprocess.run` in `asyncio.to_thread` (uvicorn SelectorEventLoop) | `toolsys.bash` |

## What we simplify (HMG-Fu-native replacements)

- **Tool/skill selection**: PA3 needed `tool_gallery` categories + neural classifier + `skill_gallery`
  + skill-doc inject/enforce (+ 4 discovery meta-tools) to pick ~22 of 60 schemas. Here, **tools and
  skills are MemoryPoints** (`type="skill"`) in the same hex grid: selection = the same 6-channel
  retrieval + activation score; usage builds Fu edges tool↔topic; grading tunes tool utility. One
  mechanism instead of five.
- **Fact supersession**: PA3 has `hmg_fact_statements` chains + `entity_facts` cache +
  `reconcile_conflicting_concepts` fighting key fragmentation. Here contradiction detection +
  `infer_resolution` (tension edges, explicit-user supersede) is the single path — no second cache.
- **Prompt building**: PA3 v2 has ~11 section classes recomposed every tool round. Here: one
  injection renderer (§23) + tool list; recomposed once per turn, not per tool round.
- **Providers**: same StreamChunk idea reduced to `chat()` (+ later `stream()`); unknown provider
  name FAILS loudly (PA3 silently defaulted to Anthropic — lesson 9).
- **Connectors**: registry + AES-encrypted vault + status only; OAuth broker deferred until needed.

## What we refuse to repeat (PA3's own tech-debt list)

1. Serial nano tax on the critical path (recall+supervisor+executive ≈ 8–11 s pre-stream) —
   here the only pre-stream model call is the sensitizer extract (1 nano call) + 1 embed; grading is post-turn.
2. 4,800-line conductor (`ws_handler`) — hard ceiling: no module here grows past ~400 lines; the
   agent loop is its own file with one responsibility.
3. Two-of-everything (prompt v1+v2, dual connector APIs, dual node stores) — one implementation per concern.
4. Polluted flat caches (`entity_facts` marker-values) — no last-write-wins cache, period.
5. 110 DB tables / ~250 config flags — we stay at 5 tables and one config module.
6. Silent provider default on typo — explicit error instead.
7. Grader landing one turn late *and being relied on next turn* — our grader output is advisory
   (EMA + patterns); nothing on the next turn's critical path depends on it.
8. Skill-doc over-forcing (tools commanded on trivial prompts) — tool points compete on activation
   score like any memory; nothing is force-injected.
9. Per-turn tool schema payload bloat (~12k chars for "hi") — top-K tool points only (default 8) +
   `tool_search` meta-tool as the escape hatch.
10. No test suite — v2 ships with tests like v1 (38 green so far).

## Import decision (agent.db → this graph)

- **Gold**: `hmg_fact_statements` LIVE rows (302) → `type=fact`, layer `L3_identity`,
  source `user_correction→user_explicit`, `llm_curator→assistant`, else `system`.
- **Good**: `hmg_nodes` active, `memory_kind ∈ {fact, preference, identity, directive}` (~870).
- **Optional** (`--include-declarative`): active declarative nodes with `importance ≥ 0.7`.
- **Dropped**: chat/session noise, `entity_facts` (distrusted by PA3's own docs), all PA3 edges
  (Fu edges are rebuilt natively on ingest + dream), hash-64/hash-1024 embeddings (junk),
  mxbai-1024 embeddings (dimension mismatch with nomic-768 — everything is re-embedded).
- Idempotent: each imported point carries `pa3:<table>:<id>` in keywords; re-runs skip existing.
