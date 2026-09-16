# Phase 81 — Measurement fidelity (Codex review 2, P0)

> **Errata 2026-09-07 (Phase 87, Codex review 3).** The LongMemEval production-arm figures in this document were measured with the `nomic-embed-text` embedder (the throwaway engines' config default) while production embeds with `bge-m3` (live settings, 1024-d vectors). Relative comparisons between configurations on the same embedder stand; no absolute figure here describes production. The harness was fixed (`e538fde`) and the reserved read on the production embedder is in `docs/PHASE87_RULER_PRECISION.md`.

Date: 2026-09-06. Branch `phase81-measurement-fidelity` from `b7d7e9c` (Phase 80 closed; backup
`bk-20260906-1322-orig37-eff80-agi47-pre-phase81-codex-review2`). Plan committed before code (`f6cfdc7`).

## Origin

Codex's second review (`reports/phase80_critical_review_20260906/ANALISE_E_PLANO.md`) asked for the ruler to be proven
before any further optimisation. Every factual claim was verified in the code before adoption (ROADMAP Phase 81 header):
A1–A4 (truth core, Phase 82), A6 (the 77.2 harness let the ASSISTANT author user facts — my defect), A6b (the judge is
word presence), A7 (reproducibility gaps), A8 (`_kept_ids` is not the final context). This phase is P0: the ruler.

## 81.1 Harness fidelity (A6)

`bench_longmemeval_e2.py` now ingests a session the way the agent does (`ingest_session_like_agent`): user turns feed the
fact ledger (`facts.apply_all`, source `user_explicit`) and the user ingest; assistant turns go only through
`_store_assistant_reply` (never the ledger; production trivia and echo gates, the turn's own retrieval as echo reference).
Test `tests/test_v68_harness_fidelity.py`. The 77.2 and 78.4 prod figures are SUPERSEDED (kept in the record as "harness defect").

| arm (faithful harness, 20 / category, k 10) | knowledge-update | temporal | multi-session | ss-user | ss-assistant | preference | abstention |
|---|---|---|---|---|---|---|---|
| defaults (`evidence_81_1_lme_defaults.txt`) | **0.450** | 0.100 | 0.050 | 0.250 | 0.200 | 0.000 | 0.950 |
| 77.2 defective harness (assistant → ledger) | 0.300 | 0.050 | 0.000 | 0.300 | 0.200 | 0.000 | 0.950 |
| excerpt 480 (`evidence_81_1_lme_480.txt`) | **0.600** (b 3 / c 0) | 0.250 | 0.100 | 0.450 | 0.400 | 0.000 | 1.000 |
| 77.2 base scan (reference) | 0.700 | 0.450 | 0.300 | 0.800 | 0.550 | 0.000 | 1.000 |

Reading: the assistant-authored ledger lines were HURTING the defective run (conflicting "facts" in front of the reader);
the real production path reads higher on knowledge-update. The 78.4 excerpt comparison is re-read against 0.450, not 0.300. On the faithful harness the 480-char window gains in every answerable category with c = 0 losses over 140 paired items (`evidence_81_1_lme_pair.txt`): the 78.4 conclusion holds — measured one-click option, default unchanged by pre-registration; the gap to the base scan is the context policy.

## 81.2 Judge audit (A6b)

`scripts/oracles/judge_set_v1.json` — 66 author-labelled replies (plain, paraphrase, negated gold, contradiction,
self-correction, wrong, decline on answerable, number words, pure decline, decline + invention, assertion on abstention,
unlisted decline). `scripts/audit_judge.py` (`outputs/evidence_81_2_judge_audit.txt`):

| judge | agreement | failure modes |
|---|---|---|
| v1 (word presence + abstention cues) | 39/66 | negated golds 0/10; decline + invention 1/8 — Codex's two cases exactly |
| v2 (negation window 4 words; hedge after a cue ≠ decline; PT number words; cue list extended in-sample, declared) | 63/66 | 3 contradictions that name the gold and commit to another value — a lexical judge's limit |

Runs declare `LME_JUDGE=v1|v2`; the harness stores each reply with its gold and judge name per item; runs are never
re-scored silently. The 100-reply author adjudication happens on the next faithful run (the two 81.1 runs pre-date reply storage).

## 81.3 Reproducibility (A7)

`run_manifest` carries `dirty_diff_sha` and `settings_sha` (effective settings hash); `write_versioned` writes exclusive
folders `<utc>-<sha7>-<uid>` (mode `x`); `pct()` is nearest-rank, summaries report n / max / method; the latency summary
labels the effective tail mode. Tests `tests/test_v69_manifest.py`.

## 81.4 Reserved sets

**`write_set_v5`** — 300 PT/EN messages authored AFTER the v1–v4 fixes with new moulds (formal/casual introductions,
relocation verbs, job frames, every preference family, pets, family, links, correction sequences, negatives: questions,
third-party facts, hypotheticals, fiction, quotes, predicates, past tense; ambiguities). Sealed by commit `b81cc8d`
(sha256 `6f650db68e6b`), run ONCE (`outputs/evidence_81_4_write_set_v5.txt`, versioned `20260906T122709Z-b81cc8d-2d0dd6`):

| set | n | precision | coverage |
|---|---|---|---|
| v1–v4 (fitted in-sample over Phases 72–77) | 111 / 90 / 83 / 84 | 0.97–1.00 | 0.97–1.00 |
| **v5 reserved** | 300 | **0.727 [0.647, 0.805]** | **0.458 [0.380, 0.533]** |
| v5 en / pt | 153 / 147 | 0.800 / 0.651 | 0.505 / 0.410 |

This is the honest write-side figure; v1–v4 are regression sets from here on. Failure families (for the NEXT reserved set —
nothing is patched against v5): (i) the open-slot mould writes predicates as facts (14 false writes on negative items:
`open.battery: at 5 percent`, `pref.color: hard to describe`, `identity.name: unusual`, the neighbour's dog); (ii) value
boundary keeps the PT article or a trailing clause (12: `o índigo`, `um Toyota Hilux`, `Swift mostly`); (iii) unseen
moulds (introductions, relocation verbs, job and preference frames, colon lists); (iv) sequences keep the FIRST value;
(v) retirements clear nothing (7/7 failed: "we don't have a cat anymore", "já não trabalho na Vodacom", "don't call me Dudu").

**`decision_v1`** — 100 PT/EN turns whose ADMISSIBLE routing decisions were adjudicated by the author from the router
contract (any-of semantics, wildcards; never a model's output). `bench_router_agreement.py --oracle` judges it and refuses
`--record` on it; test `tests/test_v70_decision_set.py`. Sealed by commit `92859f4` (md5 `953fc3d0ed20`). The production
router (gemma4:12b) and the deterministic pre-router were measured ONCE against it after the GPU chain
(`outputs/evidence_81_4_decision_router.txt`, `_bypass.txt`):

| candidate | claimed | decision correctness | per field | latency |
|---|---|---|---|---|
| production router gemma4:12b | 100/100 | **0.940** | action 0.98 · tools 0.96 · act 1.00 · memory 0.98 · freshness / polarity / directive 1.00 | p50 1727 ms · p95 2469 ms |
| deterministic pre-router (`--bypass`) | 16/100 | 1.000 on claimed | all 1.00 | p50 0 ms |

The six router misses: two plain facts routed `needs_memory=false` (the ledger write is deterministic and unaffected), two
"note that / toma nota" statements routed as a `memory_search` action (a wasted call), one over-request (`list_files` with
`remove_widget`), one `memory_timeline` for "which files did we create yesterday" (defensible; recorded as a labelling limit —
the set is not loosened after the fact). This number is CORRECTNESS on unseen turns; Phase 79's "agreement 1.000" against the
model's own recorded routes was self-consistency.

## Closure

Percentages are re-read only from the corrected ruler: originality ~37 % (unchanged), efficiency ~80 % (no default
moved), AGI-memory readiness **~45 %** (from ~47: the write-side 1.000 credited in 77.5 was in-sample; the reserved
figure is 0.73 / 0.46). Next: Phase 82 (P1, truth and execution core) before any optimisation phase.
