"""Session plans (Phase 67.3) — a plan is a SESSION object, not a turn object.

Lifecycle: proposed → approved → active → done | abandoned. A proposal ends the turn with a question;
the next turn's approval ("yes" / "sim") activates it; an active plan is PINNED at the top of the system
prompt (never compressed) and survives reconnects and restarts because it lives in a table, not in
memory recall. One execution path (the agent tool loop) — no second worker universe (docs/LONG_EXECUTION.md).
"""

from __future__ import annotations

import logging

import json
import os
import re
import sqlite3
import threading
from typing import List, Optional

from . import config
from .db import connect as db_connect
from .models import now_iso

log = logging.getLogger("hmgfu.session_plans")

STATUSES = ("proposed", "approved", "active", "done", "partial", "failed", "abandoned")
# "yes" | "yes, go ahead" | "sim, podes avançar" | "ok do it please" — one or two approval phrases, nothing else
_YES_WORD = r"(?:yes|yeah|yep|yup|sure|ok(?:ay)?|sim|claro|certo)"
_YES_ACT = (r"(?:go ahead(?: and do it)?|do it|please do|proceed|go(?: on)?|pode(?:s)?(?:\s+(?:avan[cç]ar|continuar|"
            r"fazer|seguir))?|faz|avan[cç]a|for[cç]a|vai|continua|segue)")
_YES = re.compile(r"^\s*(?:(?P<w>" + _YES_WORD + r")\b[\s,!.]*)?(?:(?P<a>" + _YES_ACT + r")\b)?[\s!.,]*"
                  r"(?:please|por favor)?[\s!.]*$", re.IGNORECASE)
_CANCEL_EXPLICIT = re.compile(r"\b(?:cancel|abort|abandon|drop|cancela|aborta|abandona)\s+(?:\w+\s+){0,3}?"
                              r"(?:work|task|plan|steps?|trabalho|tarefa|plano|etapas?)\b", re.IGNORECASE)
_CANCEL = re.compile(r"^\s*(?:stop|para|p[aá]ra|chega|cancel|abort|cancela|aborta)\b|"
                     r"\b(?:cancel|abort|abandon|drop|forget)\s+(?:the\s+|that\s+|this\s+|any\s+|all\s+)?"
                     r"(?:remaining\s+|unfinished\s+|current\s+)?(?:work|task|plan|it|steps?|that|this)\b|"
                     r"\b(?:cancela|aborta|abandona|desiste)\b|"
                     r"\b(?:j[a\u00e1] n[a\u00e3]o (?:[e\u00e9] )?preciso|j[a\u00e1] n[a\u00e3]o (?:[e\u00e9] )?necess[a\u00e1]rio|no longer (?:needed|necessary)|not needed any ?more|"
                     r"deixa (?:l[a\u00e1]|estar|isso)|never mind|forget it)\b", re.IGNORECASE)   # 95.71: a stated end of need cancels
from .value_gate import _OPENER as _DISCOURSE_OPENER          # X7a: "Afinal nao, deixa estar" declines behind an opener
_NO = re.compile(r"^\s*(?:(?:" + _DISCOURSE_OPENER + r"|afinal|na verdade|hmm|hum|pensando melhor|pensando bem|bem pensado|afinal de contas|"
                 r"on second thought|thinking about it|second thoughts)\b[,\s]+)?"     # 95.53: reconsideration openers
                 r"(?:no|nope|not now|don'?t|do not|stop|cancel|later|n[aã]o|agora n[aã]o|deixa|cancela)\b",
                 re.IGNORECASE)


_CONTINUE = re.compile(r"^\s*(?:continue|go on|carry on|keep going|next|proceed|resume|finish(?: it)?|"
                       r"continua|segue|prossegue|avan[cç]a|pr[oó]ximo|termina)\b[\s!.]*$", re.IGNORECASE)


def is_continuation(text: str) -> bool:
    """'continue' / 'next' / 'segue' — the user asks for the ACTIVE plan to move, nothing else."""
    return bool(_CONTINUE.match((text or "").strip()))


def authorization_record(origin: str, message: str, turn_seq: int) -> dict:
    """70.4 (M1.2): authority is a RECORD bound to the plan — who granted it, with which words, on which turn."""
    return {"origin": origin, "message": (message or "")[:200], "turn_seq": int(turn_seq or 0), "at": now_iso()}


def is_authorized(plan: Optional[dict]) -> bool:
    return bool(plan and isinstance(plan.get("authorization"), dict) and plan["authorization"].get("origin"))


def approval_signal(text: str, pending: bool) -> Optional[str]:
    """'yes' | 'no' | None — deterministic, only meaningful while a proposal is pending."""
    if not pending:
        return None
    t = (text or "").strip()
    if len(t) > 60:
        return None                       # a long message is new instruction, not a bare answer
    m = _YES.match(t)
    if m and (m.group("w") or m.group("a")):
        return "yes"
    if _NO.match(t):
        return "no"
    return None


class SessionPlanStore:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = db_connect(db_path or config.DB_PATH)
        self._db.execute("CREATE TABLE IF NOT EXISTS session_plans (session_id TEXT PRIMARY KEY, plan TEXT, "
                         "status TEXT, updated_at TEXT)")
        self._db.commit()

    def save(self, session_id: str, plan: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO session_plans VALUES (?, ?, ?, ?)",
                             (session_id, json.dumps(plan), plan.get("status", "active"), now_iso()))
            self._db.commit()

    def get(self, session_id: str) -> Optional[dict]:
        with self._lock:
            row = self._db.execute("SELECT plan FROM session_plans WHERE session_id=?", (session_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def pending(self, session_id: str) -> Optional[dict]:
        p = self.get(session_id)
        return p if p and p.get("status") == "proposed" else None

    def resumable(self, session_id: str) -> Optional[dict]:
        p = self.get(session_id)
        return p if p and p.get("status") in ("approved", "active") else None

    def set_status(self, session_id: str, status: str, reason: str = "") -> Optional[dict]:
        p = self.get(session_id)
        if not p:
            return None
        p["status"] = status
        if reason:
            p["reason"] = reason[:200]
        if status == "active" and not any(s["status"] == "active" for s in p["steps"]):
            nxt = next((s for s in p["steps"] if s["status"] == "pending"), None)
            if nxt is not None:
                nxt["status"] = "active"
        self.save(session_id, p)
        return p


def finalize_status(plan: dict) -> str:
    """The status a plan should be persisted with at the end of a turn."""
    if plan.get("status") in ("proposed", "abandoned"):
        return plan["status"]
    steps = plan.get("steps", [])
    # 94.3b: a REJECTED step is scope the user asked for that nothing executed. A plan holding one can
    # never be "done", however well the rest went -- otherwise a REDUCED request reports success: four
    # asked, two unworkable, two completed, "done". It reports partial, and says which.
    rejected = [s for s in steps if s["status"] == "rejected"]
    settled = [s for s in steps if s["status"] in ("done", "failed", "rejected")]
    if steps and len(settled) == len(steps):
        if all(s["status"] == "failed" for s in steps):
            return "failed"                                          # 69.2: all failed is not done
        if rejected or any(s["status"] == "failed" for s in steps):
            return "partial"                                         # 71.3: done+failed is not done
        return "done"
    return "active"


def pinned_block(plan: dict, unknown: Optional[List[dict]] = None) -> str:
    """The pinned plan block — the model's single source of truth for 'where are we'."""
    marks = {"done": "[x]", "failed": "[!]", "active": "[>]", "pending": "[ ]",
             "rejected": "[rejected: not executed]"}   # 94.3b: declared, not hidden
    lines = [f"=== PINNED PLAN ({plan.get('status', 'active').upper()}): {plan.get('title', 'Task plan')} ==="]
    for r in (unknown or [])[:6]:   # 71.4: actions whose outcome a crash left unknown — verify before repeating
        lines.append(f"[?] UNKNOWN OUTCOME: {r.get('tool')} {json.dumps(r.get('args') or {})[:80]} (receipt {r.get('id')}) "
                     "— verify the world (list_files/read_file) before repeating it")
    rec = plan.get("authorization") if isinstance(plan.get("authorization"), dict) else None
    if plan.get("status") not in ("proposed", "abandoned"):
        lines.append("Authorization: " + (f"{rec['origin']} — \"{rec.get('message', '')[:80]}\"" if rec else
                                          "NONE ON RECORD — this plan was never approved by the user; run NO tool with an "
                                          "effect for it; ask the user to confirm first."))
    for i, s in enumerate(plan.get("steps", [])):
        note = f"  — {s['note']}" if s.get("note") else ""
        lines.append(f"{marks.get(s['status'], '[ ]')} {i}. {s['text']}{note}")
    if plan.get("status") == "proposed":
        lines.append("This plan is PROPOSED and awaits the user's approval. Do NOT execute it; if the user's "
                     "message is not an approval, answer them and keep the proposal pending.")
    else:
        lines.append("Continue THIS plan from the [>] step: use tools, call update_plan as each step completes, "
                     "and do not restart from step 0. The user approved it; no further permission is needed.")
    return "\n".join(lines)


def propose(engine, session_id: str, title: str, steps: List[str], shown: str = "") -> dict:
    """94.4: `shown` is the proposal the USER actually read. The steps can come from tool calls the
    model attempted and had blocked (`saydo.enforce`), and when the reply proposes one thing while the
    attempt reaches for another, a "yes" lands on the attempt. Recording what was delivered is what
    lets the approval be checked against it. Optional, so plans persisted before this still load."""
    plan = {"title": title[:80], "status": "proposed",
            "steps": [{"text": s, "status": "pending"} for s in steps[:12]]}
    if shown:
        plan["proposed_as"] = " ".join(str(shown).split())[:600]
    shown = getattr(engine, "_turn_runbooks_shown", None) or []
    if shown:
        plan["runbook_hint"] = shown[0]               # 75.1: the runbook offered when this plan was proposed
    request = " ".join((getattr(engine, "_turn_user_message", "") or "").split())[:300]
    if request:
        plan["request"] = request                     # 75.1b: the user's own words that produced this plan
    if getattr(engine, "_turn_bandit", None):
        plan["bandit"] = list(engine._turn_bandit)    # 75.5: the (site, arm) chosen this turn — rewarded on finalize
    engine.session_plans.save(session_id, plan)
    engine._turn_plan = None                      # a proposal is not executed this turn
    engine._turn_proposed = True                  # the harness makes sure the reply ASKS (saydo.enforce)
    engine._emit({"type": "plan", "plan": plan})
    return plan


AMBIGUOUS_APPROVAL = (
    "=== WHICH ONE? === Two things are waiting for this answer: the plan \"{plan}\" and the question "
    "\"{question}\". A bare yes or no does not say which, so NOTHING was approved, declined, stored or "
    "executed. Ask the user which one they meant, in one short sentence, and do nothing else this turn.")


def competing_question(engine, session_id: str):
    """A learning question DELIVERED to this session and still waiting, or None.

    None covers every case where there is no second addressee: the protocol off (no table at all), a
    question that was never delivered, and a question belonging to another session."""
    store = getattr(engine, "session_plans", None)
    conn = getattr(store, "_db", None)
    if conn is None:
        return None
    try:
        from .learning_state import LearningState, _db_path_of
        state = LearningState(_db_path_of(conn), create=False)
        try:
            case = state.active_question(session_id)
        finally:
            state.close()
    except Exception:
        return None
    if not case or not case.get("question_delivered") or not case.get("question"):
        return None
    return case


def _shown_describes_steps(plan: dict) -> bool:
    """Can the step this approval would run be recognised in the proposal the user actually read?

    94.4: only plans that recorded `proposed_as` are checked, so anything persisted before this keeps
    approving exactly as it did (Rule 11). The test is deliberately generous -- a step is described if
    the shown text carries its ACTION or its TARGET -- because the reply is prose and the step is a
    tool call. What it catches is the case that actually happened, where the two share nothing: a
    reply offering a Python script against a step that creates a widget."""
    shown = " ".join(str(plan.get("proposed_as") or "").split()).casefold()
    if not shown:
        return True
    for step in plan.get("steps") or []:
        text = str(step.get("text") or "")
        action, _, target = text.partition(":")
        words = [w for w in re.findall(r"[^\W_]{4,}", action.casefold(), re.UNICODE)]
        words += [w for w in re.findall(r"[^\W_]{4,}", target.casefold(), re.UNICODE)]
        if words and any(w in shown for w in words):
            return True
    return not (plan.get("steps") or [])


def begin_turn(engine, session_id: str, user_message: str) -> str:
    """Start-of-turn plan logic. Returns the pinned block ('' if none). Approval of a pending proposal
    activates it; a decline abandons it; an approved/active plan resumes (restart-safe: from the table)."""
    store = engine.session_plans
    pending = store.pending(session_id)
    signal = approval_signal(user_message, pending is not None)
    # 75.1e: a bare continuation word ("continue", "next", "resume", "prossegue") answers the question a PROPOSAL just
    # asked — it is that proposal's yes. Only here: an unapproved RESUMED plan still needs an explicit yes (70.4).
    if pending is not None and signal in ("yes", "no"):
        # 93.A: one word, two possible addressees. The guide is explicit that ambiguity between
        # pendings asks and executes nothing, so neither the plan nor the question is consumed.
        rival = competing_question(engine, session_id)
        if rival is not None:
            return AMBIGUOUS_APPROVAL.format(plan=(pending.get("title") or "the proposed plan"),
                                             question=rival.get("question"))
    if pending is not None and signal == "yes" and not _shown_describes_steps(pending):
        # 94.4: the delivered proposal does not describe the step this yes would run. The user read
        # "a Python script" and the plan holds "create_widget". Asking costs one question; executing
        # costs an effect nobody authorised, so the mismatch asks and the plan stays proposed.
        step = next((st["text"] for st in pending.get("steps") or []), pending.get("title", ""))
        return (f"=== APPROVAL DOES NOT MATCH THE PROPOSAL === You asked the user: "
                f"{pending.get('proposed_as', '')[:200]} — but the plan on file would run {step!r}. "
                f"Do not run it. Ask which of the two they meant, in one short question.")
    if pending is not None and (signal == "yes" or (signal is None and is_continuation(user_message))):
        plan = store.set_status(session_id, "active")
        plan["authorization"] = authorization_record("user_approval", user_message, getattr(engine, "_turn_seq", 0))
        store.save(session_id, plan)             # 70.4: the USER approved it — a record, not a boolean
        engine._turn_plan = plan
        engine._emit({"type": "plan_update", "plan": plan})
        return pinned_block(plan) + "\nThe user just APPROVED this plan: execute it now, step by step."
    if pending is not None and signal == "no":
        plan = store.set_status(session_id, "abandoned", reason=user_message[:120])
        engine._emit({"type": "plan_update", "plan": plan})
        return ("=== PLAN DECLINED === The user declined the proposed plan; acknowledge briefly and do NOT "
                "execute it or re-propose it unless asked.")
    if pending is not None:
        return pinned_block(pending)
    plan = store.resumable(session_id)
    text = (user_message or "").strip()
    if plan is not None and (_CANCEL.search(text[:240]) or _CANCEL_EXPLICIT.search(text)):   # 70.5: no length cap
        # 69.2: "Stop. Cancel the remaining work." ABANDONS an active plan (not only a pending proposal)
        plan = store.set_status(session_id, "abandoned", reason=user_message[:120])
        engine._turn_plan = None
        engine._turn_step_tools = []
        if getattr(engine, "receipts", None) is not None:
            engine.receipts.cancel_pending(session_id)      # 71.4: cancellation revokes intended actions too
        engine._emit({"type": "plan_update", "plan": plan})
        return ("=== PLAN CANCELLED === The user cancelled the active plan; acknowledge briefly, run no further "
                "steps or tools for it, and do not re-propose it unless asked.")
    if plan is not None and not is_authorized(plan) and approval_signal(user_message, True) == "yes":
        # 70.4: an UNAPPROVED resumed plan (legacy boolean, or model-declared) becomes approved only by the user's yes
        plan["authorization"] = authorization_record("user_approval", user_message, getattr(engine, "_turn_seq", 0))
        store.save(session_id, plan)
        engine._turn_plan = plan
        engine._emit({"type": "plan_update", "plan": plan})
        return pinned_block(plan) + "\nThe user just APPROVED this plan: execute it now, step by step."
    if plan is not None:
        engine._turn_plan = plan                  # 70.4: resume PRESERVES the authorization record — never mints one
        engine._emit({"type": "plan_update", "plan": plan})
        unknown = engine.receipts.pending(session_id) if getattr(engine, "receipts", None) is not None else []
        return pinned_block(plan, unknown)
    return ""


def end_turn(engine, session_id: str, tool_trace, forced_finalization: bool) -> None:
    """Persist the turn's plan with its honest status. Unfinished steps auto-complete only when the turn
    truly finished (no failed tool, no forced finalization); otherwise they stay active and re-pin next turn."""
    plan = engine._turn_plan
    if not plan:
        return
    any_failed = any(t.get("failed") for t in tool_trace)
    used = {t["name"] for t in tool_trace if not t.get("blocked") and not t.get("failed")
            and t.get("name") not in _PLAN_TOOLS}
    plan["tools_used"] = sorted(set(plan.get("tools_used", [])) | used)     # 67.15: the plan's own evidence
    active = next((s for s in plan["steps"] if s["status"] == "active"), None)
    # 71.3 (M2): the SAME verifier as update_plan — the step's post-condition must hold in the world, backed by an
    # unconsumed receipt; a receipt consumed by one step never completes another
    from .receipts import verify_for
    ok, evidence, _missing = verify_for(engine, active.get("text", "")) if active is not None else (False, [], [])
    if ok and not any_failed and not forced_finalization:          # verified work, and the turn finished
        if active is not None:
            active["status"] = "done"
            active["evidence"] = evidence
            engine.receipts.consume(evidence, plan["steps"].index(active))
        nxt = next((s for s in plan["steps"] if s["status"] == "pending"), None)
        if nxt is not None:
            nxt["status"] = "active"
    elif not any(s["status"] == "active" for s in plan["steps"]):
        nxt = next((s for s in plan["steps"] if s["status"] == "pending"), None)
        if nxt is not None:
            nxt["status"] = "active"
    plan["status"] = finalize_status(plan)
    if plan["status"] in ("done", "partial", "failed"):
        from .runbooks import on_plan_finalized          # 75.1: an executed plan leaves a runbook
        try:
            on_plan_finalized(engine, session_id, plan)
        except Exception as exc:                          # procedural memory never breaks the turn
            log.warning("runbook derivation failed (non-fatal): %s", exc)
    engine.session_plans.save(session_id, plan)
    engine._emit({"type": "plan_update", "plan": plan})


_PLAN_TOOLS = {"plan_task", "update_plan"}


def step_evidence(step: Optional[dict], tool_trace, tool_names) -> bool:
    """69.2: did an EXECUTED tool this turn fit `step`? Named tool when the step names one; otherwise any
    non-plan, non-read-only tool. Reads (memory_*, read_file) never complete a step."""
    from .authority import PLAN_TOOLS, READ_ONLY_TOOLS
    executed = [t for t in tool_trace if not t.get("blocked") and not t.get("failed")]
    if not executed:
        return False
    named = tools_for_step((step or {}).get("text", ""), tool_names) if step else []
    from .receipts import postcondition, _same_file            # 82.4: ONE file matcher (directory-aware), shared with receipts
    files = postcondition((step or {}).get("text", ""), tool_names).get("files", [])
    if files:   # 71: a write is evidence only for the file the step names (b.txt does not verify a.txt; new/ is not old/)
        return any(t.get("name") == "write_file" and any(_same_file(f, str((t.get("arguments") or {}).get("path", ""))) for f in files)
                   for t in executed)
    if named:
        return any(t.get("name") in named for t in executed)
    return any(t.get("name") not in PLAN_TOOLS and t.get("name") not in READ_ONLY_TOOLS for t in executed)


def tools_for_step(step_text: str, tool_names) -> List[str]:
    """The tool(s) a plan step names: 'create_widget: Links' (harness proposals) or a step whose words contain
    every token of a tool name ('create the links widget' → create_widget). Never the plan tools."""
    text = (step_text or "").lower()
    names = [n for n in (tool_names or []) if n not in _PLAN_TOOLS]
    head = text.split(":", 1)[0].strip()
    if head in names:
        return [head]
    toks = set(re.findall(r"[a-z_]+", text))
    return [n for n in names if set(n.lower().split("_")) <= toks]


def current_step(plan: Optional[dict]) -> str:
    steps = (plan or {}).get("steps", [])
    nxt = next((s for s in steps if s.get("status") == "active"), None) \
        or next((s for s in steps if s.get("status") == "pending"), None)
    return (nxt or {}).get("text", "")


def ensure_step_tools(engine, plan: Optional[dict], tool_schemas: List[dict]) -> List[dict]:
    """67.12: while a plan is approved/active, the current step's tool is OFFERED (added to the schemas if the
    router did not pick it) and remembered in `engine._turn_step_tools` so the turn REQUIRES it."""
    known = list(getattr(engine.tools, "schemas", {}).keys())
    names = tools_for_step(current_step(plan), known) if plan else []
    if plan and not names:                                            # 67.15: a step that names no tool → the
        names = [n for n in plan.get("tools_used", []) if n in known]  # tools this plan already worked with
    engine._turn_step_tools = names
    offered = {t["name"] for t in tool_schemas}
    extra = [engine.tools.schemas[n] for n in names if n not in offered and n in engine.tools.schemas]
    return list(tool_schemas) + extra
