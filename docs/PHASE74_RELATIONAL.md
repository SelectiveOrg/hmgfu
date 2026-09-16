# Phase 74 — Relational bench: does the Fu package earn its complexity?

Date: 2026-09-05. Branch `phase74-relational` from `750ce33`. Programme "Fu 2" row 74. Pre-registered here BEFORE any
number (Rule 12); the arms and falsifiers are Fu-R §11's (`reports/fu_theory_proposal_20260905/FU_R_PROPOSTA.md`).

## Why this bench exists

The theory's one falsifiable claim is relational recall: memories linked by time, cause or entity to the one a question
names, not the semantically closest text. The only Fu-vs-cosine comparison on record tied (19/20, Phase 30); E.2 showed
the supersession/dates leg beating cosine on LongMemEval Knowledge-Update (+0.153) as a bundle. Originality is decided
against **B2**, the strong provenance/fixed-revision control — a win over plain cosine (B0) proves nothing new.

## Corpus (sealed: `scripts/oracles/relational_v1.json`, generator `scripts/relational_corpus.py`, seed 74)

A deterministic first-person diary, PT/EN, 159 messages over 155 days in 39 sessions: four sequential projects (start
with a reason, tool, a person met while on it with their place, a helper, a blocker, an end), preferences with one
explicit correction and three IMPLICIT revisions (STALE-style), independent facts that must survive the revisions,
semantically close distractors (a third person's preference, a hypothetical, a lunch that mentions a project contact),
and 120 unrelated diary lines so that top-k matters. Every message has an id; every question has GOLD ids, and where
relevant the CURRENT truth values and the retired STALE values.

| Family | n | What it tests |
|---|---|---|
| relational | 28 | the answer is in a message RELATED to the one the question names (project ↔ person ↔ place ↔ tool) |
| temporal | 19 | before/after/first/last; history questions where a SUPERSEDED value is the correct answer |
| implicit_revision | 5 | the current value after an unannounced change |
| non_interference | 4 | independent facts untouched by revisions around them |
| distractor | 4 | the closest text is the wrong one |

## Arms (same embedder bge-m3, same k = 12, same context budget, same reader, nano OFF at ingestion for all)

| Arm | Retrieval | Context policy |
|---|---|---|
| B0 | plain cosine top-k (bench-only comparator from `bench_ab_retrieval`) | memory lines with dates |
| B1 | cosine top-k | B0 + canonical ledger lines (validity at query time, history lines on past cues) |
| B2 | cosine top-k | B1 + provenance and FIXED-policy revision: superseded/reverted values excluded, echo-free answer context — the strong control |
| F | production `retrieve_memory` (6 channels, Fu expansion, wormholes, weights) | same as B2 |

B2 and F differ ONLY in retrieval, so F − B2 isolates the Fu package.

## Metrics

* **Hit@k** (primary, deterministic, no LLM): fraction of questions whose gold ids are all in the retrieved top-k.
  Reported per family with a paired bootstrap 95% CI for F − B2.
* **Context truth**: the injected context contains a truth value and no stale value (the truth-bench rule).
* **Answer accuracy** (co-primary, LLM leg, `--answer`, 3 repetitions): the reader answers from each arm's context.
* **Cost**: model calls and tokens per query and per ingestion, from the Phase 73 call ledger.

## Gate (fixed before the numbers)

**F beats B2 on relational Hit@k by ≥ +0.10 absolute with a paired bootstrap 95% CI excluding 0, with no regression
> 0.05 on the implicit-revision and non-interference families, at ≤ 1.25× B2's total cost.** Otherwise the honest
claim is "good provenance engineering": the Fu package (expansion, wormholes, learned weights) is re-scoped to an
experimental arm and the assessment's originality figure does not move up.

Falsifiers (Fu-R §11) checked one by one at the verdict: F ≤ B2 on held-out tasks; gains only with perfect
dependencies; gains only under frequent change; revision erasing independent facts; gains vanishing once extraction
and maintenance are counted; a win on one model/set/phrasing only.

## Results

### First run (pre-registered result; head `f1a8d7b`, clean tree)

| Arm | Hit@12 | relational | temporal | implicit_revision | non_interference | distractor | context truth | stale leak |
|---|---|---|---|---|---|---|---|---|
| B0 | 0.717 | 0.643 | 0.684 | 1.0 | 0.75 | 1.0 | 0.85 | 0.117 |
| B1 | 0.717 | 0.643 | 0.684 | 1.0 | 0.75 | 1.0 | 0.90 | 0.133 |
| B2 | 0.717 | 0.643 | 0.684 | 1.0 | 0.75 | 1.0 | **0.533** | 0.117 |
| F | **0.633** | 0.571 | 0.684 | 0.6 | 0.75 | 0.75 | 0.60 | 0.10 |

Paired F − B2 on all questions: **[−0.167, −0.017]** — the interval excludes zero on the wrong side; the falsifier
"F ≤ B2" is triggered on this run. Cost: identical ingestion, one embedding call per query in every arm, ~30 s per arm.

### What the run exposed (before any verdict)

B2's context truth collapsed below B0's because two write-side false positives turned project names into "superseded
family names" — the model mapper wrote `family.mother_name = Echo` from "For Echo I am writing everything in Kotlin"
(value in text, attribute nowhere), the regex wrote `family.sister_name = mucapata` from "My sister's favorite food is
mucapata" — and the read-side filter then dropped every memory mentioning "Echo" or "Delta" as a stale value. That is
Fu-R §11's "revision erases independent facts", reproduced on a synthetic corpus built to catch it. Fixes at their
layers: the mapper writes only when the text names the attribute; a relative's attribute is an open key, never the
relative's name; stale/reverted exclusion is attribute-gated (the 69.4 gate on the read side). Write sets v1–v3
unchanged after the fixes.

### Second run (after the fixes, head `5b32b53`; labelled, not the pre-registered result)

| Arm | Hit@12 | context truth | stale leak |
|---|---|---|---|
| B0 | 0.717 | 0.85 | 0.117 |
| B1 | 0.717 | 0.883 | 0.133 |
| B2 | 0.717 | **0.833** (was 0.533) | 0.117 |
| F | 0.633 | **0.767** (was 0.60) | 0.10 |

Context truth recovered in both provenance arms; retrieval did not move. Paired F − B2 [−0.167, −0.017]. Ablation of the
Fu package (F only): noexpand 0.633 · no_wormhole 0.633 · no_dense_recent_goal 0.617 · semantic_entity_only 0.617 ·
semantic_only 0.617 — expansion and wormholes change nothing; Fu's semantic channel alone loses to plain cosine. Cause:
the five missed gold items have cosine 0.47–0.69 but composite score 0.20–0.36, under the absolute `RETRIEVAL_MIN_SCORE`
0.35, and dream macros crowd F's top 3. Fix at the ranking layer, general: `min_score` is a relevance floor (a semantic
candidate passes on similarity; relational-channel candidates keep ½ the floor); ranking stays the composite score.

### Third run (relevance floor, head `b9507a4` + floor; `outputs/runs/20260905T180609Z-b9507a4`)

| Arm | Hit@12 | relational | temporal | implicit_revision | non_interference | distractor | context truth |
|---|---|---|---|---|---|---|---|
| B0 / B1 / B2 | 0.717 | 0.643 | 0.684 | 1.0 | 0.75 | 1.0 | 0.85 / 0.883 / 0.833 |
| F | 0.650 | 0.571 | 0.684 | 0.8 | 0.75 | 0.75 | 0.783 |
| F, no_macros | 0.683 | 0.643 | 0.684 | 0.8 | 0.75 | 0.75 | 0.80 |
| F, no_edge_kappa | **0.700** | **0.679** | 0.684 | 0.8 | 0.75 | 0.75 | 0.85 |

Paired F − B2 (all): [−0.133, −0.017]; relational [−0.179, 0.0]. **Per question, F never recovers a gold item that cosine
misses: zero F-only wins in any run; the 17 questions all arms miss are the same 17.** Removing the edge-κ term is the
only ablation that lifts F above B2 on the relational family (+0.036, far under the +0.10 gate).

### Why F loses the rest: edge-κ hub inflation (measured on the F database)

For "What is my favourite colour?" the gold message has cosine 0.515, higher than every one of F's twelve results (max
0.464), and is absent. The κ term (weight 0.20) uses the strongest edge from the candidate to ANY other candidate. Four
near-identical filler lines ("Long walk after dinner") are linked to each other by same_entity edges at κ 0.74, so each
earns ≈ +0.15 and a small distance penalty (0.33); the unique gold has a weak temporal edge (κ 0.21) and a large penalty
(0.75). Composite: gold 0.227, filler 0.326. This is the Phase 47 hub problem — gated there for density and utility, never
for edge-κ. In theory terms, §30's βκ is not query-relative: a cluster of self-similar memories inflates every member
whatever the question. The production fix is a measured step (ROADMAP 74.7), not a tune to this set.

### Extraction finding (both arms alike)

With nano OFF the heuristic extractor missed two of the three implicit revisions ("Comprei tinta burgundy para o quarto
— é a minha cor favorita", "Ordered maheu again — it has been my favorite drink for weeks now"). The ledger therefore
asserts amber and passion-fruit juice, and the reader trusts the ledger over the memory: the implicit_revision family
measures the write-side extractor, not retrieval. Recorded as a write-side item for the next phase.

### LLM leg (74.4) and bench errata

First pass (`outputs/runs/20260905T181353Z-b9507a4`): answer accuracy B2 0.367 · F 0.383 ×3 — parity, low in both arms.
Reading the replies showed two bench defects, not reader defects: the scorer's negation rule rejected any answer whose
clause contained a historical word ("the **old** spreadsheet kept breaking", "you **were** working on Atlas"), and the
sealed oracle lists English-only truths for two Portuguese questions (printer/impressora, server/servidor). The scorer is
fixed at the bench layer (historical markers count only when adjacent to the value; explicit negation stays clause-wide;
`test_v44` +7 cases). The oracle stays sealed; the PT/EN gap is errata on q003 and q012, both arms alike. The re-scored
replies exposed two more pre-existing scorer faults, fixed the same way (+8 cases): the contraction pattern matched any
word ending in "-nt" ("a **client** asked for it" failed), and a clause-wide "no" rejected "the school had **no** site at
all". "No"/"não" now negate only as a clause opener or in "no longer / no more / no idea".

Final leg (scorer as above, three repetitions, `outputs/evidence_74_llm_final.txt`):

| Arm | answer accuracy | given a retrieval hit | given a miss |
|---|---|---|---|
| B2 | 0.550 | 0.581 | 0.471 |
| F | 0.517 | 0.667 | 0.238 |

Paired F − B2 on answer accuracy: [−0.117, 0.067]. The remaining wrong answers are shared by both arms and are not retrieval:
the ledger's wrong current values on the two missed implicit revisions (amber, passion-fruit juice — 6 questions), the
PT/EN truth gap (2), reader errors on "which project came after X" ordering (4) where the context holds every project
start with its date and the reader still misorders them, and place questions (4) where the reader returns the project's
descriptor ("a podcast studio") although the meeting line with the place is in the context.

## Verdict (74.5) — against the gate fixed in 74.1

**The gate is not met. The honest claim is "good provenance engineering".** F does not beat B2 on relational Hit@k by
+0.10 with a CI excluding zero; on three runs F is BELOW B2 (0.633 / 0.633 / 0.650 vs 0.717) with the paired interval
excluding zero on the wrong side each time, and at the best ablation (no edge-κ) F reaches 0.700 overall and +0.036 on
the relational family. Answer accuracy is at parity. Cost is identical (one embedding call per query in every arm,
identical ingestion). Falsifiers from Fu-R §11, one by one:

| Falsifier | Verdict | Evidence |
|---|---|---|
| F ≤ B2 on held-out tasks | **triggered** | three runs, all arms on the same sealed set; F never recovers a gold item that cosine misses (zero F-only wins) |
| gains only with perfect dependencies | not testable — no gain to condition on | the edge structure the Fu package builds (same_entity, temporal, semantic_similarity) inflated filler clusters instead of linking question to answer |
| gains only under frequent change | no gain to condition on | temporal family tied (0.684 = 0.684) in every run |
| revision erases independent facts | **triggered on run 1, fixed** | two write-side false positives + an ungated read-side exclusion removed every Echo/Delta memory; fixed at the mapper, the key normaliser and the context builder (attribute-gated); non_interference 0.75 = 0.75 after |
| gains vanish once extraction and maintenance are counted | moot | there is no gain; cost is identical by construction (same embedder, nano off) |
| a win on one model / set / phrasing only | moot | no win to qualify |

What the Fu package did deliver on this corpus is the provenance layer — ledger lines with validity at query time,
history on past cues, superseded and reverted values excluded from the answer context, echo-free user-fact answers —
and B2 has all of it. That is engineering the theory does not own. Consequences, as pre-registered: the Fu package
(expansion, wormholes, learned weights, edge-κ) is re-scoped to an **experimental arm**; the assessment's originality
figure does not move up (row 74). The mechanism found in the loss (edge-κ is not query-relative, §30) is a real theory
correction and goes into production as a measured change (ROADMAP 74.7), gated on the same benches — a fix, not a claim.

## 74.7 — the theory correction, measured (after the verdict, not part of it)

Path-κ is now query-relative: the κ an edge lends to a candidate is edge.κ scaled by how relevant the edge's OTHER
endpoint is to the query (the Phase 47 relevance gate, reused), the score takes the strongest path (direct or via the
edge), and an edge that lends nothing brings no distance penalty. Wormhole boost and tension are untouched (one
variable). The weight learner scores exactly what retrieval scored (`RetrievedMemory.path_relevance`).

| Measurement | before | after |
|---|---|---|
| relational Hit@12, F | 0.650 | **0.683** |
| relational family, F vs B2 | 0.571 vs 0.643 | **0.643 vs 0.643** (paired CI [0.0, 0.0]) |
| context truth, F | 0.783 | 0.833 (= B2) |
| truth bench (no-echo) | 17/17 · 1.0 | 17/17 · 1.0 |
| AB retrieval (Phase 30 set), FU hit@1 / MRR | 0.78 / 0.87 | 0.78 / 0.87 |
| held-out m1 / m2 / m3 · oracles | 25/25 · 6/7 · 13/13 · 51/51 · 33/33 | identical |

The step's own gate (≥ 0.700, the edge-free ablation) is missed by one question: the colour gold is now outranked by
nine dream macros with cosine 0.42–0.46 (vs 0.515) that carry the DREAM's timestamp — recency 1.0 while every episode is
backdated — a different defect (74.8: a derived node's recency is its content's recency). The correction is adopted
because it removed exactly what it targeted with no regression on any gate; the missed gate is recorded as is. It
does not change the verdict: at parity on the relational family, F still does not beat B2.

## 74.8 — a derived node is as recent as its content (measured after the verdict)

A macro's timestamp is now its newest member's, at creation and on merge (the dream's own bookkeeping,
`last_accessed_at`, is untouched). Measured first with the harness as it was: no change (0.683) — and the F database
showed why: every macro was still dated today because the harness backdated each point AFTER ingest had built the
macros. The product gained what the bench lacked: `ingest(..., timestamp=)` carries the observation time (imports and
replays need it too), and the harness ingests each message at its time.

| Measurement (observed-time ingest) | B2 | F |
|---|---|---|
| Hit@12 | 0.717 | **0.717** |
| relational family | 0.643 | **0.679** (paired CI [0.0, 0.107]) |
| implicit_revision | 1.0 | 1.0 |
| distractor | 1.0 | 0.75 |
| context truth | 0.850 | 0.867 |

Truth bench 17/17 · 1.0; AB retrieval unchanged at FU hit@1 0.78 / MRR 0.87 (one intermediate run read 0.89 / 0.94 —
that nine-query bench runs the live nano extractor and varies run to run, so no claim is made from it); held-out and
oracles identical. **The verdict stands**: with both corrections F reaches parity with the strong control and edges it on the
relational family by +0.036 — far from the pre-registered +0.10 with a CI excluding zero. What the bench bought is two
real defects out of production scoring and one out of ingestion, each measured alone.

What would change the verdict: a corpus where the answer is reachable ONLY through a relation (no lexical or semantic
overlap between question and gold) — this corpus's relational questions still share the project name with the gold, so
cosine finds them — run with the same pre-registration. That is the next bench worth building, not another tune.
