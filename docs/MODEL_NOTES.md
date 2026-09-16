# MODEL NOTES — HMG-Fu (research + empirical evidence)

Persistent reference on the local models HMG-Fu runs on Ollama, their thinking/tool-calling
behaviour, and the exact settings the system must use. Built from web research (2026-07-06) +
live benchmarks. **Do not delete — hard-won.**

---

## ⚠️ CRITICAL — Ollama `think` + constrained decoding (Qwen3.5 / gemma4 family)

Both `gemma4:12b` and `ornith:9b` are **native reasoning models** (`ollama show` → capability
`thinking`). This interacts with our schema-constrained router in a dangerous way:

- **`think` is a top-level `/api/chat` param**: boolean `true`/`false` for Qwen3.5 (and gemma);
  `low`/`medium`/`high` for GPT-OSS-style. The reasoning comes back **separately** in
  `message.thinking`; `message.content` stays clean.
- **Ollama BUG #15260 (affects qwen3.5 + gemma4 exactly):** sending **`think:false` together with
  `format=<schema>` SILENTLY DROPS the format constraint** → the model returns plain text → the
  router JSON parse fails → misroute. **NEVER send `think:false` with a `format` schema.**
- **Correct router setting = OMIT `think`** (don't send the key) + keep the schema **enum/array-typed**.
  Under the schema grammar mask the model *cannot* emit `<think>` tags (their logits are −∞), so no
  reasoning preamble can corrupt the JSON — no strip step needed on the constrained path.
- **Temperature 0 caveat:** Qwen3.5 officially says *do not use greedy decoding* (endless
  repetition). For the router it's safe **because enum-only fields can't loop**; but a **free-text
  `string` field in constrained JSON can loop** (Ollama #15502 — "own own own…"). Mitigation: keep
  router fields enum/array; bound any string field with `maxLength`; or run temp ~0.4–0.6 + a fixed
  seed instead of exact 0.
- Optional quality boost: prepend a `reasoning: string` field as the **first** key of the router
  schema (GBNF emits keys in order) → the model reasons *inside* the JSON, schema still enforced.

Sources: github.com/ollama/ollama/issues/15260 · /issues/15502 · docs.ollama.com/capabilities/thinking

---

## Tool / action turns

- **Run action turns with `think:false`** (NOT with a `format` schema, so #15260 doesn't apply).
  Keeps reasoning from bloating a decided tool turn. KEEP this — but ⚠️ **it is NOT what fixed
  ornith's L8/L9/L10/L23** (that was the original Phase-57 hypothesis, and it was WRONG — see the
  "CORRECTED root cause" box below). Live probe (scripts/probe_think_api.py ornith:9b) showed ornith
  emits its tool command as a markdown ` ```bash ` code fence in BOTH think=true AND think=false, so
  disabling thinking changed nothing about whether the call was recovered.

> ### ⚠️ CORRECTED root cause of ornith's L8/L9/L10/L23 (Phase 58, live-probed — supersedes the
> "thinking buries the call" theory above)
> Probed the full causal chain per turn (scripts/probe_action_turns.py). THREE distinct,
> model-agnostic SYSTEM gaps — none is "the model is bad", none is native thinking:
> 1. **Emission format (L21, sometimes L8/L9):** ornith narrates the action as a **markdown code
>    fence** ` ```bash\n<cmd>\n``` ` (or an inline ` `ls` ` span, or a `<bash>` tag — the format is
>    itself non-deterministic per turn) instead of a native function-call. FIX =
>    `tool_protocol.parse_fenced_tool_call` (recovers ```bash/```json fences; complements the
>    existing hermes-envelope + `<bash>`-tag recovery). Lifted 26→30/34.
> 2. **Widget arg-shape (L10/L23):** create_widget WAS offered (score 0.46) + called natively 3×,
>    but ornith **FLATTENED the args** — `{type:'note', text:'…'}` / `{…, content:'…'}` at the TOP
>    level instead of nested `props:{text:'…'}` → "needs props ['text']" → 2 fails → blocked → fell
>    back to write_file. FIX = `widgets.enrich_widget_args` folds top-level keys into props +
>    normalizes synonyms (content→text) before validating. PROVEN L10+L23 fail→pass.
> 3. **Tool not offered (L8/L9):** `offered=[]`. "Inspect the project folder… what is its marker?"
>    is classified conversation_act='question' (needs a STRONG match to offer a tool) but read_file
>    scored only 0.332, bash <0.318 — BELOW plan_task 0.378. The semantic ranking didn't connect
>    "inspect the project folder" to the file/shell tools. FIX (two parts, both measured): (a)
>    enriched read_file/bash descriptions → read_file 0.332→0.42, bash →0.39, now correctly top-2;
>    (b) recalibrated the strong-question gate 0.44→0.40 (genuine inspection 0.42+ vs spurious
>    greeting/identity ≤0.326 — a clean ~0.10 gap). gemma 34/34 held throughout (global-change gate).
- Format = **Hermes JSON** `<tool_call>{"name":…,"arguments":…}</tool_call>` (NOT Qwen-Coder XML).
  Already handled by `tool_protocol.parse_hermes_tool_call`. Pitfalls it must survive (it does):
  name-before-arguments order; `arguments` as a stringified JSON in OpenAI-style `tool_calls[]`;
  multiple parallel `<tool_call>` blocks (findall, don't stop at first).
- Sampling for tool turns (Qwen non-thinking profile): temp 0.7, top_p 0.8, top_k 20, min_p 0.
  Note: Ollama's Go runner silently ignores repeat/presence penalties (#14493) — don't rely on them.

---

## Windows shell (ornith emits Linux-broken commands)

Three-layer, all config/probe-derived (no static per-command patch — mirrors aider/Cline):
1. **Dynamic host facts** in the `run_bash` tool schema/description (DONE: `environment_hint()`).
2. **Deterministic `normalize_for_gitbash()`** run on every command pre-exec: `\`→`/` in paths,
   CRLF→LF, `%VAR%`→`$VAR`, `dir/type/copy/del/where`→`ls/cat/cp/rm/command -v`, NUL→/dev/null.
3. **Post-failure repair loop** keyed on Git-Bash OS-mismatch stderr signatures
   (`sh: line 1: /c/Program: No such file or directory`, `command not found`, `\r: command not found`):
   auto-normalize+retry silently, only re-ask with `{stderr + host facts}` if that fails; cap 1–2
   turns and **drop the failed attempt from context** (retry-contamination trap, arxiv 2605.08563).
- Always execute via `bash -lc` so the model never picks the interpreter.

---

## ornith:9b  (Ornith-1.0-9B)

- **Publisher:** DeepReinforce (deepreinforce-ai), **MIT**, post-trained on a **Qwen 3.5 9B** base
  (arch `qwen35`, Hermes tool-call envelope, `<think>` blocks, `<|im_end|>` stop). Real, correctly
  labeled model.
- **Benchmarks:** beats its Qwen3.5-9B base AND Gemma4-12B on **agentic coding** — SWE-Bench Verified
  **69.4%** (base 53.2), Terminal-Bench 2.1 **43.1%** vs Gemma4-12B ~21%. BFCL v4 tool-calling strong
  (74–92%/category, good at abstaining). Its edge is in **multi-step tool loops**, NOT a single
  router call.
- **⚠️ No published Portuguese benchmark** (multilingual evidence is Japanese-centric). Do NOT assume
  the swap fixes the PT directive/clock items — root-cause those in HMG-Fu.
- **Settings:** main loop temp 0.6 / top_p 0.95 / top_k 20 / 262K ctx / thinking ON by default.
- **Size:** 5.6 GB Q4_K_M. **Requires Ollama ≥0.30.11** (we run 0.31.1). ~22–33% faster than gemma.

### Empirical (full Phase 57 stack, 2026-07-06): ornith:9b = **28/34**
- Fails **L8/L9/L10/L23** (tool actions not executed — *thinking buries the call*, confirmed by L9
  narrating instead of calling), **L16** (joke opener not applied), **L17** (identity supersession
  not clean). Timing 881s / 32.6s per live turn (faster than gemma's ~48s).
- vs **gemma4:12b = 34/34 REPLICABLE** (×3).
- ~~Root cause = uncontrolled native thinking~~ **← SUPERSEDED.** Phase 58 live-probing proved the
  real causes are the 3 system gaps in the CORRECTED box above (emission-format / widget arg-shape /
  tool-offering rank), NOT thinking. Progression across Phase-58 runs: 28 → **26** (unified-thinking
  alone, no help) → **30** (+ fenced-call recovery) → **30**, failures rotating L10/L23→L20/L24
  (+ widget-fold: L10/L23 fail→pass, the rest = documented single-sample router non-determinism).
  gemma held **34/34** on every run. ornith's residual is router-non-determinism + model-tier bound,
  NOT a deterministic code bug (same class as gemma's own per-run flake rotation).

---

## gemma4:12b  (Google DeepMind Gemma 4 12B — REAL model)

- **It IS real** — Google DeepMind's **Gemma 4 12B, released 2026-06-03** (after the Jan-2026
  knowledge cutoff, which is why it looked nonstandard). ~11.9B dense, **256K ctx**, **Apache 2.0**,
  Q4_K_M default (7.6 GB). Native **encoder-free multimodal reasoner** (text+image+**audio**), native
  **function-calling**, native **system-role**. Capabilities from `ollama show` are authentic.
- **Benchmarks** (secondary sources citing Google): reasoning/math are the standouts — MMLU-Pro 77.2,
  GPQA-Diamond 78.8, AIME 77.5; coding solid-not-leading LiveCodeBench 72.0. → excellent
  reasoning/routing brain (consistent with the **REPLICABLE 34/34**).
- **Multilingual**: 35+ languages out-of-box / 140+ pretrained → PT↔EN chat well covered (no PT-12B
  score published). NOTE: chat multilinguality is ORTHOGONAL to the English-centric `nomic-embed-text`
  embedder — the bge-m3 migration stays on the backlog separately.
- **vs Qwen3.5-9B (ornith)**: gemma wins reasoning/multimodal; ornith wins tool-calling + runs leaner/faster.

### Native thinking (gemma4) — same mechanism, extra gotcha
- Native reasoning via the Ollama **`think`** param (bool for gemma). **Default thinking ON** →
  omitting `think` costs ~3.9s/call. `<|think|>` system token is the underlying toggle (drive via
  `think`, not by editing the prompt). **The current `<thinking>` prompt directive is a STATIC PROMPT
  PATCH that does NOT drive native reasoning — retire it.**
- **Must use native `/api/chat`** — the OpenAI-compat `/v1/chat/completions` IGNORES `think` on
  gemma4 (#15293).
- **Same #15260 trap** as ornith: `think:false` + `format` silently drops the schema → **router OMITS
  think**. Also: disabling thinking on the 12B may still emit EMPTY `<think>` tags (except E2B/E4B) →
  extract_thinking must strip them.
- **Tool-calling gotchas**: (1) base gemma sometimes emits the call as a fenced ```json in content →
  keep the content-JSON fallback (tool_loop `recovered`); (2) on replay, NO `index` field in
  assistant tool_calls (gemma rejects "unknown variant index", #9249) — tool_loop already replays as
  `{"function":{name,arguments}}` with no index (correct, keep); (3) never insert a system message
  AFTER a tool-result message. The 12B (unlike 4B) does NOT over-call — answers in plain text when no
  tool is needed.

### Recommended settings (gemma4, per role)
- **Router (constrained JSON):** temp **0** (Ollama's own rec — keep), `format:<schema>`, **OMIT
  `think`** (never think:false), explicit modest `num_ctx` (NOT 256K), **repeat_penalty ≤1.1** (high
  values corrupt structured JSON by penalizing required repeated brace/key tokens).
- **Chat / tool turns:** temp ~0.2–0.3 (steadier tool calls), top_p 0.95, top_k 64, repeat_penalty
  1.1, explicit num_ctx. Drive thinking via `think` (dynamic→omit, always→true, off→false).
- ALL thinking/tools/format on native `/api/chat` only.

Sources: blog.google/…/introducing-gemma-4-12b · ollama.com/library/gemma4:12b · deepmind.google/models/gemma/gemma-4 · ollama issues #15260/#15293/#9249

---

## THE UNIFIED THINKING PLAN (P0 — what the user asked for + fixes ornith)

One setting (`thinking_mode`: dynamic/always/off) drives NATIVE reasoning of ANY thinking-capable
model, surfaced in the UI, controlled at the Ollama API level (not a constant prompt):

1. Add a `think` param to `OllamaClient.chat` + `OllamaProvider.chat` (like `format_schema`) and
   capture `message.thinking` from the response into the result.
2. **Detect native-thinking capability dynamically** (`/api/show` capabilities) — model-agnostic.
3. **Router**: OMIT `think` (never `false` with format) + enum/array schema. (Bug #15260.)
4. **Action/tool turns**: `think:false` — so the model doesn't bury the tool call.
5. **Answer turns**: `think` mapped from `thinking_mode` (dynamic/always→true, off→false) for
   native models; the prompt `<thinking>` directive stays only as a fallback for non-native models
   (the nano). Surface `message.thinking` (native) OR the parsed block as a UI thinking event.
6. Extend `extract_thinking` to also strip `<think>` blocks AND `<|mask|>` / `<|mask_first_thinking_block|>`
   leak tokens (any model).
7. Per-role sampling: router temp 0 (enum schema) or ~0.5+seed; action/answer temp 0.6–0.7 top_p 0.8.
8. Windows shell: add `normalize_for_gitbash()` + post-failure repair (layers 2+3 above).
