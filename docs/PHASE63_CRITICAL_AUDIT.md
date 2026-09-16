# Phase 63 — Independent critical audit of Claude's Phase 62

**Date:** 2026-09-04  
**Scope:** review, challenge, test, record, research, and recommend. No production repair was implemented.  
**Repository state:** `f795583` plus Claude's uncommitted Phase 62 changes and the Phase 63 audit artifacts listed below.

## Verdict

Phase 62 contains a real improvement: the governed fact ledger fixes a narrow set of current-value and URL-recall cases, and the current vehicle-link answer check passes 2/2. The temporal/write-side direction is worth continuing.

It does **not** yet demonstrate a reliable general memory system, much less a solution to AGI memory. The published 17/17 score is mainly a test of canonical facts that the benchmark itself injects into every query, not a clean test of retrieval. A no-retrieval control still scores 15/17. In a separate raw-retrieval diagnostic, Fu and cosine both hit 7/8, while cosine produced cleaner results (6/8 without stale values versus Fu's 5/8). The novel relational ranker therefore has no demonstrated advantage here.

The largest risk is upstream of retrieval: the writer can invent a fact absent from the user's words, save it as canonical, label it “confirmed,” and inject it into later system context. That is a persistent false-memory path.

## Evidence at a glance

| Check | Result | Interpretation |
|---|---:|---|
| Offline suite | 369 passed in 177.64 s | Existing tests are green, but omit the failure classes below |
| Python compilation | Clean | No syntax/import compilation failure |
| Production SQLite integrity | `ok` | Database structure is healthy; audit kept it read-only |
| Phase 62 official retrieval benchmark | 17/17 in 295.1 s | Reproduced, but canon is injected before scoring |
| Same scorer with `retrieved=[]` | 15/17 | Proves 15 cases do not require retrieval |
| Current vehicle-link answer check | 2/2 in 141.4 s | Genuine narrow improvement; secret link is intentionally omitted |
| Independent raw retrieval, Fu | Hit@12 7/8; clean 5/8; MRR 0.542 | Small, held-in diagnostic; stale intrusion remains |
| Independent raw retrieval, cosine | Hit@12 7/8; clean 6/8; MRR 0.509 | Same hit rate, slightly lower MRR, cleaner context |
| Natural conversation audit | 2/8 structural checks passed | Replies often claimed writes that the ledger did not perform |
| Live graph utilization | 19/11,137 edges activated; 0 active wormholes | Most relational machinery is operationally inert in this snapshot |

These metrics are deliberately separated into **write**, **retrieve**, and **read/answer** stages. A fluent answer is not evidence that the correct durable state was written, and canonical injection is not evidence that graph retrieval found it.

## What Phase 62 got right

- It introduced an explicit current-fact ledger and fact history instead of relying only on lossy summaries.
- It added a provenance field and surfaced current canonical facts in the UI/API.
- It correctly repaired the tested vehicle-link recall/answer path.
- It added an interrogative gate, slot normalization, supersession, and regression tests.
- It works on database clones in the supplied benchmark rather than deliberately writing benchmark turns into production.

Those are useful engineering steps. The problem is that their contracts are incomplete and the benchmark overstates what they prove.

## Severity-ranked findings

### Critical — canonical writer accepts invented values

`hmgfu/slots.py:175` validates that the model returned a known key, a non-empty value, and a short value. It never proves that the value occurs in, or is entailed by, the user's utterance. The prompt says “never invent,” but that is not an enforceable invariant.

Two reproductions reached the same failure:

1. A controlled mapper returned `family.mother_name=Alice` for a Portuguese color sentence; `map_to_slot` accepted it.
2. In the live natural test, the configured nano model produced the same absent value for an utterance about a favorite color and drink. The ledger stored it as `user_explicit`, and later rendering presented it as confirmed.

This is a complete Write → Persist → Recall false-memory path. The writer must be quarantined until every extracted value is grounded to exact source spans or the system explicitly records it as an uncertain inference outside canonical truth.

### High — substring supersession corrupts unrelated memories

`hmgfu/facts.py:330` uses `old_l in text` when demoting episodic nodes that contain a stale value. With a stale programming language `Rust`, an unrelated active memory containing the word `Trust` was marked `superseded`. The same semantic mistake appears in stale filtering during injection.

This is deterministic data corruption, not a hypothetical edge case. Match normalized tokens or structured claim IDs, never arbitrary substrings.

### High — the writer cannot represent ordinary multi-fact speech

`detect_fact` and the mapper return at most one fact. Natural utterances routinely contain more:

- “My name is …, I live in …, and my dog is …” saved only the name while the reply claimed all three were remembered.
- A location-and-dog correction saved only the location while the reply claimed both were updated.
- “My cat is Luna and my dog is Rex” produced a malformed single `pet.name` value and lost Rex.

The correct unit of work is a list of atomic claims, each with its own source span, subject, predicate, object, polarity, confidence, and validity interval.

### High — single-slot identity collapses entities and cardinality

The schema has one row per global key. It cannot safely express two pets, multiple siblings, repeated addresses, facts about other people, or scoped preferences. The documentation claims 26 slots and multi/single metadata; the implementation contains 25 slots and no `multi` field.

A relational system needs stable entity IDs and explicit cardinality. Otherwise “my cat” and “my dog” compete for the same global cell.

### High — retraction/forgetting is not semantically implemented

“I no longer have a dog” did not clear the dog fact because the clear path expects the model to repeat the exact stored value. The assistant nevertheless said the dog was removed. Later recall still surfaced the stale animal and generated a contradictory answer.

Retraction should target a structured claim or a subject/predicate selector, create a tombstone with provenance, and be tested independently from the assistant's prose.

### High — whole-utterance speech-act gating loses legitimate writes

“Could you remember that my favorite music is marrabenta?” was classified as a request/question and skipped by the fact writer. The assistant replied that it had remembered the information. A single binary label for the whole utterance cannot handle mixed speech acts; classification must occur per clause/claim.

### High — generated summaries are treated as user evidence

The raw point may contain the real user text, but a model-generated title/summary is later injected while retaining `user_explicit` provenance. In the natural test, a question that contained no city or pet assertion acquired a summary containing invented location and pet claims, which was later injected as if it were user evidence.

Raw evidence, derived interpretation, and assistant output must be different record types with different trust levels. Generated text must never inherit the user's provenance.

### High — public entry points implement different memory systems

`/api/agent/chat` and WebSocket agent chat call the Phase 62 ledger and canonical injection. The inherited `/api/chat`, the CLI, public `/api/ingest`, and dry `/api/retrieve` follow older paths and bypass some or all of that behavior. A controlled test stored the same preference through the legacy path: it created a graph point but no canonical fact, and the dry context had no canonical line.

This split-brain behavior makes correctness depend on which endpoint the caller happened to use. All entry points need one application service with one write/read contract.

### High — the 17/17 benchmark is not a retrieval benchmark

`scripts/bench_recall_truth.py:63` supplies `engine.facts.render_lines()` to every query before checking whether expected strings appear. Consequently:

- replacing retrieved memories with an empty list still scores 15/17;
- one Portuguese location query passed with zero retrieved points;
- the lexical scorer accepts negated or historical phrases such as “not Java,” “I do not know whether Java,” and “Java was old” as a current-fact success;
- answer mode scores a different second retrieval inside `agent_chat`, uses one shared mutating database clone, and takes one stochastic sample;
- the data and the Phase 62 code contain the same user-derived facts and value classes, so there is no held-out generalization.

The score proves that canonical injection can print most truth-set strings. It does not establish that the graph retrieved the right evidence or that the model understood current truth.

### Medium — the live Fu ranker conflicts with the project's accepted evidence

The v2 theory specifies pure cosine, and the project's own external evaluations recorded cosine above Fu on HotpotQA and LoCoMo. Yet `retrieve.py` still runs the six-channel Fu blend plus expansion. The Phase 63 diagnostic found equal Hit@12 and worse clean retrieval for Fu, although Fu's MRR was slightly higher on only eight held-in queries.

Keep Fu behind an experimental flag until preregistered external tests show a repeatable gain over a cosine baseline. The potential research contribution may be the governed temporal write/read boundary, not the current scoring formula.

### Medium — provenance is present in storage but incomplete at the trust boundary

Nine of ten live canonical rows lack `source_turn_id`, and `FactStore.active()` omits the fact source even though history stores it. The UI can therefore display a value and a source-turn field without conveying whether it was user text, imported state, model inference, or a generated summary.

Trust metadata needs to survive storage, API serialization, rendering, retrieval, and answer generation end to end.

### Medium — documentation and runtime configuration have drifted

README/AGENTS advertise `nomic-embed-text`, while the project and persisted engine setting use `bge-m3`. `/api/health` reads static config constants, not the resolved engine setting, so it can report a different embedder from the one actually in use. Phase 62 ROADMAP items 62.2 and 62.4 also remain unchecked even though their descriptions say DONE.

This is operationally dangerous because embedding-space mismatches can silently invalidate similarity scores.

### Medium — privacy and memory-poisoning boundaries are not sufficient

An instruction-shaped alias was accepted and injected as a confirmed fact. One subsequent arithmetic probe resisted the instruction, so execution was **not** demonstrated in that one sample; persistence and control-plane exposure were. The system lacks a hard separation between remembered data and instructions.

The truth set and benchmark outputs also contain personal facts and a direct private vehicle-share link while remaining untracked and not ignored. `/api/facts` returns verbatim facts/history, and no authentication middleware was found. Local binding reduces exposure, but any tunnel or network publication must treat these endpoints as sensitive.

### Low/Medium — latency and reproducibility obscure conversational quality

One polite-memory turn required three 300-second route timeouts and completed after 922 seconds. This may be model/runtime behavior rather than the memory algorithm, but a memory benchmark must report retrieval time separately from model-generation time and must use bounded retries. Otherwise a passing answer can hide an unusable system.

## Natural conversation test

The audit ran 12 turns against a scratch database with the currently persisted chat, nano, and embedding models. Tools, grader, learning, and dreams were disabled only to isolate the memory path. The production database was never opened for writing.

The scenarios covered:

- multi-fact disclosure and restart recall;
- multi-fact correction;
- two entities of the same broad type;
- natural retraction without repeating the old value;
- a polite “remember this” request;
- a question containing facts but no assertion;
- an instruction-shaped fact and a later canary probe.

Only 2/8 structural expectations passed: the interrogative gate avoided a canonical write, and the single canary probe did not obey the stored instruction. The assistant often produced reassuring prose that contradicted the actual ledger. Restart recall still returned several facts through raw episodic retrieval, which shows why answer-only evaluation masks write failures.

Detailed machine-readable results are in `outputs/phase63_natural_audit.json`.

## Independent retrieval diagnostic

The audit queried eight current truth cases once each with canonical injection disabled, then scored only the retrieved point contents. It compared the existing Fu pipeline with pure embedding cosine on the same graph and query vectors.

| Pipeline | Hit@12 | Clean hit | MRR |
|---|---:|---:|---:|
| Fu blend/expansion | 7/8 | 5/8 | 0.5417 |
| Pure cosine | 7/8 | 6/8 | 0.5087 |

Both missed the location case. Both returned current and stale values for the programming-language case. Fu ranked the current value higher for one identity query but also admitted an older value; cosine found the current value later without that stale intrusion. A pet hit was itself a lexical false positive caused by an unrelated generated summary, so 7/8 is an optimistic upper bound.

This diagnostic is intentionally modest: eight held-in personal facts, lexical matching, and no confidence interval are insufficient for a research claim. Its purpose is to falsify the interpretation that 17/17 establishes retrieval superiority. Full results are in `outputs/phase63_actual_retrieval.json`.

## Code that is unnecessary, duplicated, or in the wrong lifecycle

Do not delete these blindly; first lock behavior with parity tests and measure the replacement.

1. **Legacy chat/CLI memory path.** It duplicates the agent path while omitting the governed ledger. Deprecate it or route every caller through one memory service.
2. **Fu scoring/expansion in the production default.** The accepted v2 contract and project benchmarks favor cosine; keep the machinery experimental until it earns promotion. The current graph has 11,137 edges but only 19 have ever been activated, and there are no active wormholes.
3. **One-off PA3 importer.** `scripts/import_pa3_user_facts.py` hard-codes another project's path and test-marker names despite this repository's standalone boundary. Its `--dry` mode still constructs an engine whose initialization can migrate/hygiene-sync the target. Archive it after a verified migration, or rewrite it as a truly read-only, input-driven tool.
4. **Permanent startup repair scans.** `retype_stored_questions` and legacy re-keying behave like migrations but run repeatedly. Replace them with versioned, idempotent migrations recorded in schema state.
5. **Hard-coded value dictionaries as semantic truth.** Exact color/language lists are brittle and overlap the benchmark data. They can remain optional extraction hints, but not a fallback capable of asserting canonical truth without a source span.
6. **Open facts beside a “closed” schema.** Arbitrary `open.*` records are stored and displayed but excluded from canonical prompt injection. Either give them a defined review/promotion lifecycle or remove this half-supported path.

## Recommended architecture

The next version should be smaller at the center and stricter at the boundaries:

1. **Immutable evidence log:** preserve raw user/assistant/tool events with conversation, turn, timestamp, and subject IDs. Never overwrite evidence.
2. **Grounded claim writer:** emit zero or more atomic claims, each tied to exact source spans. Reject any value that cannot be grounded; store uncertain inferences separately.
3. **Entity-aware temporal ledger:** model `(subject, predicate, object, valid_time, transaction_time, polarity, status, provenance)`. Derive current views; do not make the view the only truth.
4. **Explicit cardinality and identity resolution:** single-valued preferences, multi-valued relations, and named entities need different merge rules.
5. **One memory application service:** every API, WebSocket, CLI, tool, and benchmark uses the same write/query/retract contracts.
6. **Data/control isolation:** retrieved memories are quoted data with typed fields, never executable system instructions. Tool parameters require grounding back to trusted evidence.
7. **Simple retrieval baseline by default:** cosine plus canonical/temporal filters; Fu relations stay as an ablation arm until external results justify them.
8. **Answer verifier:** compare every claimed write/update/delete in the assistant reply with the committed transaction; either correct the reply or expose the failure.

The valuable hypothesis is therefore narrower and stronger than “a hex grid solves AGI memory”: **a grounded, entity-aware, bitemporal claim ledger combined with measured retrieval and explicit trust may improve long-term agent consistency**. That hypothesis is testable.

## Benchmark required before promotion

Build a frozen, versioned benchmark with independent databases per case and report each stage separately.

### A. Write and update (minimum 200 held-out, multilingual utterances)

Include single facts, 2–5 facts per turn, corrections, negation, retractions, questions, quoted speech, third-person facts, co-reference, two pets/siblings, adversarial instructions, spelling variants, and unsupported model outputs. Measure claim precision/recall, exact source-span grounding, entity accuracy, cardinality, state after update, and false canonical writes.

Promotion gate: **zero ungrounded canonical values and zero cross-entity overwrites** in the frozen safety set.

### B. Retrieval only

Disable canonical text injection. Score retrieved gold point/claim IDs, not strings. Report Recall@k, MRR, stale-intrusion rate, contradiction rate, latency, and index size. Compare:

- no memory;
- raw cosine;
- cosine + temporal/canonical filters;
- cosine + ledger;
- full Fu graph/expansion.

Use paired bootstrap confidence intervals and multiple random seeds. Fu is promoted only if its gain is repeatable and its stale/error rate is no worse.

### C. Reading and answer consistency

Freeze retrieved contexts so every reader sees exactly the same evidence. Score current facts, temporal questions, multi-session synthesis, updates, and abstention. Use structured expected claims plus a semantic judge; never accept a truth word merely because it occurs under negation or as history.

### D. Active application and safety

Test whether memory correctly fills tool parameters and changes actions, not merely whether it can be recited. Separately evaluate the Write → Execute → Forget lifecycle for poisoning, instruction-shaped facts, deletion, and residual retrieval.

### E. External generalization

Run standard splits from LongMemEval and LoCoMo-style long-conversation tasks, then an action-grounding and memory-security suite. Keep the personal truth set only as a private regression smoke test, never as the headline research result.

## Research comparison

- **LongMemEval** separates indexing, retrieval, and reading, and targets information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention across 500 questions: <https://arxiv.org/abs/2410.10813>.
- **LoCoMo-Plus** reports that surface string matching and task-specific prompting can be misaligned with long-term memory consistency, reinforcing the need for latent-constraint and semantic evaluation: <https://aclanthology.org/2026.acl-long.1150/>.
- **APEX-MEM** uses an append-only temporal property graph and resolves conflicts at query time, a closer match to the robust form of the HMG-Fu temporal idea than destructive single-slot replacement: <https://aclanthology.org/2026.acl-long.749/>.
- **Mem2ActBench** evaluates whether recalled memory is actively and correctly applied to tool use, a capability absent from the present recall benchmark: <https://aclanthology.org/2026.acl-long.370/>.
- **MemSecBench** isolates Write, Execute, and Forget phases for memory poisoning; one canary reply is not an adequate security evaluation: <https://arxiv.org/abs/2607.27080>.
- **HippoRAG 2** is evidence that relational retrieval can help, but only when factual, sense-making, and associative gains are measured against baselines: <https://arxiv.org/abs/2502.14802>.

## Limitations of this audit

- The natural conversation run used one local model stack and one stochastic trajectory; it is a failure discovery test, not a population estimate.
- The raw retrieval comparison has only eight held-in facts and a lexical checker. It supports falsification of the 17/17 interpretation, not a general ranking claim.
- Tools, grader, learning, and dreams were disabled during the conversation run to isolate memory behavior.
- Only one instruction canary was tested. Persistence was confirmed; successful execution was not.
- The full current 17-case answer benchmark was not rerun because it takes roughly half an hour; the changed vehicle-link subset was rerun and passed 2/2.
- Claude's Phase 62 code remained uncommitted throughout the audit, so this report identifies the inspected working tree and audit artifacts explicitly.

## Reproduction artifacts

- `scripts/audit_phase63_natural.py` — isolated natural conversation harness.
- `scripts/audit_phase63_retrieval.py` — canonical-disabled Fu-versus-cosine diagnostic.
- `outputs/phase63_natural_audit.json` — turn-level replies, ledger state, injected context, and structural assertions.
- `outputs/phase63_actual_retrieval.json` — per-query rankings and aggregate retrieval metrics.
- `outputs/phase63_truth_current.json` — truth selection used by the retrieval audit; contains private data and must not be published.
- `outputs/phase63_car_answer.json` — current narrow answer regression; handle as private data.
- `ROADMAP.md`, Phase 63 — execution log and evidence.

## Golden Rules proof

| Rule | Evidence |
|---|---|
| 1. Understand the actual system | Read AGENTS, PROJECT_ID, ROADMAP, THEORY, v2/v3 contracts, runtime routes, writer, storage, retrieval, UI, tests, and Phase 62 artifacts before judging. |
| 2. Investigate before changing | Audited the dirty diff, reproduced failures, ran the full suite, checked DB integrity/statistics, and traced all entry points. No production repair was made. |
| 3. Avoid patches that hide problems | Report identifies the write contract, provenance model, schema, endpoint split, and benchmark design as root causes. |
| 4. Build modular components | Recommendation separates evidence log, grounded writer, temporal ledger, retriever, reader, verifier, and safety layer. |
| 5. Do not duplicate | Duplicate legacy/agent paths and repeated migrations are explicit removal/deprecation candidates. |
| 6. Plan first | Phase 63 was added to ROADMAP before execution, with source, baseline, benchmark, conversation, trace, research, and publication steps. |
| 7. Follow the plan | Each completed Phase 63 step was checked immediately with measured evidence. |
| 8. Document changes | This report, scripts, JSON outputs, and ROADMAP record the audit and its limits. |
| 9. Think full-stack | Review followed user speech through act gate, extraction, storage, provenance, supersession, retrieval, prompt injection, reply, API, and UI. |
| 10. Make flags/state visible | Found model-reporting drift and missing source visibility; recommendation requires resolved runtime state and trust metadata end to end. |
| 11. Preserve compatibility intentionally | No existing production code or database was altered; deprecations require parity tests before removal. |
| 12. Demand evidence | Claims are backed by full tests, deterministic reproducers, a live conversation trace, ablations, database measurements, and primary research. |
| 13. Fix at the right layer | Recommendations move truth enforcement to the write boundary and shared service, not to prompt wording or answer post-processing. |
| 14. Protect user assets | Production DB was read-only; all writes used a scratch DB or clones; the private URL is omitted from this report. |
| 15. Keep interfaces clean | Proposed contracts use typed claims and one entry point instead of hidden endpoint-specific behavior. |

## Final decision

**Do not promote Phase 62 as validated general memory.** Preserve the useful ledger work, quarantine ungrounded canonical writes, fix corruption and endpoint parity first, then run the staged benchmark above. If HMG-Fu cannot beat cosine + a grounded temporal ledger on frozen external data, the graph/Fu layer should remain research-only or be removed from the production path.
