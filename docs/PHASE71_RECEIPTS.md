# Phase 71 — M2: receipts per action, post-conditions per step

Date: 2026-09-05. Branch `phase71-receipts` from `4e7625b`. Codex's finding C after Phase 70: "a tool ran" was
confused with "this step was fulfilled".

## What a receipt is

Every executed action opens a row in `receipts` BEFORE dispatch (status `pending`: the intended action is durable
first) and closes it after with the observed effects from the WORLD: files written with their sha256, widget ids, exit
codes. A blocked call leaves no receipt (the authority boundary already records it). Receipts survive restarts; a
receipt left `pending` by a crash is an UNKNOWN OUTCOME and is shown to the model on resume with the instruction to
verify the world before repeating. Cancellation marks pending receipts `cancelled`.

## What "done" now means

A step's post-condition is derived from its text: the files it names must exist on disk and be backed by a receipt
that wrote them; a "widget" step needs a widget receipt; a step naming a tool needs a successful receipt of that tool;
any other step needs some successful receipt. `update_plan(done)` and `end_turn` use the same verifier; the evidence
ids are recorded on the step and the receipts are `consumed_by` that step, so one write can never complete two steps.
A plan with done and failed steps finalizes as `partial`; all failed as `failed`.

## Evidence

* Codex's delta oracle (unchanged): the four deferred M2 checks now pass — **26/26 accepted** (9 deferred, all M3/M5).
* Sealed held-out M2 (7 cases written and committed before the code): 6/7; the miss is a fixture that expected a
  wrong-file write to happen, which Phase 70's plan scope blocks before it can exist — the product is stricter than
  the case. Left sealed, recorded.
* Full suite **477 passed**; say-do `plan_restart` **3/3 in both window arms** on the final code (after folding the
  `filename`→`path` and `tasks`→`steps` argument-name drift, and fixing two live findings: "e.g." is not a file, a
  thinking step needs no receipt); two live replays with a recorded, consumed widget receipt.

## Open

M3 assertions (7 deferred checks) and M5 target-bound claims (2) — next phases. The receipt store is also the
substrate for procedural memory (runbooks = plan + receipts) in Phase 75.
