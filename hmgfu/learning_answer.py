"""93.P3 — recognising a bare answer to a question this session actually asked.

Authorised in terms by the standing goal: recognising a simple answer may be deterministic when the
pending case is unambiguous, and that never authorises a write without evidence nor a different task.
It is the last link of the clarification chain — the confirmation path writes the preserved proposal
end to end (v145), while the model keeps returning `memory_update: null` for a one-word turn.

No vocabulary is invented here. `approval_signal` already decides yes/no deterministically for plan
proposals, in both languages, and already refuses anything longer than a bare answer; this reuses it
and adds only the third answer a question can get — "maybe", which confirms nothing.

What comes out is a FEEDBACK and never a proposal. The write still comes from the proposal already on
the case, with the evidence it was given, so nothing here can authorise a fact nobody stated.
"""
from __future__ import annotations

import re
from typing import Optional

# the third answer: neither agreement nor refusal, and it must not be read as either
_MAYBE = re.compile(r"^\s*(?:maybe|perhaps|possibly|not sure|unsure|i think so|dunno|"
                    r"talvez|se calhar|possivelmente|n[aã]o sei|acho que sim)\b[\s!.,?]*$",
                    re.IGNORECASE)
_FEEDBACK = {"yes": "confirm", "no": "reject"}
_EMPTY = re.compile("")


def _signal(body: str):
    from .session_plans import approval_signal
    return approval_signal(body, True)


def simple_feedback(text: str, case: Optional[dict]) -> Optional[str]:
    """'confirm' | 'reject' | 'uncertain' for a bare answer to a DELIVERED question, else None.

    None means "this is not a bare answer" — the turn goes to the model as any other would. That is
    the safe direction: a composite or qualified reply carries content of its own, and deciding it
    here would be guessing at what the user meant."""
    if not case or case.get("state") != "awaiting" or not case.get("question_delivered"):
        return None                      # nothing was asked, or it was never delivered
    body = (text or "").strip()
    if not body:
        return None
    if _MAYBE.match(body):
        return "uncertain"
    # 93.P3: a case that still NEEDS something was not asking for agreement. "yes" cannot supply a
    # subject nobody named, and treating it as agreement is how a placeholder became a definition.
    # A refusal still lands: declining needs no missing piece.
    if case.get("needs") and _FEEDBACK.get(_signal(body) or "") != "reject":
        return None
    from .session_plans import _NO
    signal = _signal(body)
    if signal == "no":
        # `approval_signal` accepts a refusal by its opening words, which is right for a plan: "no,
        # cancel it" declines whatever follows. Here it is not: "no - instead, my dog is called Green"
        # REFUSES and TEACHES, and consuming it as a bare answer would silently drop the teaching. So
        # the refusal must account for the whole message, using the same words, anchored at the end.
        rest = body[(_NO.match(body) or _EMPTY).end():]
        if re.search(r"[^\W_]", rest, flags=re.UNICODE):
            return None
    return _FEEDBACK.get(signal or "")
