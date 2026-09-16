# P-AUDIT — Synthetic Perception Audit of the Grader (PRE-REGISTERED)

> Written and committed **before** the first run (Rules 3/6). Renamed from "E.4-live" to **P-AUDIT** to
> undo the name collision with THEORY_V3's E.4 (typed-port routing / H-route), which is unrelated.
> This is the **flip precondition** for `HMGFU_REGULATOR_ENABLED`.

## Why P-AUDIT exists (what changed vs E.3)

E.3 proved **mechanism-validity**: the I1 arithmetic is correct and non-vacuous — but with **perfect
signal labels by construction**. Live, the labels come from the **grader** (gemma-cpu nano), which can
mislabel: miss an implicit/PT correction, or read an "ah ok" as a confirmation. **The arithmetic is
proven; the PERCEPTION layer that feeds it is the weak link.** P-AUDIT measures that layer directly.

The Invariant's asymmetry sets the risk profile: erring **toward not-promoting** (missing a praise /
silent signal) is *safe* — the caps bound it. Erring **on a correction** (missing it, or inventing one)
is the *danger* — the absorbing signal has **no undo**. So the bars are strict on the dangerous
direction (correction recall high, ghost corrections ~zero).

## Ecological caveat (stated up front)

Trailblazer can't be at the machine, so the "user" is **simulated** (Claude — a stronger model than
gemma — playing Trailblazer). This is a **synthetic** audit: it stresses the grader with realistic
dirty input under a crisp ground truth, but it is **not** a sample of real users. A passing P-AUDIT
authorizes the flip **with a post-flip observation window** (log the first N real turns for Trailblazer
spot-audit); it does not replace real-world validation.

## Method

### Simulated user (live, interactive)
Claude (this agent) plays Trailblazer live, reading each real system reply and adapting the next
message, **bound to a committed beat sheet** (`scripts/paudit_beatsheet.json`). Hard rules:
- The beat sheet fixes the **signal sequence**; the simulator **never adds or removes a signal beat**.
- Each turn is expressed **faithfully** to its committed signal (a correction beat is a genuine
  correction; a ghost beat is genuinely ambiguous-not-a-correction) — no softening a correction or
  sharpening a ghost to game the grader.
- Language is **mandatorily dirty**: typos, Valencia slang, short messages, PT/EN code-switch. This makes
  the grader's job *harder* (the point).
- Each turn is tagged with its **beat-id** in a separate log (`scratch/paudit_log.jsonl`) the grader
  **never** sees. Ground truth = the beat sheet, not anyone's interpretation.

### Beat sheet (committed quotas — see `scripts/paudit_beatsheet.json`)
≥15 correction events across 4 styles (explicit 4 · implicit 4 · buried 3 · mixed PT/EN 4); ≥10
ghost-bait turns (ambiguous non-corrections: "ah ok", "certo…", "hmm", "se tu o dizes"); genuine praise
(4) and silence/filler (4) interspersed; setups (6) that plant the facts later corrected.

### What is measured
Per turn, `engine.agent_chat(msg)` returns `result["grade"]["correction"]` — `None`, or
`{ingested, conflicts_marked}` when the grader detected+applied a grounded correction. That non-None is
the grader's **"this turn is a correction"** label. Correction detection runs **regardless** of
`REGULATOR_ENABLED` (grader.py:102), so the flag stays **OFF** (shadow).

## Measurement — two directions, PRE-COMMITTED bars

| Metric | Definition | Bar |
|--------|-----------|-----|
| **correction-recall** | detected / total, over beat-sheet correction beats | **>= 0.90** |
| **ghost-corrections** | # non-correction beats the grader flagged as correction (absorbing, no undo) | **<= 1** |

Also report the **full matrix by correction style** — a passing global recall can hide "all implicits
failed". And the false-positive breakdown by non-correction kind (ghost/praise/silence).

## Audit procedure
Automatic beat-id vs grader-label comparison, turn by turn (`scripts/paudit_audit.py`), **plus manual
reading of every disagreement** (missed corrections + ghost hits). Evidence = the matrix + the tagged
log (`scratch/paudit_log.jsonl`) + the transcript.

## Guards (chosen + documented)
- **Production untouched:** run on a **throwaway DB** in `scratch/` (`AgentEngine(db_path=...)`), NOT
  production `hmgfu.db`. (Flag-OFF alone is insufficient — `_apply_correction` ingests/supersedes in
  the graph regardless of the flag, so it would mutate production; the throwaway DB is the real
  isolation. `paudit_step.py` HARD-REFUSES if `--db` resolves to the production DB.)
- Beat sheet committed **before** the first run. One session, one measurement.
- Everything in `ROADMAP.md` with evidence.

## Decision rule (pre-registered)
- **Both bars pass** (recall >= 0.90 AND ghost <= 1, no missing/errored beats) -> **flip
  `HMGFU_REGULATOR_ENABLED` AUTHORIZED**, with a post-flip observation window (log the first N real
  turns for Trailblazer's spot-audit).
- **Any bar fails** -> do **not** flip. The next problem is the **grader's signal classification** — fix
  at that layer (Rule 13), then **repeat P-AUDIT with a NEW beat sheet** (never tune against the failed
  script, Rule 3).

## Anti-tuning commitment
The beat sheet, both bars, and the decision rule are fixed by this document + `paudit_beatsheet.json`,
committed **before** any turn is graded. No adjustment after seeing the matrix.
