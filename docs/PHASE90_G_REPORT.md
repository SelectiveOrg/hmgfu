# Phase 90.G — Overnight report (goal of 2026-09-07 ~22:20 local; ≤ 6 h; ≤ 2 hypotheses per problem)

Goal (user): correct and demonstrate (a) real execution of promised searches, (b) receipts tied to the correct action, (c) fact updates
recoverable across conversations — with no new undue writes. Order: the after-proposal interaction first, then fact writes; 90.C full and
90.E only if the gates pass; branch only, nothing activated in production; kNN OFF; `thinking_mode` untouched; no new module, no cleanup,
no automatic phase; one GPU run at a time. Branch `phase90-diagnostic-cycle`. Start 20:23Z.

## 1. Results

Evidence files under `outputs/` (private, not in git); numbers copied verbatim.

| item | before | after | evidence |
|---|---|---|---|
| (a) promised / requested search executed | live 2026-09-07: 0 of 3 attempts ran the search | "how many links?" answered directly from the ledger 3/3 (no promise); the explicit broader-search request ran `memory_search` **3/3** and reported results | `evidence_90_G_promised_search*.txt`; v90 covers the promise-on-order case |
| (b) receipts tied to the correct action | 90.2 (`verify_step` turn + action match; v88) — done before this goal | unchanged | `test_v88_step_needs_matching_receipt.py` |
| after-proposal interaction (order-matched pair) | plan_restart after proposal_yes: 0/2 pre-90, 0/3 head; A→B1 0/5 | A→B1 **3/3 executed**; say-do pair 2/2 ×3; full say-do 6/6; suite 800 | `evidence_90_G1_verify2_*.txt` |
| (c) fact update recoverable in a NEW conversation (6 sentinels × 3 reps) | not measured before | defaults **11/18** (c02, c03 never written); candidate (spans/chat + open slots off, it.1 prompt + H-B1) **15/18** — link update and PT preference change recovered 3/3; only "we are working on HMG" fails | `evidence_90_G3_newsession_*.txt` |
| undue writes on v1–v5 (candidate, it.1 prompt) | 5 new (D3) | **2** — both `misc.lucky_number` (errata candidates); v5 = 84.3 baseline exactly | `evidence_90_G2_spans_chat_v*.txt` |

## 2. What was found (G1)

The failing shape is not a router problem: the router's raw decision for the imperative request is identical with and without a
preceding proposal exchange (`action_requested true, [plan_task, write_file]`), no timeouts in the failing runs, and deleting the learned
route exemplar changes nothing (H-A1 refuted). The model's REPLY changes — after a proposal exchange sits in memory it answers the order
with a promise and no tool call — and the say-do gate then PROPOSES a write-intent promise whenever no approved plan exists, even though
the user's message is an explicit order with effects allowed. Fix (test v90 first): on an explicit order the promise is re-asked once
to execute (the existing single `rerun`, `EXPLICIT_REASK`), as read-only intents already were; suggestion turns keep the proposal.

**Verification of that first fix: negative** (`evidence_90_G1_verify_ab.txt`: B1 still proposed 3/3; say-do pair 1/2 ×3; suite 798). The
events probe showed effects allowed and the re-ask running, but the model had **no tool schema at all** in either pass. The route probe
(`evidence_90_G1_route.txt`) located the loss: the router's result reaches `merge_route` intact (`action_requested true, [plan_task,
write_file]`) and is then wiped by `_sanitise`, because the router also emitted `runtime_context_sufficient: true` with no runtime key —
the sanitiser cleared tools on any sufficiency claim. This happened in the control too; there the semantic tool fallback rescued the turn
with `list_files`, after the proposal session the tool-point scores no longer matched → zero tools → promise → proposal.

**Second and last hypothesis (H-A2, test v92 first):** a sufficiency claim that names no runtime key while requesting tools is inconsistent;
the sanitiser keeps the action and drops the flag; a genuine clock answer (keys named) stays tool-free. **Verified** (`evidence_90_G1_verify2_*`):
A→B1 executed 3/3 with `plan_task, write_file` offered and three files written (0/5 before); say-do proposal_yes+plan_restart 2/2 ×3; full
say-do 6/6; suite 800. The first fix (explicit-order re-ask) stays: it is correct on its own terms (v90) and is the safety net when a model
still promises with tools available.

## 3. What was found (G2)

The it.1 prompt's five undue writes split into two errata candidates (lucky number: the slot exists, the v1/v3 oracles predate it) and
three real ones. H-B1 at the validation layer (tests v91 first): an employer value must be a name (first letter upper-case); a value the
regex already wrote this message is not a second fact under another slot (`apply_spans(skip_values=)`, wired in the tail, the LME
harness and the write-set runner). Not touched: the regex, the nano, the oracles.

**Regression** (`evidence_90_G2_*`): v5 **0.980 / 0.980 with `spans tp 0 fp 0` — the 84.3 baseline exactly** (z018 alias and z046 "logistics
firm" gone); v4 1.000 / 1.000 (y011 "district hospital" gone); v2 1.000 / 1.000; v1 0.954 / 0.954 and v3 0.983 / 1.000 with one spans write
each — w108 / x048 `misc.lucky_number`, a registered slot the v1/v3 oracles predate. Production (`--mapper`) v5 unchanged 0.976 / 0.985;
truth core 390 PASS. The three real undue writes are gone; the two remaining are oracle-vs-slot disagreements, recorded as errata candidates
and not added to the errata files by me. **v7 not run**: the goal's gate is zero undue writes on the regression sets, and that hinges on the
errata decision.

## 4. Failures and open items

- The first G1 hypothesis (explicit-order re-ask) did not change the outcome on its own; it stays as the correct safety net (v90) but the
  carrier was the sanitiser (H-A2). Two hypotheses used, as allowed.
- "we are actually working on HMG" is still written by no path (3/3 under both configs): the model does not list it as a personal fact and, when
  it does, the attribute maps to no closed slot. Closing it needs an attribute→slot mapping — the widening the user excluded.
- Two spans writes remain on v1/v3 (`misc.lucky_number = 8 / 9`): correct facts against oracles that predate the slot. Not added to the errata
  files by me; the user decides. Until then the "no undue writes" gate is not formally met, so 90.C full and 90.E were not started and v7 was not run.
- c05 (past vs present) failed once under defaults because the reply quoted the CLONE's real location history (Lisbon → Valencia) instead of the
  conversation's Nampula: the DEV set contradicts the live memory it runs on — a set-design flaw for that family, to fix in conv_v1 before any
  claim about that family.
- Ollama timeouts (gemma, qwen) recurred in two say-do runs (one took 693 s and still passed); infra contention with three resident models, as in 90.D.
- Not touched, as instructed: the regex moulds, the nano role, `thinking_mode`, the kNN router (OFF), production defaults, the reserved sets.

## 5. Cost and limits

Wall clock 20:23Z → 22:35Z (≈ 2 h 12 of the 6 h). One GPU chain at a time throughout (f → j → k → g → h → i → l → m → n). Code changes: 3 files
in `hmgfu/` (`saydo.py` +7 lines, `extraction_schema.py` +4, `fact_spans.py` +6 incl. the `skip_values` parameter wired at its three call sites),
no new module, 4 new test files (v90, v91, v92 + the earlier v88/v89), 6 probe scripts under `scripts/` (diagnostics, reusable). Production
behaviour changes only through the two say-do/sanitiser fixes, which are deterministic and covered by tests; the write-side candidate stays OFF.

## 6. Next decision (for the user)

1. **Errata** for w108 / x048 (lucky number) in the v1 / v3 oracles: accept (then the "no undue writes" gate is met and v7 can run once, and
   90.C full / 90.E can start) or reject (then the candidate keeps two undue writes and stays a candidate).
2. **The write-side candidate** (spans/chat + open slots off + it.1 prompt + H-B1): now 15/18 on the cross-conversation sentinels vs 11/18 for
   production, v5 precision back to baseline; adoption remains your call — nothing is activated.
3. **The residual** "we are working on X": approve (or not) a slot-mapping step for attribute phrasings as the next single hypothesis.
4. **conv_v1 c05**: allow the DEV set to use a location absent from the live history (set design, no code).
