# E.2 — LongMemEval external arbiter — RESULT (decisive Knowledge-Update line)

Pre-registration: `ROADMAP.md` §E.2 + `docs/THEORY_V2.md` §E.2, committed `b898d52` **before any number** (Rule 3/12).
Harness: `scripts/bench_longmemeval_e2.py` (committed `e6b5875`, `f881e76`). Dataset: `xiaowu0162/longmemeval` **oracle** (evidence-sessions-only — isolates supersession/canon from retrieval-at-scale, which is what §E.2 arbitrates). Production (8777) untouched; all runs on throwaway scratch DBs.

## Decisive line — Knowledge Update (n=72; the category that IS supersession)

| arm | accuracy | Δ (full − base) |
|---|---|---|
| **BASE** (pure cosine bge-m3, honest k=10) | **0.694** | — |
| **FULL** (deterministic leg: cosine + D.3 dates + canon/Σ supersession + Regulator ON) | **0.847** | **+0.153** |

Run: 144 answer calls (gemma4:12b, temp 0), 0 correction-detector calls (deterministic FULL, detector-off per pre-registration), wall 112 min.

### Verdict vs the pre-committed falsifier
> **Falsifier:** FULL ≤ BASE on Knowledge Update ⇒ the deterministic-leg advantage does not generalise externally and the value claim re-scopes.

**NOT triggered.** FULL (0.847) > BASE (0.694) by **+0.153** (11 more correct of 72). The deterministic supersession/canon + D.3 leg — the leg that survived every internal falsification (Phase 30.4 ablation 78%→100%; the field-as-retrieval thesis died 3×) — **GENERALISES to an external, third-party benchmark on its decisive category.** First external positive for this project's surviving thesis.

## Honest caveats (Rule 12 — reported, not hidden)
1. **Attribution not isolated.** FULL is the pre-registered BUNDLE (D.3 dates + canon/Σ + Regulator). The +0.153 is the bundle vs pure cosine; it does NOT isolate P3's specific *Sigma/canon* claim from *D.3 dates*. E.1 already showed D.3 date-surfacing is worth +0.353 on temporal attribution, and KU answers require "pick the later-dated value" — so **D.3 dates plausibly carry much of the win**. A canon/Σ-without-D.3 decomposition arm is the isolating follow-up.
2. **Run cleanliness.** 0 nano-sensitizer timeouts (nano forced OFF for deterministic, thrash-free, arm-equal ingestion). 7/144 gemma4 *answer* timeouts (~5%, empty→wrong, spread across both arms) — too few and too balanced to flip an 11-item gap, but noted. 0 correction-detector *source* fallbacks (the pre-registered "zero source fallbacks in the decisive run" bar is met because the deterministic FULL makes 0 detector calls).
3. **Oracle, not the full haystack.** The oracle isolates the mechanism (the §E.2 intent) but does not test retrieval-at-scale; a `longmemeval_s` haystack run would add the retrieval confound.
4. **Sampled detector arm pending.** The gemma chat-correction detector (B6 perceiver path — the /goal's "Regulador ligado, correção diferida") is the OPTIONAL sampled arm (per-turn gemma, ~prohibitive at full n); a silent-swallow bug returned 0 calls in the cost probe (error-surfacing now added). It measures whether the PERCEIVER closes any gap the regex canon leaves; not part of this decisive deterministic line.

## Secondary lines (done — n=127 temporal after `_abs` split, n=30 abstention; 314 answer calls, 0 detector calls, wall 3.4 h)

| category | n | BASE | FULL | Δ (full−base) | reading |
|---|---|---|---|---|---|
| **knowledge-update** (decisive) | 72 | 0.694 | **0.847** | **+0.153** | FULL wins big — falsifier NOT triggered |
| temporal-reasoning | 127 | 0.244 | 0.291 | +0.047 | FULL wins modestly; D.3 dates help but the category is hard (both arms low) |
| abstention | 30 | 1.000 | 0.933 | **−0.067** | FULL slightly WORSE — a real cost |

**Per-category only; aggregates never decide (HotpotQA lesson).**

### Honest reading of the secondaries
- **Temporal (+0.047):** D.3 date-surfacing helps, consistent with E.1 (dates are answer-layer attribution), but the oracle temporal questions are hard (BASE 0.244) so the lift is small. Directionally positive, not decisive.
- **Abstention (−0.067):** an **honest cost**. BASE's sparse pure-cosine context makes the model abstain readily (1.000). FULL injects canon current-values + dates, which nudges the model to ANSWER — it over-asserts on 2/30 questions whose answer is not in history. So the deterministic-leg injection buys Knowledge-Update accuracy at a small over-assertion cost when the honest answer is "I don't know". Worth surfacing (the pre-registration asked for Abstention precisely to catch this).

### Net
The decisive line is a clear, robust external **win** (+0.153, falsifier not triggered). The secondaries show the win is **specific**: FULL helps where supersession/recency matter (KU, temporal) and slightly hurts calibration (abstention). Consistent with THEORY_V2's scoping — the deterministic leg is a memory-management win, not a free lunch.

Run cleanliness (secondaries): 13/314 gemma4 answer timeouts (~4%, both arms, empty→wrong); **0 nano timeouts** (nano-off); 0 correction-detector calls.

---

## Post-processing (pre-registered `6aa9acb` before any number): seal + decompose

### PASSO 1 — discordant pairs (McNemar), Knowledge Update, same 72 items
Honest correction: the first runs did not persist per-item verdicts, so the paired data was captured on a **re-run with additive per-item instrumentation** (answer/judge logic byte-identical). The re-run **reproduced base 0.694 / full 0.847 exactly** (temp-0 determinism; reproducibility confirmed).

| arm vs BASE | b (arm✓/base✗, gains) | c (arm✗/base✓, losses) | net | reading |
|---|---|---|---|---|
| **FULL** | **11** | **0** | **+11** | pre-committed "b=11,c=0 SEALS it" — zero losses, McNemar exact p≈0.0005 |
| D3-ONLY | 9 | 1 | +8 | dates gain broadly, ~no losses |
| CANON-ONLY | 3 | 4 | **−1** | canon/Σ alone gains 3 / loses 4 — no net help |

The FULL win is statistically **solid** (11 gains, 0 losses on paired items).

### PASSO 2 — bundle decomposition, Knowledge Update (n=72; same ingestion, judge, k, nano-off, detector-off)

| arm | accuracy | Δ vs base |
|---|---|---|
| BASE (cosine) | 0.694 | — |
| **FULL** (canon/Σ + D.3 dates) | **0.847** | +0.153 |
| **D3-ONLY** (D.3 dates, no canon/Σ) | **0.806** | **+0.112** |
| **CANON-ONLY** (canon/Σ, no dates) | 0.681 | −0.013 |

**Pre-committed verdict (written before the numbers): D3-ONLY ≈ FULL ⇒ the win is the DATES; canon/Σ re-scopes to what CANON-ONLY shows.**

- **D.3 date-surfacing is the driver:** dates alone recover +0.112 of the +0.153 bundle (73% of the win), McNemar b=9/c=1. This is the SAME mechanism E.1 found (answer-from-timestamp, +0.353) — a Knowledge-Update answer is "pick the later-dated value", and surfaced dates let the model do exactly that.
- **canon/Σ supersession does NOT carry it:** CANON-ONLY (0.681) sits at/below BASE (0.694), McNemar net −1. **Pre-registration P3 — "Sigma/canon materially beats pure cosine on Knowledge Update" — is NOT confirmed in isolation.** On LongMemEval's conversational updates the regex `detect_fact` canon has low coverage (as the pre-committed caveat warned), and Σ dropping turns can occasionally remove a still-useful turn → no net gain alone.
- **Small synergy:** FULL (0.847) − D3-ONLY (0.806) = **+0.041** — canon/Σ adds a little ON TOP of dates (the current-value line helps once the model is already date-anchored), but is not the engine.

### Re-scoped conclusion
The deterministic-leg **bundle** generalises externally on its decisive category (+0.153, falsifier NOT triggered, McNemar b=11/c=0) — E.2 is a **GAIN**. But the decomposition attributes the win to **D.3 date-surfacing (the answer-layer temporal mechanism from E.1)**, not to the canon/Σ supersession leg, which is neutral in isolation on this external benchmark. **P3's specific supersession claim re-scopes: canon/Σ is validated internally (Phase 30.4 ablation) but does not, alone, beat cosine on LongMemEval KU; the external KU win is carried by dates + a small canon synergy.** Honest and directional — no arm was tuned after seeing numbers.

Run cleanliness (decomposition): 24/288 gemma4 answer timeouts (~8%, retried attempt-1/2/3, mostly recovered — base/full reproduced exactly so trustworthy); **0 nano timeouts**; 0 detector calls.

## Known system cost (logged, NOT tuned now)
The abstention −0.067 (FULL over-asserts when the honest answer is "don't know") is a **known cost** of injecting canon current-values + dates. Future candidate (own gate, not tuned here): epistemic framing of the canon injection so it does not license over-assertion. Out of scope for E.2.

## Out of scope (explicit, per the decomposition /goal)
haystack (`longmemeval_s`, retrieval confound — future optional); E.4/E.5 (Trailblazer's call); any abstention mitigation.

---

## E.2-P — the PERCEIVER-FED CANON arm (the measurement P3 needs), pre-registered `686c01d`

Question: CANON-ONLY (regex `detect_fact`) ≈ base — was that a PERCEPTION-coverage failure (the P-AUDIT story: regex misses conversational updates)? Replace the regex with the REAL gemma chat-correction **perceiver** (`_detect_correction_via_chat`→`_apply_correction`, the B6 path) on the update turns, no dates, Σ status-filter. Same 25-item sample (7 canon-diverged qi {4,8,19,39,57,61,63} + 18 `random.seed(0)`), same k=10, gemma4 temp-0.

**Rule-1 fix first:** the "0 detector calls" was `engine.retrieve(txt)[0]` (=QueryPoint) → `facts_summary` slices it → `TypeError`, all 12/12 turns silently errored. Fixed to `[1]`.

### Result — 3 runs, reproducible, all INCONCLUSIVE by the strict bar, all one direction

| run | model | base | canon | **pcanon** | pcanon-vs-base McNemar | perceiver errs |
|---|---|---|---|---|---|---|
| #1 | gemma4:12b (256K ctx) | 0.720 | 0.720 | **0.680** | b=2 c=3 **net −1** | 4 (+61 timeouts) |
| #2 | gemma4-bench (8K ctx) | 0.680 | 0.680 | **0.600** | b=1 c=3 **net −2** | 2 |
| #3 | gemma4-bench, fresh Ollama | 0.680 | 0.680 | **0.600** | b=1 c=3 **net −2** | 2 |

Runs #2 and #3 (fresh Ollama restart between) **reproduced EXACTLY** — the result is stable, not noise.

### Verdict vs the pre-committed reading
> pcanon > BASE with net-positive McNemar → P3 REVIVES externally; pcanon ≈ BASE → P3 dead externally, canon internal-scoped, recorded without drama.

**P3 is DEAD externally.** pcanon ≤ base in every run (net −1, −2, −2). The perceiver's higher coverage does NOT rescue the KU win. **Both** canon mechanisms fail externally: regex-canon 0.681 ≈ base, perceiver-canon 0.600 ≤ base. The external KU win is carried by **D.3 dates** alone (decomposition above).

### Why pcanon LOSES — a real mechanism finding (not an error artifact)
The losses are `c=3` (pcanon wrong / base right) vs `b=1` (gains) → **OVER-SUPERSESSION**. A perceiver *error* merely SKIPS a correction (pcanon behaves like base on that item) — it cannot make pcanon LOSE. So the c=3 are items where the perceiver **superseded an answer-bearing turn that base kept**. On a haystack, aggressive per-turn B6 supersession drops the very turn holding the answer. Even error-free (the 2 errs could recover ≤2 items → pcanon ≤ 0.680 = base), pcanon never BEATS base. More supersession ≠ better retrieval.

### Honest infra caveat (Rule 12)
A strictly 0-perceiver-error run was **infeasible on this single-GPU box**: 3 runs (each 3–7 h) all degraded — gemma4 returns `empty chat response (ollama degraded)` under the pcanon arm's ~292 constrained-decoding perceiver calls sustained over hours (num_ctx-capped AND fresh-restarted, still degrades → per-run, not just uptime). This is a documented HARDWARE limit, **not** a mechanism result. The verdict rests on the **reproducibility (#2≡#3)** + the **structural over-supersession** (c>b, error-independent), not on a single clean number. Cost/latency: single call 6s (gemma4-bench) vs 300s-timeout (256K); pcanon arm ~283s/item vs ~20s/item base.

### Net position
E.2 closes: the deterministic-leg **bundle** wins externally on Knowledge Update (+0.153, McNemar b=11/c=0) — a real first external validation — but the **engine is D.3 date-surfacing**, not supersession. The supersession leg (canon/Σ, regex OR perceiver) is **internally proven (Phase 30.4)** yet **externally neutral-to-negative** on LongMemEval's conversational updates. P3 does not generalise; recorded without drama.

---

## E.2-A — Σ as GOVERNANCE+ANNOTATION vs REMOVAL (the Rule-1 + amendment gate), pre-registered `313d5ba`

**Rule-1 report (what production DOES with superseded, verified in code before any change):** `retrieve_memory` gathers candidates only from `graph.active_points()`, and `active_points()` returns `status=="active"` — so a **status=`superseded` NODE is REMOVED from all 6 retrieval channels**. Status is set superseded by `dream.mark_tension`, `facts.supersede_stale_nodes`, `hygiene` (×3), and B6 `supersede_named_stale`. The injection layer annotates only the ACTIVE survivors (header "trust most recent / narrate old as history", a canon value-filter, the `[SUPERSEDED]` state-pill). **Superseded-status nodes never reach injection → production Σ = REMOVAL at the node level**, exactly the mechanism E.2-P showed drops answer-bearing turns.

**Gate (same 25 KU items, gemma4-bench, canon regex Σ, no dates, NO perceiver → clean):**

| arm | accuracy | vs canon-remove (McNemar) |
|---|---|---|
| base (control) | 0.680 | — |
| canon-remove (current: drop superseded) | 0.680 | — |
| **canon-annotate (keep superseded turns, tag `[superseded]`)** | **0.640** | **b=1 c=2 net −1** |

Clean run: 75 answer calls, 0 timeouts, 0 errors (E.2-A has no perceiver, so no Ollama degradation).

**Verdict (pre-committed): annotation buys NOTHING on KU — removal stays.** canon-annotate (0.640) ≤ canon-remove (0.680), McNemar net −1. On the ORACLE the regex canon barely fires (canon-remove ≈ base, net 0), so the over-supersession removal-loss E.2-P saw on the perceiver/haystack path is small here; keeping the tagged stale turn adds mild noise/crowding instead of recovering a loss. **No production change is earned.** The Σ-as-annotation *reframing* is defensible in principle (a superseded node is a visibility signal, not an existence delete), but E.2-A gives it **no empirical mandate** on this benchmark — recorded without drama, as pre-registered.

## E.2 — FINAL POSITION (arc closed)
- **Bundle (FULL) wins Knowledge Update externally: +0.153, falsifier NOT triggered, McNemar b=11/c=0.** First external validation of the surviving deterministic-governance thesis.
- **The engine is D.3 date-surfacing** (D3-only 0.806 ≈ full 0.847), not the supersession leg.
- **Supersession (Σ/canon) is externally NEUTRAL by every route tested:** regex-canon 0.681 ≈ base; perceiver-canon 0.600 ≤ base (over-supersedes); annotate-vs-remove net −1 (no gain either way). It stays **internally proven** (Phase 30.4 ablation 78%→100%) but does not carry the external KU win.
- **Secondaries:** Temporal +0.047; Abstention −0.067 (a known over-assertion cost of canon+date injection, logged, not tuned).
- **Honest scope:** oracle (isolates the mechanism); a `longmemeval_s` haystack run would add the retrieval confound. A strictly 0-error perceiver run was infeasible on one GPU (documented Ollama sustained-load degradation); the E.2-P verdict rests on reproducibility (#2≡#3) + structural over-supersession, not a single clean number.
