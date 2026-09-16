"""TurnPlan — execution progress as a first-class turn object (docs/LONG_EXECUTION.md).

The model declares a plan (plan_task), marks steps as it works (update_plan); the UI's
PlanTracker card renders/updates from the plan/plan_update events; a declared plan EARNS
an extended iteration budget. Per-session turn locks keep one-writer discipline (PA3).
"""

from __future__ import annotations

import json
import re
import threading
from typing import Dict, List, Optional

STEP_STATUSES = ("pending", "active", "done", "failed")
# models phrase statuses loosely (gemma live: "completed") — normalize, don't reject
_STATUS_SYNONYMS = {
    "done": "done", "completed": "done", "complete": "done", "finished": "done", "success": "done",
    "active": "active", "in_progress": "active", "working": "active", "started": "active",
    "current": "active", "failed": "failed", "failure": "failed", "error": "failed",
    "pending": "pending", "todo": "pending", "waiting": "pending", "blocked": "failed", "skipped": "failed",
    "in": "active", "progress": "active", "ongoing": "active",
}


# 95.75 (P1): a model that writes its plan as markdown ("[x] 0. Research…", "- 1. Write the file")
# had its own list markers stored AS the step text, and the statuses it declared were dropped. The
# label is the WORK; the status is the system's to settle from receipts, so the markers come off and
# the claim they carry is not honoured.
_STEP_MARKER = re.compile(r"^\s*(?:[-*+\u2022]\s+|\[\s*[xX>~v\u2713\u2717]?\s*\]\s*|\d{1,2}\s*[.)]\s+|#{1,6}\s+)")


def strip_step_markers(text: str) -> str:
    """The step's words, without the list/checkbox/number decoration a model puts in front of them."""
    out = (text or "").strip()
    for _ in range(4):                       # "- 1. Write" carries two markers; a handful is plenty
        stripped = _STEP_MARKER.sub("", out, count=1).strip()
        if stripped == out:
            break
        out = stripped
    return out or (text or "").strip()       # never normalise a step away entirely


def _step_text(step) -> str:
    """Steps arrive as strings OR dicts ({text}/{step}/{description}) — normalize."""
    if isinstance(step, dict):
        for key in ("text", "step", "description", "title", "name", "action", "task"):   # 95.4d: {"action": ...}
            if step.get(key):
                return strip_step_markers(str(step[key]))[:120]
        return ""
    return strip_step_markers(str(step))[:120]


_ENUM_ITEM = re.compile(r"(?:(?<=\s)|^)(\d{1,2})\s*[.)]\s+")


def enumerated_items(message: str) -> List[str]:
    """95.4: the user's own enumerated items ("1. write x. 2. 1234567890."), in order; [] when the
    message does not enumerate. Structural -- an ordinal marker followed by text -- so a step can be
    validated in the user's words rather than in the model's paraphrase of them."""
    text = (message or "").strip()
    marks = [m for m in _ENUM_ITEM.finditer(text)]
    if len(marks) < 2:
        return []
    nums = [int(m.group(1)) for m in marks]
    if nums != list(range(1, len(nums) + 1)):
        return []                                         # not a 1..n list ("in 2 days, 3 files")
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append(text[m.end():end].strip())
    return [o for o in out if o]


def _describes_work(text: str) -> bool:
    """Does this step name something to DO?

    94.3: `_step_text` turns anything into a step -- `str(1234567890)` is truthy -- and a real call
    arrived as `{"steps": [1234567890, "I will first research...", 2345678901, ...]}`. Step 0 became
    the literal "1234567890", no receipt could ever match it, and `update_plan` refused three times
    with a correct post-condition error. The plan could not be finished, and the user had to ask why.

    The test is not a list of phrases: a description of work contains a WORD. A bare number, an id or
    punctuation does not. Two letters is the smallest thing worth calling one, in any language."""
    import re
    return bool(re.search(r"[^\W\d_]{2,}", str(text or ""), re.UNICODE))


# 95.6/95.6b/95.6c: does this turn request work? The predicates every producer of a plan honours
# (plan_task here, the say-do promise and blocked-attempt paths). Moved from session_plans at its ceiling.
from .session_plans import approval_signal


def _idle(engine, session_id: str):
    """(message, True) when nothing is pending and no plan is live -- the state in which a turn can only
    clarify; (message, False) otherwise."""
    store = getattr(engine, "session_plans", None)
    pending = store.pending(session_id) if store is not None and hasattr(store, "pending") else None
    return (getattr(engine, "_turn_user_message", "") or ""), not pending and getattr(engine, "_turn_plan", None) is None


def confirmation_without_pending(engine, session_id: str) -> bool:
    """95.6/95.6b: 'yes'/'no' answer the delivered pending question and nothing else; with nothing pending
    they are a clarification, never authority to invent work (E8: the apology became a plan)."""
    msg, idle = _idle(engine, session_id)
    return idle and bool(approval_signal(msg, True))


def clarification_turn(engine, session_id: str) -> bool:
    """95.6c: a bare answer (95.6b) or a question that asks for no effect and suggests none requests no
    work -- the say-do gate proposes nothing on it (E8 rep1: "what are you working on?" turned the
    model's conditional promise into a proposed plan). plan_task keeps 95.6b only: an information
    request ("tell me a curious fact") is planned work."""
    from .speech_act import is_interrogative, is_suggestion, requests_side_effect
    msg, idle = _idle(engine, session_id)
    return idle and (bool(approval_signal(msg, True))
                     or (is_interrogative(msg) and not requests_side_effect(msg) and not is_suggestion(msg)))


PLAN_ITERATIONS_PER_STEP = 4
PLAN_ITERATIONS_CAP = 60

_session_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def session_lock(session_id: str) -> threading.Lock:
    with _locks_guard:
        if session_id not in _session_locks:
            _session_locks[session_id] = threading.Lock()
        return _session_locks[session_id]


def plan_action(engine, name: str, args: dict) -> dict:
    from .session_plans import authorization_record
    """Handle the plan_task / update_plan tools for the current turn."""
    if name == "plan_task":
        sid = getattr(engine, "_turn_session", None) or ""
        store = getattr(engine, "session_plans", None)
        live = store.resumable(sid) if (store is not None and sid) else None
        # 67.11: continue, do not re-plan -- but 93.B: that rule binds the MODEL, not the user. When the
        # current turn carries the user's own request, an explicit new task supersedes the old plan, and
        # the supersession is RECORDED with its reason and turn rather than dropped silently.
        from .authority import user_directly_requested
        from .session_plans import approval_signal, is_continuation
        msg = str(getattr(engine, "_turn_user_message", "") or "")
        # an approval or a continuation answers the CURRENT plan; only a fresh request switches task
        switching = (user_directly_requested(engine) and approval_signal(msg, True) != "yes"
                     and not is_continuation(msg))
        from .offers import adopt_declared_steps, is_placeholder
        if engine._turn_plan is not None and is_placeholder(engine._turn_plan) and not switching:
            # 95.78 (D2): the active plan is a placeholder the harness synthesised from the reply's
            # prose. The model is now declaring the real work for the SAME approved request — which is
            # exactly what it was refused for. Adopt it, keeping the approval the placeholder earned.
            declared = [t for t in (_step_text(x) for x in (args.get("steps") or [])) if t][:12]
            if declared:
                adopt_declared_steps(engine, sid, engine._turn_plan, declared)
                out = {"ok": True, "steps": len(declared), "adopted": True,
                       "hint": "the approved placeholder now holds your declared steps; work them and call update_plan"}
                out.update(step_recall(engine, declared[0]))
                return out
        if live is not None and engine._turn_plan is not None and not switching:
            nxt = next((s["text"] for s in live["steps"] if s["status"] in ("active", "pending")), "")
            return {"ok": True, "already_active": True, "title": live.get("title"), "steps": len(live["steps"]),
                    "hint": f"A plan is already ACTIVE and approved (pinned above) — do not start another. "
                            f"Continue with the current step: {nxt!r}; call update_plan as steps complete."}
        if live is not None and engine._turn_plan is not None and switching:
            sid = getattr(engine, "_turn_session", None) or ""
            reason = (f"superseded at turn {getattr(engine, '_turn_seq', 0)} by the user's own request: "
                      f"{str(getattr(engine, '_turn_user_message', ''))[:80]}")
            store.set_status(sid, "superseded", reason=reason)
            engine._turn_plan = None
            engine._turn_step_tools = []
            engine._emit({"type": "plan_update", "superseded": live.get("title"), "reason": reason})
        # 95.6: "yes" / "no" answer the delivered pending question and nothing else. With nothing
        # pending they are a clarification, not authority to invent work -- the pilot and L1 rep3 saw
        # the model's apology for having nothing pending become a PROPOSED plan whose step was the apology.
        if confirmation_without_pending(engine, getattr(engine, "_turn_session", None) or ""):   # not the question clause: an information request is planned work
            return {"error": "nothing is pending to confirm or refuse -- ask the user what they want "
                             "done instead of proposing a plan"}
        raw_steps = args.get("steps")
        if not raw_steps:                                   # 71.7: models drift on the arg name (tasks/plan/items/actions)
            raw_steps = next((args[k] for k in ("tasks", "plan", "items", "actions", "subtasks", "step_list") if args.get(k)), None)
        if isinstance(raw_steps, str):   # some models pass a JSON/CSV string
            try:
                raw_steps = json.loads(raw_steps)
            except (ValueError, TypeError):
                raw_steps = [s for s in raw_steps.split("\n") if s.strip()]
        candidates = [t for t in (_step_text(s) for s in (raw_steps or [])) if t]
        # 94.3b: an entry that describes no work is REJECTED IN PLACE, never dropped. Dropping
        # renumbered everything after it, and `receipts.consume(ids, step_index)` binds a receipt to
        # an INDEX -- so a receipt recorded against index 2 would have certified a different step.
        # Dropping also let a REDUCED request finish as "done": four asked, two silently removed, two
        # completed, plan reports done. Keeping the entry preserves both the index and the scope.
        # 95.4: validate each step in the USER's words when the message enumerates them one-to-one.
        # X3 3/3 and E5 4/6: the model paraphrased "1234567890" into "acknowledge the numeric
        # sequence", which describes work, so 94.3b's rejection never saw the item that describes none.
        items = enumerated_items(getattr(engine, "_turn_user_message", "") or "")
        if items and 0 < len(candidates) < len(items):    # 95.4c: a dropped item is scope, not a simplification
            return {"error": f"the request enumerates {len(items)} items and the plan declares {len(candidates)} "
                             "steps -- declare one step per item, in the user's order; an item you cannot do "
                             "still gets its entry (it is marked rejected, never dropped)"}
        judged = items if items and len(items) == len(candidates) else candidates
        rejected = [i for i, t in enumerate(judged) if not _describes_work(t)]
        workable = [t for i, t in enumerate(candidates) if i not in rejected]
        if not (1 <= len(workable) <= 12):
            return {"error": "plan_task needs 1\u201312 steps that each describe work"}
        steps = candidates
        dropped = [candidates[i] for i in rejected]
        # title is optional — models reliably give steps but often omit the title (synthesize it)
        title = (str(args.get("title", "")).strip()
                 or (steps[0][:60] if len(steps) == 1 else "Task plan"))[:80]
        # 67.3: ask first, execute on approval. 67.10: on a turn where side effects are not allowed (a
        # SUGGESTION, no approved plan) the harness forces the proposal — the model cannot re-open the
        # gate by declaring an "active" plan around the side effect.
        from .speech_act import is_suggestion
        forced = (is_suggestion(getattr(engine, "_turn_user_message", ""))
                  and not getattr(engine, "_turn_effects_allowed", True)
                  and getattr(engine, "_turn_plan", None) is None)
        if forced or str(args.get("status", "")).lower() == "proposed":
            from .session_plans import propose
            sid = getattr(engine, "_turn_session", None) or ""
            propose(engine, sid, str(args.get("title") or steps[0][:60]), steps)
            out = {"ok": True, "proposed": True, "steps": len(steps),
                   "hint": "The plan is PROPOSED. Ask the user to confirm (yes/no) and STOP — do not execute now."}
            if dropped:
                out["rejected_steps"] = dropped
                out["hint"] += (f" {len(dropped)} entr{'y' if len(dropped) == 1 else 'ies'} "
                                f"({dropped[:3]}) describe no work and are marked rejected.")
            return out
        first_workable = next((i for i in range(len(steps)) if i not in rejected), None)
        engine._turn_plan = {
            "title": title,
            "steps": [({"text": t, "status": "rejected",
                        "note": "describes no work, so no receipt can ever prove it"}
                       if i in rejected else
                       {"text": t, "status": "active" if i == first_workable else "pending"})
                      for i, t in enumerate(steps)],
            # 69.1 → 70.4: a plan the MODEL declares carries only the authority the turn already had — as a RECORD
            "authorization": (authorization_record("user_request", getattr(engine, "_turn_user_message", ""),
                                                   getattr(engine, "_turn_seq", 0))
                              if getattr(engine, "_turn_effects_allowed", False) and not getattr(engine, "_turn_prohibited", False)
                              else None),
        }
        engine._emit({"type": "plan", "plan": engine._turn_plan})
        out = {"ok": True, "steps": len(steps),
               "hint": "work the steps; call update_plan as each completes"}
        if dropped:
            # 94.3: a step that describes no work can never earn a receipt, so keeping it would make
            # the plan impossible to finish. Say which ones went, rather than leave a silent gap.
            out["rejected_steps"] = dropped
            out["hint"] += (f"; {len(dropped)} entr{'y' if len(dropped) == 1 else 'ies'} "
                            f"({dropped[:3]}) describe no work and are marked rejected -- they keep "
                            f"their position, and this plan cannot report done while they are there")
        out.update(step_recall(engine, steps[0]))                       # 67.9 self-instructed recall
        return out
    if name == "update_plan":
        plan = engine._turn_plan
        if plan is None:
            # 95.75 (P5): after the user's own request superseded the old plan, the model proposed a new
            # one and then tried to tick a step. "no active plan" sent it back to plan_task in a loop;
            # the plan is not missing, it is waiting for the user's yes.
            store = getattr(engine, "session_plans", None)
            sid = getattr(engine, "_turn_session", None) or ""
            proposed = (store.pending(sid) if (store is not None and sid) else None) or (
                {} if getattr(engine, "_turn_proposed", False) else None)
            if proposed is not None:
                return {"error": "the plan is PROPOSED and not yet approved — ask the user to confirm "
                                 "(yes/no) and stop; steps are updated only after the approval."}
            return {"error": "no active plan — call plan_task first"}
        # arg-drift tolerance (gemma live: "step_index"); no index = the current active step
        raw = next((args[k] for k in ("step", "step_index", "index", "step_number")
                    if args.get(k) is not None), None)
        if raw is None:
            raw = next((i for i, s in enumerate(plan["steps"]) if s["status"] == "active"), None)
        try:
            index = int(raw)
        except (TypeError, ValueError):
            return {"error": f"step must be 0..{len(plan['steps']) - 1}"}
        if not 0 <= index < len(plan["steps"]):   # L-05: negative index must NOT wrap to the last step
            return {"error": f"step must be 0..{len(plan['steps']) - 1}"}
        step = plan["steps"][index]
        raw_status = str(args.get("status", "done")).strip().lower()
        status = _STATUS_SYNONYMS.get(raw_status)
        if status is None:   # 71.7: "failed due to a permission error" → failed (the first known status word wins)
            for word in re.findall(r"[a-z_]+", raw_status):
                if word in _STATUS_SYNONYMS:
                    status = _STATUS_SYNONYMS[word]
                    if not args.get("note"):
                        args["note"] = raw_status[:160]
                    break
        if status is None:
            return {"error": f"status must be one of {STEP_STATUSES}"}
        if step.get("status") == "rejected":
            # 94.3b: it was never executable, so it cannot be completed or failed into silence
            return {"error": f"step {index} was rejected at plan time ({step.get('note', '')}). "
                             f"It describes no work, so it cannot be marked {status}. "
                             f"Re-plan with a step that says what to do, or leave the scope declared."}
        if status == "done":
            # 71.3 (M2): "done" is a CLAIM — the step's post-condition must hold in the WORLD, backed by an
            # unconsumed receipt (a read cannot certify a write; a.txt cannot certify b.txt)
            from .receipts import verify_for
            ok, evidence, missing = verify_for(engine, step.get("text", ""))
            if not ok:
                step["note"] = ("unverified: " + "; ".join(missing))[:160]
                # 95.75 (P7): the model read this as an authorisation gate ("the system blocked me… so I
                # can proceed legally") and asked for a yes the user had already given. Say what it is.
                return {"ok": False, "error": f"step {index} cannot be marked done — post-condition not met: "
                                              f"{'; '.join(missing)}. This is not a permission gate and no "
                                              f"approval is needed: do the work with a tool now, then call "
                                              f"update_plan."}
            step["evidence"] = evidence
            engine.receipts.consume(evidence, index)
            engine._turn_work = 0
        step["status"] = status
        if status == "active":
            # 95.75 (P4): the live plan ended with two active steps because marking one in progress never
            # released the previous one. The pinned plan then showed two "current" steps at once.
            for i, other in enumerate(plan["steps"]):
                if i != index and other.get("status") == "active":
                    other["status"] = "pending"
        if args.get("note"):
            step["note"] = str(args["note"])[:160]
        # auto-advance: first pending step becomes active
        if status in ("done", "failed"):
            nxt = next((s for s in plan["steps"] if s["status"] == "pending"), None)
            if nxt is not None:
                nxt["status"] = "active"
        engine._emit({"type": "plan_update", "plan": plan})
        done = sum(1 for s in plan["steps"] if s["status"] == "done")
        out = {"ok": True, "progress": f"{done}/{len(plan['steps'])}"}
        nxt_active = next((s for s in plan["steps"] if s["status"] == "active"), None)
        if nxt_active is not None and status in ("done", "failed"):
            out.update(step_recall(engine, nxt_active["text"]))         # 67.9: recall for the NEXT step
        return out
    return {"error": f"unknown plan action '{name}'"}


def step_recall(engine, step_text: str) -> dict:
    """67.9 self-instructed recall: when the agent picks up a plan step, the harness recalls memory for
    the STEP (not the user's sentence) and hands it back inside the tool result — the model's own plan
    triggers recall, exactly like a user message would."""
    try:
        if not engine.settings.get("plan_step_recall"):
            return {}
        _, retrieved, _ = engine.retrieve(step_text, limit=5)
    except Exception:
        return {}
    items = [(r.point.content[:160] if r.point.source in ("user", "user_explicit")     # 69.5: raw user words
              else (r.point.summary or r.point.title or r.point.content[:120])) for r in retrieved[:5]]
    if items:
        engine._emit({"type": "memory_used", "turn_seq": getattr(engine, "_turn_seq", 0), "count": len(items),
                      "items": [{"text": t[:120], "id": r.point.id, "score": round(r.score, 3), "kind": r.point.type,
                                 "reason": "plan step"} for t, r in zip(items, retrieved)], "source": "plan_step"})
    return {"memory_for_step": items} if items else {}


def iteration_budget(base: int, plan: Optional[dict]) -> int:
    """A declared plan EARNS a longer leash; unplanned turns keep the small budget."""
    if not plan:
        return base
    return min(max(base, PLAN_ITERATIONS_PER_STEP * len(plan["steps"])), PLAN_ITERATIONS_CAP)


PLAN_TOOLS: List[dict] = [
    {
        "name": "plan_task",
        "description": ("Declare a step-by-step plan BEFORE starting any multi-step task "
                        "(builds, research, refactors). The user sees a live progress tracker, "
                        "and you get a larger tool budget. 2-12 short steps. status='proposed' asks the "
                        "user for permission first (the plan waits for yes/no; nothing runs now)."),
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["active", "proposed"],
                       "description": "proposed = ask the user first; default active"},
            "title": {"type": "string", "description": "short task title"},
            "steps": {"type": "array", "items": {"type": "string"},
                      "description": "ordered step descriptions"},
        }, "required": ["title", "steps"]},
        # A plan is declared ONCE — re-calling plan_task instead of doing the work is the
        # runaway loop the user saw (~16 wasted model calls before finalization). After the
        # first success it is blocked; use update_plan to record progress and DO the steps.
        "x-max-successful-calls-per-turn": 1,
    },
    {
        "name": "update_plan",
        "description": "Mark a plan step done/active/failed as you work. Call it every time a step completes.",
        "parameters": {"type": "object", "properties": {
            "step": {"type": "integer", "description": "0-based step index"},
            "status": {"type": "string", "description": "done | active | failed"},
            "note": {"type": "string", "description": "optional short note"},
        }, "required": ["step", "status"]},
    },
]
