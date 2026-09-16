# P-AUDIT — Result (run 1)

Pre-registration: `docs/P_AUDIT_PREREG.md`. Beat sheet (committed before run): `scripts/paudit_beatsheet.json`.
Harness: `scripts/paudit_step.py` (live turns, throwaway DB, flag OFF) + `scripts/paudit_audit.py`.
Raw tagged log: `scratch/paudit_log.jsonl` (gitignored; the compact table below is the durable copy).
System under test = production config: chat `gemma4:12b`, grader `gemma-cpu:latest` (nano), embed `bge-m3`.

## Verdict: **FAIL — do NOT flip `HMGFU_REGULATOR_ENABLED`.**

| Metric | Result | Bar | Pass |
|--------|--------|-----|------|
| correction-recall | **4/15 = 0.267** | ≥ 0.90 | ❌ |
| ghost-corrections | **0** | ≤ 1 | ✅ |
| complete (39/39, no errors) | yes | — | ✅ |

### Recall by style
| style | recall |
|-------|--------|
| explicit | 1/4 = 0.25 |
| implicit | 1/4 = 0.25 |
| buried | **0/3 = 0.00** |
| mixed (PT/EN) | 2/4 = 0.50 |

### Correction beats (ground truth vs grader)
| beat | style | target | grader |
|------|-------|--------|--------|
| C1 | explicit | name Nelson→Nelito | miss |
| C2 | implicit | city Matola→Valencia cidade | miss |
| C3 | buried | job redes→suporte | miss |
| C4 | mixed | course março→maio | **DETECT** |
| C5 | explicit | job suporte→developer | miss |
| C6 | implicit | lang python→javascript | miss |
| C7 | buried | name spelling Nelito | miss |
| C8 | mixed | city→Matola | miss |
| C9 | explicit | course started→finished | miss |
| C10 | implicit | role→data engineer | miss |
| C11 | buried | work lang→SQL/Go | miss |
| C12 | mixed | course year→2023 | **DETECT** |
| C13 | explicit | home Matola vs work Valencia | **DETECT** |
| C14 | implicit | surname Machava→Vidal | **DETECT** |
| C15 | mixed | role→ML engineer | miss |

### Non-corrections: 0 false positives (0/10 ghost, 0/4 praise, 0/4 silence, 0/6 setup).

## Manual reading of disagreements (required by the pre-reg)
All 11 disagreements are false negatives; 0 false positives. In **every** missed correction the **chat
model's own reply proved it understood** the correction (e.g. C8 → "registrei que você mora na **Matola**
(e não em Valencia Cidade)"; C10 → "atualizei... você é um **Data Engineer**"; C5 → "Anotado: você é
**developer**"). So the miss is unambiguously the **grader** (gemma-cpu nano), not message ambiguity or
the grounding gate (the corrected value is in-message, so `_correction_grounded` would have passed had
the nano emitted a `user_correction`). The nano simply does not emit the correction label for most
dirty/PT corrections.

## Interpretation (honest)
- The Regulator **arithmetic** is proven (E.3) and its **false-positive** behavior is perfect here (0
  ghost-corrections — it never invents an absorbing signal on an "ah ok"/praise/silence). That is the
  *safe* direction and is good news for I1.
- But the **perception layer that feeds it is too weak**: the grader sees only 27% of corrections. With
  the flag ON, 73% of corrections would never fire the absorbing signal → superseded values keep being
  served (the exact failure P-AUDIT guards) AND the Regulator would be near-inert in practice. **Flip
  not justified.**
- Worst style = **buried** (0/3): a correction hidden mid-message in a long off-topic turn is invisible
  to the nano. Mixed/EN-cue helped only partially (2/4; "actually" in C4 detected, C15 missed).

## Next (Rule 13 — fix the RIGHT layer, then repeat with a NEW beat sheet; never tune this one, Rule 3)
The signal source is the weak link, not the arithmetic. Candidate fixes for the *next* iteration
(to be designed + pre-registered separately, not tuned against this sheet):
1. **Correction signal from the chat model, not the nano.** gemma4:12b understood 15/15; the correction
   is already "known" in the turn. Emit a structured correction signal from the chat turn (or a focused
   second pass on the strong model) instead of relying on the weak omnibus nano grade.
2. **A dedicated, PT-aware correction-detection prompt** with dirty/buried examples, separate from the
   omnibus grade prompt (which dilutes correction detection among memory/tool/score grading).
3. **A stronger grader model** for the correction field specifically.
Because the failure is *conservative* (misses, never invents), it is safe to keep the flag OFF while the
grader is improved — no poisoning risk in the meantime.
