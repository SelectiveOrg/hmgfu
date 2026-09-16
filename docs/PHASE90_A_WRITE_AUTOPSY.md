# Phase 90.A — Autopsy of the write side (Phase 88 sample + the two live cases)

Date: 2026-09-07. Evidence: `outputs/evidence_90_A_autopsy_chat.txt`, `outputs/evidence_90_A_autopsy_live_nano.txt`, the probe runs
recorded in ROADMAP 90.A, `outputs/evidence_90_C_pilot.txt`. Everything below ran on throwaway clones; the user's private link is replaced
by a synthetic URL; the LongMemEval turns are benchmark text.

## 1. The question

Why did the Phase 84/88 write-side candidate (span extractor, role `chat`) write 3 ledger lines in 1,691 LongMemEval user turns, and why did
two live corrections ("here's the updated link: <url>", "we are actually working on HMG") not reach the ledger?

## 2. Sample and method (fixed before reading)

Items qi 40–79 of the five categories (the Phase 88 reserved items); per category the longest and the shortest user turn plus two at
random (seed 20260907) — 20 turns; plus the two live DEV cases. Each turn went through the production path with every intermediate list
recorded: regex `facts.apply_all` → declarative clauses → third-party filter → span extractor (`chat` = the Phase 88 candidate; `nano` =
production's role) → the same filters `apply_spans` uses → store. Closed classification. **Gap declared:** the Phase 88 artefacts do not say
which three turns wrote; finding them costs 1,691 extractor calls (~20 min GPU) and was not run.

## 3. Table (22 turns, role chat) — the classifier's first pass and the correction it needed

| class (first pass) | n | what the record actually shows |
|---|---|---|
| nothing_memorable | 12 | short turns (37–234 chars): questions, plans, opinions — the regex wrote nothing; the extractor returned `[]` |
| insufficient_evidence | 8 | long turns (314–5,425 chars) with several declaratives; regex nothing; extractor `[]` |
| written | 2 | kn49: the REGEX wrote `open.average_pace = around 9` (an OPEN key — the 84.2 leak, `open_slot_regex_writes` still on); live_updated_link: the REGEX wrote the link (see §4) |

**Correction to the first pass.** "extractor returned `[]`" was read as "nothing memorable" — that reading is wrong when the extractor is
the `chat` role, because §5 shows the `chat` extractor returns `[]` even for plain first-person facts. The 20 LME rows therefore carry
**no evidence either way** about memorable content; the honest class for them is *extractor silent (role chat) — undetermined*.

## 4. The two live cases

| case | regex | extractor chat | extractor nano | ledger |
|---|---|---|---|---|
| "heres the updated link: <url>" | **writes `asset.car_location_link`** (the link mould since Phase 83.3, 2026-09-06) | `[]` | `[]` | updated — on today's code |
| "we are actually working on HMG, this memory system of yours" | nothing (`project.main` needs an alias: "project", "projeto") | `[]` (0/5 runs) | 4/5 runs: `identity.job = working on HMG`, `identity.company = HMG` — wrong slot | nothing (or a wrong fact with nano) |

So D1 (the link) was a **write miss on 2026-09-04 that today's regex no longer has** — and the live ledger stayed stale because nothing
revisits an old episode once the code improves. D4 (the correction "we are actually working on HMG") is **unwritable today by every path**:
the regex needs the slot's alias, the `chat` extractor is silent, the `nano` extractor mislabels.

## 5. The finding that names the layer (probe, 5 runs per sentence, temperature 0)

| sentence | extractor `chat` (gemma4:12b, the Phase 84/88 candidate) | extractor `nano` (qwen2.5:1.5b, production's role) |
|---|---|---|
| "we are actually working on HMG, this memory system of yours" | `[]` 5/5 | job/employer = HMG 4/5 (wrong slot), `[]` 1/5 |
| "My main project is a Java billing API." | `[]` 5/5 | `project.main = Java billing API` 5/5 |
| "Ultimamente prefiro chá de gengibre." | `[]` 5/5 | `pref.food = chá de gengibre` 5/5 (should be `pref.drink`) |

The `chat`-role extractor is **silent on plain first-person facts** — the ones the prompt lists explicitly ("their job or employer", "a
favourite … drink"). That single fact explains the Phase 88 result (3 writes in 1,691 turns was the extractor saying nothing, not the
corpus lacking facts) and re-opens Phase 84's "spans/chat" reading: its v7 precision 0.947 / coverage 0.592 stand, but the coverage came
from the regex share of the pairs, not from the model. The `nano` extractor talks but mislabels slots (job vs project, food vs drink) and
is unstable (4/5).

## 6. The 90.C pilot confirms the layer (6 DEV conversations, defaults, `outputs/evidence_90_C_pilot.txt`)

| conversation | write | retrieval | reply | verdict |
|---|---|---|---|---|
| c01 updated link (synthetic) | ledger moved to the new URL | delivered | correct new link | OK |
| c02 "we are actually working on HMG" | **not written** (ledger still "Java billing API") | the episode delivered | "HMG" — correct from the episode, Java mentioned as forbidden-current | FAIL@write |
| c03 "Gosto muito de café" / "Ultimamente prefiro chá de gengibre" | **not written** (PT "gosto de / prefiro" have no mould) | delivered | correct from the episode | FAIL@write |
| c04 third party (Ana → Aveiro) | nothing written for Ana; Valencia already in ledger | — | Valencia | OK |
| c05 past vs present | Valencia written; Nampula in history | delivered | Nampula | OK |
| c06 no evidence | teal written | — | abstained | OK |

Reading and retrieval carried both failures (the reader answered from the episode). The ledger — the profile the agent trusts first and
states with confidence — is what stays wrong, and it is what made the live agent say the old link "with confidence" and repeat "Java project".

## 7. ONE priority hypothesis (for 90.D, presented for approval — not started)

**H1 — the model-backed write path is the failing layer: its `chat`-role contract returns nothing for plain first-person facts, and its
`nano`-role contract mislabels the slot.** Both symptoms sit in `fact_spans.extract_spans` (prompt + slot mapping), not in the store, the
gates or the reader. A fix would be measured first on the two live cases and c03 (DEV), then on the write sets v1–v5 (regression, must not
lose precision), then once on the reserved v7 — never tuned against it.

Not chosen (recorded): widening the regex moulds case by case (symptom patches, Rule 3); turning the nano extractor on as is (it writes
wrong slots — a precision cost the write sets would show); re-processing old episodes to refresh the ledger (a second mechanism; needs its
own justification and approval).

## 8. Side findings (not acted on)

- `open.average_pace = around 9` written from an LME turn: the 84.2 open-slot regex leak is still on by default (`open_slot_regex_writes`).
- Ollama contention during the chains: the nano timed out 3× and the chat model returned empty responses (a 950 s say-do case = 3 × the 300 s
  timeout); three models (gemma4:12b 8.3 GB, qwen 2.1 GB, bge-m3 0.7 GB) resident on a 24 GB card while benches swap roles. Infra, recorded.
