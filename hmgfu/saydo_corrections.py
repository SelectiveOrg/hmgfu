"""The corrections saydo appends when a reply claims what the turn's receipts do not support (93.A, 95.4b,
95.56b). One place for the wording; `saydo` imports these back, so every name still resolves from there."""
from __future__ import annotations

CORRECTION = ("\n\n(Correction: nothing was actually written \u2014 no record, directive or file changed this turn. "
              "Tell me the exact value or ask me to do it and I will.)")
PLAN_CORRECTION = ("\n\n(Correction: the step '{step}' was NOT completed this turn \u2014 no receipt shows the work. "
                   "The plan stays open; say 'continue' and I will do that step.)")
REJECTED_CORRECTION = ("\n\n(Correction: the step '{step}' describes no work and was NOT executed \u2014 the request "
                       "is only partly done. Tell me what that step should do and I will add it.)")
_CLASS_WORDS = {"remove": "remove", "create": "create or write", "update": "change", "memory": "store", "complete": "complete"}


def correction_for(classes, ops) -> str:
    """95.56b: a correction tells what the turn DID. "nothing was actually written" is true only when no
    operation exists; with operations on file it names the unsupported claim and the work that was done.
    `ops` are the turn's create/update/remove operations (the plan's own are not work)."""
    ops = [o for o in (ops or []) if not str(o.get("target") or "").startswith("plan:")]
    if not ops:
        return CORRECTION
    did = ", ".join(sorted({f"{o['op']} {o['target']}" for o in ops}))[:160]
    claimed = " / ".join(_CLASS_WORDS.get(c, c) for c in classes) or "do that"
    return f"\n\n(Correction: this turn did not {claimed} anything -- what it did: {did}. Tell me what you meant and I will do it.)"
