# P-AUDIT-3 — Result (clause-partition + deferred GPU-free queue)

Three fronts (FRONT 0 nano-out / FRONT 1 buried clause-partition / FRONT 2 serialized queue), one
decisive run. Pre-reg: the P-AUDIT-3 `/goal` (ROADMAP). Beat sheet 3 (Zeca, buried ×7) committed before
the run: `scripts/paudit_beatsheet_3.json` + concrete `scripts/paudit3_turns.json`. Harness:
`scripts/paudit_run3.py` (Phase A retrieval+ingest nomic-only → real facts; Phase B detect-only gemma4).

## Verdict: **FAIL — do NOT flip.** (But the fronts worked; the residual is a *new* failure mode.)

| Metric | P-AUDIT-2 | **P-AUDIT-3** | bar | pass |
|--------|-----------|------|-----|------|
| correction-recall | 0.800 | **0.800 (12/15)** | ≥ 0.90 | ❌ |
| ghost-corrections | 0 (facts=[]) | **1 (real facts)** | ≤ 1 | ✅ (at the bar) |
| source fallbacks | 18/39 (contaminated) | **0 (clean)** | 0 | ✅ |

### Recall by style — buried nearly doubled
| style | P-AUDIT-2 | **P-AUDIT-3** |
|-------|-----------|------|
| explicit | 4/4 | 3/3 = 1.00 |
| implicit | 3/4 | 2/3 = 0.67 |
| **buried** | **1/3 = 0.33** | **5/7 = 0.71** ← FRONT 1 worked |
| mixed | 4/4 | 2/2 = 1.00 |

## What the fronts delivered (Rule 12 evidence)
- **FRONT 1 (clause partition) worked on BURIAL:** buried recall 0.33 → 0.71 on a larger (×7) buried
  sample. 5 of 7 buried corrections — hidden mid-way in long messages about rain/football/family/a
  trip — were caught by presenting the message as numbered clauses.
- **FRONT 2 (deferred GPU-free queue) SOLVED the contamination:** 0/38 source fallbacks (vs P-AUDIT-2's
  18/39 chat→nano). The separated phases (Phase A nomic-only retrieval, Phase B gemma4-only detection)
  removed the gemma4↔embedder residency conflict entirely — a fully clean, complete run.
- **FRONT 0 (nano out of the hot path when the flag is on):** implemented; flag-OFF unchanged.
- **Ghost with REAL facts-context = 1** (S4, a setup "o meu barco chama-se Estrela", flagged as a
  correction). The isolation's facts=[] had hidden this; with recalled facts present the detector
  over-fires on new-fact statements. Exactly at the ≤1 bar — a real precision watch-line.

## Autopsy of the misses (pre-registered on a buried fail) — NOT burial, a DIFFERENT form
FRONT 1 solved *burial* (the clauses were isolated); the three misses escape on **semantics**, not
position:
- **C12 (buried) — a CLARIFICATION:** "…só pra esclarecer, eu moro em nicoadala mas a banca é em
  quelimane, são coisas diferentes…". Phrased as disambiguation ("just to clarify, X and Y are
  different"), not a replacement — the detector reads it as re-stating two facts, not changing one.
- **C15 (buried) — a REFINEMENT/qualifier:** "…por sinal a banca afinal não é só minha, sou sócio com o
  meu irmão…". A partial correction ("not ONLY mine, I'm a partner") — adding a qualifier reads as new
  info, not a value replacement.
- **C3 (implicit) — a preference shift against an UNRECORDED prior:** "na verdade agora sou mais do
  textáfrica, o ferroviário desiludiu-me". No team was ever planted, so there is no recorded fact to
  contradict; the detector sees a new preference, not a correction.

**Finding:** the residual failure is the **correction-vs-clarification/refinement/new-preference**
distinction, NOT burial. A 4th iteration (if pursued — a separate `/goal`, never tuning this beat sheet)
targets THAT: teach the detector that a clarification/qualifier/preference-shift that alters what was (or
would have been) recorded is still a correction. Beat-sheet note: C12 vs C13 name different work cities
(authoring slip); both remain valid single-turn correction signals, so it doesn't affect the count.

## Reply non-regression + production untouched
Reply non-regression holds by construction (unchanged from P-AUDIT-2: the correction is a separate,
now-deferred call; the reply is finalized before grade_turn). `HMGFU_CHAT_CORRECTION_SIGNAL` stays OFF;
production is byte-identical (flag-OFF branch = the unchanged nano path). The failure is CONSERVATIVE on
recall (a missed correction just leaves the old value un-superseded — no poisoning).

## Design decision to record in THEORY_V3 B.5
The implementation that survives is the **focused, DEFERRED, serialized second call** on the strong
chat model — NOT B.5's literal single-call "answer + classification" contract. Evidence: (1) a separate
call leaves the reply byte-identical (no answer-quality regression, which the single-call contract
risks); (2) deferring it to a GPU-free queue removed the VRAM thrash that a co-resident call caused
(0 fallbacks vs 18/39). The perception is not yet at 0.90, but the *architecture* is settled.
