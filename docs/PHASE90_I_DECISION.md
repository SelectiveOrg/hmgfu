# Phase 90.I — Consolidated evidence and the adoption decision

Date: 2026-09-08. Branch `phase90-diagnostic-cycle`. Candidate frozen at `7ce88be` (spans/chat in the tail + open slots off + the
it.1 extractor contract + the 90.G2/H1/H3 rules) and OFF throughout. No new correction in this goal; no new hypothesis; nothing activated.

## 1. Reserved reader reading, W0 vs W1 (90.I1)

Pre-registered in ROADMAP 90.I1 before the run (`2adc778`): items never used in development — multi-session qi 80–119 and
temporal-reasoning qi 80–119 (verified against every per-item log: max qi ever used was 79 in those categories). **Knowledge-update,
single-session-user, single-session-assistant and abstention have no unused items** (72 / 64 / 56 / 30 items, all touched by phases
77–88); single-session-preference 20–29 is unused but its golds are rubrics (Phase 85) — excluded. So this reading does not cover the
knowledge-update category, the one where a write-side change matters most; that gap is part of the decision, not hidden by it.

Same initial state per item (throwaway DB, heuristic sensitization for both arms), same models (bge-m3, gemma4:12b from the live settings),
same production configuration, same items and order; W1 differs only in the write side. Judge v2, k 10. Metrics: accuracy per category
per arm; McNemar b/c; bootstrap 95 % CI on the net; per-item differences; infra errors excluded from pairing and reported. Gates: G-R1 no
category with a net loss whose CI excludes 0; G-R2 pooled net ≥ 0; G-R3 infra errors ≤ 5 % per arm else INCONCLUSIVE; G-R4 W1 wrote ≥ 1
ledger line.

| category (unused items, n = 40 each) | W0 production | W1 candidate | b (W1✓ W0✗) | c (W0✓ W1✗) | net [95 % CI] |
|---|---|---|---|---|---|
| multi-session | 4/40 = 0.100 | 3/40 = 0.075 | 0 | 1 | **−1 [−3, +0]** |
| temporal-reasoning | 2/40 = 0.050 | 2/40 = 0.050 | 0 | 0 | 0 [0, 0] |

Infra errors 0 in both arms (timeouts did not occur, so none was counted either way). W1's extractor ran on every user turn: 960
calls, 721 s, **3 ledger writes** — the same picture as Phase 88: LongMemEval's user turns are long and task-oriented, and the contract
lists almost nothing durable in them, so the candidate barely changes what the reader sees on this benchmark. The single per-item
difference is multi-session qi 85 (gold "$300"): W0 answered "$300", W1 "I don't know." Gate verdicts: G-R1 held; **G-R2 not met**
(pooled net −1, CI [−3, 0]); G-R3 held; G-R4 held. Two honest caveats about power: both categories sit at the floor at production
defaults (0.05–0.10), so one item is the whole difference; and knowledge-update — the category a write-side change is for — has no unused
items left and was not read.

## 2. conv_v2, once per arm (90.I2)

Sealed `f56c3da` (sha256 0ea0c2a63fa0): 24 conversations, 8 families × 3, synthetic values checked absent from the live memory,
criteria fixed before any answer. Similarity control against conv_v1 by embedding (flag ≥ 0.90). One run per arm, final question in a
new session on the same memory.

Similarity control: 69 texts vs conv_v1's 20, nearest cosine p50 0.624 / p90 0.818; two flags, both literal repeats of a final
question phrasing ("what is the link to locate my car?", "o que é que eu gosto de beber?") — the written facts are all new.

| family (3 each) | defaults | candidate |
|---|---|---|
| explicit value change by reference | 1 | 1 |
| explicit correction | 2 | 2 |
| preference A → B | 0 | **2** |
| third-party attribution | 2 | **3** |
| past vs present | 1 | **3** |
| information across turns | 3 | 3 |
| fiction / hypothesis / quote | 2 | 1 |
| question without evidence | 2 | 2 |
| **total** | **13/24** | **17/24** — paired net **+4 [95 % CI +0, +9]** (b 5, c 1) |

The candidate's five gains are write-side recoveries in a new session (two preferences, a PT third-party city, a past city, a past
company). Its one loss is real: "My own name is Zélia Mutemba." — **corrected in 90.J**: the regex writes only the open key `open.own`; in production the
fallback nano mapper then maps it to `identity.name`; in spans mode that mapper is replaced by the chat extractor, which returns nothing for
this plain name sentence, so the name is never written. The loss is the extractor's, not open-slots-off's (the P+E arm with open slots on
loses it too). Both arms
fail r03 (a PT replacement phrased without "my car is"), r05, r09, r21, and r02 — where the READER answered "my timezone" with the
runtime clock's zone instead of the user's stated fact, a reader finding; r23 is a criterion error of the set (the reply abstains
correctly but mentions the known brother, which I had listed as forbidden), counted against both arms equally. Timeouts: the defaults'
r19 ran 914 s under three nano timeouts and still passed — not counted as approval of anything; the candidate arm had none.

## 3. v7, clarified (90.I3)

Global precision 152/160 = 0.950 (regex 94/96 = 0.979; spans path 58/64 = 0.906); coverage 152/213 = 0.714. Six of the eight false
writes are the spans path's: two slot-choice errors on a listed fact (a club as a place; a cat's name as the user's), two the contract should
have refused (a hedged colour; a bare "favourite"), one a company the set does not count as employer, one a name where an alias was
expected. Full table in `docs/PHASE90_H_REPORT.md` §5.

## 4. Total cost of the 90.G / 90.H / 90.I work

| item | amount |
|---|---|
| GPU wall-clock, one chain at a time | **4.6 h** = 2.6 h (90.G/H) + 1.2 h (reader reading) + 0.8 h (conv_v2 control + two arms) |
| product code delta since the Phase 89 close | 8 files, +76 / −19 lines (`extraction_schema`, `fact_spans`, `grounding`, `receipts`, `saydo`, `slots`, `turn_tail`, `value_gate`); no new module |
| tests | 10 files, +329 lines (v87–v94) |
| per-turn cost in production today | unchanged (candidate OFF) |
| per-turn cost if adopted | one extractor call per declarative user turn, after the reply, 0.7–0.9 s on the 12B chat model |

## 5. Adoption decision

**Do not adopt now. The candidate stays frozen and OFF.** The pre-registration said adoption needed G-R1–R4 and the v7 reading; G-R2
(pooled reader net ≥ 0) was not met: −1 [−3, 0], one item, in categories that sit at the floor at production defaults, with the category
that matters most (knowledge-update) unreadable because no unused items remain. Weighed honestly, the evidence for the candidate is
substantial and all on the write side — v7 once: precision 0.864 → 0.950, coverage 0.446 → 0.714; regression sets: no undue write from
the model path; conv_v2 once: 17/24 vs 13/24, +4 [0, +9] — and its costs are also real: one extractor call per declarative turn after the
reply, and one conv_v2 loss caused by the open-slots-off half of the configuration. What would change the decision, in order: (1) a
reader reading that can see the mechanism — either a fresh knowledge-update-type reserved set (LongMemEval has none left) or the
production reader at a setting where those categories are not at the floor (the 480 window the user has not decided on); (2) the
candidate without the open-slots-off half, measured once on the regression sets (it might keep r19 while keeping precision); (3) the
conv_v2 loss and the r02 reader finding as single hypotheses. None of these was started (no new hypothesis in this goal).

## 6. The three targets, assessed on evidence (no scientific percentages)

**Originality (target: above 60 %).** What moved the needle in phases 89–90 is not the Fu geometry but the contract layer around the
local model: a deterministic value and slot contract on the model's output, receipts that prove only their own action, a say-do gate
that turns promises into execution, and a sanitiser that keeps the router's decision consistent. Those are sound engineering, and they are
where the measured wins are; the distinctive claim of the project (Fu relations as a memory substrate) remains unmeasured against a
plain-vector control at equal cost (the ablation named since Phase 76). Standing estimate unchanged, ~37 %, with that ablation as the
one reading that could raise it.

**Efficiency / utility (target: 100 %).** Utility on evidence: promised actions now execute (explicit search 3/3; plan after a proposal
3/3), a step is done only with its own receipt, and a changed fact is recovered in the next conversation for the families the write side
covers (candidate 17/24 on unseen conversations). Efficiency: no change — production still makes ~4.3 model calls before the reply on the
bench and 10–16 in the live session (thinking always on, tail nanos, embeddings), and the one efficiency lever tried (kNN router) did not
move the median. Standing estimate unchanged, ~80 %; the next efficiency reading is the router call itself, not a cheaper router beside it.

**AGI-memory readiness (target: 75 %).** The cycle the user defined — message → structured fact → related memory → retrieval → reply —
works end to end for plain first-person facts and their updates, in one conversation and across conversations (link, preferences, third
party, past vs present, abstention). It does not yet: correct a fact by reference ("the car I told you about", "we are actually working on
X"), record a stated past period, keep a quoted or fictional value out, or let a stated fact beat the runtime clock. On LongMemEval's
hardest categories the reader is at the floor at production defaults. Standing estimate unchanged, ~50 %; not a scientific figure — a
reading of which families pass and which do not.

## 7. Pending, by the user's priority

"we are actually working on X" — the chat model lists no fact for it and the mapping cannot act on what is not listed; a single
hypothesis for later, not started. Also recorded: past periods ("until 2019") are not temporal facts; "moved to X in <year>" writes no
current location; the open-key default (`open_slot_regex_writes`) contradicts the README.

## 9. 90.J — attribution: the extractor vs open-slots-off (2026-09-08)

Arms on identical code: **P** = production (fallback mapper, open slots on) and **P+E** = production + the chat extractor in the tail, open
slots on. Everything else equal; P's lines reused from the same commit.

| reading | P | P+E | who owns the difference |
|---|---|---|---|
| write sets v1–v5 | H4 control lines | **byte-identical** (spans tp 0 fp 0 on every set) | the extractor: nothing. Every regression-set difference the candidate showed (precision v2/v5 up, coverage v1/v5 down) is **open-slots-off's** |
| conv_v1 ×3, new session | 12/21 | 13/21, net +1 [−4, +5] | the extractor: c03 preference 3/3 gained; c05 lost 2/3 — the reader quoting the live history on the known contaminated case |
| conv_v2 (DEV now) ×1, new session | 13/24 | 17/24, net +4 [0, +9] | the extractor: the same five gains and the same loss (r19) as the full candidate → **open-slots-off adds nothing on conversations** |
| extractor exercised | turns with a ledger delta 15 / 25 | 24 / 33 | yes — 9 and 8 additional writing turns |

Named cases. Zélia (r19): a **loss of the extractor** — see §2 correction. Third parties: c04, r10, r12 pass in both arms, r11 gained; no
undue third-party write by the extractor (r12's `family.sister_name = Pantufa` is the regex's, in both arms). Quotes: r20 passes both,
r21 fails both (neither arm writes the user's own drink), r19 the loss. Preferences: c03, r07, r08 gained; r09 fails both — and under
P+E it also produced the one **new undue write**: "These days I prefer kizomba." → `identity.name = kizomba`. Mechanism, verified
deterministically: the extractor listed attribute "preference"; `slots.normalise_key` strips noise words, and an attribute made only of
noise words matches the first alias made only of noise words — `identity.name` through its alias "name". A latent mapping defect, exposed
by the contract now counting stated preferences.

**Decision.** The gate "gain without new undue writes" fails on DEV, so the small new validation was not prepared and the goal stops
here. Attribution is clear: the extractor owns all the conversation gains, the Zélia loss and the kizomba overwrite; open-slots-off owns
the regression-set numbers and nothing on conversations. Recommendation for the next corrections, before any further adoption reading:
(1) the noise-alias match in `normalise_key` — an identity overwrite is the most harmful write the system can make; (2) keep the fallback
mapper beside the extractor rather than replacing it (the Zélia case); the user's stated priority, "we are actually working on X", stands
as the next hypothesis by their order. Candidate OFF; nothing activated.
