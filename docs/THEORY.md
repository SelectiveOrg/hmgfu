# HMG-Fu — Polished Theory

Analysis and refinement of *Algoritmo de Memória HMG-Fu* + *HMG-01 Vision* (H. H. Ferreira).
Part A restates the theory faithfully. Part B is the **polish log**: every issue found in the source
documents, the decision taken, and where it is implemented. The code in `hmgfu/` implements *this*
document; where it deviates from the PDFs, the deviation is recorded here (Golden Rule 8).

---

## Part A — The formal system

```
HMG-Fu = (P, E, H, ρ, κ, Ω, Φ, Ψ, Δ, Λ)
```

| Symbol | Meaning | Implementation |
|--------|---------|----------------|
| P | Memory points (discrete units: message, fact, goal, person, event, pattern, macro…) | `models.MemoryPoint` |
| E | Fu edges — the *interval* between points, a first-class entity | `models.FuEdge` |
| H | Hexagonal grid organising points by contextual neighbourhood | `hexgrid.py` (cube coords) |
| ρ | Ontological density — how much a memory "exists" (0..1) | `fu_math.compute_density` |
| κ | Coupling strength between two memories (0..1) | `fu_math.compute_kappa` |
| Ω | Relation-type geometry factor (0..1.2; wormhole > 1) | `fu_math.OMEGA` via config |
| Φ | Energy propagation through Fu edges | `propagate.py` |
| Ψ | Contextual retrieval (multi-channel + activation score) | `retrieve.py` |
| Δ | Decay / healthy forgetting | `fu_math.compute_decay`, `dream.py` |
| Λ | Compression (macros) & promotion across layers | `dream.py`, `ingest.update_macros` |

### Core principle
> Memory is not `message → embedding → nearest vector`.
> Memory is `point → Fu interval → relational field → propagation → contextual recall`.
> The memory lives **in the interval between points**, not in the points.

### Layers
`L0_raw → L1_session → L2_project → L3_identity → L4_world_model → L5_deep_pattern`.
Promotion moves a point up one layer when it proves stable, recurrent and useful (§21).

### The Fu equation (memory form)
With £P ≡ 1 relational unit:

```
F(A,B) = N(A,B) · [1 + κ(A,B) · ρ(A) · ρ(B) · Ω(A,B)]
```

F is the **relational magnitude** of the interval. See Part B, issue 1 for how F relates to the
retrieval *distance penalty* (they are not the same thing).

### Density ρ (§6)
`ρ(p) = clamp01( 0.22·I + 0.16·R + 0.13·E + 0.18·U + 0.12·C + 0.07·N + 0.12·L )`
I importance, R recurrence (log-normalised access count), E emotional intensity, U utility,
C confidence, N novelty, L relational centrality. Weights sum to 1.00 ✓.

### Coupling κ (§7)
`κ(A,B) = clamp01( 0.25·S + 0.10·T + 0.18·En + 0.18·G + 0.14·C + 0.15·X )`
S semantic cosine, T temporal proximity, En entity Jaccard, G topic/goal Jaccard,
C causal signal, X explicit reference. Weights sum to 1.00 ✓.

### Relation type Ω (§8)
Fixed table (same_entity 1.00 … contradiction 0.55), `wormhole = 1.20` — deliberately >1: a rare,
non-local, high-value traversal between memory biomes.

### Activation score (§10) and final retrieval score (§30)
```
MemoryScore(p|q) = αS + βκ + γρ + δU + εR + ζM + ηW − λD_Fu − τT
α..τ = 0.42, 0.20, 0.06, 0.05, 0.07, 0.08, 0.07, 0.03, 0.02
```
S = `0.75·embeddingCosine + 0.25·literalQueryCoverage`; the literal component prevents an
embedding collision from outranking an exact codeword/name/content match. W = wormhole boost,
D_Fu = normalised Fu distance penalty, T = unresolved tension penalty.
The density and utility mass is multiplied by a query-relevance gate. Query fit (S + query κ)
therefore remains stronger than accumulated repetition: popularity supports a relevant memory,
but cannot reverse a material semantic-relevance advantage after the gate saturates.
Max positive mass = 0.95, penalties ≤ 0.05 → score naturally lives in [−0.05, 0.95] ⊂ [−1, 1],
clamped to [0,1]. (§10's ACTIVATION_WEIGHTS is the earlier draft of the same formula; the code uses
the §30 FINAL weights as the single source of truth — Part B, issue 2.)

### Energy propagation Φ (§14)
BFS from an activated point, depth ≤ 3, attenuation per hop:
`E' = E · κ · Ω · trust · distanceDecay(d) · (1 − tension)`, cut-off at 0.05.

### Ingestion (§11–13)
sensitize → embed → density → hex placement (weighted-centroid of 12 nearest semantic points,
weight = cos·ρ) → candidate search → FuEdge build (drop κ < 0.18 unless wormhole) → propagate →
macro update.

### Retrieval Ψ (§15–16)
Six candidate channels — semantic (60), entity (30), active-goal (30), recent (20),
dense-identity (20), wormhole (20) — deduplicated, scored, top-k (≥ 0.35), then **Fu expansion**
(neighbours with κ ≥ 0.45, trust ≥ 0.55, distance ≤ 2.5; expanded score = parent · κ · trust,
floor 0.25), then compression to a token budget, then structured injection (§23):
identity / projects / facts / recent / warnings / contradictions / likely next actions.

### Dream loop (§19)
Periodic reorganisation: consolidate clusters (≥5 nodes, κ ≥ 0.4) into **macros**; create
**wormholes** for distant analogical pairs (§17 criteria); detect **contradictions** (§22) and mark
tension; **decay** weak memories to dormant; **promote** stable ones (§21); rebalance hex grid;
generate insights. Produces a persisted `DreamReport`.

### Wormholes (§17)
`hexDistance > 5 ∧ analogy > 0.7 ∧ utility > 0.6 ∧ novelty > 0.5 ∧ semantic > 0.42 ∧
entityOverlap < 0.5 ∧ topicOverlap ≥ 0.25` → two-way edge, κ=0.85, Ω=1.2, distance=0.5, trust=0.65.

### Decay Δ (§20)
`D(p) = 0.04 · (1−ρ) · (1−utility) · (1−recurrence) · ageFactor`, capped at 0.2.
`energy < 0.05 ∧ ρ < 0.2 ∧ accessCount < 2` → status **dormant** (never deleted).

### Promotion (§21)
`ρ > 0.68 ∧ utility > 0.55 ∧ confidence > 0.65 ∧ accessCount ≥ 3 ∧ stability > 0.6` → layer+1,
stability +0.15.

### Contradictions (§22)
Scored between strong neighbours; resolution: newer > higher-confidence (+0.2 margin) >
explicit-user-statement > needs_clarification. Loser is *superseded*, not erased (tension recorded
on the edge; retrieval surfaces contradictions explicitly in the injection).

### Master cycle (§24)
Per user turn: query point → retrieve → build injection → **gemma4:12b** answers → ingest user
message → optionally ingest assistant reply → reinforce activated paths (§25: accessCount+1,
energy += score·0.2, κ += score·0.03, trust += 0.01) → mini dream loop if due.

### From HMG-01 Vision (kept as requirements)
- Macro→micro **zoom navigation** over the hex grid (UI).
- **Explainability**: show "where the AI walked" — every retrieved memory carries a `reason`.
- Emotional indexing of memories; session clusters compressed into macros.
- Deterministic, milliseconds-scale navigation (retrieval is local math, not an LLM call).

---

## Part B — Polish log (issues found → decisions)

**Issue 1 — F "distance" grows when the relation is *stronger*.**
`F = N·(1+κρρΩ)` increases with κ, ρ, Ω — so treating F as a metric distance would push strongly
related memories *apart* in retrieval. The source itself warns "distância baixa nem sempre significa
relação forte" and forbids ranking by F alone.
**Decision:** F is interpreted as *relational magnitude* (size of the interval's content, like a
"mass" of the relation). For the retrieval penalty `D_Fu` we use the **base separation N only**,
normalised — hops in the graph / hex distance — while κ, ρ, Ω contribute *positively* through their
own terms. `FuEdge.distance` stores F for analytics and propagation decay, but ranking uses the §30
score exactly as specified. This preserves the theory (F exists, is computed, is stored) and fixes
the metric misuse.

**Issue 2 — Two overlapping scoring tables (§10 vs §30).**
ACTIVATION_WEIGHTS (§10) and FINAL_MEMORY_SCORE_WEIGHTS (§30) describe the same A(p|q) with
different numbers; §30 adds the wormhole term.
**Decision:** §30 is canonical (it is the "final formula"). One implementation:
`fu_math.memory_score()`. §10's table is not implemented separately (Rule 5: no duplication).

**Issue 3 — Energy amplification with Ω > 1.**
Wormhole Ω = 1.2 could in principle amplify energy per hop. Worst case per hop:
`κ·Ω·trust·decay·(1−tension) = 0.85·1.2·0.65·decay·1 ≈ 0.663·decay < 1` — attenuating even before
distance decay. General guard anyway: the per-hop attenuation factor is clamped to ≤ 0.95 so **no
edge configuration can amplify**, and point energy is clamped to [0,1].

**Issue 4 — Decay could silence load-bearing memories.**
`D(p)` uses ρ, but a briefly-idle hub could still drift toward dormancy in edge cases (and a prior
system of the same author suffered exactly this failure mode).
**Decision:** dormancy additionally requires **low centrality** (weighted degree < 0.3 normalised).
Dormant ≠ deleted: dormant points stay in the store, are excluded from candidate channels, but can
be *re-awakened* if directly referenced (entity match), restoring status to active.

**Issue 5 — Undefined helper functions.**
The PDFs use `normaliseLog`, `temporalProximity`, `recencyScore`, `distanceDecay`,
`computeBaseSeparation`, `computeResonance`, `computeTension`, `computeRelationTrust`,
`computeStability`, `computeModeMatch` without definitions. **Decisions (all in `fu_math.py`):**
- `normalise_log(x) = min(1, ln(1+x)/ln(1+X_REF))`, X_REF = 20 accesses.
- `temporal_proximity(t1,t2) = exp(−|Δt|/τ)`, τ = 72 h.
- `recency_score(t) = exp(−age/τ_r)`, τ_r = 14 days.
- `distance_decay(F) = 1/(1+max(0,F−1))` — F=1 (minimal interval) → 1.0, larger intervals attenuate.
- `base_separation(A,B) = 1 + hex_distance(A,B)/3` (hexes are contextual neighbourhoods; ≥1 by def).
- `resonance(A,B) = 0.6·semantic + 0.4·(1 − |valenceA − valenceB|/2)`.
- `tension(A,B) = contradiction_signal · topicOverlap` (conflict only matters on shared topics);
  contradiction_signal from sensitizer (nano) or negation-heuristic fallback.
- `trust(A,B) = 0.5·source_trust(A,B) + 0.5·mean(confidence)`, source_trust: user_explicit 0.95,
  user 0.80, assistant 0.65, dream 0.60.
- `stability(p) = 0.5·ρ + 0.3·normalise_log(accessCount) + 0.2·confidence`.
- `mode_match`: cosine between query intent/topic set and point topics (Jaccard), fallback 0.5.
  "User mode" is modelled as the query's declared intent (question/task/reflection/emotional).

**Issue 6 — Macro storage split-brain.**
§27 defines a separate `memory_macros` table, but macros must participate in retrieval, propagation
and the hex grid like any point (§18 links macros to clusters).
**Decision:** a macro **is a MemoryPoint** with `type="macro"`, higher layer, plus a
`macro_sources(macro_id, point_id)` table and `part_of` FuEdges to its children. No second storage
path (Rule 5). `dream_reports` table kept as specified.

**Issue 7 — `inferResolution` favours A on equal timestamps and never checks B's explicitness.**
**Decision:** symmetric resolution — compare newer-first with strict inequality, then confidence gap
> 0.2 either way, then explicit-user-source either way, else `needs_clarification`. Winner
supersedes: loser gets status `superseded` when the winner is `user_explicit`, otherwise both stay
active with recorded tension (safer than auto-deleting a possibly-true memory).

**Issue 8 — Nano models produce malformed JSON.**
The whole pipeline depends on the sensitizer. A 1.5B model will sometimes emit broken JSON or drift.
**Decision:** three-stage parse (strict `json.loads` → first-`{…}`-block extraction → per-field
regex), then a **deterministic heuristic fallback** (capitalised-token entities, keyword topics,
valence lexicon, length/`?`-based importance defaults) so ingestion *never* fails on nano failure.
Every extraction records `extractor: "nano" | "fallback"` for observability.

**Runtime context and multilingual action control (2026-07-05).**
Time is an observation, not model knowledge. At the start of each turn the system captures one
immutable tuple `C_t = (local ISO time, UTC ISO time, local date, local time, timezone name,
UTC offset, Unix seconds)`. The exact same `C_t` is supplied to query sensitization/routing and to
the answer model. Relative-time interpretation therefore has a single source of truth; changing
clock values are never frozen in a prompt or stored as permanent facts.

Action selection is `route_gemma(message, live_tool_catalog) -> (act, requested_tools,
needs_memory, freshness, directive)`, with returned names schema-validated against the registry.
The registry is read live so created skills participate without code changes. HMG scoring ranks
related tool points; successful use and user feedback update their utility/Fu relations. Exact tool
names are the only structural fallback—there is no locale-specific natural-language phrase table.
Standing directives preserve the original multilingual instruction; semantic opener text is
generated once, persisted, and deterministically enforced on future matching turns.

**Issue 9 — Retrieval cost of κ against every candidate.**
`estimateQueryKappa(query, point)` needs entity/topic/semantic terms only (no timestamps between
query and memory, no stored edge) — defined as κ with T=0, X computed from literal mention of the
point's title/entities in the query text.

**Issue 10 — Wormhole `analogy > 0.7` needs an analogy detector.**
**Decision:** analogy = structural similarity with lexical dissimilarity:
`analogy = semantic · (1 − entityJaccard)` boosted by shared *topics*; when the nano dream worker is
available it re-scores the top distant pairs (LLM judgement), else the heuristic stands. Candidate
pairs are sampled from high-density points in different hex regions (full O(n²) scan avoided).

**Issue 11 — "Mini dream loop" trigger undefined.**
**Decision:** `shouldRunMiniDreamLoop` = every `MINI_DREAM_EVERY_N_TURNS` (default 8) or when
unpropagated tension count > 5. Mini version runs decay + promotion + contradiction marking only
(no macro/wormhole LLM work) to stay fast; the full dream loop is manual (`/api/dream`, `:dream`)
or nightly.

**Issue 12 — Token budget compression (§15 `compressForLLM`).**
**Decision:** budget in tokens ≈ chars/4. Greedy fill by score: identity & warnings first (small,
high value), then facts/projects, then recent context; each item rendered as its `summary` (falls
back to truncated content). Hard cap default 1800 tokens as specified.

**Issue 13 — Hex placement races/collisions.**
`findNearestAvailableHex` needs a deterministic free-cell search: spiral ring walk (radius 1,2,3…)
around the target centroid, first free cell wins; origin fallback when the grid is empty. One point
per hex cell (a cell is the *address* of a point; zones emerge from neighbourhood, matching the
Vision doc's macro-zones as emergent, not pre-labelled).

**Issue 14 — Assistant-response storage criterion (`shouldStoreAssistantResponse`).**
**Decision:** store when the reply contains commitments, decisions, or novel synthesis — proxy:
extraction importance ≥ 0.45 or type ∈ {decision, plan/task, fact} — else skip (avoids memory
filling with the assistant's own chatter).

**Issue 15 — Assistant self-poisoning of recall (found live, v2).**
Stored assistant replies ("I don't have X recorded…") re-surface with maximal recency and drown
the true canonical facts — the agent keeps confirming its own past ignorance. PA3 hit the same
failure (assistant-role demote 0.85 + canonical-facts-first injection).
**Decision:** the §30 score gains a *source-trust factor*: `score ×= SOURCE_SCORE_FACTOR[source]`
(user_explicit 1.25, user/system 1.00, dream 0.95, assistant 0.85). Combined with the
question-echo filter (`ECHO_FILTER_MIN_COSINE = 0.93` — a candidate whose embedding ≈ the query IS
the query and answers nothing), canonical user statements reliably outrank both the user's own
echoed questions and the assistant's stored chatter. Regression-tested.

---

## Part C — What the prototype must demonstrate (traceability to Vision)

1. **"The AI that always remembers"** — fact taught once, recalled turns later without chat history.
2. **Relational recall, not RAG** — recall path may traverse Fu edges (entity/goal/wormhole), and
   the trace shows *which* relation carried each memory into context.
3. **Living field** — reinforcement strengthens used paths; dream loop reshapes the grid; noise
   decays; patterns promote.
4. **Explainability** — UI shows the hex walk: query → activated points → expansion edges → injection.
