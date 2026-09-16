# HMG-Fu vs PA3 — execution parity analysis (2026-07-03)

Method: each PA3 area (from `project_arq/` 01–12) scored for **execution capability parity** —
"can our system DO this, live" — not code volume. PA3 ≈ 40k+ LOC, no test suite; hmg-fu ≈ 5.5k
LOC Python + 1.3k frontend, 71 tests. Parity ≠ copying: several PA3 mechanisms were deliberately
replaced by simpler HMG-Fu-native ones (docs/PA3_LESSONS.md) — those count as parity when the
*outcome* is equivalent.

## Scoreboard

| Area | PA3 has | We have | Parity | Biggest gap |
|---|---|---|---|---|
| Memory core (recall/facts/curation/dream) | 5-layer recall, fact-statement chains, macros L1/L2, dream every 10 min | Full HMG-Fu theory: Fu edges, ρ/κ/Ω, energy, wormholes, macros, decay+reawaken, echo filter, source-trust | **~75%** | FTS keyword channel; auto-scheduled dream; concept-key supersession chains |
| Tool recall & execution | galleries+classifier+skill-docs, 1 dispatcher, guards, MCP, CLI sub-agents, parallel batches | tools-as-HMG-points (simpler, graded), 1 dispatcher, same core guards, create_skill, tool_search | **~65%** | MCP routing; sub-agents (claude/codex); parallel tool batches; arg-normalizer |
| Efficiency (critical path) | 8–11 s pre-stream serial nano tax; token streaming; 12k-char tool payloads | 1 nano extract + 1 embed pre-reply (~1–2 s warm); retrieval 120 ms @1.2k pts; top-K tool payload | **~85%** (better where it counts) | token streaming of the reply; async grader off-path |
| **Directives** (incl. standing/override) | directives table, relevance-gated injection, forbidden-tool enforcement, `request_directive_exception`, cross-session OutputFormat enforcement | only implicit: a directive survives as a memory (e.g. "Master" suffix worked via injection) — no table, no enforcement, no override flow | **~20%** | THE gap to close next — first-class directives: store, always-inject when relevant, deterministic enforce, override/exception |
| Overnight / background execution | dream loop 10 min, autonomy loop 60 s, cron jobs, goals/todos, task DAG+workers, reflections | mini-dream every N turns; manual full dream; no scheduler/goals/tasks | **~15%** | background scheduler (dream nightly + autonomy); goals/todo store; task worker |
| Multi-provider | 5 providers, mid-turn fallback chain, retries+backoff, nano role cascades | 3 providers, per-role routing, loud failures, native+protocol tool modes | **~70%** | mid-turn fallback chain; retry/backoff policy |
| Frontend workflow (cards/widgets) | streaming deltas, 30+ widgets, A2UI surfaces, ui_state bus, voice | thinking/execution/memory/grade cards, 9 widget types LLM-creatable, hex+graph live, session restore | **~55%** | token streaming; widget layout persistence; A2UI-style forms |
| Connectors | OAuth broker+PKCE, AES vault, google/github/slack/notion, MCP install | registry + Fernet vault + status API (env-key based) | **~25%** | OAuth flows; actual service skills (gmail/calendar/search) |
| Learning loop | step reflections, playbook match-into-plans, object-intent ranker, learning_stats | grader EMA→ρ, playbook extraction+dedup, corrections→supersede, tool grading | **~55%** | playbooks not yet *matched into* future turns; no learning telemetry endpoint |
| Voice / companion | full always-on companion, Kokoro TTS, barge-in | none (PROJECT_ID: out of scope) | 0% (by design) | — |
| Safety & guards | capability enforcement, redirects, plan-first, response gates | bash blocklist, workspace guard, binary refusal, 2-strike, blocked≠failure | **~60%** | directive-driven tool forbidding (depends on directives) |
| Observability | learning_stats, logs API, prompt preview | graph stats, grade cards, ROADMAP evidence | **~30%** | /api/stats for learning + logs endpoint |

**Overall execution parity: ≈ 55–60%** — with the *core agentic loop* (remember → recall → tools →
answer → learn) at or above PA3 quality (tested, faster critical path, cleaner recall), and the
*periphery* (autonomy, directives-as-a-system, connectors, voice) still thin.

## Missing — ranked by value (candidate Phase 20+)

1. **First-class directives** (user emphasis): `directive` table + always-inject-when-relevant +
   deterministic output enforcement (PA3's OutputFormatDirectiveSection lesson: soft prompts don't
   bind local models) + `request_directive_exception` override flow. ~1 day.
2. **Background scheduler**: nightly full dream + periodic decay (currently only turn-triggered);
   hooks for cron'd tasks. ~half day.
3. **Reply token streaming** over /ws (`text_delta`), grader moved off-path (async). ~half day.
4. **Playbook recall**: matched `pattern` memories injected as "learned procedure" when a similar
   task arrives (extraction exists; the *replay* half is missing — PA3's tier-1 lesson). ~half day.
5. Goals/todos + autonomy loop (observer→suggest→auto modes). ~1–2 days.
6. Mid-turn provider fallback chain + backoff. ~half day.
7. Real connector skills (brave_search first — key already env-recognised). ~half day each.
8. MCP client routing (`__`-named tools). ~1 day.
9. Learning/observability endpoint (`/api/stats/learning`: grades, EMAs, tool utilities). ~2 h.
10. Widget layout persistence (ui_state-style) + A2UI-like forms. ~1 day.

## Tailscale serve — status
Implemented and wired (Settings → System → toggle; `POST /api/system/tailscale {on|off}`;
binary detected at `C:\Program Files\Tailscale`, v1.98.4). Live on/off verification recorded in
ROADMAP Phase 19.
