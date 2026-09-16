# Phase 72 — M3: assertions, modalities, cardinality, query-time validity

Date: 2026-09-05. Branch `phase72-assertions` from `f73dae4`. Programme "Fu 2", step M3 (ROADMAP Programme table).
Codex's 7 facts findings (68/69) and his Fu-R proposal (`reports/fu_theory_proposal_20260905/FU_R_PROPOSTA.md`,
analysed in `docs/FU_R_VS_FU2_ANALYSIS.md`) set the schema: **E** evidence (episodes), **C** bitemporal assertion with
a modality, **R** justification with AND/OR premises.

## What changed

| Layer | Before | After (72) |
|---|---|---|
| `hmgfu/utterance.py` | drop-only vetoes (quotes, fiction, past) | **sentence MODALITIES** `assert / cite / hypothesis / fiction / past / question`; single-quoted speech with an attribution cue; "the hero says:" makes the NEXT sentence a citation (the splitter cuts on the colon); reported speech with a complementiser ("o meu colega diz que…", "told me that…") is a citation unless first person; fiction/hypothesis carry over ONE sentence until a reality cue ("anyway / in reality / na verdade / my real name"); only discourse markers are stripped, never the fact; "since/desde/a partir de <year>" is CURRENT with `valid_from` |
| `hmgfu/assertions.py` (new, 144 lines) | — | `AssertionStore`: tables `entities`, `assertions` (polarity, modality, `valid_from/valid_to`, source episode + span), `justifications`; `assert_` supersedes the previous value of the same relation (bitemporal), `retract`, `active(at=)` (validity resolved at QUERY time), `history`, `justify` / `supported` (positive AND/OR fragment) |
| `hmgfu/facts.py` | one flat `canonical_facts` row per slot | assertions written in the same transaction as the ledger; **cardinality**: two entities of one kind in one message → `pet.dog.name` + `pet.dog.name.2` (duplicate guard when the same entity is reached through two surface forms); **named negation** "Teca, not Bento" retracts the value across the pet family; update subject must be ONLY generic; `render_history_lines()` ("Before <date>, your <label> was <old>") added to the context on past-cue questions |
| `hmgfu/slots.py` | closed schema | ordinal-aware `is_slot / label_for / normalise_key` (`<slot>.N`), `relation_in_clause` (mapper needs cue and value in the SAME clause), aliases `prato`, `mulher` |
| `hmgfu/fact_detect.py` | EN-centric forms | PT/EN parity: `chama-se`, `chamar-me / tratar-me por`, `trabalho como / I work as`, `eu sou o X`, `moro na`, `based in`; value canonicalisation (`called X` → X, leading article dropped, trailing "these days / agora", `/` allowed for `Africa/Valencia`); **structural guards**: a complement clause or prepositional phrase is never a value ("my guess is that…", "a minha dúvida é sobre…"), a bare URL scheme is never a value, PT clause cut before "e o <noun> … é"; link forms with a possessive first ("my car location link: URL") or a copula ("o link … do meu carro é URL") |
| `hmgfu/agent.py` | canonical lines only | HISTORY block on past-cue questions; metadata persists `grounding` |
| `web/app/MemoryPanels.jsx` | canonical ledger | `history (n)` toggle over the existing `/api/facts` history (cache-buster v13) |

No new settings. `declarative_text` kept as the compatibility view (assert sentences only). Existing slot keys, routes
and the `canonical_facts` table are unchanged; the assertion tables are additive.

## Evidence discipline (M0 rules applied)

* Held-out M3 (`scripts/oracles/heldout_m3.json`, 13 facts cases) sealed and committed at `400d58f` BEFORE the code:
  first run 11/13 → 13/13 after fixing the two defects it exposed (discourse-marker stripping ate "my real name";
  PT "vivo na"; duplicate ordinal).
* **Write precision / coverage** on sealed multilingual sets, each committed before its first run, bootstrap 95% CI
  over items (`scripts/run_write_set.py --set …`). An `<set>.errata.json` lists sealed expectations found inconsistent
  AFTER sealing; the runner prints the SEALED figure first and the sealed file is never edited.

| Set | Items | Sealed at | First run (held-out) | After fixes (dev) |
|---|---|---|---|---|
| v1 | 111 (79 pos / 32 neg) | `6a93404` | P 0.887 [0.817, 0.949] · C 0.816 [0.727, 0.891] | P 0.966 · C 0.966 (errata-adjusted 1.000: 3 leading-article expectations contradict the set's own w027) |
| v2 | 90 (63 / 27) | `fafbf93` | P 0.918 [0.833, 0.985] · C 0.957 [0.905, 1.000] | P 0.986 · C 1.000 (errata: v068 open-slot design) |
| v3 (final) | 83 (56 / 27) | `1188b2e` | **P 0.948 [0.882, 1.000] · C 0.932 [0.862, 0.984]** | P 1.000 · C 1.000 |

Verdict on the 72.5 target (P ≥ 0.98, C ≥ 0.90 on a fresh set): **coverage met on every held-out run; precision not
met**. Each fresh set exposes 3–5 lexical gaps of the regex path — the long tail of a hand-written detector. The fixes
were made structural where the defect was structural (complement clause, bare scheme, sentence-intro citation,
article canonicalisation), but the write path is still regex-bound. Reaching ≥ 0.98 on unseen phrasing needs the
model-backed mapper on the open residue with the same grounding rule (value must be in the text) — a Phase 73/74
candidate, not a claim made here.

* Facts-layer suites (`test_v9`, `test_v32`, `test_v36`, `test_v42`, `test_v48`): 85 passed. Full offline suite: see
  ROADMAP 72.6.
* Benches (truth, tool precision, say-do ×3 per window arm) and the live replay: ROADMAP 72.6 (`outputs/evidence_72.txt`).
* **Environment finding (72.6b).** The first tool-precision run fell to 4/8 because the shell's `python` was the system
  interpreter without `cryptography`: the credential vault could not be read, every search case answered "not
  configured" (honestly — the model had chosen the right tool). Every bench manifest now records `executable` and
  `environment_warnings` (`scripts/_bench_paths.environment_warnings()`), and `guard_scratch` prints them on stderr.
  Benches are run under `.venv/Scripts/python.exe`.
* **Say-do finding (72.6c).** In one of six say-do reps the `plan_restart` case ended 2/3 files: the receipts gate
  refused both premature `update_plan(done)` calls (correct), but on "continue" the gate's re-ask was accepted because
  *a* tool ran (a read-only `bash`), not the required `write_file`, and "all steps are now complete" went out. Fix:
  `saydo._fulfilled(new_steps, required)` — a re-ask counts only when a required step tool ran unblocked; otherwise
  the step stays open and any completion claim gets `PLAN_CORRECTION`. The bench row now derives `false_exec_claim`
  from the engine's own reports (it had recorded the false claim the summary did not show).
* **Storage finding (72.6d).** One rep aborted with `database is locked` in `receipts.open`: each store opened its own
  connection with SQLite's defaults (rollback journal, 5 s busy timeout). New `hmgfu/db.py: connect(path)` — WAL
  journal + 30 s busy timeout — is now the single connection policy for `store`, `facts`, `assertions`, `receipts`,
  `session_plans` and `directives` (`tests/test_v49_db_connect.py`: two writers with overlapping transactions no longer
  fail). `hmgfu.db-wal/-shm` are covered by the existing `hmgfu.db-*` gitignore rule.

* **Live replay finding (72.6g) — the echo loop.** The history question "Where did I live before?" answered "Lisbon …
  and Chimoio". Chimoio was the Phase 69 probe, rolled back with a migration row — a value that was never true. Three
  layers let it through: the history renderer read the rollback row's previous value as history; the answer itself was
  stored as an assistant memory and re-taught "Chimoio" on the next question (three such echoes accumulated during the
  replay); and the P2 history timeline pooled memories from any source. Fixes: `FactStore.reverted_values()` (rows from
  migration/rollback/audit sources) excluded from history lines and from the timeline; `supersede_stale_nodes` demotes a
  reverted value even beside the current one, with an inflection-aware attribute gate (`slots.mentions_attribute`); the
  timeline pool is the user's own statements only. After the hygiene pass and restart the answer is "Before May 2026,
  you lived in Lisbon" with no reverted value in the retrieved set. Rule added to the replay discipline: on production,
  a history question is itself a write — the answer becomes a memory — so verify one answer before asking again.

## What this buys the theory (assessment revision in `docs/FU_THEORY_ASSESSMENT.md`)

Semantic memory now has belief revision with time: a value is not overwritten, it is superseded with `valid_to`, and
"what was my X before?" is answered from the same store at query time (ACT-R/TMS-style justification is the positive
fragment only — no defeaters yet). Cardinality (two dogs) and named negation stop the single-slot collapse Codex
found. What is still missing for the Fu-R schema: justification chains actually consumed by the reader (only written),
conflict surfacing to the user when two active assertions clash, and the mapper on the open residue.
