# Phase 90.H — Generalising the write-side improvement without losing precision

Date: 2026-09-08. Branch `phase90-diagnostic-cycle`. Goal (user): keep the three targets and the evidence criteria; errata only if the
contract and context justify them; c05 verified before a synthetic isolated scenario; ONE hypothesis (attribute→slot mapping, ≤ 2
iterations, negatives included); candidate OFF; development and regressions closed before the reserved validations; reserved
validations once, never tuned against, never repeated; no automatic phase, no production activation. Percentages only with explicit
criteria and new evidence.

## 1. Errata (H1) — not justified; the contract decided

The write sets mark "My lucky number is 9." / "O meu número da sorte é 8." as no-write while "17" / "42" are writes. The regex path
accepts a value only if it has at least two characters and is not a stop word (`fact_detect.push`); single-digit numbers are refused
(the counting-number ambiguity). The oracles encode that contract exactly, and the slot existed before the sets were authored, so the
two "undue writes" were real: the spans path lacked the rule. Fixed at the spans path (test v93 first), originals untouched, no errata
file written. Control and candidate were then compared on the same unchanged oracles.

## 2. c05 (H2) — legitimate interference, plus a gap found alongside

Live history (read-only): `identity.location` Lisbon → Valencia (May 2026) → Chimoio → Valencia. The reply "Lisbon, then Valencia" is
consistent with that ledger history for "where did I live before I moved?" — legitimate. Alongside: "I lived in Nampula until 2020."
records nothing (no assertion, no history); a stated past period is not a temporal fact today — an open product item, not fixed here.
c05 and its evidence were kept; c05b (Quelimane → Tete, both absent from the live memory) was added as the isolated scenario. Its run
(§5) found a second write-side gap: "I moved to Tete in 2020 and I still live there" writes no current location (a year cue reads as
past; "there" is not a value) — the reader still answered Quelimane correctly from the episode.

## 3. The single hypothesis H-C (attribute→slot mapping), two iterations

**Layer:** the deterministic side of the model-backed write path (`slots.normalise_key` alias index; `fact_spans.extract_spans` value
rules; `value_gate.third_party_attr`). No new module.

| iteration | change | test first |
|---|---|---|
| 1 | `project.main` gains the extractor contract's own phrasing as aliases — "working on" (content tokens working+on, so "currently working on" / "what I am working on" match; "working hours" does not) and "trabalhar em" | v94: contract phrases map; descriptions / third-party attributes / tasks stay open; hedged, pronoun and predicate values rejected |
| 2 | the v94 negatives caught two invented attributions on iteration 1: (a) a project value must be a NAME (first letter upper-case, the same rule as an employer) — "the weather report for tomorrow" is a task; (b) a pronoun possessor in the attribute ("their project", "his job", "o projecto dele") is a third party | v94 all green; 44 span/slot tests; truth core 390 PASS |

Stated side effect: aliases also feed the regex "my <attr> is <value>" mould — measured in §4 on both paths (no change).

## 4. Regressions (H4, same oracles, `outputs/evidence_90_H4_*.txt`)

| set | control (`--mapper`, production) | candidate (spans/chat + open slots off) | candidate spans path |
|---|---|---|---|
| v1 (111) | 0.966 / 0.966 | 0.965 / 0.954 | tp 0 fp **0** |
| v2 (90) | 0.986 / 1.000 | 1.000 / 1.000 | tp 0 fp **0** |
| v3 (83) | 1.000 / 1.000 | 1.000 / 1.000 | tp 0 fp **0** |
| v4 (84) | 1.000 / 1.000 | 1.000 / 1.000 | tp 0 fp **0** |
| v5 (300) | 0.976 / 0.985 | 0.980 / 0.980 | tp 0 fp **0** |

The candidate's model path writes nothing undue on any regression set; every remaining false write is the regex path's, shared with
the control and errata-covered (articles; job written where the oracle lists only the company or language). Coverage on v1/v5 is
lower with open slots off (the 84.2 trade, unchanged). Suite 805 passed; truth core 390 PASS.

Conversations, final question in a NEW session, 7 sentinels × 3 reps: defaults **12/21**, candidate **15/21**. Recovered across
conversations 3/3 under the candidate: the link update, the PT preference change (café → chá de gengibre), third-party isolation, the
past-vs-present question, abstention. Not written by either: "we are actually working on HMG" (the chat model lists no fact for it —
the mapping can only act on what the model lists) and c05b's "I moved to Tete in 2020 and I still live there" (§2).

## 5. Reserved validation (H5) — v7, once

| arm | precision / coverage | by path |
|---|---|---|
| production (recorded 84.5) | 0.864 / 0.446 | regex tp 94 fp 15 · spans — |
| candidate (recorded 84.5, old prompt, old rules) | 0.947 / 0.592 | regex tp 94 fp 2 · spans tp 32 fp 5 |
| candidate (this run, it.1 prompt + G2/H1/H3 rules; `outputs/evidence_90_H5_v7_candidate.txt`) | **0.950 [0.911, 0.981] / 0.714 [0.642, 0.780]** | regex tp 94 fp 2 · spans **tp 58 fp 6** |

**Metrics, made explicit (90.I3).** Global precision = (regex tp 94 + spans tp 58) / (94 + 58 + regex fp 2 + spans fp 6) = 152 / 160 = **0.950**.
Spans-path precision = 58 / (58 + 6) = **0.906**; regex-path precision = 94 / 96 = 0.979. Coverage = 152 / 213 expected = 0.714. The eight
false writes by path and sentence (synthetic set): spans — s094 "Sou do Maxaquene." → location (a football club read as a place); s112
"O nome do gato é Bagheera." → the user's name (the cat's); s239 "Maybe my favourite colour is burgundy; I keep changing my mind." →
colour (hedged, the model listed it anyway and the value gate does not see the hedge in the value); s254 "O meu preferido é o verde." →
colour (a bare "favourite" with no attribute — the set expects no write); s287 "I named my company Sumbane & Filhos." → company (the set
treats naming a company as not the user's employer); s291 "I answer to Osvi or Osvaldo, either works." → name where alias was expected.
regex — s238 "Sou madrugador." → job; s243 "Text my brother Dinis…" → brother's name. Six of the eight are the spans path's, two the
regex's; four of the six are slot-choice errors on a listed fact, two (s239, s254) are writes the contract should have refused.

Read once, not repeated. Against the recorded candidate the spans path writes 26 more true facts (tp 32 → 58) for one more false one
(fp 5 → 6): coverage +0.122 with the coverage intervals barely overlapping, precision +0.003 (intervals overlap — held, not improved).
Against production: precision +0.086, coverage +0.268. The eight false writes: six were already there in 84.5 (s094 a team written as a
location, s112 a cat's name as the user's, s238 "madrugador" as a job, s243, s254, s287); new: s239 `pref.color = burgundy` and s291 the
name "Osvaldo" where the alias "Osvi" was expected; gone: s288. Sixty misses remain (names, places, jobs, companies, birthdays, dishes,
drinks in unseen moulds) — the coverage ceiling of this model-backed path, not touched by this goal.

## 6. Costs

Unchanged on the production path (candidate OFF: 0 extra calls). With the candidate on: one extractor call per declarative user turn
in the tail (0.7–0.9 s, chat role), paid after the reply. Code: `fact_spans.py` (+2 rules), `value_gate.py` (+1 regex), `slots.py`
(+2 aliases), `extraction_schema.py` (+4 lines, 90.G), `saydo.py` (+7, 90.G); tests v90–v94. GPU time this goal ≈ 1 h 10.

## 7. Adoption recommendation

**Recommend adopting the candidate write side** (spans/chat in the tail + open slots off + the it.1 contract + the G2/H1/H3 rules) as
the next production default — **after one reserved reader reading**, because the Phase 85 erratum stands: every write-side change alters the
ledger lines the reader sees, and this one writes more of them. The reading is the plan's 90.E item: LongMemEval items 80–119 (never
used), production embedder, W0 (today) vs W1 (candidate), paired with intervals, once. If the reader holds (no category down beyond its
interval), adopt; if it does not, keep the candidate OFF and report. Nothing was activated here; the setting stays OFF.

What adoption buys, on evidence: on unseen first-person sentences precision 0.864 → 0.950 and coverage 0.446 → 0.714 (v7, once); on the
regression sets no undue write from the model path; across conversations 15/21 vs 12/21 on the DEV sentinels. What it costs: one extractor
call per declarative user turn, after the reply (0.7–0.9 s on the 12B chat role). What it does not fix: correction phrasings the model does
not list ("we are actually working on X"), past periods ("until 2019"), and "moved to X in <year>" as a current location — three write-side
items now named with evidence, for a later single hypothesis each.

## 8. Percentages

Criteria for a change would be explicit and new: (i) a reserved write-side reading with the candidate's precision not below production
and coverage above it, (ii) the cross-conversation recovery demonstrated on a reserved conversation set (conv_v2, not yet authored),
(iii) no regression on the reader's reserved readings. (i) is read once in §5; (ii) and (iii) are not — so the percentages stay at
~37 / ~80 / ~50 until those readings exist.
