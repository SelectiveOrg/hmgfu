# Phase 82 — Truth and execution core (Codex review 2, P1)

Date: 2026-09-06. Branch `phase82-truth-core` from `4d14b63` (Phase 81 closed; backup
`bk-20260906-1312-orig37-eff80-agi45-phase81-closed`). Plan committed with Phase 81's (`f6cfdc7`), before code.

## Origin

Codex's second review, after the ruler (Phase 81): A1 retraction by bare value across entities, A2 two commits on two
connections with no known-time axis, A4 assertions without an episode and with a cut span, A3 receipts that check a
basename and existence. Each item was built failing-test-first; the phase closes on a deterministic adversarial suite.

## 82.1 Scoped retraction (A1)

A user named Bento with a dog named Bento lost their name when "my dog is Teca, not Bento" retired the dog: the canonical
sweep was family-scoped, the assertion retraction was by value across every entity and relation. `AssertionStore.retract`
gained `relation_prefix`; `_retract_named` now retracts within the SAME base slot plus the legacy species-less `pet.name`
(82.5 found that `pet.%` still crossed species: dog Bento's correction retired cat Bento). Tests `tests/test_v71_scoped_retraction.py`.

## 82.2 One durable revision (A2)

`AssertionStore(conn=)` writes on the FactStore's own connection and never commits; `FactStore._apply_one` wraps the
canonical row, the history row and the assertion in ONE transaction with rollback on any exception. Construction
reconciles the two views and REPORTS (`store.reconcile_report`: backfilled, orphaned, relinked) — `hmgfu/fact_reconcile.py`.
`active(at=, known_at=)`: valid time and known time answer differently (valid since 2020, recorded today: holds at 2021,
not known at 2021). Replaced values stay as `superseded` in history, never overwritten. Tests `tests/test_v72_one_revision.py`
(fault injection included).

## 82.3 Exact provenance (A4)

Assertions carry `source_episode` (the ingested point id — `link_source` links the assertion, not only the canonical
projection) and `span_start/span_end`, the exact offsets of the value in the ORIGINAL message (None when the value is not
verbatim — never a guess); `source_span` is the whole message (4000 cap, was a 300-char cut). Legacy assertions take the
episode their canonical row recorded at write time. Live clone: 9 active assertions, 2 linkable from real turn ids, 7 with
spans — the rest carry no turn id anywhere; from this phase every assertion written on the agent path links (100 % in the
suite). Tests `tests/test_v73_provenance.py`.

## 82.4 Receipts prove the requested outcome (A3)

| blocked case | before | after |
|---|---|---|
| `new/report.md` requested, `old/report.md` written | proven (basename) | not proven: the requested path keeps its directory (`norm_path`, `_same_file`) |
| content changed after the receipt | proven (exists) | not proven: on-disk sha256 must equal the receipt's observed hash |
| receipt without a hash | proven | UNKNOWN, not done |
| widget `Budget` requested, `Links` touched | proven (any widget) | not proven: a named widget must be the one touched (id or args) |
| a read receipt carrying the file's hash for a write step | **proven** (Codex's exact case) | not proven: only non-read receipts prove file steps |

Kept and said plainly: a generic step ("verify the result") is still proven by any successful action, reads included;
a bare basename request accepts the file wherever it was written. `session_plans.step_evidence` uses the same matcher
(one matcher, Rule 5). Runbooks learn only from plans whose steps passed this verification. Tests `tests/test_v74_receipts_prove.py`.

## 82.5 Adversarial suite

`scripts/bench_truth_core.py` — 390 deterministic cases, no model, throwaway DBs, versioned output
(`outputs/evidence_82_5_truth_core.txt`):

| family | cases | first run | after the two fixes |
|---|---|---|---|
| A scoped retraction (5 families × 6 shared names × 3 negation slots × EN/PT) | 144 | 132 — dog Bento's correction retired cat Bento | **144** |
| B correction sequences (colour ×3, city ×2, EN/PT) | 36 | 36 | **36** |
| C provenance on the agent-like path | 12 | 1 — accented values never linked | **12** |
| D fault injection (every step × assert / retract) | 34 | 34 | **34** |
| E receipts (5 directories × 4 files; changed, no hash, read-for-write; widgets) | 164 | 164 | **164** |

Gates: undue changes **0**, provenance **100 %**, every injected interruption recovers a consistent revision, receipts
**100 %**. The two first-run defects were real: the species-crossing sweep, and SQLite's `lower()` folding ASCII only —
`Élio`, `Íris` never matched Python's fold in retract / supersede / link (a latent PT defect since Phase 72). Both fixed
at the cause, tests added, suite re-run.

## Closure

Suite 615 passed; sealed write sets v1–v4 unchanged (0.966 / 0.986 / 1.000 / 1.000; v5 is reserved and NOT re-run);
held-out m1–m5 25/25 · 6/7 · 13/13 · 28/28 · 18/18; oracles contracts 51/56 (accepted 51/51) · delta 33/35 (accepted 33/33). Percentages: originality ~37 % (unchanged), efficiency
~80 % (no default moved), AGI-memory readiness **~45 → ~50 %**: the truth core now holds under an adversarial deterministic
suite (one durable revision, scoped retraction, exact provenance, receipts that prove the requested outcome) — the integrity
properties Codex listed as missing are built and measured; the write-side coverage on unseen messages (0.46) is what still
keeps the figure far from 75.
