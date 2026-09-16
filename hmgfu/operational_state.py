"""93.D — what is actually in force this turn, compiled from the sources that already hold it.

Operational self-knowledge, in the guide's sense: knowledge of the VERIFIED state, not a monologue
and not a second model call. The real conversation of 2026-09-11 is full of the gap this fills — the
assistant removed a directive and then said no directive had changed, justified a plan it could not
see the status of, and reported having updated records nothing had recorded.

Three rules hold this together, and the tests exist for them rather than for the wording:

  * every line is read from a store at the moment it is built. Nothing is remembered from an earlier
    turn, so a stale snapshot cannot outlive the effect that invalidated it;
  * a source that cannot be read says so. "No access" is a true statement about the state; silence
    reads as "nothing there", which is a different claim and often a false one;
  * the block is DESCRIPTIVE. It names what is in force and what is waiting; it authorises nothing,
    and a question answered from it is not a permission to act.
"""
from __future__ import annotations

from typing import Optional

HEADER = "=== WHAT IS IN FORCE RIGHT NOW (verified state, not a memory of it) ==="
NO_ACCESS = "unavailable (say so if asked; do not guess)"


def _directives(engine) -> str:
    try:
        rows = engine.directives.active()
    except Exception:
        return NO_ACCESS
    if not rows:
        return "none"
    out = []
    for d in rows:
        line = f"{d['kind']}={d.get('value')!r}"
        if d.get("condition"):
            line += f" unless {d['condition']}"
        out.append(line)
    return "; ".join(out)


def _plan(engine, session_id: str) -> str:
    store = getattr(engine, "session_plans", None)
    if store is None:
        return NO_ACCESS
    try:
        pending = store.pending(session_id)
        if pending is not None:
            return f"a plan is PROPOSED and waiting for the user: {pending.get('title')!r}"
        plan = store.resumable(session_id)
    except Exception:
        return NO_ACCESS
    if not plan:
        return "none"
    steps = plan.get("steps") or []
    done = sum(1 for s in steps if s.get("status") == "done")
    return f"{plan.get('title')!r} ({plan.get('status')}, {done}/{len(steps)} steps done)"


def _question(engine, session_id: str) -> str:
    """The learning question this session is waiting on — and WHO it is addressed to."""
    try:
        from .session_plans import competing_question
        case = competing_question(engine, session_id)
    except Exception:
        return NO_ACCESS
    if not case:
        return "none"
    return (f"you asked the user {case.get('question')!r} and their answer is still outstanding — "
            f"a bare yes/no this turn answers THAT, nothing else")


def _describe(ops) -> str:
    return "; ".join(f"{o.get('op')} {o.get('target')}" for o in list(ops)[:8])


def _last_effects(engine, session_id: str) -> tuple:
    """(what THIS conversation changed, what another one did) - from the transaction summary.

    93.R2: the record used to be one list on the engine, which serves every session, so an operation
    performed in session A was printed in B's block as something B's previous turn had done. Both
    halves are kept: an effect from elsewhere is real and often still in force (a directive is
    global), so it is shown -- but labelled with where it came from, never claimed as work done here."""
    record = getattr(engine, "_turn_operations_by_session", None)
    if record is None:                      # a caller that never named a session: pre-93.R2 behaviour
        ops = list(getattr(engine, "_turn_operations", []) or [])
        return (_describe(ops) if ops else "nothing", "")
    mine = record.get(session_id) or {}
    others = [(sid, entry) for sid, entry in record.items()
              if sid != session_id and entry.get("ops")]
    here = _describe(mine.get("ops") or []) if mine.get("ops") else "nothing"
    elsewhere = ""
    if others:
        sid, entry = others[-1]
        elsewhere = (f"{_describe(entry['ops'])} — done in ANOTHER conversation "
                     f"(session {sid}, turn {entry.get('turn_seq')}), not by you here")
    return here, elsewhere


def _recall(engine) -> str:
    """93.Q3: which of the four recall states this turn is in, said so the reply cannot turn an empty
    CONTEXT into an empty MEMORY. Read from what the turn already knows -- the router's own
    `needs_memory`, whether a search ran, and whether the tool worked."""
    marks = getattr(engine, "_turn_recall", None)
    if not marks:
        return ""
    from .recall_state import describe, recall_state, should_search
    state = recall_state(**marks)
    tail = " A focused search is warranted before saying anything about what is stored." \
        if should_search(state) else ""
    return f"{state} -- {describe(state)}.{tail}"


def state_block(engine, session_id: str) -> str:
    """The compact block for the system prompt, or "" when there is genuinely nothing to say."""
    here, elsewhere = _last_effects(engine, session_id)
    rows = [("standing directives", _directives(engine)),
            ("plan", _plan(engine, session_id)),
            ("question you are waiting on", _question(engine, session_id)),
            ("changed by the previous turn in this conversation", here)]
    recall = _recall(engine)
    if recall:
        rows.append(("what the retrieved memories cover", recall))
    # 95.78 (D4): WHICH file each app on the canvas is showing. Without it the agent inspected a file
    # of the same subject from twelve days earlier and explained that one to the user.
    from .app_errors import session_app_files
    shown = session_app_files(engine, session_id)
    if shown:
        rows.append(("apps on this canvas (the files they show)", ", ".join(shown[:6])))
    # 95.75 (P6): what an app on this canvas reported while it RAN. It is state of the session, seen by
    # the system rather than told by the user, so it travels with the rest of the state, pinned once.
    from .app_errors import app_error_block
    reported = app_error_block(engine, session_id)
    if elsewhere:
        rows.append(("changed elsewhere, still in force", elsewhere))
    if all(v in ("none", "nothing") for _k, v in rows) and not reported:
        return ""
    lines = [HEADER] + [f"- {k}: {v}" for k, v in rows]
    if reported:
        lines.append(reported)
    lines.append("- This block DESCRIBES the state; it authorises nothing. If asked what you did or "
                 "what is in force, answer from it, and say plainly when something is unavailable.")
    return "\n".join(lines)


def record_operations(engine, transactions: Optional[dict], session_id: str = "",
                      turn_seq: int = 0) -> None:
    """Keep this turn's real operations, WITH the session and turn that performed them.

    Without `session_id` the pre-93.R2 single-slot behaviour is kept, so an existing caller does not
    silently change meaning; with one, the record is per session and a later turn of the same session
    replaces its earlier entry."""
    ops = list((transactions or {}).get("operations") or [])
    engine._turn_operations = ops
    if not session_id:
        return
    record = getattr(engine, "_turn_operations_by_session", None)
    if record is None:
        record = engine._turn_operations_by_session = {}
    record[session_id] = {"ops": ops, "turn_seq": turn_seq}
