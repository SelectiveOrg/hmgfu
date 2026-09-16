"""The agentic tool loop (extracted from agent.py at the 400-line ceiling, Phase 28).

One turn's execution engine: provider rounds, PA3-proven guards (2-strike per tool,
stuck-signature, no-progress cutoff, forced finalization), sequenced thinking narration
(doctrine: no silent tool rounds), artifact recording, and event emission via the engine.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from typing import List

from .plans import iteration_budget
from .providers import ProviderError
from .thinking import extract_thinking, narrate_tool_calls
from .tool_protocol import parse_text_tool_call
from .toolsys import classify_tool_result, tool_signature

log = logging.getLogger("hmgfu.tool_loop")


def fill_missing_single_arg(args, schema: dict, user_message: str) -> dict:
    """62.14 (live T4 failure: `memory_search` called with {} → embedded "" → tool error → no answer).
    When a call omits its ONLY required string argument, the turn's user message is the obvious
    value — the same single-required-string-arg principle `tool_protocol` already uses for
    text-form calls. Multi-arg tools are never guessed."""
    args = dict(args) if isinstance(args, dict) else {}
    params = (schema.get("parameters") or {})
    required = params.get("required") or []
    if len(required) != 1 or not user_message:
        return args
    key = required[0]
    ptype = ((params.get("properties") or {}).get(key) or {}).get("type")
    if ptype == "string" and not str(args.get(key) or "").strip():
        args[key] = user_message
    return args


def _required_met(required, tool_trace, schemas) -> bool:
    """95.47b: a required WRITE is satisfied only by itself -- its receipt is what proves the work (X2: a bash
    write satisfied a required write_file, and nothing could prove the file); a required read or search is
    a means, satisfied by any successful call. Effect classes, never names."""
    from .authority import BUILTIN_EFFECTS
    ok = [t for t in tool_trace if not t.get("blocked") and not t.get("failed")]
    writes = [n for n in required if ((schemas.get(n) or {}).get("x-effect") or BUILTIN_EFFECTS.get(n)) in ("write", "unknown")]
    return any(t.get("name") in writes for t in ok) if writes else bool(tool_trace)


def run_tool_loop(engine, messages: List[dict], tool_schemas: List[dict],
                  native: bool = True, turn_seq: int = 0,
                  required_actions=None, think=None) -> tuple:
    """Returns (reply, tool_trace, forced_finalization). `think` (Phase 58): the native-reasoning
    setting for this turn (False on action turns so thinking never buries the tool call — ornith;
    None/True on conversational turns to show reasoning). Reasoning surfaces via message.thinking."""
    started = time.perf_counter()
    base_budget = getattr(engine, "_turn_iteration_cap", None) or engine.settings.get("agent_max_iterations")
    tool_trace: List[dict] = []
    failure_counts: dict = {}
    recent_signatures: deque = deque(maxlen=6)
    initial_request = next((m.get("content", "") for m in reversed(messages)
                            if m.get("role") == "user"), "")
    offered = {t.get("name") for t in tool_schemas}
    required_actions = [n for n in (required_actions or []) if n in offered]
    action_retry_used = False

    # Explicitly named, zero-argument status/introspection tools need no model-generated
    # arguments. Execute them immediately so proactivity does not depend on a model deciding
    # to echo the exact tool name back through native tool-calling.
    schemas = {t.get("name"): t for t in tool_schemas}
    for name in required_actions:
        schema = schemas.get(name, {})
        parameters = schema.get("parameters", {})
        required_params = parameters.get("required", [])
        optional_params = parameters.get("properties", {})
        defaults = schema.get("x-auto-execute-defaults")
        can_preexecute = isinstance(defaults, dict) or (not required_params and not optional_params)
        if name.lower() not in initial_request.lower() or not can_preexecute:
            continue
        call_id = f"t{turn_seq}_{len(tool_trace)}"
        args = dict(defaults or {})
        engine._emit({"type": "tool_call", "id": call_id, "name": name,
                      "arguments": args, "turn_seq": turn_seq})
        outcome = engine.tools.execute_tool(name, args)
        failed, summary = classify_tool_result(outcome)
        engine._record_artifacts(name, outcome)
        engine._emit({"type": "tool_result", "id": call_id, "name": name,
                      "result": outcome[:1200], "failed": failed,
                      "blocked": False, "turn_seq": turn_seq})
        tool_trace.append({"name": name, "arguments": args, "result": outcome[:2000],
                           "failed": failed, "blocked": False, "summary": summary})
        messages.append({"role": "system", "content":
                         f"PROACTIVELY EXECUTED TOOL {name}. Result: {outcome[:8000]}"})

    iteration = 0
    # while-loop: a plan declared MID-TURN grows the budget (docs/LONG_EXECUTION.md)
    while iteration < iteration_budget(base_budget, engine._turn_plan):
        iteration += 1
        engine._emit({"type": "status", "turn_seq": turn_seq, "iteration": iteration,
                      "tools_used": len(tool_trace),
                      "elapsed_s": round(time.perf_counter() - started, 1)})
        try:
            result = engine.registry.chat_for_role(
                "chat", messages, temperature=0.5,
                tools=tool_schemas if (tool_schemas and native) else None,
                think=think,
            )
        except ProviderError as exc:
            log.error("chat provider failed: %s", exc)
            if tool_trace:
                last = tool_trace[-1]
                return (f"I performed {last['name']}. Result: {last['result']}",
                        tool_trace, False)
            return f"(provider error: {exc})", tool_trace, False
        content, tool_calls = result["content"], result["tool_calls"]
        if not tool_calls:
            # Recover a tool call the model emitted as TEXT (JSON protocol OR an XML tag like
            # `<bash>…</bash>`) — non-native models always, and native models that occasionally
            # narrate the call instead of emitting it (ornith/Qwen3.5). A normal prose answer
            # contains no such pattern, so this never hijacks a real answer.
            recovered = parse_text_tool_call(content or "", tool_schemas)
            if recovered is not None:
                tool_calls = [recovered]
        # reasoning surfaces as a THINKING block IN SEQUENCE (PA3 lastBlockByTurn); a silent
        # tool round gets deterministic SYSTEM narration (doctrine: no silent tool rounds).
        # Native reasoning (message.thinking, Phase 58) is surfaced too — the user sees the model
        # think regardless of model; extract_thinking also strips any inline <think>/<|mask|> leak.
        content, thoughts = extract_thinking(content or "")
        native_think = (result.get("thinking") or "").strip()
        if native_think:
            thoughts = "\n\n".join(b for b in (native_think, thoughts) if b)
        narration = "\n\n".join(
            b for b in (thoughts, content.strip() if tool_calls else "") if b).strip()
        if not narration and tool_calls:
            narration = narrate_tool_calls(tool_calls, engine._turn_plan)
        if narration:
            engine._emit({"type": "thinking", "text": narration, "turn_seq": turn_seq,
                          "final": True})
            engine._turn_thoughts.append(narration)
        if not tool_calls:
            if required_actions and not action_retry_used and not _required_met(required_actions, tool_trace, schemas):
                # System-owned proactivity: reject one prose-only attempt for an explicit
                # action. The model supplies arguments, but it cannot claim completion first.
                action_retry_used = True                     # 95.47b: a required WRITE is met only by itself
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({"role": "user", "content":
                                 "ACTION REQUIRED: you have not performed the requested action with the tool that "
                                 f"proves it. Call one of these applicable tools now: {', '.join(required_actions)}. "
                                 "Do not claim completion until a tool result confirms it."})
                continue
            if not (content or "").strip() and iteration < iteration_budget(base_budget, engine._turn_plan):
                # empty reply (some templates go silent) — nudge one continuation
                messages.append({"role": "user",
                                 "content": "Continue: give your answer as plain text."})
                continue
            return content, tool_trace, False

        if native:
            messages.append({
                "role": "assistant", "content": content or "",
                "tool_calls": [{"function": {"name": tc["name"], "arguments": tc["arguments"]}}
                               for tc in tool_calls],
            })
        else:
            messages.append({"role": "assistant", "content": content or ""})
        for tc in tool_calls:
            name, args = tc["name"], tc["arguments"]
            full_schema = schemas.get(name) or getattr(getattr(engine, "tools", None), "schemas", {}).get(name, {})
            args = fill_missing_single_arg(args, full_schema,
                                           getattr(engine, "_turn_user_message", ""))   # 62.14
            qarg = full_schema.get("x-search-query-arg")
            if qarg and isinstance(args, dict) and hasattr(engine, "facts"):   # 66.3 argument grounding
                from .deixis import complete_query
                args[qarg], added = complete_query(str(args.get(qarg) or ""), getattr(engine, "_turn_user_message", ""),
                                                   getattr(engine, "_turn_runtime", None), engine.facts.active())
                if added:
                    args["_completed"] = added
            if name in ("create_widget", "update_widget") and isinstance(args, dict) and hasattr(engine, "facts"):
                from .deixis import grounded_props, memory_lines         # 67.6/67.10/67.11 memory-grounded content
                plan = getattr(engine, "_turn_plan", None) or {}          # on an approval turn the PLAN is the request
                referent = " ".join([getattr(engine, "_turn_user_message", ""), plan.get("title", "")]
                                    + [s.get("text", "") for s in plan.get("steps", [])])
                props = grounded_props(args.get("type"), args.get("props"), memory_lines(referent, engine.facts.active()))
                if props is not None:
                    args["props"] = props
            tc["arguments"] = args
            from .authority import guard as authority_guard, resolve_name
            alias, name = name, resolve_name(engine, name)     # 70.7 (M1.6): resolve ONCE; policy and dispatch see the same tool
            call_id = f"t{turn_seq}_{len(tool_trace)}"
            engine._emit({"type": "tool_call", "id": call_id, "name": name, "alias": alias if alias != name else None,
                          "arguments": args, "turn_seq": turn_seq})
            sig = tool_signature(name, args)
            # 95.17: the cap lives on the registry's schema; an un-offered tool the model calls anyway
            # (E7: create_widget withheld, called, succeeded TWICE) is capped like an offered one
            schema = schemas.get(name) or getattr(getattr(engine, "tools", None), "schemas", {}).get(name, {})
            success_cap = schema.get("x-max-successful-calls-per-turn")
            prior_successes = sum(1 for t in tool_trace if t["name"] == name
                                  and not t["failed"] and not t.get("blocked"))
            # guard (66.6 → 69.1 → 70.4): ONE authority boundary — declared effects, scoped authorization RECORD,
            # prohibition wins; a model-declared plan grants nothing (only the user's request or approval does)
            echoed = engine.tools.echoes_the_request(name, args) if hasattr(engine.tools, "echoes_the_request") else None
            blocked_outcome = None if echoed is not None else authority_guard(engine, name, args)
            if blocked_outcome is not None:
                outcome = blocked_outcome
            # guard: 2-strike block per tool per turn
            elif isinstance(success_cap, int) and prior_successes >= success_cap:
                outcome = json.dumps({"blocked": True,
                                      "reason": f"{name} already succeeded this turn"})
            elif failure_counts.get(name, 0) >= 2:
                outcome = json.dumps({"blocked": True,
                                      "reason": f"{name} failed twice this turn — answer without it"})
            # guard: stuck loop (same signature repeating)
            elif list(recent_signatures).count(sig) >= 2:
                outcome = json.dumps({"blocked": True,
                                      "reason": "identical call repeated — vary arguments or answer now"})
            elif echoed is not None:                                   # 95.40: an echoed request is not a command; nothing to
                outcome = echoed                                       # authorise, one failed attempt -- 95.60b: judged AFTER the
            else:                                                      # guards, so its third repetition is cut like any other
                from .receipts import close_for, open_for
                rid = open_for(engine, name, args, turn_seq)              # 71: the intended action is persisted FIRST
                outcome = engine.tools.execute_tool(name, args)
                close_for(engine, rid, name, args, outcome, classify_tool_result(outcome)[0])
            recent_signatures.append(sig)
            failed, summary = classify_tool_result(outcome)
            if name == "tool_search" and not failed:
                # 95.8: discovery -> the schema is put in front of the model for the REST of this turn.
                # `offered`/`schemas` were computed once and `tool_schemas` goes to the model on every
                # iteration, so a found tool was never offered and had to be called blind (X6: 2/3).
                # Availability only -- authority_guard still decides every call.
                try:
                    found = [r.get("name") for r in json.loads(outcome).get("results", [])]
                except (json.JSONDecodeError, ValueError, AttributeError):
                    found = []
                known = getattr(engine.tools, "schemas", {}) or {}
                added = [n for n in found if n in known and n not in offered]
                for n in added:
                    tool_schemas.append(known[n]); schemas[n] = known[n]; offered.add(n)
                if added:
                    engine._emit({"type": "tools_discovered", "names": added, "turn_seq": turn_seq})
            if failed:
                failure_counts[name] = failure_counts.get(name, 0) + 1
            try:
                blocked = bool(json.loads(outcome).get("blocked"))
            except (json.JSONDecodeError, ValueError, AttributeError):
                blocked = False
            engine._record_artifacts(name, outcome)
            if not failed and not blocked and name not in ("plan_task", "update_plan"):
                engine._turn_work = getattr(engine, "_turn_work", 0) + 1     # 69.2: evidence for update_plan(done)
            engine._emit({"type": "tool_result", "id": call_id, "name": name,
                          "result": outcome[:1200], "failed": failed,
                          "blocked": blocked, "turn_seq": turn_seq})
            tool_trace.append({"name": name, "arguments": args,
                               "result": outcome[:2000], "failed": failed,
                               "blocked": blocked,
                               "summary": summary, **({"alias": alias} if alias != name else {})})
            if native:
                messages.append({"role": "tool", "content": outcome[:8000]})
            else:
                messages.append({"role": "user",
                                 "content": f"[TOOL RESULT {name}]: {outcome[:8000]}"})
        # guard: no-progress — too many total failures → forced finalization
        if sum(failure_counts.values()) >= 4:
            break
    # forced finalization: one last call with tools disabled (never a dead placeholder)
    try:
        result = engine.registry.chat_for_role(
            "chat",
            messages + [{"role": "user",
                         "content": "Finalize now: give your best complete answer using what you have. Do not call tools."}],
            temperature=0.5, tools=None,
        )
        return result["content"], tool_trace, True
    except ProviderError as exc:
        return f"(provider error during finalization: {exc})", tool_trace, True
