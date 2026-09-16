"""Per-turn UI event builders (extracted from agent.py at the 400-line ceiling, Phase 65)."""

from __future__ import annotations

from typing import List

from . import fu_math
from .taxonomy import category_of, node_class


def memory_items(retrieved) -> List[dict]:
    """The `memory_used` pill payload: what was recalled this turn (top 12)."""
    return [{"text": (r.point.summary or r.point.title or "")[:120], "id": r.point.id,
             "score": round(r.score, 3), "kind": r.point.type,
             "nodeClass": node_class(r.point), "category": category_of(r.point),
             "reason": r.reason} for r in retrieved[:12]]


def registry_of(engine):
    """The tool registry, or a stand-in with no schemas. 94.5: the pack reports what EXISTS as well as
    what was offered, and must not break a caller whose engine carries no registry."""
    return getattr(engine, "tools", None) or type("_None", (), {"schemas": {}})()


def emit_context_pack(engine, query, tool_schemas, turn_seq: int) -> None:
    """Phase 47 visibility: what ELSE this turn recalled beyond memories — the HMG-ranked tools/skills
    offered to the model (query-scored with the same memory_score as memories) + the active
    mandatory directives (always-on, unscored)."""
    _skills = engine.tools.skill_handlers
    _w = engine.weight_learner.weights()

    def _tool_entry(t):
        tp = engine._tool_point(t["name"])
        return {"name": t["name"],
                "score": round(fu_math.memory_score(query, tp, weights=_w), 2) if tp is not None else None}

    # 94.5: four states, not one. The pack used to show only what was OFFERED, so a turn where the
    # model said "I cannot do that" was indistinguishable from one where the capability did not exist.
    # REGISTERED is what the system has; OFFERED is what this turn put in front of the model; WITHHELD
    # is the difference, and it is the number that explains a refusal. AUTHORISED is per call and is
    # already on each receipt, so it is not duplicated here.
    offered = {t["name"] for t in tool_schemas}
    registered = sorted(getattr(registry_of(engine), "schemas", {}) or {})
    engine._emit({"type": "context_pack", "turn_seq": turn_seq,
                  "tools": [_tool_entry(t) for t in tool_schemas if t["name"] not in _skills],
                  "skills": [_tool_entry(t) for t in tool_schemas if t["name"] in _skills],
                  "registered": len(registered),
                  "withheld": sorted(n for n in registered if n not in offered),
                  "directives": [{"kind": d["kind"], "value": d["value"]}
                                 for d in engine.directives.active()]})
    # 95.10: the two stages before the protocol -- the router's own classification and the nano/router
    # fusion -- recorded by the sensitizer at merge_route time, emitted here, cleared here (one turn, one
    # trace). agent.py is at its ceiling; the trace module is where the trace belongs.
    trace = getattr(getattr(engine, "sensitizer", None), "_last_route_trace", None)
    if trace:
        engine._emit({"type": "router_raw", "turn_seq": turn_seq, "nano": trace["nano"], "router": trace["router"]})
        engine._emit({"type": "fusion", "turn_seq": turn_seq, "fused": trace["fused"]})
        engine.sensitizer._last_route_trace = None


def plan_turn_actions(engine, query, user_message: str, offered_names, retrieved):
    """Decide what this turn is allowed / required to do (65.2, 66.5, 66.6). Returns
    (requested_actions, forced_actions, retrieved)."""
    from .speech_act import is_suggestion, prohibits_effect, refers_to_self, requests_side_effect
    from .toolsys import SIDE_EFFECT_TOOLS
    memory_actions = {"memory_search", "memory_timeline", "memory_zoom"}
    low = user_message.lower()
    requested = [n for n in query.requested_tools if n in offered_names]
    if query.action_requested and not requested and offered_names:
        requested = offered_names[:1]
    # 66.5: the user's own standing tool rules ("always use brave for weather") are named tools
    rule_tools = engine.directives.tool_rules_for(user_message, offered_names)
    for n in rule_tools:
        if n not in requested:
            requested.append(n)
    named = [n for n in requested if n.lower() in low or n in rule_tools
             or n in (getattr(query, "explicit_tools", None) or [])]   # 95.47d: a named file/tool/enumeration NAMES its tool
    # 65.2: pure external actions drop autobiographical context — but never the user's tool rules
    if ((requested and not (set(requested) & memory_actions))
            or (query.extractor == "nano" and not query.needs_memory)) and not refers_to_self(user_message):
        retrieved = [r for r in retrieved if "_tool_rule" in r.point.keywords]
    forced = [n for n in requested                    # 95.37: on a QUESTION a tool is a means, never the required
              if n in named or (n not in memory_actions and not refers_to_self(user_message)      # action -- the
                                and query.conversation_act != "question"
                                and not getattr(query, "directive", None))]   # 95.55: a standing-rule turn asks for no tool

    for n in getattr(engine, "_turn_step_tools", []) or []:          # 67.12: the approved step's tool is required
        if n in offered_names and n not in forced:
            forced.append(n)
    # 66.6: side effects only when asked / router-requested / planned; questions get a short leash
    engine._turn_prohibited = prohibits_effect(user_message)                 # 70.5: prohibition is state
    engine._turn_effects_allowed = ((requests_side_effect(user_message)
                                     or bool(set(query.requested_tools) & SIDE_EFFECT_TOOLS))
                                    and not is_suggestion(user_message)        # 67: suggestions are proposed
                                    and not engine._turn_prohibited)           # 70.5: "do not create…" wins
    sens = getattr(engine, "sensitizer", None)                # 93.R4: whose pending question
    if sens is not None:
        sens._turn_session_id = getattr(engine, "_turn_session", "") or ""
    # 93.Q3: what the recall state is read from. `needs_memory` is the router's own judgement that the
    # context in front of it does not answer the turn; the rest is filled in as the turn runs.
    engine._turn_recall = {"needs_memory": bool(getattr(query, "needs_memory", False)),
                           "searched": False, "found": False, "tool_failed": False}
    engine._turn_unconfirmed_effects = []
    if getattr(engine, "tools", None) is not None:            # 93.R5: a new turn may search again
        from .recall_budget import budget_for
        budget_for(engine.tools).begin_turn()
    engine._turn_proposed = False
    engine._turn_work = 0
    engine._turn_iteration_cap = (engine.settings.get("question_max_iterations")
                                  if query.conversation_act == "question" and not named else None)
    if not engine._turn_effects_allowed:
        # 70.5 (M1.3): never FORCE a tool the authority boundary will block — a router pin or a learned tool point
        # must not push a side effect on a suggestion, question or prohibited turn
        from .authority import BUILTIN_EFFECTS
        schemas = getattr(getattr(engine, "tools", None), "schemas", {}) or {}
        def _declared(n):
            return (schemas.get(n) or {}).get("x-effect") or BUILTIN_EFFECTS.get(n) or "unknown"
        forced = [n for n in forced if _declared(n) not in ("write", "unknown")]   # 'shell' is judged per command
    return requested, forced, retrieved


def plan_enumerated_request(engine, user_message: str, tool_schemas, forced, pinned: str):
    """95.54b: an enumerated multi-request ("Dois pedidos. 1. ... 2. ...") is a plan of the turn's own, born by
    the harness through the plan tool's one handler (94.3b/95.4 validate each item in the user's words, so an
    item that describes no work is rejected in place whether or not the model ever calls plan_task -- X5 on v5
    wrote the file with the garbage item folded in, 4/4). The step's tool joins the offered and required tools
    (67.12) and the pinned block tells the model where it stands. A question list, a pending proposal or live
    plan, a prohibited turn, no plan tool: nothing is planned. Returns (pinned, tool_schemas, forced)."""
    from .plans import enumerated_items
    from .session_plans import ensure_step_tools, pinned_block
    from .speech_act import is_action_request
    items = enumerated_items(user_message or "")
    tools = getattr(engine, "tools", None)
    if (len(items) < 2 or not any(is_action_request(i) for i in items) or pinned or tools is None
            or getattr(engine, "_turn_plan", None) is not None or getattr(engine, "_turn_prohibited", False)
            or "plan_task" not in (getattr(tools, "schemas", {}) or {})):
        return pinned, tool_schemas, forced
    tools.execute_tool("plan_task", {"title": items[0][:60], "steps": items})
    sid = getattr(engine, "_turn_session", "") or ""
    plan = getattr(engine, "_turn_plan", None) or engine.session_plans.pending(sid)
    if plan is None:
        return pinned, tool_schemas, forced
    if getattr(engine, "_turn_plan", None) is not None and getattr(engine, "_turn_effects_allowed", False):
        tool_schemas = ensure_step_tools(engine, engine._turn_plan, tool_schemas)
        offered = {t.get("name") for t in tool_schemas}
        forced = list(forced) + [n for n in (getattr(engine, "_turn_step_tools", []) or []) if n in offered and n not in forced]
    return pinned_block(plan), tool_schemas, forced


def recent_window(engine, session_id: str, n: int) -> str:
    """67.4: the recall-only memory's guaranteed anaphora window — the last N turns of THIS session,
    verbatim (truncated), independent of retrieval. N=0 disables (the pre-Phase-67 behaviour)."""
    if not n or not session_id:
        return ""
    rows = engine.sessions.history(session_id, limit=2 * n)
    if not rows:
        return ""
    lines = ["", f"Recent conversation (last {min(n, len(rows) // 2 or 1)} turns, verbatim):"]
    for m in rows[-2 * n:]:
        who = "User" if m["role"] == "user" else "You"
        lines.append(f"{who}: {(m['content'] or '').strip()[:300]}")
    return "\n".join(lines)


def turn_response(engine, reply, sid, turn_seq, context, retrieved, retrieval_ms, tool_schemas, tool_trace,
                  finalized, runtime, grade, mini_report, timings=None) -> dict:
    """The agent_chat response (moved out of agent.py in 73.0; the contract is unchanged, `timings` added)."""
    return {
        "response": reply,
        "session_id": sid,
        "turn_seq": turn_seq,
        "injected_context": context,
        "retrieved": [r.public() for r in retrieved],
        "retrieval_ms": round(retrieval_ms, 1),
        "tools_offered": [t["name"] for t in tool_schemas],
        "tool_trace": tool_trace,
        "forced_finalization": finalized,
        "runtime_context": runtime.public(),
        "grade": grade,
        "mini_dream": mini_report.public() if mini_report else None,
        "stats": engine.graph.stats(),
        "timings": timings,
    }
