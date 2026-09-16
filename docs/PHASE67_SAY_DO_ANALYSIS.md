# Phase 67 — Say-do fidelity: intent claims, approvals, and plans that survive the turn

Date: 2026-09-04. Case: live session `02acd6e33b79470f` (7 turns, gemma4:12b). Question from the user:
"the agent says it is going to do something and doesn't do it; it should ask permission, then execute" —
and this is where a *recall-based* memory (no conversation context window) meets long execution.

## 1. What happened, turn by turn (records)

| T | User | Assistant | What the record shows |
|---|---|---|---|
| 2 | share the link to track my car | link given | ✅ from the ledger, no tool |
| 3 | here's the updated link: `…cc67…` | "I've **updated** your car location link in my records" | ❌ **FALSE execution claim** — `canonical_facts` still holds the OLD link, `fact_history` has no write. The statement form "here's the updated link: URL" matches no resolver form (no "my X" / "link for my X"), so nothing was written |
| 5 | share the clickable link | markdown link with the NEW URL | ⚠️ correct by accident: the new URL came from RECALL of turn 3's message, not from canon; canon and recall now disagree |
| 6 | hmm, it's not clickable, I think it's a UI issue | "**I'll take a look** at the project structure to identify which component might be causing the issue." | ❌ **INTENT claim, zero action** (no tool, no plan, turn over) — and the wrong target: the thinking bound "UI" to the ExampleProject *workspace*, not to this chat; **0 memories recalled** on the turn, so "it" had no referent |
| 7 | maybe create a widget to keep links | note widget created (first call failed on missing props, second ok) with placeholder text; "let me know which links you'd like me to add" | ⚠️ acted, but ignored the link it already knew (argument not grounded in memory); one wasted round |

Root causes (not model mood):
1. **No say-do contract.** A reply that announces an action ("I'll take a look") or claims one ("I've updated")
   ends the turn with no check against telemetry. PA3 had two categorical gates for exactly this
   (`action_claim_enforcer`: intent → required tool family, decided from tool telemetry; `execution_claim_enforcer`:
   tool results must not contradict the claim). hmg-fu has only the router-driven "ACTION REQUIRED" retry, which
   fires only when the router labelled the turn an action — a vague complaint is a statement.
2. **No approval → execution flow, and no plan beyond the turn.** hmg-fu's `TurnPlan` is per turn
   (`engine._turn_plan` is reset each turn); a proposal cannot wait for "yes" and be resumed. PA3 solved it with a
   second execution universe (supervisor/worker/task tables + a pinned-plan block) that drifted from the chat loop.
3. **Recall-only memory has an anaphora hole.** The model receives `[system, current user message]` — no
   conversation history. Everything it knows of the previous turn must come back through retrieval. A short,
   vague follow-up ("it's not clickable") retrieves nothing (0 memories), so the assistant literally does not know
   what "it" is. This is the experiment the user wants: how far can recalled memory replace a context window in
   long executions, and where must a guaranteed window exist.
4. **The update form is missing in the resolver.** "here's the updated link: URL" (no possessive, no attribute)
   must supersede the single URL-valued slot when unambiguous — today it writes nothing and the model *says* it did.
5. **Workspace over-attribution.** The ACTIVE WORKSPACE block says "for questions about this project… inspect the
   workspace"; the model read "UI issue" as the workspace's UI.

## 2. What PA3 built (read, not copied)

- `action_claim_enforcer` (543 lines): categorical gate — intent families declared as data
  (create/add/build/open/write… → required tool families); the reply is denied unless a successful action tool
  fired this turn; counts prior denials; default-off flag.
- `execution_claim_enforcer` (140 lines): "successfully deployed/verified" is denied when tool RESULTS contradict it.
- `continuation_prompt_builder`: a pinned plan block at the top of the system prompt that never gets compressed —
  the model's single source of truth for "where are we".
- `task_supervisor` / `task_worker` (3.4k lines): detects multi-step asks, persists plans in SQLite, executes
  step by step in a background worker, injects follow-ups for incomplete steps, auto-approves low/medium risk.
- PA3's own debt list (docs/LONG_EXECUTION.md): the second execution universe drifted from the chat loop;
  the DAG stayed sequential; enforcement was lexical in places.

## 3. The better implementation (hmg-fu-native, one execution path)

**Principle: every claim is a contract, checked from telemetry at the end of the turn — and a plan is a
session object, not a turn object.**

1. **Say-do gate** (`hmgfu/saydo.py`, deterministic, runs after the tool loop like the grounding gate):
   - *Intent claims* ("I'll / let me / I'm going to / vou / deixa-me ver…") with **no tool this turn** →
     read-only intents (look/check/inspect/search/read) are executed NOW (one more loop iteration with the
     intent as the instruction); side-effecting or multi-step intents become a **proposal** (see 2) and the
     reply ends with the question, never with a dangling promise.
   - *Execution claims* ("I've updated/created/saved/deleted…") must match a committed transaction this turn:
     ledger write (`facts.apply_all` result), directive change, or a successful side-effect tool. No transaction →
     the sentence is rewritten to the truth ("I could not update it — nothing was written") or the write is
     performed when it is unambiguous (case 4 below).
   - *Value claims* — already 66.2.
2. **Proposal → approval → execution** (`hmgfu/session_plans.py`): `plan_task` gains `status`
   (`proposed | approved | active | done | abandoned`) and plans persist per **session** (table `session_plans`,
   restored on reconnect and restart). A proposal ends the turn with a one-line question. The next turn runs a
   deterministic approval detector (short affirmative/negative, EN/PT, only when a proposal is pending; the router
   gets an `approval` act as the second opinion). Approved → the plan is **pinned** at the top of the system prompt
   (never compressed, PA3's one good idea kept), the earned iteration budget applies, `update_plan` marks steps,
   incomplete steps re-pin on the next turn. Declined → abandoned with the reason stored. Resumable after restart:
   the pinned block is rebuilt from the table, not from memory recall.
3. **Anaphora window, measured** (`config.RECENT_TURNS_WINDOW`, default 3): the last N turns of the session are
   injected verbatim (truncated) as "Recent conversation", independent of retrieval. This is the controlled
   experiment the user asked for — arms N=0 (today), N=3, N=6 — reported per case class (anaphoric follow-ups,
   corrections, long executions) so the memory-vs-context question is answered with numbers, not belief.
4. **Update form in the resolver**: "here's the updated/new X: VALUE" and "updated X: VALUE" → when exactly one
   slot of that value type (URL/number/name) exists, it supersedes it; otherwise the assistant asks which one.
5. **Workspace scoping**: the workspace block applies only when the message refers to files, code, a repo or the
   project by name; UI complaints about *this* app are answered from the recent window / recalled memories.
6. **Argument grounding from memory for side-effect tools**: a widget/file created for a known value carries
   the value from the ledger (the link), not a placeholder — extension of 66.3 (`x-content-from-memory` on the
   tool schema, filled by the harness from the ledger when the user's request names the slot).

## 4. Bench (gates first): `scripts/bench_say_do.py` — multi-turn, real gemma, clone of the live DB

Cases (EN + PT): anaphoric complaint after a link; "here's the updated link: URL"; "can you build a links widget?"
→ "yes" (executed with plan, steps done, widget carries the link) and → "no" (abandoned, nothing built);
5-step build across two turns with a simulated restart between (plan resumes from the table); read-only intent
("let me check…") auto-executed; workspace misattribution case. Metrics: intent-claim-without-action rate,
false-execution-claim rate, approval honoured, plan persisted/resumed, steps completed, workspace misattribution,
rounds per case. Arms: window N=0/3/6. Promotion of each step only if its metric improves and the Phase 62/65/66
benches do not regress.


## 67.10 — What the bench found after the first fix, and what was wrong at the harness layer

The first post-fix say-do run (window 3) scored 3/6 with the two claim classes at zero. The three
remaining failures were all *harness* defects, not model defects, and one was a defect in the bench itself:

| Symptom | Root cause | Fix |
|---|---|---|
| "yes" / "no" / restart cases never saw the previous turn | the bench passed invented session ids; `SessionStore.ensure_session` silently creates a fresh session for an unknown id, so every turn was a new session | `new_session()` creates a real session; the plan is read from `session_plans` |
| a suggestion was built immediately | `requests_side_effect` matched "create a widget" inside "you can maybe create a widget" | `speech_act.is_suggestion` closes the side-effect gate; the blocked call is recorded and the harness proposes it deterministically |
| the model wrapped the side effect in `plan_task` and the gate reopened | an active plan is (by design) the permission to run tools | on a suggestion turn `plan_task` is forced to `proposed`; a proposal made this turn always ends with the confirmation question |
| after approval the model promised again and was re-proposed (loop) | the intent gate proposed whenever no tool ran, regardless of the plan state | active plan + promise/"continue" + no tool → approved re-ask; the plan stays active if the re-ask still does nothing |
| "let me know" counted as a promise | `_INTENT` matched "let me" | negative lookahead `let me(?! know)` |
| the links widget had no link on the approval turn | "yes please" names nothing; only note text was grounded | referent = user message + pinned plan; `ground_widget_props` grounds note text and table rows |

The pattern: **every place where the model can talk its way past a gate needs the gate to be a state of
the turn, not a phrase match on the reply.** The suggestion gate, the forced proposal and the approved
re-ask are all keyed on turn state (`_turn_effects_allowed`, `_turn_proposed`, `_turn_plan`).


## 67.11–67.15 — four more bench passes, what each one found

| Pass | Found | Layer | Fix |
|---|---|---|---|
| 67.11 | sparse `create_widget` with no props failed; `plan_task` after approval replaced the approved plan; "I'm getting started…" was not a known promise | harness | props built from the ledger (`grounded_props`); `plan_task` returns `already_active`; plan tools are not "work"; `_INTENT` extended |
| 67.12 | on "yes please" the router did not offer the step's tool, so neither the turn nor the re-ask could call it | harness | `ensure_step_tools`: the current step's tool is offered and REQUIRED; the re-ask carries required actions |
| 67.13 | the runtime clock "14:26:32" grounded a fabricated "26°C" whenever the minute matched (a suite failure that depended on the wall clock) | grounding gate | clock tokens ground only time-shaped claims; a time of day is one claim |
| 67.14 | a turn cut short after 2 of 3 files marked every step done; shared clone made the widget check look for a stale link | harness + bench | only the worked step completes on evidence; the bench reads the ledger's current value and records failed tool results |
| 67.15 | after a restart, a step naming no tool had nothing to require → apology | harness | the plan remembers `tools_used`; a resume requires them |

Final: say-do **5/6 (window 3) / 6/6 (window 0)**, both claim classes 0 in both arms; tool-precision harness
metrics all held (7/8 on a name-phrasing check); truth 16/17 with the miss proven to be live-data drift. The one
open gap is the model's own `update_plan(done)` being taken on its word (67.16).
