# Phase 62 — The governed write side (concept → working memory)

Companion to THEORY_V3 (The Governed Hexagon). V3 specified WHO decides truth (the Regulator's
signal hierarchy) and WHERE relations live (typed ports). The 2026-09-03 autopsy of both memory
systems (`PriorAgent/reports/hmg_memory_reassessment/ANALYSIS.md`) showed that governance
was operating on a ledger it could not govern: **the key vocabulary was open**. When the extractor
mints the key, one real-world attribute fragments into many spellings, and a correction (the
absorbing transition V3 is proud of) retires only its own spelling. The user's favorite language
lived under eight keys in PA3 and two in hmg-fu; the name had 56 live values.

## Axiom A5 (new, measured): the ledger's vocabulary must be closed

Governance is only as strong as the identity of the thing governed. A fact slot is a
**closed identifier** (`pref.language`), never an extracted string. Everything that writes a fact
— regex, model, legacy import — passes through one normaliser. The model may *choose* a slot
from the enum (schema-constrained decoding, the Phase 57 mechanism), it may never *name* one.
Attributes outside the schema are kept (`open.<attr>`) but never presented as identity.

## Axiom A6 (new, measured): speech act gates the write

A question is not a fact. Both stores held "what is my name?" as a person/fact and recalled it
as evidence. The gate is deterministic (PT+EN interrogative/request forms) because 93% of
production points were typed by the regex fallback, not the nano — the gate cannot depend on the
layer that failed.

## What this buys, on the user's own data (truth bench, retrieval mode, clone of live)

| stage | pass | what changed |
|---|---|---|
| baseline (pre-Phase 62 DB + code) | 12/17 | Valencia never in context; Python+Rust presented as current, Java absent |
| + closed slots + gate + replay of PA3 user statements | 16/17 → 17/17 after the idempotence fix | one live value per slot, history kept, stale values demoted |

Ground truth is the user's own latest explicit statement per slot, with provenance recorded in
`scripts/truth_set.json` (it corrected two of the analyst's assumptions: color = chartreuse, not
teal; language = Java, not Rust).

## Relation to the field

Nothing here touches ranking. Ψ_cos still finds; Σ (now slot-keyed) governs validity; Θ and the
timeline reader are unchanged. The hex field, energy and wormholes remain the organiser and the
explainability surface. The write side is where "the AI that always remembers" was actually
leaking, and it is closed at three choke points instead of patched at the prompt.
