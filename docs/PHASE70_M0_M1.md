# Phase 70 — M0 + M1 of the improvement plan: immutable evidence, scoped authority

Date: 2026-09-05. Base: `8b1cc91` (Phase 69 + Codex's resumed audit). Branch: `phase70-authority-scope`.
Input: `docs/PHASE68_PLANO_MELHORIAS.md` (Codex's M0–M7) and `docs/PHASE69_REVALIDACAO_INDEPENDENTE.md`.
External gate: Codex's 35-check delta oracle (`scripts/audit_phase69_delta.py`), **3/35 → 22/22 accepted**; the
13 deferred checks belong to M2 (receipts), M3 (assertions) and M5 (target-bound claims) and are NOT claimed here.

## M0 — evidence you can trust

* Every bench and oracle run writes to `outputs/runs/<utc>-<sha7>/…` with a manifest (commit, branch, dirty flag,
  Ollama model digests, python, host, UTC). Legacy `--json` paths still work. Nothing is overwritten.
* `guard_scratch(db_path, workspace)` refuses the production database and the repo root before any bench engine is
  built (the Phase 69 live-replay incident can no longer happen from a bench).
* `import_pa3_user_facts --dry` copies the target to scratch first; a dry run never opens the real target.
* `scripts/run_oracles.py` runs the two frozen audit scripts unchanged and compares against
  `scripts/oracles/expected.json`: 51 accepted + 2 superseded (old pet slot) + 3 downgraded (semantic grounding) for
  the 56; 22 accepted + 13 deferred for the 35. Any accepted check failing is a regression (exit 1).
* `scripts/oracles/heldout_m1.json` — 14 shell strings and 11 multi-turn cases in eight families, written before
  the M1 code, run once by `scripts/run_heldout.py`. First run 24/25 (a fixture of mine carried a literal
  backslash-n instead of a newline, so the "materializer order" case ran with no code block and the "suggestion"
  case passed vacuously); after correcting only that encoding, 25/25.
* Evaluator integrity: `is_user_grounded` never accepts assistant/system/dream lines; `_present` rejects
  contractions ("isn't", "não é").

## M1 — authority is a record with a scope, not a boolean

`hmgfu/authority.py` (204 lines) is the one boundary. What changed against Phase 69:

| Codex finding | Phase 70 |
|---|---|
| resume minted `authorized=True` | authorization is a RECORD `{origin, message, turn_seq, at}` written only by the user's approval (or the user's own order for a model-declared plan); resume preserves it; a plan without a record is pinned "NONE ON RECORD" and only the user's yes activates it |
| "Do not create a widget. Just answer." still built | `speech_act.prohibits_effect` → `_turn_prohibited` closes authority regardless of router pins or keywords; forced actions are filtered through the boundary |
| read-only program list bypassed by `find -exec`, `xargs`, `awk`, `sed w`, git config/branch/tag/worktree, newline | `shell_is_read_only` is an allow-list GRAMMAR: one segment, known program, known flags, no redirection/substitution/pipe/newline; git read subcommands take no positional branch names; everything else is an effect; reads go through the native `list_files`/`read_file` |
| unknown skill presumed read-only | every builtin declares `x-effect` (none/read/external/write/shell); skills default to `unknown` = effect; the gog skill declares its seven tools |
| alias resolved after the guard | the tool loop resolves once and dispatches the resolved tool; the trace keeps `alias` |
| HTML materializer wrote silently | the materializer calls the boundary, then dispatches a real `write_file` through the registry and returns a trace entry (receipt) — or a blocked entry the say-do gate turns into a proposal |
| approval for A opens B | an approved plan authorizes the tools its steps name (and already used); when steps name files, `write_file` may only touch those files |
| cancellation capped at 160 chars | cancel words in the opening clause, or an explicit "cancel/abort … work/task/plan" anywhere |
| UI silent about who authorized | plan cards say awaiting your approval / approved by you / requested by you / unapproved — confirm first / cancelled, live and after restore |

A defect found by my own test on the way: on a shared database the semantic tool recovery learned `write_file` from an
earlier turn and the turn planner FORCED it on a suggestion turn. The guard held, but forcing what the boundary blocks
is contradictory; forced actions are now filtered through `effect_of` when effects are not allowed.

## Evidence

* Offline suite **467 passed**. Frozen oracles: contracts 51/51 accepted, delta **22/22 accepted** (3/35 → 22/35 with
  the oracle unchanged). Held-out 25/25 after one fixture-encoding correction (first run 24/25).
* Say-do **5/6 (window 3) / 5/6 (window 0)**, both claim classes 0. The two misses are M5 (a promise after the tool had
  already run) and M2 (the model's own `done` closed the plan early) — both deferred by design.
* Tool-precision 7/8 (nickname phrasing), answer grounding 1.00, no hallucinated tools, no unasked effects.
* Truth bench CONTEXT 16/17; PRECISION **0.515** — the metric no longer counts assistant echoes as grounding (M0.6), so
  the number dropped from 1.0 to the honest value; half of what recall returns for user questions is assistant-authored
  (an M6 finding).
* Live replay on the restarted server restated only the user's real values: proposal → "Sim, podes avançar." recorded as
  `user_approval` with those exact words → widget built; a prohibition turn ran no tools; a read turn used a read-only
  shell listing; the real ledger was verified unchanged.

## Open after Phase 70

M2 receipts per step (argument-bound evidence, partial failure, crash between effect and receipt), M3 assertions with
subject/relation/value/modality, M5 target-bound claims — Codex's plan, unchanged. The 13 deferred delta checks are the
gate for those phases.
