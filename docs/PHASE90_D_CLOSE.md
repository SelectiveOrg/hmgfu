# Phase 90.D — Close: the model-backed write contract (H1), limited execution

Date: 2026-09-07. Branch `phase90-diagnostic-cycle`. Approved scope (user, 2026-09-07): stage trace first; smallest fix at the identified
layer, at most two iterations on the DEV cases; regression on the write sets (correct writes AND no undue writes); reserved v7 once only
after that; say-do inconclusive under timeouts and repeated in stable conditions; the open-key question recorded; no new module, no regex
widening, the nano not the alternative, `thinking_mode` untouched, kNN OFF; no production activation without approval.

## 1. Question

Where exactly do the user's plain first-person facts disappear on the model-backed write path, and does the smallest change there write
them without writing anything undue?

## 2. Where the facts disappear (D1, `outputs/evidence_90_D1_stages.txt`)

At the **raw model response**, in every decoding mode (grammar-constrained schema, JSON-only, plain text; thinking on or off). Parsing,
validation (grounding, value gate, third party, origin) and slot mapping drop nothing: when the model does list a fact, "main project" maps
to `project.main` and "favourite drink" to `pref.drink`. The model's own reasoning names the cause: the prompt's category list has no
"project" ("does 'main project' fall under job or employer? not explicitly"), and "I prefer X" is read as an excluded opinion/state.
Decoding is not the factor (JSON-only is equally empty; free-form JSON breaks the schema).

## 3. The single change and its two iterations (D2)

| iteration | change to `SPAN_PROMPT` | DEV, role chat, production decoding, 3 reps | kept? |
|---|---|---|---|
| before | — | `project.main` 0/3 · `pref.drink` 0/3 (both PT sentences) · "we are working on HMG" 0/3 | — |
| 1 (`8d78c9d`) | names the project family; a stated current preference ("I prefer X", "prefiro X", "gosto de X") counts as the favourite; every exclusion kept; contract test v89 written first (failing on "project") | `project.main` **3/3** · `pref.drink` **3/3 + 3/3** · "we are working on HMG" still 0/3 · the link sentence `[]` (the regex owns it) | yes |
| 2 (reverted) | a clause that "we are working on X" in a user–assistant dialogue is the user's project | no change under production decoding (`{"facts": []}` 3/3) | no — no benefit, longer prompt |

Residual, stated: the correction phrasing "we are actually working on X" is written by no path today; the model does not list it as a
personal fact and, when it does (JSON-only), the attribute ("working on") maps to no closed slot. Closing that needs an attribute→slot
mapping — the mould/alias widening excluded from this fix.

## 4. Before / after on the regression sets (D3, candidate = spans/chat + open slots off, `outputs/evidence_90_D3_spans_chat_v*.txt`)

| set | before (recorded) | after (new prompt) | correct writes added by the spans path | undue writes added by the spans path |
|---|---|---|---|---|
| v1 (111) | production regex 0.966 / 0.966 | 0.954 / 0.954 (errata-adjusted 0.989 / 0.989) | 0 | w108 `misc.lucky_number = 8` |
| v2 (90) | production 0.986 / 1.000 | 1.000 / 1.000 | 0 | — |
| v3 (83) | production 1.000 / 1.000 | 0.983 / 1.000 | 0 | x048 `misc.lucky_number = 9` |
| v4 (84) | production 1.000 / 1.000 | 0.984 / 1.000 | 0 | y011 `identity.company = "district hospital"` |
| v5 (300) | candidate 84.3 0.980 / 0.980 (`spans tp 0 fp 0`) | 0.971 / 0.980 (`spans tp 0 fp 2`) | 0 | z018 `identity.alias = Bernardo`, z046 `identity.company = "logistics firm"` |

Production (`--mapper`, prompt unused) v5 unchanged at 0.976 / 0.985. Truth core 390/390, every gate PASS.

Reading. On the sealed sets the spans path still adds **no true positive** — the regex already writes those sentences and `skip_keys`
stops duplicates — while the new prompt adds **five undue writes**. Two are errata candidates: `misc.lucky_number` is a registered slot and
"my lucky number is N" is a plain first-person fact, but the v1/v3 oracles predate the slot and expect no write. Three are real: two generic
noun phrases written as employers, one wrong slot (alias for a name). **D3's criterion — correct writes and no undue writes — is not met.**

## 5. Reserved v7 (D4)

**Not run.** The user's gate was D3 first. v7 stays sealed and untouched by this change (its recorded lines stand: production 0.864 / 0.446,
candidate 0.947 / 0.592).

## 6. Say-do (D5)

The two chained runs (5/6, 4/6) under Ollama timeouts stay **inconclusive**. Stable-conditions repeats, affected cases alone ×3
(`outputs/evidence_90_D5_saydo_affected.txt`): proposal_yes 2/3; **plan_restart 0/3** with no timeouts — turn 1 ends as a proposal (the model
calls `plan_task` with status `proposed` and asks), so "continue" meets an unapproved plan and stays a promise; no file is written.
Attribution, two rounds (`outputs/evidence_90_D5_plan_restart_*.txt`). Round 1 — plan_restart ALONE: pre-90 (33174a0) 2/2 OK, 90.1-only
(fec96a3) 2/2 OK — but the failing head runs had proposal_yes before plan_restart in the same bench process (one clone shared by the
cases), so round 1 was confounded by case order. Round 2, order-matched: **head, plan_restart alone: 2/2 OK**; **pre-90, proposal_yes then
plan_restart: 0/2** (turn 1 ends with no tool, once as a false execution claim). Conclusion: **not a 90.2 regression** — a pre-existing
interaction: after a suggestion-style case ("you can maybe create a widget…", answered with a proposal) the next explicit request in another
session on the same memory is handled as a proposal / without tools. The bench shares one clone across cases exactly as production shares one
memory across sessions, so this is a product finding worth its own question (does route learning from a proposal turn contaminate later
imperative requests?), recorded here, not fixed. Gate status: the affected cases were repeated in stable conditions — plan_restart passes
alone; proposal_yes 2/3 alone — so the say-do gate is **inconclusive as a 6/6 ×3 claim and not asserted**; the earlier timeout runs stay
inconclusive.

## 7. Cost

The write path's cost is unchanged by the prompt (one extractor call per declarative user turn when `fact_mapper_mode=spans`, ~0.7–0.9 s
for the chat role, ~0.4–0.5 s for the nano; production runs `fallback`, so 0 extra calls today). No change to calls before the reply.

## 8. Open question recorded (D6)

`open.average_pace = around 9` was written by the regex from a benchmark turn. `hmgfu/settings.py` sets `open_slot_regex_writes = True`
("default on = today … the systematic precision leak the reserved sets showed") and `docs/PHASE84_STRUCTURAL_WRITE.md` agrees; `README.md`
(Phase 84 section) says the switch is "off by default". The write is consistent with the code's contract and inconsistent with the README.
Not fixed; the user decides which is wrong.

## 9. Recommended decision

- **Do not adopt** the new prompt as the write-side candidate: it fixes the DEV sentences but adds undue writes on the sealed sets and no
  correct ones. Two options for the user: (a) revert `8d78c9d` (and v89 with it) so the branch carries no half-measure; (b) keep it in the
  branch, OFF, as the measured candidate with its five undue writes listed, for a later contract revision that also fixes slot mapping.
- Treat w108 / x048 (lucky number) as **errata candidates** for the v1 / v3 oracles — the user's call, recorded, not applied.
- H1 stands **confirmed as the layer** (the raw model response under the prompt contract) and **unresolved as a fix** within two iterations:
  the contract needs a fuller slot vocabulary AND a slot-mapping step for attribute phrasings ("working on", "employed at … as") — a design
  item to present, not to start.
- plan_restart: not caused by 90.2 (order-matched attribution, §6); the 90.2 correction text does what was asked. The case-order interaction
  (a proposal turn changing how a later imperative request is routed) is a new open question for the user, not acted on.

No automatic next phase; nothing activated in production; kNN OFF; `thinking_mode` unchanged.
