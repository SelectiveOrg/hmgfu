# HMG-Fu v3 — The Governed Hexagon

Extension of THEORY_V2 (The Interval Governs). v2 settled WHAT finds and WHAT governs:
cosine finds (Psi_cos), the interval governs (Sigma validity, Theta temporal). v3 specifies
HOW governance works: the Regulator (a signal-hierarchy state machine driven by the user),
the typed-port hexagon (geometry as routing schema, the answer to "why six sides"), the
lifecycle of a memory (temporary -> candidate -> fact, promotion by use subordinated to user
verdict), and in-turn analogical linking (the main LLM proposes; the funnel validates).

Provenance: v1 falsified 3x (THEORY_V2 Part A, settled); v2 committed with R1-R5 amendments
(commit 956ba9e); the v3 mechanisms emerged from first-principles dialogue (2026-07-06) and
were then checked against the literature. Convergences and genuinely novel deltas are
declared in Part G. Everything in Parts B-D is HYPOTHESIS with a pre-registered test
attached; nothing here is claimed as result.

---

## Part 0 — Lineage (one line each)

- v1: field terms inside the ranking. Falsified (dilution, measured 3x).
- v2: cosine ranks; edges carry bi-temporal validity; deterministic temporal/supersession
  operators. Committed. E.1 landed (D.3 answer-from-timestamp +0.353 external). **E.2 = GAIN**
  (LongMemEval oracle, Knowledge-Update decisive): the FULL bundle beats pure cosine **+0.153**
  (0.694→0.847), pre-registered falsifier NOT triggered, McNemar b=11/c=0 — first external
  validation of the surviving thesis. Decomposition (pre-registered) attributes the win to **D.3
  date-surfacing** (D3-only 0.806 ≈ full); **canon/Σ supersession alone is neutral (canon-only
  0.681 ≈ base, McNemar net −1) → P3's supersession-beats-cosine claim re-scopes** (validated
  internally by the Phase 30.4 ablation, but not carrying the external KU win). See `docs/E2_RESULT.md`.
- v3: the governance layer made concrete: WHO decides truth (the user, through a signal
  hierarchy), WHERE relations live (six typed ports + one wormhole port), HOW memories
  harden (lifecycle states with absorbing corrections), WHEN links are born (in-turn by the
  main LLM + cold by the dream loop, both validated by the same funnel).

## Part A — Settled axioms (from measurement, not revisited here)

- A1. Pure cosine (bge-m3) owns ranking. No field term may enter the score
  (dilution inequality, THEORY_V2 A.1).
- A2. Similarity-derived edges carry no orthogonal information; traversal for RANKING is
  cosine at one remove (THEORY_V2 A.2). v3 uses edges for ROUTING and STATE only.
- A3. Recency is a prior, not a likelihood; temporal value lives in deterministic operators
  and timestamp metadata, never in the score (THEORY_V2 A.3).
- A4. Deterministic supersession beats the probabilistic substrate on contradiction
  resolution (ablation 100% vs 78%). It is the proven leg v3 builds on.

---

## Part B — The v3 formal system

```
HMG-Fu v3 = (P, S, Ports, R, Psi_cos, Sigma, Theta, Rho, W, D)
```

| Symbol | Meaning | New in v3 |
|---|---|---|
| P | Memory points (hexes) | carries lifecycle state |
| S | Lifecycle states {TEMP, CANDIDATE, FACT, SUPERSEDED, EVAPORATED} | NEW |
| Ports | 6 typed side-ports + 1 center wormhole-port per hex | NEW (schema, not capacity) |
| R | The Regulator: signal-hierarchy state machine | NEW |
| Psi_cos | Retrieval = pure cosine | from v2, unchanged |
| Sigma | Validity/supersession operator | from v2, now precedence-ordered |
| Theta | Temporal operator (fires only on temporal intent) | from v2 |
| Rho | Port-routed expansion (append-only, intent-matched) | NEW, replaces dead untyped expansion |
| W | Wormhole funnel (hot hunter in-turn + cold hunter in dream) | NEW mechanism, old concept |
| D | Dream/maintenance (decay, macros, hygiene, cold hunting) | from v1/v2, maintenance only |

### B.1 — Memory lifecycle S

Every point carries a state and a bounded confidence c in [0,1].

```
TEMP --------> CANDIDATE --------> FACT
  \                |                 |
   \---------------+----> SUPERSEDED (absorbing via user correction or explicit supersession)
            |
            +----> EVAPORATED (TTL without use, TEMP only)
```

Rules (the Regulator's transition table, Part B.3 gives the arithmetic):
- Birth: every ingested point is TEMP (except user_explicit statements, which are FACT
  candidates through the existing FactStore path, unchanged).
- TEMP -> CANDIDATE: crossable by accumulated weak signal (silent use, praise).
- CANDIDATE -> FACT: requires at least ONE explicit user signal (statement, confirmation,
  or correction-in-its-favor). No amount of repetition or praise alone can cross this edge.
  This is Invariant I1 (Part C.2).
- Any state -> SUPERSEDED: a user correction. Absorbing: no counter, no praise, no
  repetition can undo it; only a NEW explicit user statement can create a successor fact.
- TEMP -> EVAPORATED: TTL (default 30 days) with zero traversals/uses.

### B.2 — The typed-port hexagon (why six sides)

Each hex has SEVEN ports. The six sides are TYPE buckets for local relations; the center is
the single non-local port.

| Port | Relation type | Maps to existing FuEdge.relation |
|---|---|---|
| side 1 | factual (same entity, part-of, attribute) | same_entity, part_of |
| side 2 | temporal (before/after/during, validity link) | temporal |
| side 3 | contradictory (tension, supersession link) | contradiction |
| side 4 | positive (supporting evidence, user-confirmed) | goal_related + positive valence |
| side 5 | negative (weakening evidence, user-corrected) | emotional negative / corrected |
| side 6 | neutral/context (co-occurrence, session) | semantic, session |
| center | wormhole (non-local structural analogy) | wormhole |

Design decisions, explicit:
- A port is a BUCKET, not a slot: each side holds unbounded links of its type. The hexagon
  is a SCHEMA (six kinds of local relation + one kind of non-local), not a capacity limit
  of six neighbours.
- Ports never contribute to ranking (A1/A2). They exist for two purposes only:
  (a) ROUTING: the Regulator follows intent-matched ports during expansion (B.4);
  (b) STATE: Sigma reads the contradiction port; the lifecycle reads positive/negative ports.
- The single center port is a structural throttle: at most ONE provisional wormhole per hex
  at a time. Geometry rate-limits non-local hypothesis formation (Part C.4).

### B.3 — The Regulator R (signal hierarchy)

The Regulator answers the question that kills naive promotion-by-use: repetition is not
truth. The literature names the failure "memory misevolution" (biased feedback loops degrade
agents; static defenses insufficient). The Regulator is the non-static defense: an explicit
hierarchy where the user's verdict dominates everything the system generates about itself.

Signal hierarchy (strongest to weakest), with bounded arithmetic in C.2:
1. USER CORRECTION: absorbing state transition (-> SUPERSEDED). Not a score delta.
2. USER EXPLICIT CONFIRMATION / statement: +0.30 to c, unlocks CANDIDATE -> FACT.
3. USER PRAISE (generic approval): +0.05 to c, total praise contribution capped at 0.10.
   Praise is treated as NOISY (approval of tone is not verification of fact).
4. SILENT SUCCESSFUL USE (point served, turn ended, no correction): +0.01 to c, total
   silent contribution capped at 0.10. Silence is ambiguous; it is the weakest signal.

The Regulator also owns edge-type refinement: the LLM's edge-type classifications (B.5) are
PROPOSALS; a user correction on an answer that traversed an edge demotes that edge's
confidence; sustained clean traversals confirm it. Same hierarchy, applied to relations.

### B.4 — The retrieval pipeline (operator precedence, fixed)

Order is a design constant, not a runtime choice. It answers "which side wins when two
light up" (e.g. "is Green still mine?" touches temporal AND contradiction):

```
1. Psi_cos      cosine top-k over active points (finds)
2. Sigma        validity first: drop/annotate SUPERSEDED, resolve contradiction-port state
3. Theta        temporal filter, ONLY if the constrained router extracted temporal intent
4. Rho          port-routed expansion: follow ONLY intent-matched ports from survivors,
                append-only BELOW the cosine ranking, cap m per source (default 3)
5. Injection    typed annotations: each item carries its state (FACT/TEMP), its timestamp,
                and its port provenance ("reached via contradiction port" etc.)
```

Justification for Sigma before Theta: validity determines what EXISTS to be filtered.
Filtering by time before resolving supersession can surface a dead fact that happens to
match the window. "Is Green still mine?" resolves as: Sigma keeps the currently-valid
ownership fact and suppresses the superseded "I have no dog"; Theta then reads "still" as
present-validity, already satisfied. One deterministic path, no tie to break.

### B.5 — The turn contract (Path A: answer + classification, one call)

Per user turn, the MAIN LLM (not a separate nano) receives the query, the injected context
(typed, per B.4), and returns via constrained decoding (the schema channel proven 40/40):

```
{ answer:            the user-visible reply,
  point_type:        classification of the new memory (fact/preference/event/...),
  edge_proposals[]:  typed links from the new point to injected points (port types),
  wormhole_proposal: OPTIONAL and rare, a non-local analogy to an injected point }
```

Rules:
- The user sees only `answer`. The rest flows to the Regulator as PROPOSALS.
- Nothing the LLM proposes is final: edge types and wormholes enter provisional and are
  confirmed or demoted by the signal hierarchy (B.3). The LLM proposes; the user disposes.
- On ACTION turns the classification fields are DISABLED (measured: multi-task prompts
  degrade the primary task; same mechanism as the opener suppression).
- The nano sensitizer is retained as FALLBACK ONLY (offline, degraded mode), per the
  existing Issue-8 resilience doctrine.
- Path B (HMG-as-LLM, intelligence inside the structure) is REJECTED: weights are frozen
  functions, memory is mutable state; fusing them requires training we cannot do and kills
  precise recall. The "memory that thinks between questions" already exists: the dream loop.

**AMENDMENT (P-AUDIT-2/3, measured): the correction field is a FOCUSED, DEFERRED, SERIALIZED second
call — NOT the literal one-call "answer + classification" contract above.** Evidence, from three
measured rounds against a synthetic dirty-PT simulator: (1) folding classification into the answer call
risks the answer (one constrained JSON); a SEPARATE call leaves the reply byte-identical (reply
non-regression by construction — the correction runs in grade_turn after the reply is emitted). (2) A
co-resident correction call on the one GPU thrashes the embedder (gemma4 KV cache vs nomic) — 18/39 turns
silently fell back to the weak nano; DEFERRING it to a queue drained only when the GPU is free removed
that entirely (0/38 fallbacks). (3) BURIAL (a correction hidden mid-way in a long off-topic message)
defeats attention; a mechanical CPU CLAUSE-PARTITION fed into the one prompt lifted buried recall
0.33→0.71. Implemented: grader._detect_correction_via_chat + _split_clauses; engine.enqueue_correction/
drain_corrections (FRONT 2); gated CHAT_CORRECTION_SIGNAL, nano demoted to offline fallback (FRONT 0).
STATUS: WON (P-AUDIT-3b) — sharpening the detector to a KNOWN-FACTS comparison (a clause that
changes/narrows/splits/contradicts a recorded value is a correction; a brand-new value is not) lifted
recall to 15/15=1.00 with ghost 0 on a clean run → the flip is AUTHORIZED (enable via env
HMGFU_CHAT_CORRECTION_SIGNAL=1 HMGFU_REGULATOR_ENABLED=1, with the OBSERVE_FIRST_N post-flip window).

### B.6 — Wormholes: two hunters, one funnel

- HOT hunter: the main LLM in-turn (B.5). It is the only point in the cycle where both
  banks are visible at once (the new message AND the retrieved memories) with full context.
  This is why the two previous attempts failed: the nano at turn-start saw only one bank;
  the grader at turn-end judged leftovers; both were fed by a cosine-based analogy formula
  that is blind to structure-with-surface-dissimilarity (measured: genuine analogies 0.43
  to 0.47 under a 0.7 gate; junk at 0.8).
- COLD hunter: the dream loop over distant pairs no recent conversation touched (existing
  calibrator retained). Different territory, same funnel.
- THE FUNNEL (both hunters feed it):
  born PROVISIONAL (zero ranking effect, traversable in Rho) ->
  SOLIDIFY after 3 clean traversals (a recall crossed it and the turn ended uncorrected) ->
  EVAPORATE on 1 correction of an answer that crossed it, or TTL 30 days untraversed.
- Structural throttle: one provisional wormhole per hex (single center port).

### B.7 — Maintenance (unchanged in role)

Dream, decay, macros, hygiene keep their v1/v2 duties: shape the store, never touch the
ranking. The dream loop additionally runs the cold hunter and processes the Regulator's
pending demotions in batch.

---

## Part C — Calculations

### C.1 — Why nothing enters the ranking (carried, settled)
Dilution inequality (THEORY_V2 A.1): with cosine effective weight 0.315 of 0.95 mass, a
noise mass of 0.635 needs only ~g/2 mean advantage to flip a gold with margin g. Measured
margins 0.02-0.05; kappa alone gave distractors +0.0168. Any weight w > 0 on a term with
correlation <= 0 to relevance strictly reduces MRR. Therefore: ports route, states filter,
nothing scores.

### C.2 — The Regulator arithmetic and Invariant I1

Let c0 = 0.40 (TEMP birth confidence). Caps: silent Sum(eps) <= 0.10, praise <= 0.10.
Thresholds: CANDIDATE at c >= 0.50; FACT at c >= 0.80 AND >= 1 explicit user signal.

- Maximum c reachable WITHOUT explicit user signal:
  c_max = 0.40 + 0.10 (silent, capped) + 0.10 (praise, capped) = 0.60 < 0.80.
  **Invariant I1: there is NO path from repetition and praise to FACT.** A lie repeated 40
  times reaches c = 0.50 (10 effective uses, cap) and stalls at CANDIDATE forever.
- One correction beats any count: SUPERSEDED is an absorbing STATE, not a score. 40
  repetitions vs 1 correction is not 0.40 vs 0.30 on some scale; it is a state transition
  that no arithmetic can reverse. This is what makes the anti-poisoning guarantee a
  structural property instead of a tuning choice.
- One explicit confirmation (+0.30) plus modest use: 0.40 + 0.30 + 0.10 = 0.80 -> FACT.
  The intended path: the user's word, corroborated by use.

### C.3 — Port routing cost and the displacement risk, stated honestly

- Cost: expansion traverses only the intent-matched port. With 6 types and fan B split
  across ports, Rho costs O(k * B/6) per query against v1's O(k * B): ~6x fewer edges, and
  zero on queries with no matching intent (most queries -> pure cosine, untouched).
- Displacement: v2 MEASURED that untyped append hurts (recall@20 0.985 -> 0.970) by pushing
  rank-11-40 golds down. Typed append is exposed to the SAME risk. The v3 hypothesis
  (H-route) is that intent-matching raises appended-item precision enough to net-gain ON
  THE MATCHED INTENT CLASS without harming others. This is not assumed; it is E.4's job,
  and the v2 result is the prior AGAINST it. Append stays capped (m <= 3) and strictly
  below the cosine block.

### C.4 — The wormhole funnel filter

Let p_f = probability a proposed bridge is false; q = probability a traversal of a false
bridge produces a user-visibly wrong answer (and thus a correction).
- P(false bridge solidifies) = p_f * (1 - q)^3. At q = 0.5: 12.5% of false bridges survive
  the funnel; at q = 0.7: 2.7%. The funnel is a multiplicative filter on hallucinated links.
- Never-traversed false bridges are killed by TTL regardless of q.
- The center-port throttle bounds concurrent exposure: at most one provisional non-local
  hypothesis per memory, so even a proposal-happy LLM cannot flood the graph.
- Solidified-wormhole precision is measured, not assumed (E.5); if q proves low (silent
  wrong answers), the funnel weakens and the threshold s rises or the hot hunter dies.

### C.5 — Turn-cost budget

The classification channel adds one constrained schema (~50-150 output tokens) to the
existing call: no second model call, no second GPU pass. Disabled on action turns. Against
the measured 33-56 s/turn, marginal; measured before/after in E.5's harness anyway.

---

## Part D — Pre-registered tests (Gate-1 discipline: falsifiers first)

Carried from v2 (amended, unchanged): E.1 temporal operator on LoCoMo cat-2 with
answer-accuracy co-primary + anchored pre-count (known: 72 anchored / 249 point / n=321)
+ retrieval-vs-answer layer separation; E.1b false-supersession guard; E.2 LongMemEval with
honest-k. New in v3:

### E.3 — The Regulator (the deterministic leg's new mechanism)
Harness: longitudinal replay (their own bench B2/L17 correction pattern, extended) plus
LongMemEval knowledge-update items. Arms: (a) full hierarchy, (b) repetition-only
(counters, no user dominance), (c) OFF (v2 baseline).
Metrics, all deterministic:
- CPR, Correction Persistence Rate: after a user correction, fraction of subsequent related
  queries served the corrected value. Target: full >= 0.95; the v1 poisoning history is the
  cautionary baseline.
- Poison Rate: fraction of served "facts" whose lifecycle never contained an explicit user
  signal (i.e. things the system convinced itself of). Target: full ~ 0 by I1; arm (b)
  measures how bad counters-alone get.
- Promotion Precision: of points promoted to FACT, fraction later corrected. Target >= 0.95.
Falsifier: if arm (b) matches arm (a) on CPR and Poison Rate, the hierarchy adds nothing
over plain counters and R collapses to the existing utility EMA. If arm (a) does not beat
arm (c), the Regulator itself is dead weight.

### E.4 — Typed-port routing (H-route)
Harness: LoCoMo (intent classes from the router) and optionally HotpotQA bridge. Arms:
BASE (pure cosine) vs cosine + Rho (typed, append-only, m<=3). Report PER INTENT CLASS and
per non-matched class (drift guard).
Falsifier: typed append <= BASE on its matched intent class. Given v2 killed untyped
append, this would kill expansion in ALL forms; Rho is deleted and ports remain
state-and-Sigma-only. Pre-committed: no threshold tuning to rescue a negative.

### E.5 — The in-turn wormhole funnel
Harness: live longitudinal run (their bench + organic sessions), N pre-counted.
Metrics: proposal rate/turn, traversal precision of provisional bridges, survival rate,
precision of SOLIDIFIED bridges (fraction never subsequently corrected), answer-latency
delta of the classification channel (C.5).
Falsifier: solidified precision < 0.8, or survival ~ 0, or proposal rate so low the
mechanism is inert -> the hot hunter dies; cold-only or no wormholes. (The concept has
already survived zero times in production; this is its last test.)

### Reporting rules (carried)
Per-category n pre-counted before any decisive claim; one change = one measurement;
aggregates never decide (per-class lines do); honest k everywhere; production untouched
until numbers land; every run recorded in the ROADMAP with evidence.

---

## Part E — Implementation mapping (Rule 5: reuse, never duplicate)

| v3 element | Existing asset it extends | Change class |
|---|---|---|
| Ports | FuEdge.relation (8 types already stored) | enum mapping + port index; additive |
| Lifecycle S | facts.FactStore + status field (active/superseded/dormant) | add TEMP/CANDIDATE states + c |
| Regulator R | grader + taxonomy.apply_user_feedback + directives signal path | promote grader from turn-scorer to state-machine owner |
| Turn contract | constrained router schema (40/40) + context_pack channel | add fields; action-turn gating exists (opener pattern) |
| Theta/Sigma | v2 plan (committed) | unchanged |
| Rho | retrieve expansion code path (currently dead per v2) | rewrite as typed append-only |
| Hot hunter | agent turn loop + tool_loop event channel | new optional schema field |
| Cold hunter | dream loop + WormholeCalibrator | funnel replaces instant creation |
| Funnel counters | route_memory-style confirmation gating (execution-confirmed exemplars) | same pattern, new table |

Compatibility (Rule 11): all changes additive; v2's Sigma/Theta unchanged; existing canon,
directives, hygiene, UI contracts untouched; nano fallback retained.

## Part F — Rejected and dead (so it is never re-litigated)

- Path B, HMG-as-LLM: rejected (frozen function vs mutable state; no training budget;
  kills precise recall; the between-questions thinking is the dream loop).
- Untyped expansion: dead (v2 measurement). Typed expansion lives only until E.4 speaks.
- Recency, kappa, density, distance in ranking: dead (v1, settled).
- Nano as sole edge-classifier: demoted to fallback (fragility measured, Issue 8 history).
- Instant wormhole creation (no funnel): dead (it produced zero true and unbounded false).

## Part G — Honest framing: convergences and the actual deltas

Convergent with published work (verified this revision):
- LLM-driven link generation at ingest: A-Mem (NeurIPS 2025) retrieves candidates and lets
  an LLM decide links, evaluated on LoCoMo. The v3 hot hunter is this idea placed mid-turn
  with the answer call, plus a validation funnel A-Mem lacks.
- Feedback-driven memory: growing stores of user corrections (Madaan 2022; Tandon 2021);
  lifecycle tiers with promotion/demotion (AMV-L); gated memory transitions (TrustMem).
- The failure mode the Regulator prevents has a name and a benchmark: memory misevolution
  (MemEvoBench, 2026): biased feedback degrades agents and static defenses are
  insufficient. v3's hierarchy is a dynamic defense.

Claimed as this project's deltas (hypotheses until E.3-E.5 speak):
1. Invariant I1: corrections as ABSORBING state transitions, making anti-poisoning a
   structural property (no repetition path to FACT), not a tuned weight.
2. The typed-port hexagon: geometry as routing schema, six local relation types + one
   throttled non-local port. Answers "why hexagonal" for the first time since HMG-01.
3. Promotion-by-use strictly subordinated to user verdict (the two-teacher loop: one user
   signal trains both the chooser (LLM) and the governor (Regulator)).

## Part H — Golden Rules traceability

R1/R2: every settled claim carries its measurement; every new mechanism was checked against
code assets and literature before design. R3: v3 changes architecture (governance layer),
not weights. R5/R11: Part E maps every element to an existing asset, additive. R6/R7/R8:
this document precedes implementation; E.3-E.5 define the evidence. R12: no v3 mechanism
may be reported as working without its pre-registered number. R13: the funnel fixes link
formation at the proposal layer, not by tuning gates. R14: production untouched until
E-gates pass on clones.
