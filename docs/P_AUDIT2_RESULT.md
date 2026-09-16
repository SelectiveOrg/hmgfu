# P-AUDIT-2 — Result (chat-perceiver correction signal, THEORY_V3 B.5)

Fix (Rule 13): the correction signal now comes from the STRONG chat model (`gemma4:12b`) via
schema-constrained decoding (`grader._detect_correction_via_chat`, gated on `CHAT_CORRECTION_SIGNAL`,
disabled on action turns, nano = fallback), because P-AUDIT run 1 showed the `gemma-cpu` nano missed
73% of corrections the chat model understood. Pre-reg: `docs/P_AUDIT_PREREG.md`. NEW beat sheet
(committed before the run): `scripts/paudit_beatsheet_2.json` (Betinho persona).

## Verdict: **FAIL — do NOT flip `HMGFU_REGULATOR_ENABLED`.** (But a 3× improvement.)

| Metric | run 1 (nano) | **P-AUDIT-2 (chat)** | bar | pass |
|--------|------|------|-----|------|
| correction-recall | 0.267 | **0.800 (12/15)** | ≥ 0.90 | ❌ |
| ghost-corrections | 0 | **0** | ≤ 1 | ✅ |

### Recall by style — the autopsy
| style | run 1 | **P-AUDIT-2** |
|-------|-------|------|
| explicit | 1/4 | **4/4 = 1.00** |
| implicit | 1/4 | **3/4 = 0.75** |
| buried | 0/3 | **1/3 = 0.33** ← the residual failure |
| mixed (PT/EN) | 2/4 | **4/4 = 1.00** |

**Misses:** C7 (buried — name spelling hidden in a Chimoio-trip message), C11 (buried — "frota de
camiões" hidden in a family message), C6 (implicit — "na real prefiro carne"). C3 (buried — despachante
in a rain/football message) WAS caught. So the strong perceiver solves explicit+mixed entirely and most
implicit, but a correction **buried deep in a long off-topic message** still evades it — the detector
weights the surface topic. This is the single, specific failure mode to attack in a 3rd iteration.

## How this was measured (honest — Rule 12)
- The intended FULL-TURN run (`paudit_step.py`, flag ON, 39 live turns) was **VRAM-contaminated**: the
  extra `gemma4:12b` correction call under 4-model pressure intermittently thrashed the embedder out of
  VRAM and fell back to the nano (**18/39 turns**, degrading over the run). The `correction_source` field
  exposed this; the source-aware auditor flagged it INCONCLUSIVE.
- Root cause (Rule 2): the full-turn path juggles gemma4(reply) + embedder + gemma-cpu(grade) +
  gemma4(correction); over a long run that juggling thrashes. Fixes that helped but didn't fully cure it:
  patient retry (4×/~9s), free the nano sensitizer (~2 GB), one-process run.
- **Clean measurement (`paudit_isolate.py`):** the thing under test is only
  `_detect_correction_via_chat` + `_correction_grounded`. Calling it directly per beat (ONE gemma4 call
  each, no embedder/reply/grade churn → gemma4 stays resident) ran **0 errors, fully stable**, fed the
  real logged messages + replies. This measures the exact decision function without the infra noise.
- **Caveat on the ghost number:** the isolation used facts-context `[]`. The live system (with recalled
  facts) showed transient false positives on setups (S2/S4) in earlier attempts, though the clean
  one-process full run AND the isolation both showed **0** setup false-positives. So ghost = 0 is the
  clean-measure result with a noted context-sensitivity; it is **not** decision-relevant here because
  recall already fails the 0.90 bar.

## Reply non-regression (Rule 12) — holds by construction
The reply is finalized in `tool_loop` (agent.py:292) and emitted BEFORE `grade_turn` runs (agent.py:334);
the correction call lives INSIDE `grade_turn`, gated by the flag. So the flag **cannot** change the reply
— the reply path is byte-identical flag on/off (the 295-passed suite runs with the flag OFF). The cost of
the fix is **+1 gemma call/turn of latency** (post-turn, advisory — it does not block the user's reply),
not reply quality. This is why the focused-second-call design was chosen over B.5's literal single-call
contract (which would fold the reply into the constrained JSON and risk degrading it).

## Decision (pre-registered)
Recall 0.80 < 0.90 → **FAIL → do NOT flip.** Per the pre-reg, a per-style autopsy precedes any 3rd
iteration (done above: BURIED is the failure). A 3rd iteration — if pursued — targets buried corrections
specifically (e.g., a detector instructed/structured to scan a long message for ANY fact-change clause
regardless of surrounding topic, or a sentence-split pre-pass), then re-runs P-AUDIT with a NEW beat
sheet (never tune this one, Rule 3). The Regulator stays OFF; the failure remains CONSERVATIVE for the
recall side (a missed buried correction just means the old value isn't superseded — no poisoning).
