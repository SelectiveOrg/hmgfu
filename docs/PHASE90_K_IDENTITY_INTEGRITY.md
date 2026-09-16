# Phase 90.K — Identity integrity in the attribute→slot mapping

Date: 2026-09-08. Branch `phase90-diagnostic-cycle`. Goal: the deterministic `normalise_key` fix — an attribute with no
discriminative content must never match a slot by noise coincidence. Candidate OFF; no new module; nothing activated in production;
no reserved set run. The Zélia fallback is **investigated and presented, not implemented** (§5).

## 1. The defect, reproduced first — and it reached production

`normalise_key` strips noise words ("name", "is", "the", "my", "current", "preference", "preferred", …) to get the attribute's
*content* tokens, then matches an alias when `toks == at or content == ac`. Exactly one alias in the whole table has empty content
tokens: `identity.name`'s alias **"name"**. So any attribute made *only* of noise words had empty content and matched it.

Verified against the pre-fix code (test v95, failing in four places before the change):

| input | pre-fix | post-fix |
|---|---|---|
| `normalise_key("preference")` | `identity.name` | `open.preference` |
| `normalise_key("preferred")` / `("my current")` / `("a")` | `identity.name` | `open.*` |
| ledger after "My name is Teodoro H. Ferreira." then **"My preference is kizomba."** (production defaults, regex path) | `identity.name = kizomba` — the name destroyed | `identity.name = Teodoro H. Ferreira`, `open.preference = kizomba` |
| extractor path: attribute "preference", value "chá de gengibre" | `identity.name = chá de gengibre` | `pref.drink = chá de gengibre` (value-class inference) |

**This was a production defect, not a candidate one.** The regex detector emits the raw attribute and `FactStore.apply` normalises
it, so "My preference is kizomba.", "A minha preferência é kizomba.", "My current is …", "My favourite is …" overwrote the user's
name on today's defaults. 90.J saw it only through the extractor because that is where the attribute "preference" was produced;
the mould `my <attr> is <value>` produces it in production too.

## 2. The fix (existing layer, one condition)

`hmgfu/slots.py`, `normalise_key`: content equality now requires content on both sides.

```
if toks == at or (content and content == ac):
```

No new module, no new setting, no other layer touched. Exact alias-token equality is untouched, so the legitimate alias "name" →
`identity.name` still resolves; the subset branch below already guarded `if ac`.

## 3. Verification across all slots (test v95, 7 tests)

- **Every alias of every slot** in `SLOTS` resolves to its slot, lower and upper case (property test over the whole table).
- **Every noise word alone** resolves to `open.*`, except the one that is itself an alias ("name"), which is preserved.
- **Empty, whitespace and `None`** → `open.unknown`; **unknown attributes** → `open.*`.
- **A preference cannot change identity without explicit evidence**: attributes "preference" / "preferred" / "my current" with a
  value write nothing; an explicitly named identity ("name" → "Zélia Mutemba") still writes.
- **The value-class path still rescues a bare preference** with a recognisable value (→ `pref.drink`).
- 55 tests green across slots, facts, spans, detect, pre-router, temporal and architecture.

## 4. Affected regressions and DEV cases, candidate OFF

Everything re-run at **production defaults (candidate OFF)**; no reserved set touched.

| reading | before the fix | after the fix |
|---|---|---|
| suite | 805 passed | **812 passed** (the 7 new v95 tests) |
| truth core | 390, every gate PASS | **390, every gate PASS** |
| write sets v1–v5, production `--mapper` | 0.966/0.966 · 0.986/1.000 · 1.000/1.000 · 1.000/1.000 · 0.976/0.985 | **identical on all five**, same `by path` counts, and the false-write lists diff to nothing |
| conv_v1 ×3, new session, defaults | 12/21 | **12/21** |
| conv_v2 ×1, new session, defaults | 13/24 | **13/24** |

**Targeted check on the case that exposed the defect** (r09 with the extractor on, the only configuration that produced it):
"These days I prefer kizomba." now has a ledger delta of `{}` — before the fix it wrote `identity.name = kizomba`. The conversation
still fails its own criterion because `pref.music` is not updated to kizomba, which is the pre-existing r09 failure in both arms
(the extractor's attribute "preference" carries no slot and the value is in no closed class); the difference is that it now writes
**nothing** instead of the wrong thing.

## 5. The Zélia fallback — contract and cost, presented before any implementation

**What is actually lost, and where.** "My own name is Zélia Mutemba." → the regex mould yields the attribute "own name", whose
content token is "own" (not an alias), so the key is `open.own`. Production then consults the **pre-reply nano mapper**, which maps
the sentence to `identity.name`. Proved deterministically with a stub mapper (no model call): with `use_mapper=True` the ledger gets
`identity.name = Zélia Mutemba`; with `use_mapper=False` it gets only `open.own`. The candidate sets `use_mapper=False` (spans
mode), and the chat extractor returns nothing for that sentence — hence the loss. **In production today the coverage exists**, so
this loss is hypothetical until the candidate is adopted.

**The mapper's trigger, exactly**: inside `FactStore.apply_all`, pre-reply, only when (a) the regex found **no closed slot** in the
message, (b) a mapper is bound, (c) `use_mapper` is on, and (d) the text has a declarative cue. One nano call, grammar-constrained,
value must appear in the text.

**Concurrent writes are already impossible** and need no new mechanism: the tail's `apply_spans` receives `skip_keys` and
`skip_values` built from that turn's pre-reply `fact_changes` (90.G2), so a key or value already written this turn is never written
again by the extractor. One writer per key per turn; the pre-reply path wins.

**Three shapes, with their costs:**

| option | model calls added | where | risks |
|---|---|---|---|
| **A. Both paths as they are** — mapper pre-reply + extractor in tail | +1 nano (~0.4–0.5 s) on every declarative turn with no closed regex slot | on the **pre-reply critical path** — exactly the call Phase 84 removed | none for correctness (skip_keys/skip_values); a certain latency cost for a coverage gain Phase 84.1 measured as small (the mapper wrote 0 lines on five sealed sets) |
| **B. Sequential fallback in the tail** — the extractor first; the mapper only when the extractor returned nothing *and* the regex found no closed slot | +1 nano only on turns where both earlier paths were empty | after the reply, one writer, one place | needs `use_mapper` decoupled from `fact_mapper_mode` (a setting change, not a new module); the ledger update lands later in the turn, which the "time to a usable memory" measure would show |
| **C. Add "own name" as an alias of `identity.name`** | none | deterministic | it is exactly the case-by-case widening the user forbade in the 90.D instructions; it fixes this sentence and no other |

**Recommendation, not implemented.** Do nothing for Zélia now: production keeps the mapper and therefore keeps the coverage, and
the candidate is not adopted, so the loss does not exist anywhere today. If adoption is reconsidered, **option B** is the smallest
correct shape — one writer, no duplicate call, no pre-reply cost — and it must be preceded by one measurement: how often the
extractor returns nothing on turns with no closed regex slot (that frequency is the whole cost). Option A is the honest fallback if
the pre-reply latency is acceptable; option C is ruled out by the standing instruction.

## 6. Decision

**Keep the fix; it is a production correctness fix, not a candidate one.** It removes a write that destroyed the user's name on
today's defaults, it changes nothing else measurable (write sets, truth core and both conversation sets identical; suite green with
seven new tests), and it costs nothing at runtime — one boolean in an existing condition, no model call, no new module, no setting.
Nothing was activated: the write-side candidate stays OFF and the reserved sets were not run.

Recorded, not acted on: the r09 conversation still fails on its own terms (a stated preference whose value is in no closed class
writes nothing) — that is the extractor-contract question, not an identity question. The Zélia fallback stays as presented in §5,
unimplemented. **"We are actually working on X" remains the next correction by the user's priority, now that identity integrity is
protected.**
