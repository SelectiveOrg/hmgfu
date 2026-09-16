# Phase 90.M — Does refusing the ledger erase anything? The three-way distinction, measured

Date: 2026-09-08. Goal: the modality protection of 90.L is accepted as **safety**, not as a fix for the five missing writes.
Before adding any rule, verify **with the existing mechanisms** that facts, activities, intentions and proposals survive in the
episodes and are recovered in another session **with the right status**. No new module and no new mould. `projecto`/`projeto`
authorised only as a general normalisation, with regressions.

## 1. A regression of mine, found and proved first (90.M1/M2)

The intent modality of 90.L labelled the **sentence**, so an intention silenced a fact that shared it. Proved against a worktree at
`5d509ad` (the commit before 90.L): "I plan to move to Aveiro, but I live in Valencia." wrote `identity.location = Valencia` **before**
and nothing **after** — 3 of the 5 mixed cases. The same root cause predates 90.L for another modality: "In 2019 I lived in Lisbon,
but I live in Valencia now." is `past` end to end and writes nothing.

Fixed at the right layer, with no new mould: **a modality is a property of the clause**, so a contrastive coordinator
(`but / mas / porém / contudo / no entanto / however / whereas / ao passo que`) starts a new claim. One alternative added to the
**existing** sentence splitter `_SENT` in `hmgfu/utterance.py`; it serves every modality at once (intention, past, citation).
Test `v97` written first: 3 failures before, all green after; 16 green across v95+v96+v97.

## 2. The verification the user asked for (90.M3)

`scripts/diag_episode_status.py` over `scripts/oracles/status_v1.json` — 16 DEV cases, PT/EN, including mixed sentences, with the
criteria fixed **in the oracle before any answer**. Each case says one sentence in session A and asks a question in a **new session
B** on the same memory, recording three layers separately so a failure is attributable:

| layer | question | measurement |
|---|---|---|
| 1 STORED | is it in the episodes (`memory_points`) and/or the ledger? | the ledger may legitimately refuse it |
| 2 RETRIEVED | did the value reach the reader (injected context or ledger lines)? | |
| 3 STATUS | is it presented as fact / wish / activity, and never as a current state it is not? | `must_not_say_as_current` |

### The distinction

| class | cases | result |
|---|---|---|
| **not stored** | **0 / 16** | **the ledger refusing a write erases nothing.** Every intention, proposal and activity has an empty ledger delta *and* 3–84 memory points carrying the value |
| **stored but not retrieved** | **0 / 16** | every value the reply needed reached the reader |
| **retrieved but misinterpreted** | **2 / 16** | one genuine defect (s06), one omission counted by the pre-registered criterion (s04) |

**Not stored = 0** is the answer to the user's concern, in numbers: `s03 "I want to work on Mapiko."` → ledger `{}`, episodes 4;
`s06 "We should work on Mapiko."` → ledger `{}`, episodes 7; `s08 "We are working on HMG."` → ledger `{}`, episodes 70. The
information survives; only its promotion to canon is refused.

**Each claim judged separately, in the mixed sentences** — the 90.M2 fix, seen end to end:
`s11 "Quero trabalhar no Mapiko, mas atualmente trabalho na Kuvala."` → **"Atualmente, você trabalha na Kuvala, embora tenha
mencionado o interesse em trabalhar no Mapiko."** Fact as fact, wish as wish, in one reply.
`s13 "I plan to move to Aveiro, but I live in Valencia."` → ledger `identity.location = Valencia`, reply "You live in Valencia" and Aveiro
never presented as current.

### The one genuine defect

**s06 — a proposal reported as a current activity, by the reader.** Said "We should work on Mapiko."; asked in another session
"what is my main project?"; reply: *"Your main project is HMG. I'm also aware that we are currently working on Mapiko as well."*
The write side is correct (nothing entered the ledger) and the retrieval is correct; the **reader** converts a proposal into an
ongoing activity. This is the "intention becomes reality" failure at the last layer, and it is **not** fixable by the write-side
contract that 90.L added.

### The other miss, reported for what it is

**s04** (`"Quero trabalhar no Mapiko."` → "qual é o meu projeto principal?") answered with the real project (HMG, from the live
clone) and **did not mention** the wish. Nothing is misrepresented; the pre-registered criterion for `wish` requires the reply to
surface the value, so it counts as a miss. Recorded as an **omission**, not a status error. Two caveats about the probe, stated
rather than tuned away: the clone carries the user's real `project.main`, so project-family cases are contaminated, and the `absent`
rule was corrected once (a value the reply must *not* use need not be retrieved) — a probe fix, applied to the **recorded replies
offline**, never to the write path.

## 3. `projecto` → `projeto` as a general normalisation (90.M4)

Verified before touching anything: of the **136** tokens in the slot alias vocabulary, exactly **one** has a European Portuguese
variant. So this is a spelling family, not a synonym for one phrase: the pairs joined `_MORPH` beside `favourite`→`favorite` and
`colour`→`color`, and property test `v98` enumerates the 1990-reform family (silent `c`/`p`) so a future alias is covered by the
same rule instead of a new special case.

| reading | before | after |
|---|---|---|
| DEV modality diagnostic | 27/32, **0 undue writes** | **29/32, 0 undue writes** (m02, m27 fixed) |
| suite | 821 | **824** |
| truth core | 390 PASS, undue changes 0 | **390 PASS, undue changes 0** |
| write sets v1–v5, production | .966/.966 · .986/1.000 · 1.000 · 1.000 · .976/.985 | **identical**, false-write lists diff to nothing |
| conv_v1 ×3 / conv_v2 ×1 | 10/21 · 14/24 | **10/21 · 14/24**, verdict distribution identical, ledger deltas identical (15 = 15, 25 = 25) |

The three remaining diagnostic misses (m03, m05, m06) are all the **activity-form** gap, which the user has not authorised.

## 4. Complexity balance

| added | removed / not added |
|---|---|
| one alternative in an existing regex (`_SENT`) | no new module, no new mould, no new setting, no new path |
| three pairs in the existing `_MORPH` map | the phrase list a "projecto" special case would have started |
| two DEV oracles + one diagnostic script (measurement only, never imported by the product) | — |

Product code touched: `hmgfu/utterance.py` (one regex line), `hmgfu/slots.py` (three map entries). The central cycle is unchanged.

## 5. Decision

**Keep both.** The clause split repairs a regression I introduced and a pre-existing one, with production behaviour otherwise
identical. The spelling normalisation buys two writes in the diagnostic at zero cost to every production reading.

**Open, not authorised, and named:** the activity-form mould (m03, m05, m06 — its risk is precisely *activity → main project*); the
reader defect s06, which belongs to the reading layer and needs its own hypothesis; the Zélia fallback (presented, not implemented);
the `open_slot_regex_writes` README-vs-default contradiction.
