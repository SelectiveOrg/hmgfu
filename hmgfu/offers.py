"""95.78 (D1/D2) — an offer the assistant made, and the answer it is waiting for.

The harness registered a proposal only when the reply PROMISED in the first person ("I'll rewrite the
widget"). A reply that OFFERS the same work as a question ("Would you like me to rewrite the widget?")
registered nothing, so the user's "yes" had no addressee: planning was refused as unprompted, the model
asked again, and the user answered again. Grammar decided whether the user's answer counted.

What is registered is a PLACEHOLDER: the offer says what was agreed, not how it will be done. The
model's own `plan_task` on the approval turn replaces the placeholder steps with the declared work,
which is what it was trying to do when it was told a plan was already active.
"""

from __future__ import annotations

from typing import Optional

PLACEHOLDER = "synthesised"     # this plan's steps came from prose, not from a declared plan_task


def register_offer(engine, session_id: str, reply: str) -> bool:
    """True when this reply's closing offer became the pending proposal. False when it offers nothing,
    or when something is already pending — an offer never displaces a live proposal or plan."""
    from .speech_act import offers_to_act
    if not offers_to_act(reply):
        return False
    store = getattr(engine, "session_plans", None)
    if store is None or not session_id:
        return False
    if store.pending(session_id) is not None or getattr(engine, "_turn_plan", None) is not None:
        return False
    if hasattr(store, "resumable") and store.resumable(session_id) is not None:
        return False
    from .session_plans import propose
    offered = offer_sentence(reply) or (reply or "").strip()
    propose(engine, session_id, offered[:80], [offered[:120]], shown=reply)
    plan = store.get(session_id)
    if isinstance(plan, dict):
        plan[PLACEHOLDER] = True          # 95.78 (D2): prose stands in for the work until it is declared
        store.save(session_id, plan)
    return True


def offer_sentence(reply: str) -> Optional[str]:
    """The closing question that carries the offer, without the surrounding prose."""
    from .speech_act import last_question
    return last_question(reply)


def is_placeholder(plan: Optional[dict]) -> bool:
    """A plan whose steps the harness synthesised from prose. Its steps describe the agreement, never
    the work, so the first real declaration of steps for the same request supersedes them."""
    return bool(isinstance(plan, dict) and plan.get(PLACEHOLDER))


def adopt_declared_steps(engine, session_id: str, plan: dict, steps: list) -> dict:
    """Replace a placeholder's steps with the declared ones, keeping what the placeholder EARNED: the
    user's approval record, the request it came from, and what the user read when they approved."""
    plan["steps"] = [{"text": t, "status": "active" if i == 0 else "pending"} for i, t in enumerate(steps)]
    plan.pop(PLACEHOLDER, None)
    plan["status"] = "active"
    store = getattr(engine, "session_plans", None)
    if store is not None and session_id:
        store.save(session_id, plan)
    engine._emit({"type": "plan", "plan": plan})
    return plan

PROPOSAL_SUFFIX = "\n\nShall I go ahead with this? (yes / no)"


def proposal_suffix(steps) -> str:
    """94.4: name the action the yes would authorise, instead of "this".

    The harness builds a proposal from the tool calls the model ATTEMPTED and had blocked, while the
    user reads the reply. In session 5314a8a1 the reply offered to write a Python script, the plan on
    file was `create_widget: Valencia Weather Forecast`, and "yes" ran the widget. Naming the step in the
    question removes the mismatch instead of guessing afterwards whether prose describes a tool call.
    Moved here from saydo.py in 95.78: what the user reads when offered work belongs with offers."""
    named = [str(st).strip() for st in (steps or []) if str(st).strip()][:3]
    if not named:
        return PROPOSAL_SUFFIX
    listed = named[0] if len(named) == 1 else "; ".join(named)
    return f"\n\nShall I go ahead with: {listed}? (yes / no)"


def with_offer_registered(engine, session_id: str, turn_seq: int, decided):
    """The say-do decision, plus the two obligations that fall on the reply whatever the gate decided:
    what this turn OFFERED stays pending (95.78 D1), and what it SHIPPED is disclosed (95.78 D5).
    Both are orthogonal to the claim decision and neither overrides it."""
    reply, trace, report = decided
    report = report if isinstance(report, dict) else {}
    extra = {}
    from .artefacts import disclosure
    note = disclosure(engine, session_id, turn_seq)
    if note and note.strip() not in (reply or ""):
        reply = (reply or "").rstrip() + note
        extra = {"appended": ((report.get("appended") or "") + note), "shipped_placeholders": True}
    if register_offer(engine, session_id, reply):
        extra["offer_pending"] = True
    if not extra:
        return decided
    return reply, trace, {**report, "turn_seq": turn_seq, **extra}
