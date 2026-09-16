# Phase 66 — Harnessed tool use: why a small model fabricated the weather, and what the field does about it

Date: 2026-09-04. Case: live session `8269adf1ef1047c4`, turn 4 ("tell me whats todays weather"), gemma4:12b.
Method: DB records (tool trace, recall, grade, thinking) + UI replay, then primary-source research.

## 1. What actually happened (the record)

| Step | Tool call | Result | Failure class |
|---|---|---|---|
| 1 | `weather` `{}` | `unknown tool: weather` (hint: use tool_search) | **schema hallucination** — invented tool name |
| 2 | `tool_search("tell me whats todays weather")` | create_widget (weather type), brave_web_search… | recovery worked (1 extra round) |
| 3 | `brave_web_search("tell me whats todays weather")` | generic US snippet ("Mostly sunny… patchy fog… showers") | **argument hallucination** — raw sentence as query, no place, although the ledger says Valencia |
| 4 | `create_widget(weather, Valencia, 26°C, "Clear sky")` | ok | **over-action** — unasked widget, with a value from nowhere |
| — | reply: "26°C with clear skies" | | **output hallucination** — the number appears in NO tool output and NO memory |

Recalled memories on the turn: 0 — an action turn drops autobiographical context, so the user's standing rule from
June ("always use brave search for Valencia weather") never reached the prompt; it is stored as a MEMORY (fact/task
points), not a DIRECTIVE, because the directive kinds are opener/closer/prefix/suffix only. Turn 3
("stop with the scientifics facts") WORKED at the directive layer (closer cleared; table now empty) while the
model's words misread it as "drop the formal tone" — the deterministic layer beat the model's understanding.

Cost: 4 tool rounds for one question; the answer is unverifiable and probably wrong (it was a US snippet).

## 2. What the research says (2025–2026)

**Harness beats size.** Adapting the harness lifted gemma-4-26b-a4b from 75.0% to 98.3% on a repetitive task
(the frontier model: 97.3%) at 4% of the cost; 86% of successful adaptations were CONTEXT changes (explicit
step procedures, externalised conventions, exemplars), then tool-set filtering (40+ tools → 7) and narrow custom
tools, then runtime hooks (anti-loop). Gains were small on diverse tasks (code refactoring 60.6 → 62.2%).
[Better Harnesses, Smaller Models](https://arxiv.org/html/2607.08938) ·
[From Model Scaling to System Scaling](https://arxiv.org/html/2605.26112v1) (context governance, verified memory
and checked skill routing are the bottlenecks) ·
[It's Not the Size: Harness Design Determines Operational Stability in SLMs](https://arxiv.org/pdf/2605.12129).

**Tool hallucination has three classes** — schema (invented names), argument (format/content), output (fabricated
result without a call) — exactly steps 1, 3 and the reply above. Pre-execution validation and region-scoped
constrained decoding address the first two.
[Tool-call hallucination fix stack](https://iamkarmesh.medium.com/tool-call-hallucination-the-fix-stack-2279e45081c5) ·
[vLLM region-scoped guided decoding RFC](https://github.com/vllm-project/vllm/issues/39848) ·
[Internal representations as hallucination indicators in tool selection](https://arxiv.org/html/2601.05214v1).

**But constraints have a tax.** Grammar/JSON-schema constraints SUPPRESS tool calling in open-weight models,
worst for small ones; mitigations: constrain only the tool-call region, two-phase decode (free reasoning, then
constrained format). hmg-fu already uses schema-constrained decoding for the ROUTER only (Phase 57) — consistent.
[Constraint Tax in Open-Weight LLMs](https://arxiv.org/pdf/2606.25605).

**Grounding is a trace constraint, not a prompt.** AgentLTL enforces "every entity in the final answer must
appear in a prior tool output", detects violations at runtime and rejects/repairs; GSAR does typed grounding
across agents; 2026 practice gates the answer behind a faithfulness check that re-retrieves or refuses.
[AgentLTL](https://arxiv.org/pdf/2607.02599) · [GSAR](https://arxiv.org/pdf/2604.23366) ·
[Hallucination evaluation methods 2026](https://www.braintrust.dev/articles/ai-hallucination-evaluations-metrics-methods-2026).

**Small models fail at the middle rungs.** AgentFloor (7–12B open models): dominant failures are hallucinated
tools, wrong arguments, fabricated results, over-calling; what helps: in-context exemplars, restricting tools to
the task-relevant subset, pre-execution validation, structured schemas, explicit planning.
[AgentFloor](https://arxiv.org/pdf/2605.00334) · [SLM agentic survey](https://arxiv.org/pdf/2510.03847) ·
[EffGen](https://arxiv.org/pdf/2602.00887).

**Tool selection is the new planning problem.** 177k MCP tools exist; retrieval alone tops out at nDCG@10 ≈ 0.34
(ToolRet); the working pattern is necessity assessment → candidate reduction → sequence planning → validation,
and active discovery on demand (MCP-Zero) rather than listing everything.
[MCP-Zero](https://arxiv.org/pdf/2506.01056) · [Dynamic ReAct](https://arxiv.org/pdf/2509.20386) ·
[Set-level tool retrieval](https://arxiv.org/html/2607.25718v2) · [Tools in 2026](https://medium.com/@Micheal-Lanham/tools-in-2026-why-picking-the-right-action-is-the-new-planning-problem-d28d8443bf3f).

**Tool calling is trainable, and the scoreboard is BFCL v4.** Llama-3.2-1B ≈ 10.8, frontier ≈ 75; Liquid's 8B
went 25.5 → 48.5 with training alone. Model tier still matters for the residual.
[BFCL v4](https://gorilla.cs.berkeley.edu/leaderboard.html) · [SLMs for efficient tool calling](https://arxiv.org/abs/2512.15943) ·
[Hammer: function masking](https://arxiv.org/pdf/2410.04587) · [Harness-Bench](https://arxiv.org/html/2605.27922v1).

## 3. Mapping to hmg-fu — what already exists, what is missing

| Mechanism | hmg-fu today | Gap |
|---|---|---|
| Schema hallucination guard | `execute_tool` returns unknown-tool + difflib hint; `tool_search` meta-tool | costs a model round; no automatic resolution |
| Argument validation | required-arg back-fill (62.14); `x-auto-execute-defaults` | no CONTENT grounding (query without the known place) |
| Output grounding | none | the fabricated 26°C passed straight to the user and into a widget |
| Tool-set reduction | HMG-ranked top-8 tools per turn | not intent-conditioned; a weather question saw 8 tools incl. create_widget |
| Over-action guard | 2-strike / stuck-loop / iteration budget | no "unasked side-effects" rule (widgets), no per-intent round budget |
| Standing tool rules | memories only (`fact`/`task`), dropped on action turns | no `tool_rule` directive kind → never enforced |
| Exemplars / procedures | router exemplars for routing only | none for argument construction ("weather today" → "<city> weather <date>") |
| Constrained decoding | router only (right, per the constraint tax) | keep tool calls native/free; validate after |

## 4. The plan (Phase 66 in ROADMAP.md) — gates first

Baseline first: a **tool-precision suite** on real gemma (weather / time / news / "my link" cases) reporting
hallucinated-tool rate, argument-grounding rate, answer-grounding rate, rounds per question, over-action rate.
Then, in evidence order: (1) answer-grounding gate (AgentLTL-style, deterministic), (2) argument grounding
(exemplar + deterministic deixis completion from runtime/ledger), (3) automatic unknown-tool resolution,
(4) `tool_rule` directive kind + migration of the three stored rules, (5) intent-conditioned tool set and
per-intent round budget with an unasked-side-effect guard, (6) model-tier arm (gemma4:26b-a4b vs 12b).
Promotion of each step only if the suite improves and the Phase 62/65 truth bench does not regress.
