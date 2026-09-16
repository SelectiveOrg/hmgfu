# HMG-Fu v2 — The Interval Governs (Field-as-State)

Revision of *HMG-Fu — Polished Theory* (THEORY.md) forced by measurement.
Part A records what was falsified and why, with the exact evidence. Part B records the axiom
that survived and its external grounding in the literature. Part C states the reformulated
core principle. Part D specifies the v2 formal system (the retrieval contract). Part E
pre-registers the falsifiable tests that decide this revision. Part F lists what is
deliberately dropped.

Provenance: three retrieval falsifications (HotpotQA fused, HotpotQA decoupled, LoCoMo cat-2
with recency alive), one ablation win (Phase 30.4), one directive-lifecycle win (Phase 55),
per-query component diagnostics, and external literature (HippoRAG 1/2, RGMem, ROMEM,
MemArchitect, LongMemEval). Every claim below carries its evidence pointer.

**Amendment (2026-07-06, adversarial review R1–R5, recorded in ROADMAP before commit).** The v1
pre-registration of E.1 was itself found defective and fixed BEFORE running: E.1 gains ANSWER
ACCURACY as a co-primary metric + an anchored-subset sample gate (R1 — MRR-only was structurally
blind to v2's own answer-layer value per D.3, the mirror of running LoCoMo with recency dead); E.1b
added (Sigma false-supersession guard, R4); Parts C/D marked explicit HYPOTHESIS-not-result (R3);
Part B reframed as convergence-with-SOTA, not novelty, with the point-vs-interval nuance (R5);
external memory-benchmark citations flagged DIRECTIONAL after verification found documented
result-inflation in that space — top_k=50 "100% LoCoMo", GitHub #29 (R2). **Part A (the
falsification) is unchanged — it is measured.** Parts C–E are a falsifiable hypothesis, not a result.

---

## Part A — What was falsified (axiom by axiom)

v1 fused three independent claims into one system. Two died under measurement; the third won.

### A.1 — The field as a RANKING signal (§30 memory_score). FALSIFIED, three ways.

The v1 score is a linear blend where cosine holds effective weight
`0.42 x 0.75 = 0.315` of a 0.95 positive mass; the non-cosine mass is `0.635`.

**Dilution inequality.** A gold with cosine margin `g` over a distractor is demoted whenever

```
SUM_{i != cosine} w_i * (s_i(distractor) - s_i(gold))  >  0.315 * g
```

i.e. the noise mass needs only a mean advantage of roughly `g/2` to flip the rank. Measured
cosine margins on HotpotQA were 0.02 to 0.05; the kappa term alone gave adversarial
distractors +0.0168. Any term whose correlation with relevance is <= 0 on the query
distribution strictly reduces MRR by construction. This was not tunable.

**Evidence.**
| Test | Result |
|---|---|
| HotpotQA, fused score | cosine wins (MRR 0.936 vs 0.825); demotion decomposition: kappa 38%, lexical blend 30%, fuDistancePenalty 18% of the gap (n=44 demoted golds of 120) |
| HotpotQA, decoupled append | append displaces near-miss golds (recall@20 0.985 -> 0.970); best case ties, never beats; missing bridge golds sit at cosine rank 11-40 and are recovered by cosine itself at deeper k (recall@30 = 0.995) |
| LoCoMo cat-2 (temporal, n=90, recency ALIVE in a fair rebased window) | BASE cosine MRR 0.408 vs Fu-A 0.222; cosine wins ~2x on the field's claimed home turf |

### A.2 — Kappa edges as a retrieval channel. FALSIFIED, with the deep reason.

`kappa = 0.25*S + 0.10*T + 0.18*En + 0.18*G + 0.14*C + 0.15*X`. Nearly every component is
DERIVATIVE of the signals cosine already uses (S is cosine itself; En/G are surface overlap,
which adversarial distractors maximise by construction). Walking a similarity-derived graph
is cosine at one remove: it contains no orthogonal information, so traversal cannot find
anything cosine cannot; it can only displace. The decouple A/B measured exactly this
("topology != relevance": Fu-hop pulled topological neighbours, not missing golds).

**External contrast (why graphs are not the problem).** HippoRAG 1/2 beats direct dense
retrieval consistently, across retrievers, including single-step multi-hop cases where the
bridge entity is absent from the query passage. Its edges come from LLM-extracted OpenIE
triples (relational knowledge the embedding does NOT contain), traversed by Personalized
PageRank seeded from query entities. Graphs beat cosine when edges carry orthogonal
information. Fu edges did not. The v1 error was not "graph"; it was "graph of what".

**Verification (2026-07-06, R2).** HippoRAG's edge over dense retrieval is corroborated by
THIRD-PARTY comparisons (e.g. the HopRAG paper's table places HippoRAG well above dense BGE, ~3%
below HopRAG itself), not only the authors' self-report — the positive contrast stands. Two caveats
kept honest: (i) it is QA-domain evidence; (ii) the memory-benchmark space where the deterministic
leg would compete (Zep/ROMEM on LoCoMo/MultiTQ) has DOCUMENTED result-inflation — a "100% LoCoMo"
was reported with top_k=50 (retrieve-everything), honest performance is ~60% Recall@10, and an
independent GitHub audit (Issue #29) called it out. So the "graph of what" DIAGNOSIS is
measured-at-home (kappa is derivative — falsified here) and the positive contrast is third-party
real, but any specific memory-benchmark NUMBER cited below is DIRECTIONAL until we run it ourselves
at honest k (E.2).

### A.3 — Recency as a score term. FALSIFIED at the mechanism level.

`recency_score = exp(-age / 14d)` is a query-independent PRIOR: it does not know whether the
question asks about something recent or old. For a question about an early session, the term
boosts late-session distractors by up to eta = 0.07, larger than typical cosine margins, so
it flips ranks AGAINST the gold; for recent-session questions it helps. A two-sided term with
near-zero net effect: measured Fu-A minus Fu-B = +0.027 MRR against a 0.19 gap to cosine.
Temporal questions require timestamp MATCHING conditioned on the query (a likelihood), not a
freshness boost (a prior). By construction the v1 term cannot answer "when did X happen".

### A.4 — Wormholes as organic analogy discovery. FALSIFIED as specified.

The surfacing signal `analogy = semantic * (1 - entityJaccard)` mis-ranks with real
embedders: genuine cross-domain analogies measure 0.43-0.47 (below the 0.7 gate), while short
generic text hits 0.8+ (and is nano-vetoed). Zero organic wormholes in production after 59
dream loops. The gate mechanics were repaired (Phase 33/56) but the candidate-surfacing
functional form remains wrong; retrieval value unproven in any benchmark.

### A.5 — Density/utility as ranking mass. FALSIFIED (hub bias).

Measured twice (Phase 30 hub dilution, Phase 47 relevance gate): well-connected hubs out-mass
topical relevance. Mitigated by the gate, then made irrelevant by A.1 (no field terms in the
ranking at all).

---

## Part B — The axiom that survived, now externally grounded

**Deterministic supersession and contradiction resolution (v1 §22, issue 7).**
Ablation (Phase 30.4, real model, 3 trials): substrate-only 78% vs canon 100%, deficit
isolated exactly in directive-contradiction resolution. Directive lifecycle
(follow / change / clear), multilingual, 6/6 live.

**External grounding.** The mechanisms that win LoCoMo-temporal in the literature are
precisely conflict-resolution over time, not recency-boosted ranking:

- RGMem: best temporal reasoning score (88.91%) attributed to its thresholded evolution
  mechanism for resolving temporal conflicts.
- ROMEM: diagnoses that static baselines (Mem0, Zep, HippoRAG) let contradictory facts
  cluster in retrieval space and confuse the LLM; it rotates obsolete facts out of phase so
  the correct fact shadows the contradictions, lifting HippoRAG MRR 0.203 -> 0.337 on
  MultiTQ. This is supersession applied to retrieval, done geometrically.
- LongMemEval ships a first-class "Knowledge Update" category: the field's proven leg has a
  dedicated external benchmark.

v1 reached the winning mechanism through the deterministic layer and failed only to connect
it to retrieval. That connection is v2.

**Framing (R5 + R2, honesty).** v2 is CONVERGENCE with the state of the art — bi-temporal validity
and supersession-as-retrieval-filter are already Zep/ROMEM — NOT a novel algorithm. Its value is
aligning HMG-Fu with what demonstrably works, inside a clean conceptual frame and on infrastructure
already built (constrained router, deterministic canon, FactStore/DirectiveStore supersession).
Honest rediscovery outranks fictional novelty. And the external numbers above (RGMem 88.91%, ROMEM
0.203→0.337) are CITED from a benchmark space with documented inflation (A.2 verification) — they
MOTIVATE the direction, they do not SETTLE it; E.2 settles it on our own honest-k run. Slogan
nuance: bi-temporal validity is per-POINT state; what genuinely lives in the INTERVAL is the
supersession relation and the contradiction tension. "The interval governs" is generous — more
precisely, per-point validity + inter-point supersession govern.

---

## Part C — The reformulated core principle

v1 (falsified as stated):
> Memory lives in the interval between points, not in the points.
> point -> Fu interval -> relational field -> propagation -> contextual recall

v2 (the rescue, falsifiable):
> **Finding memories is a function of the points (cosine over embeddings).**
> **Governing memories is a function of the intervals (edges carrying validity,**
> **supersession, contradiction).**
> The field does not rank. The field decides what is ALIVE at the moment of the question.

**STATUS (R3): this is a HYPOTHESIS, not a result.** Part A (what the field is NOT) is MEASURED —
three falsifications. Part C's POSITIVE claim (cosine + validity-governance beats cosine-alone by
adding the temporal/validity layer) is UNPROVEN and rests entirely on the pre-registered tests in
Part E. Until E.1/E.2 land, v2's earned contribution is exactly two things: (i) a measured teardown
of field-as-ranking, and (ii) a well-formed, falsifiable rescue hypothesis. Nothing in Parts C/D is
yet a result — the prose below specifies the system to TEST, not a system proven to work.

What this preserves from v1: E (the edge) as a first-class entity; F as relational magnitude
(analytics/propagation, never ranking); §22 resolution; the dream loop as hygiene; macros as
compression; explainability ("show where the AI walked"); the hex UI. What it discards is in
Part F.

---

## Part D — The v2 formal system (retrieval contract)

```
HMG-Fu v2 = (P, E_t, H, Psi_cos, Sigma, Theta, Delta, Lambda)
```

| Symbol | Meaning | Change vs v1 |
|---|---|---|
| P | Memory points | unchanged |
| E_t | Bi-temporal edges: {t_valid, t_invalid, supersedes, tension, causal} | edges carry STATE; score contribution = 0 |
| H | Hex grid | UI/organisation only; no ranking role |
| Psi_cos | Retrieval = pure cosine (bge-m3) | replaces the §30 blend |
| Sigma | Supersession/validity filter at the retrieval boundary | promoted from side-mechanism to core operator |
| Theta | Query-time temporal operator (deterministic) | NEW |
| Delta | Decay/hygiene | maintenance only |
| Lambda | Compression/promotion | maintenance only |

### D.1 — Ranking rule
`Rank(q) = cosine(embed_bge-m3(q), embed_bge-m3(p))`, full stop.
Literal query coverage survives ONLY as an exact-ID/codeword tie-break gate (lever 1): it may
promote an exact-match collision case, it may never demote a semantically correct candidate.
No kappa, no density, no utility, no recency, no Fu distance, no wormhole term in the score.

### D.2 — Edge state (bi-temporal)
Every fact-bearing point carries `(t_valid, t_invalid)`. Ingest of a correcting statement
closes the old fact's `t_invalid` and opens the new one's `t_valid` (the existing
deterministic supersession, now with a time axis). Contradiction edges keep tension as in v1.
This is the "Zep-style bi-temporal validity" already deferred in Phase 57 P6: v2 promotes it
from deferred hardening to the core of the theory.

### D.3 — Temporal operator Theta (query time, deterministic)
The constrained-decoding router (proven 40/40 well-formed) extracts
`temporal_intent in {none, point(t), before(t), after(t), range(t1,t2)}`.

- `none` -> pure cosine, untouched. The operator does not fire.
- otherwise -> deterministic filter/re-rank of the cosine candidate set by timestamp
  compatibility and validity intervals. A filter over cosine's candidates, never a score blend.
- "when did X happen" questions (no timestamp in the query): retrieve the event by cosine,
  ANSWER from the timestamp metadata surfaced in the injection. An answer-layer operation,
  not a ranking operation.

### D.4 — Validity operator Sigma (retrieval boundary)
Present-tense queries are served currently-valid facts (t_invalid = null). Historical
queries ("what was true at T", "before the correction") are served facts valid at T. Superseded
values never enter the answerable context as current (v1 Phase 49 pattern, now time-indexed).

**AMENDED 2026-07-12 (E.2-P evidence): Sigma GOVERNS + ANNOTATES, it does NOT REMOVE.** E.2-P showed
that the current implementation — `retrieve_memory` gathers only from `active_points()`, so a
`status=superseded` NODE is dropped from all retrieval channels — is *over-supersession*: on a haystack a
superseded turn often still carries answer-bearing content, and removing the whole node loses it (pcanon
McNemar c>b, the perceiver LOST items base kept). The correct Sigma keeps the superseded node
**retrievable but TAGGED** `[superseded/historical]`, and lets the prompt-level governance (the injection
header + `[SUPERSEDED]` state-pill, already applied to active nodes) instruct the model to state only the
CURRENT value while still SEEING the historical turn. Removal is a special case of annotation with the
tag forced to "hide" — never the default. NODE-status supersession is a *ranking/visibility* signal, not
an *existence* delete; only the VALUE-level canon filter (organise_for_injection, D.4-value) may hard-drop
a stale value from the answer. This is a HYPOTHESIS gated by **E.2-A** (annotate vs remove on the KU
sample) before any production change; if E.2-A shows no gain, removal stays and this amendment is
theory-only, recorded without drama.

**E.2-A RESULT (2026-07-12, `313d5ba`; docs/E2_RESULT.md): no empirical mandate — removal STAYS in
production.** canon-annotate 0.640 ≤ canon-remove 0.680 on the 25-item KU sample (McNemar net −1). On
the oracle the regex canon barely fires (canon-remove ≈ base), so the over-supersession loss E.2-P saw on
the perceiver/haystack path is small here, and keeping the tagged stale turn adds mild noise instead of
recovering a loss. The governance-not-existence REFRAMING stands as principle (a superseded node is a
visibility signal); the empirical claim that annotation beats removal on KU is NOT supported. Production
Σ (node-level removal via `active_points`) is unchanged. A haystack (`longmemeval_s`) run, where
supersession fires far more, is the only place the amendment could still earn a production change — deferred.

### D.5 — What the maintenance layer keeps
rho, kappa, decay, macros, dream, hygiene all survive as MAINTENANCE operators (dedup,
consolidation, promotion, contradiction detection feeding E_t). They shape the store; they
never touch the ranking.

---

## Part E — Pre-registered falsifiable tests (Gate 1 discipline)

Both tests run on the bge-m3 graph, one change per measurement, production untouched until
both numbers land. Negative results falsify; no domain escape hatches.

### E.1 — LoCoMo cat-2, temporal operator
Same harness, same labels, same rebased fair window. Arms: BASE (pure cosine, anchor
MRR 0.408) vs COSINE+Theta+Sigma. Report split by subset: questions WITH an explicit temporal
anchor (where Theta fires) vs without.

**R1 CORRECTION (mandatory before running — the instrument was measuring the wrong thing).**
By D.3, point "when did X" questions do NOT re-rank (Theta does not fire) → v2 = pure cosine →
MRR delta = 0 BY CONSTRUCTION. Their temporal value is at the ANSWER layer (read the date from the
retrieved turn's timestamp metadata), which a retrieval-MRR test is structurally BLIND to. Running
E.1 as MRR-only could return "no improvement" and be MIS-read as falsifying the temporal leg — the
mirror image of running LoCoMo with recency dead. Two required fixes:
- **CO-PRIMARY METRIC — ANSWER ACCURACY**, not only retrieval MRR: does the system output the
  correct date/answer? MRR scores the anchored re-rank path; answer-accuracy scores the "when did X"
  metadata path. Both reported; neither alone decides.
- **SAMPLE GATE — pre-count the ANCHORED subset** (where Theta fires: before/after/range intents)
  BEFORE its MRR line is treated as decisive. If it is a handful, that line is indicative only (the
  same discipline imposed on LoCoMo itself). Report the count first, conclusion second.

- **P1a (anchored, re-rank path):** anchored-subset MRR >= BASE + 0.05, IF the anchored count holds weight.
- **P1b (all cat-2, answer path):** COSINE+Theta+Sigma answer-accuracy beats BASE (cosine + naive
  latest/first-date heuristic) on cat-2 by a material margin.
- **P2 (no-drift guard):** zero regression on non-anchored questions and non-temporal categories
  (Theta fires only on intent; the catastrophic-drifting failure mode of temporal models must be
  SHOWN absent, not assumed).
- **Falsifier:** P1a fails (or its sample is too small to decide) AND P1b fails → the temporal leg
  is dead entirely; HMG-Fu = deterministic canon + cosine, and Part D.3 is deleted.

### E.1b — Sigma false-supersession guard (R4)
The validity filter has an unguarded failure mode: a FALSE-POSITIVE supersession removes a
still-valid fact from the answerable context and recall drops SILENTLY. P2 guards non-temporal drift
but not this. Measure it with a number — on queries whose gold IS a superseded-but-historically-asked
fact ("what WAS X before the change") and on queries whose gold is a CURRENT fact adjacent to a
superseded one: recall with Sigma ON vs OFF.
- **P4:** Sigma removes ONLY what it should — no recall drop on the historical/current-adjacent set
  vs Sigma-OFF; the only delta is on present-tense queries where a stale value was correctly shadowed.
- **Falsifier:** Sigma-ON recall < Sigma-OFF on that set → the filter over-cuts; D.4 needs a
  correctness fix before Sigma may serve the retrieval boundary.

### E.2 — LongMemEval, the deterministic leg's external arbiter
The proven leg (supersession/contradiction) has never faced an external benchmark. Run
LongMemEval with the benchmark's own labels, categories isolated; the decisive lines are
**Knowledge Update** and **Temporal Reasoning**; report Abstention too.

- **P3 (prediction):** Sigma/canon materially beats the same-harness pure-cosine baseline on
  Knowledge Update (the category that IS supersession).
- **Falsifier:** no material win on Knowledge Update -> the deterministic-layer advantage
  does not generalise beyond the internal ablation, and the project's value claim must be
  re-scoped again.
- **HONEST-k RULE (R2):** report at a REASONABLE k (e.g. Recall@10), NEVER a retrieve-everything k.
  This benchmark space has documented top_k=50 inflation (independent GitHub #29 audit); a win must
  survive honest k or it is not a win. Same rule binds E.1's BASE and all arms.

**RESULT (2026-07-08, `docs/E2_RESULT.md`; oracle, k=10, gemma4 temp-0):** Knowledge-Update n=72 —
BASE 0.694 → **FULL 0.847 (+0.153)**, falsifier **NOT triggered**, McNemar b=11/c=0 (solid). First
external validation of the surviving deterministic leg. BUT the pre-registered decomposition splits
the credit: **D3-ONLY 0.806 (dates alone = 73% of the win), CANON-ONLY 0.681 (≈ base, McNemar net −1).**
So **P3 as stated is NOT confirmed in isolation** — the external KU win is carried by **D.3 date-surfacing**
(the E.1 answer-from-timestamp mechanism), not by Sigma/canon supersession, which is neutral alone on
LongMemEval's conversational updates (regex `detect_fact` low coverage; small +0.041 canon synergy on top
of dates). Secondary: Temporal +0.047, Abstention **−0.067** (a known over-assertion cost of canon+date
injection). Net position: **E.2 is a GAIN for the v2 bundle, re-scoped — the temporal/answer-layer (D.3)
is the external engine; the supersession leg stays internally-proven (Phase 30.4) but externally-neutral here.**

**E.2-P confirms P3 dead externally (2026-07-09, `686c01d`):** the CANON-ONLY≈base failure was NOT mere
regex low-coverage — replacing the regex with the REAL gemma chat-correction PERCEIVER (the B6 path, on
the update turns) gives **pcanon ≤ base across 3 runs** (0.680→0.600, McNemar b=1/c=3 net −2; runs #2≡#3
reproduced exactly). The perceiver's higher coverage does not rescue KU — it LOSES via **over-supersession**
(it drops answer-bearing turns base kept; c>b, error-independent). So the supersession claim P3 does NOT
generalise by EITHER mechanism; the external KU win is D.3 dates, full stop. (Strict zero-perceiver-error
run infeasible on one GPU — Ollama degrades under the arm's sustained constrained-decode load; verdict rests
on reproducibility + the structural over-supersession, not a single clean number. `docs/E2_RESULT.md`.)

### E.3 — Sample-size and reporting rules
Per-category n reported before any conclusion; single-sample category lines are indicative,
not decisive. All numbers per-category (aggregates hide the signal; HotpotQA lesson). Every
run recorded in the ROADMAP with evidence (Rules 6/7/8/12).

---

## Part F — Deliberately dropped from the theory

| v1 element | v2 status | Reason |
|---|---|---|
| §30 blended memory_score as retrieval | DROPPED | falsified 3x (A.1) |
| kappa in ranking | DROPPED | derivative signal (A.2) |
| recency in ranking | DROPPED | prior, not likelihood (A.3) |
| fuDistancePenalty | DROPPED | 18% of demotion gap; no relevance signal on static corpora |
| wormhole term in ranking | DROPPED | never fired organically; unproven (A.4) |
| density/utility in ranking | DROPPED | hub bias (A.5) |
| Fu expansion as score-bearing retrieval channel | DROPPED | displaces golds (decouple A/B) |
| "field beats RAG at retrieval" | DROPPED as a claim | the thesis v2 makes is Part C |

Open research note (not a v2 commitment): if score-bearing graph retrieval is ever revisited,
the edges must carry orthogonal information (OpenIE-style triples + PPR, per HippoRAG), not
similarity-derived kappa. Recorded so the lesson is never re-litigated.

---

## Part G — Traceability

- Rule 1/2: every falsification above cites the measured run that produced it.
- Rule 3: v2 changes the architecture (field out of ranking), not weight cosmetics.
- Rule 5: Theta reuses the constrained router; Sigma reuses FactStore/DirectiveStore
  supersession; E_t extends existing FuEdge/facts tables (no parallel store).
- Rule 11: v1 THEORY.md remains the historical record; this file supersedes its retrieval
  claims only. Deterministic canon, directives, hygiene, UI contracts unchanged.
- Rule 12: Part E defines completion evidence before implementation starts.
