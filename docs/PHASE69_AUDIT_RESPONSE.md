# Phase 69 — Response to the Phase 68 re-audit

Date: 2026-09-05. Base: `04fc9ba` (end of Phase 67). Branch: `phase69-audit-response`.
Input: Codex's independent re-audit `docs/PHASE68_REAUDITORIA.md` and its deterministic oracle
`scripts/audit_phase68_contracts.py` (56 checks), the live-model runs in `outputs/phase68_live_*.json`, and the UI
reducer oracle `scripts/audit_phase68_ui.cjs` (4 checks). Codex stopped at 00:40 on a usage limit with 68.5, 68.6,
68.8 and 68.9 open; its promised improvement plan was never written. The plan below is mine, and every fix was
verified against Codex's oracle as an **external** check I did not write.

## 1. Independent verdict on the 44 failing checks

I re-ran the oracle on `04fc9ba` first: **12/56, reproduced exactly** (it is deterministic: FactStore cases, fake-provider
full turns, pure-function probes). Then each failing row was judged on its own merits:

| Verdict | Count | Which |
|---|---|---|
| Accepted as a real contract gap | 36 | everything below in sections 2–6 |
| Downgraded (limit of a lexical gate; documented, not fixed) | 3 | `grounding_entity_binding`, `grounding_small_number`, `grounding_unknown_entity` |
| Schema decision (species pet slots; Codex's own `two_pets` asked for them) | 2 | `multi_en`, `pet_selector_preserves_cat` now "fail" only because the oracle still expects the old single slot |
| Benchmark-oracle defects (fixed in the benches) | 3 | `benchmark_failed_search_not_success`, `benchmark_negation_53/55` |

Two findings of my own from Codex's live turns (`outputs/phase68_live_memory.json`), not in his list:

* the say-do gate manufactured absurd **proposals on plain memory acknowledgements** — "I've noted your name… I'll
  make sure to remember" became a "proposed" plan whose title was the reply sentence. A promise about remembering is
  fulfilled by the memory write side, never by a tool; it is not an intent.
* "**Sim, podes avançar.**" was not recognised as approval (the yes-regex required the message to end right after
  the yes-word).

## 2. The one design rule behind every fix

**Authority and truth are turn state and evidence — never a phrase in the reply.** Codex's strongest point (F03) was
that heuristics were scattered: the effect list disagreed between modules, the alias resolver ran after the guard,
a model-declared plan reopened the gate, the code-block materializer wrote files with an empty tool trace. Phase 69
puts one module in charge and makes every other path ask it.

## 3. What changed, by finding

| Finding | Fix (module) | Evidence |
|---|---|---|
| F03 authority bypasses | `hmgfu/authority.py`: canonical `SIDE_EFFECT_TOOLS`, `resolve_name` before the check, fail-closed `shell_is_mutating` (known read-only programs and git read-only subcommands pass; everything else confirms), `effect_authorized` (user request or a **user-approved** plan; `plan["authorized"]`), `guard`. Wired into the tool loop, `plan_task`, `session_plans`, the HTML materializer, say-do and both benches. | `tests/test_v39_authority.py` (6); oracle: alias, bash, model plan, materializer all pass |
| F04 plan truth | `_CANCEL` abandons an active plan; `step_evidence` (the step's named tool, else a non-plan non-read-only tool); `update_plan(done)` needs executed work since the last completion (`engine._turn_work`) — closes 67.16; all-failed plans finalize as `failed`; `_YES` accepts "Sim, podes avançar" | `tests/test_v40_plan_truth.py` (5) |
| F05/F06 claims and grounding | `exec_claims` typed (remove/create/update/memory; first-person, passive, PT, coordinated verbs) and `_supported` per class from `transactions_of` (facts, retractions, effects, remove-effects, episode); failed/blocked tools are not action; memory promises are not intents; grounding runs on the **final** reply after the say-do rerun; a number carries its unit ("26%" does not ground "26°C") | `tests/test_v41_saydo_claims.py` (5) |
| F01/F02 write side | `hmgfu/utterance.py` `declarative_text` (per-sentence vetoes: questions, quoted speech, hypotheticals, past/dated); compound values survive; `pet.dog.name`/`pet.cat.name` (+`pet.name` kept); last-wins per slot; update form binds only to a fitting subject ("new recipe: URL" → `open.recipe`); attribute-aware supersession ("my car is blue" survives a colour change); cleared values demote their evidence; mapper `relation_conflict`; PT "a minha X favorita é Y" | `tests/test_v42_write_side.py` (8) |
| F07/F08 provenance, lifecycle | `directive_tombstones` (a retired rule is never resurrected at startup; only the user's restatement lifts it); `migrate_tool_rules` never overwrites a live directive; session delete cascades to its plan; recall returns raw `content` with `derived_summary` only for non-user points; canonical facts on empty retrieval; legacy `chat()` applies the same ledger | `tests/test_v43_lifecycle.py` (5) |
| F09 arguments, UI | explicit place and relative time preserved in search completion ("tomorrow" → tomorrow's date); widget grounding adds only missing values; `saydo`/`grounding` events rendered (`VerifyPill`), history restore keeps `blocked` and the self-grade | `tests/test_v44_args_benches.py`; UI oracle 0/4 → 4/4 |
| F10 benchmark validity | a failed search is never success; `_present` judges the whole clause; `is_user_grounded` drops the bare-digit rule | `tests/test_v44_args_benches.py` |

## 4. Evidence

* External contract oracle (Codex's script, unchanged): **12/56 → 51/56**; the five left are the documented ones above.
* External UI oracle: **0/4 → 4/4**.
* Offline suite **452 passed**; say-do **6/6 (window 3) / 5/6 (window 0)**, both claim classes 0; tool-precision
  **8/8, answer grounding 1.00**; truth bench **16/17, precision 1.0** (= Phase 67 baseline). Two regressions of my own
  were caught by the benches and fixed (JSON-escaped units in evidence; a clause splitter cutting dotted values).
* Live replay on the restarted server: suggestion blocked and proposed, "Sim, podes avançar" approved, widget built
  with the real link, quoted third-person name vetoed. One incident: a write-side probe changed the user's real home
  city; rolled back at once with an audit row. Live replays must restate only the user's real values.

## 5. What stays open

* Semantic grounding (entity/unit binding across sentences, unknown-name claims) is beyond a lexical gate; the honest
  next step is a small verifier model behind the same `verify_grounding` seam, measured on a held-out set.
* Codex's live diagnostics (`scripts/audit_phase68_live.py`) were not re-run here; the deterministic oracle covers the
  contract layer, the say-do/tool/truth benches cover the live layer.
* Codex's 68.5 retrieval diagnostic and 68.6 sweeps never completed; nothing here claims them.
