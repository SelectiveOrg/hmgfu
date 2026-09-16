# P-AUDIT-3b — Result: the flip is WON (both bars pass on a clean run)

The 4th iteration (the P-AUDIT-3 autopsy's fix). Beat sheet 4 (`scripts/paudit4_turns.json`, Fátima/Tete,
buried ×6, every correction targets a planted fact) committed before the run. Harness: `paudit_run3.py`
(separated phases, real facts-context).

## Verdict: **PASS — flip AUTHORIZED.**

| Metric | result | bar | |
|--------|--------|-----|---|
| correction-recall | **15/15 = 1.000** | ≥ 0.90 | ✅ |
| ghost-corrections | **0** | ≤ 1 | ✅ |
| source fallbacks | **0 / 38** | 0 | ✅ |

By style: explicit 3/3 · implicit 3/3 · **buried 6/6** · mixed 3/3. Zero misses, zero false positives.

## The fix (Rule 13) — one lens closed both gaps
P-AUDIT-3's autopsy found the residual was **not burial** (FRONT 1 had solved that) but a *semantic*
form: clarifications / refinements / preference-shifts the detector didn't call corrections, and — with
real facts-context — an over-fire on brand-new facts (the S4 ghost). Both are the **same question**: does
the clause change something *already recorded*? So I sharpened `_CHAT_CORRECTION_SYS` to a **KNOWN-FACTS
comparison**: a clause that changes / narrows / splits / contradicts a value in KNOWN FACTS is a
correction (incl. "só pra esclarecer X e Y são diferentes" / "não é SÓ minha, sou sócio" / "agora sou
X"); a brand-NEW value not in KNOWN FACTS is not. That single change lifted recall to 1.00 **and** held
ghosts at 0. General fix from the autopsy — the failed beat sheet 3 was never tuned against; beat sheet 4
is new (fresh persona + phrasings), well-formed (every correction has a planted prior to change).

## The full P-AUDIT arc (measured, honest)
| round | perceiver | recall | ghost | notes |
|-------|-----------|--------|-------|-------|
| run 1 | gemma-cpu **nano** | 0.267 | 0 | the perception failed its own exam |
| run 2 | **chat** (B.5) | 0.800 | 0* | 3× lift; buried 0.33; *facts=[] hid the over-fire |
| run 3 | chat + FRONT 1/2 | 0.800 | 1 | CLEAN (0 fallbacks); buried 0.33→0.71; residual = clarification |
| **run 3b** | **chat + KNOWN-FACTS** | **1.000** | **0** | **buried 6/6; both bars pass clean → FLIP** |

## Honest caveats (Rule 12)
- This is a **single clean synthetic run** on a beat sheet I authored. It clears both bars with margin
  (1.00 / 0, not marginal), and gemma4's mild non-determinism (±1 seen across smokes) cannot cross a
  0.90 bar from 1.00 — but it is **synthetic**, not real users. The pre-registered **observation window**
  is the ecological check: the first `OBSERVE_FIRST_N` real corrections log `correction_source` +
  lifecycle-ledger to `observation_log.jsonl` for Trailblazer's spot-audit.
- The flip is CONSERVATIVE-safe on recall (a miss just leaves a value un-superseded — no poisoning); the
  ghost side (absorbing signal on a non-correction) is the one to watch, and it measured 0 here.

## Enabling the flip (production untouched by default; env-gated)
The config **defaults stay OFF** so the test suite keeps guarding the flag-off (production-byte-identical)
path. To execute the authorized flip on the live server:
```
HMGFU_CHAT_CORRECTION_SIGNAL=1 HMGFU_REGULATOR_ENABLED=1 OBSERVE_FIRST_N=50 python -m hmgfu.api
```
- `CHAT_CORRECTION_SIGNAL=1` — corrections from the strong chat model (deferred, GPU-free), nano fallback.
- `REGULATOR_ENABLED=1` — the lifecycle Regulator goes live (records signals + the display pill; it does
  NOT yet govern retrieval — that is a separate, later gate).
- `OBSERVE_FIRST_N=50` — the post-flip observation window for spot-audit.
Reversible (drop the env vars). Restarting the live server is a deliberate operator step, not done here.

## THEORY_V3 B.5 (amended)
The winning architecture — focused, deferred, serialized second call on the strong model, with a CPU
clause-partition + KNOWN-FACTS decision rule — is recorded in `docs/THEORY_V3.md` B.5 with the evidence.
