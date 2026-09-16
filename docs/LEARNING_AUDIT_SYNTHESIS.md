# What five real conversations showed about learning — anonymised synthesis

Source: a local audit of five recent sessions (23 exchanges) read from the personal database in
read-only mode. **The audit report itself stays local and unversioned: it contains personal content.**
This file is the anonymised synthesis the execution plan permits to be published, with the personal
terms replaced by neutral placeholders.

## The one thing that already works

A personal fact corrected in conversation reached the ledger and was answered correctly in two later
sessions. That capability exists and must be preserved by any change, not re-derived.

## The three that do not

1. **A taught domain definition is stored but not reused.** The user taught the expansion of an
   acronym. The correction was kept verbatim as a user point and `memory_search` could find it, yet
   three direct questions in new sessions did not use it — the correct answer appeared only after an
   explicit hint from the user, or after a search was actually executed. *Absence of retrieval is not
   absence of storage*, and the two must be measured separately.

2. **A behaviour instruction was persisted as the wrong kind of thing.** "Search memory when you are
   unsure" became an `output_prefix` whose literal value was the word `none`, so the word was
   prepended to later replies instead of a conditional search policy being installed. A deterministic
   probe on synthetic bases reproduced the mechanism: the correct tool-rule detector does recognise
   the instruction, but the supplied candidate takes precedence, and a malformed prefix passes the
   sanitiser. The historical raw router output was NOT captured, so the origin of that candidate in
   that turn remains inferred, not proven.

3. **Derived summaries invent content and compete with the user's correction.** A summary added an
   expansion that appears nowhere in the content it summarises; other derived points carry different
   invented expansions. Unsupported derived information competing with a user correction is
   demonstrated. What is *not* demonstrated is the causal weight of each derived point in each wrong
   answer — that needs its own ablation.

## What this means for the work

The priority is not another list of linguistic forms. It is closing the cycle
`evidence -> correct update -> retrieval -> verifiable behaviour`, with three properties tested
separately:

- a definition taught outside the personal slot catalogue must be representable, retrievable in a new
  session without a hint, and answerable with its source and status;
- a behaviour policy must be distinguishable from a response format, and approval must change the
  right target rather than produce a promise;
- provenance and status must survive summarisation and consolidation, so an assistant's conjecture
  never becomes a user-confirmed definition.

A receipt must separate *received* from *updated*, and no answer should promise never to forget.

## Cost observed, not a benchmark

Across the 23 replies, median reply time 8.6 s (min 4.6, max 39.0) and 258 aggregated model calls,
about 11.2 per turn — a counter that includes several roles and embeddings, not main-model replies
alone. These are observations on one machine under one profile. They are not a paired baseline and
not a universal limit.

## Explicitly not concluded

No originality or AGI-readiness figure is recalculated from these conversations: they are localised
functional evidence, not a representative sample. Repair of the already-affected live data is a
separate, separately authorised action; the audit performed neither repair nor code change.
