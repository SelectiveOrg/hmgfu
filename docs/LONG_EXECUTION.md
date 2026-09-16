# Long executions — what PA3 did, what we build instead (Phase 21)

## How PA3 keeps long executions alive (from project_arq 04/08)

| Mechanism | What it does | Cost |
|---|---|---|
| `MAX_TOOL_ITERATIONS=200` + `MAX_CONTINUATION_ROUNDS=50` | lets a turn run for minutes/hours of tool calls | runaway risk, guarded by stuck/no-progress detectors |
| `task_supervisor` + `task_worker` | detects multi-step asks, builds a plan (LLM or template), executes step-by-step in a background worker | a whole parallel execution system (tables, queue, 10s poll) living OUTSIDE the chat turn |
| `reflect_on_task()` per step | mid-task learning notes feeding the next step | extra nano call per step |
| DAG planner / replan engine | plan data structure exists | execution stayed sequential — dead weight |
| Heartbeats (`run_tool_with_heartbeat`, 20s) + `show_progress` tool | UI liveness during long steps | — |
| `_WSRef` buffering | tokens survive WS disconnect/reconnect | — |
| Per-session turn lock | one turn at a time per session | — |
| Forced finalization | never a dead placeholder at limits | — |

**PA3's core insight:** long executions need (1) a visible plan, (2) generous-but-guarded
iteration budgets, (3) liveness signals, (4) survival of the transcript, (5) one-writer discipline.
**PA3's core burden:** it built a second execution universe (supervisor/worker/task tables) beside
the chat loop, and the two drifted (its own docs list the `step['status']` crash and sequential-only
DAG as debt).

## Our design — the plan IS a turn object, not a second system

One execution path (the agent tool loop we already trust) gains a first-class **TurnPlan**:

1. **`plan_task` tool** — for multi-step work the model declares `{title, steps[]}`.
   → `plan` event → PlanTracker card in the transcript (the design-system component).
2. **`update_plan` tool** — the model marks steps `active/done/failed` as it works.
   → `plan_update` events → the SAME card updates in place (2/4 progress).
3. **Extended budget, earned not default** — a turn with a declared plan gets
   `max(agent_max_iterations, 4×steps, cap 60)` iterations; unplanned turns keep the small budget.
   The stuck-loop / 2-strike / no-progress guards stay armed the whole time.
4. **Heartbeat** — a `status` event each loop iteration (`iteration`, `tools_used`, `elapsed_s`)
   so the UI shows liveness between cards even during a slow gemma call.
5. **Per-session turn lock** — a second `chat` for a busy session is rejected with a clear error
   (PA3 invariant, ~10 lines here).
6. **Persistence** — the final plan lands in `conversations.metadata.plan`; history restore
   re-renders the tracker. The plan is also what the grader sees (planned turns produce better
   playbooks — the steps ARE the procedure).

Why this is better for us: zero parallel infrastructure, the plan lives in the same event
stream/DB as everything else, the model self-reports progress (which PA3's worker had to infer),
and the learning loop gets structured procedures for free. What we consciously DON'T take:
background task queues and cron autonomy (separate parity item), DAG parallelism (PA3 never
shipped it either).
