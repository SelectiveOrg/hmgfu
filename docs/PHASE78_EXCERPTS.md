# Phase 78 — Long-form excerpt policy

> **Errata 2026-09-07 (Phase 87, Codex review 3).** The LongMemEval production-arm figures in this document were measured with the `nomic-embed-text` embedder (the throwaway engines' config default) while production embeds with `bge-m3` (live settings, 1024-d vectors). Relative comparisons between configurations on the same embedder stand; no absolute figure here describes production. The harness was fixed (`e538fde`) and the reserved read on the production embedder is in `docs/PHASE87_RULER_PRECISION.md`.

Date: 2026-09-06. Branch `phase78-long-form-excerpts` from `e833730` (Phase 77 closed; backup
`bk-20260906-0654-orig37-eff80-agi47-phase77-closed`). Plan committed before code (`230ad36`).

## Origin (the 77.2 attribution)

On the LongMemEval sample the production path read far below a plain top-10 scan of full turns in every answerable
category, in both retrieval modes. The deterministic attribution charged the loss to the CONTEXT POLICY after retrieval,
not to retrieval: production retrieval found the gold about as often as the scan; `organise_for_injection` then cut every
memory to its first 200 characters (user) or to the nano summary / 160 characters (others), and on a user-fact question
dropped every assistant-authored memory (the 73.3 echo guard). The injected context was about five times shorter than the
base arm's.

## What changed (78.2 / 78.3), all behind settings whose defaults reproduce today's output

- `hmgfu/context_render.py` (new; the section order and the greedy renderer moved out of `retrieve.py` verbatim at the
  400-line ceiling): `excerpt_for_query(text, query, max_chars)` returns the contiguous sentence window that shares the most
  salient words with the question, grown greedily around the best sentence up to the budget, "…" at a cut; with no overlap
  the head is kept. `is_echo(point, query, ledger_pairs)` is true when an assistant memory restates a ledger value of an
  attribute the question names.
- `organise_for_injection` / `build_llm_context` take `query`, `excerpt_chars`, `echo_scope`, `echo_pairs`; the production
  sites (agent turn, plain chat, `/api/retrieve`) and the production-path benches pass them from settings.
- Settings (visible in Settings → Memory recall): `excerpt_max_chars` (default **200** = today's head cut, range 120–2000)
  and `echo_guard_scope` (`all` = today; `echoes` = drop only the restatements). Candidate under measurement: 480 + echoes.
- Gate benches take `--excerpt` / `--echo-scope` on the clone; the LME harness and the attribution script take
  `LME_EXCERPT` / `LME_ECHO_SCOPE`. `scripts/derive_lme_pair.py` pairs two per-item files (McNemar per category).

## Pre-registered gates (ROADMAP Phase 78)

G1 truth no-echo held (CONTEXT 17/17, precision 1.0); G2 relational Hit@12 ≥ 0.717 both modes; G3a attribution keeps
≥ 90 % of what retrieval found per category; G3b LME prod paired vs the 77.2 run: knowledge-update ≥ 0.55 with b > c and
no category net < −1; G4 gate set alone + latency within 10 %. Defaults move only if all pass.

## Measurements

| gate | result |
|---|---|
| G1 truth no-echo, window-only (480 / all) | CONTEXT 17/17 · precision 29/29 = 1.0 · current 1.0 — **met**; defaults 30/30 = 1.0 (after an instrument fix: precision over the memories the builder keeps) |
| G1 with `echo_guard_scope = echoes` | CONTEXT 17/17 but precision 62/118 = 0.525 on the live corpus — **fails**; the scope stays `all` |
| G2 relational, all arms at 480 | Hit@12 0.717 everywhere, context truth identical to 77.1, stale leakage slightly lower — **met** |
| G3a attribution (retention of what retrieval found) | 0.86 · 1.00 · 0.75 · 0.80 · 0.75 vs the 0.90 bar — **not met**; today 0.57 · 0.60 · 0.50 · 0.47 · 0.50; residue = the 1800-token budget (4 items), one correct stale exclusion, two coincidental gold matches on aggregation questions, one window-choice limit |
| G3b LongMemEval, prod at 480 paired vs 77.2 | knowledge-update 0.300 → **0.550** (b 7 / c 2), temporal 0.05 → 0.25, multi-session 0.00 → 0.15, single-session-user 0.30 → 0.45, single-session-assistant 0.20 → 0.35, abstention 0.95 = 0.95 — **met** |
| G4 gate set at defaults, alone | say-do 6/6 · 6/6 · 6/6; tool precision 8/8 ×3 (grounded 1.0, hallucinated 0); held-out 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles 51/51 · 33/33; latency p50 5.6 s · p95 9.4 s (73 close: 5.8 s) — **met** |

Two defects were caught by the pre-registered checks and fixed at their layer before any conclusion: the setting's
default 200 rendered the span (now 0 = off, byte-identical), and the truth bench's precision counted an unfiltered list
after the bench's own pre-filter was removed (now measured over the builder's kept memories). The 800-char window buys one
item for +40 % context; 480 stays the candidate.

## Decision

By the gates, as pre-registered: **the default does not move** (`excerpt_max_chars` 0, `echo_guard_scope` all). Three
gates pass; G3a fails on a bar set before knowing that the residue is the token budget, and the phase wrote down before
the LME run that the external reading could not rescue it. The evidence for the user's own decision: a 480-character
query-matched window improves the external reading in every answerable category, holds the truth set, relational recall
and context truth, and costs about 60 % more context characters per turn. It is one reversible setting in Settings →
Memory recall. `echoes` is not recommended (fails G1 on the live corpus).
