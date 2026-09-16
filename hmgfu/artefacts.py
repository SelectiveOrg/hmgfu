"""95.78 (D5) — what a built artefact actually is, said plainly.

Asked for a widget that shows the weather, the agent wrote a page whose temperature is a constant,
under its own comment saying that in production it would fetch one, and reported the widget finished.
Writing the file is real work, so the say-do gate had nothing to catch: the claim was true about the
FILE and false about what the file does. The user found out by looking at their phone.

So the artefact is read at the moment it is written, its unresolved markers are recorded on the
receipt, and the harness appends the disclosure to the reply. The model does not have to volunteer it.

TRADEOFF, stated rather than hidden (Rule 10): the markers below are a short list of code idioms. They
are the conventional ways a draft announces itself, they are visible here and documented in the
roadmap, and they are matched as whole tokens so ordinary prose ("the production line") is not caught.
The thorough alternative — running the artefact and checking it does what it claims — is a much larger
change; this catches the case that happened without touching anyone's wording.
"""

from __future__ import annotations

import re
from typing import List

# Each entry is how a draft conventionally marks itself. Whole-token matching only.
PLACEHOLDER_MARKERS = (
    r"TODO", r"FIXME", r"XXX",
    r"mock\w*", r"dummy\w*", r"stub\w*", r"placeholder\w*",
    r"YOUR_[A-Z_]*KEY", r"YOUR_[A-Z_]*TOKEN", r"<your[\w-]*>",
    r"in production,? you'?d", r"replace (?:this|with)", r"lorem ipsum",
    r"hard-?coded", r"sample data", r"fake data",
)
_MARKER = re.compile(r"\b(?:" + "|".join(PLACEHOLDER_MARKERS) + r")\b", re.IGNORECASE)
MAX_REPORTED = 4


def placeholders_in(text: str) -> List[str]:
    """The unresolved draft markers in what was written, in the order they appear, without repeats."""
    out: List[str] = []
    for m in _MARKER.finditer(text or ""):
        token = m.group(0)
        if token.lower() not in {x.lower() for x in out}:
            out.append(token)
    return out


def disclosure(engine, session_id: str, turn_seq: int) -> str:
    """The line the reply must carry when this turn shipped an artefact with its own markers left in.
    Empty when the turn shipped nothing, or nothing unresolved."""
    store = getattr(engine, "receipts", None)
    if store is None or not session_id:
        return ""
    try:
        rows = store.for_session(session_id)
    except Exception:
        return ""
    shipped = []
    for r in rows:
        if r.get("turn_seq") != turn_seq or r.get("status") not in ("ok", "already_present"):
            continue
        for entry in (r.get("effects") or {}).get("files", []) or []:
            marks = entry.get("placeholders") or []
            if marks:
                shipped.append((entry.get("path") or "the file", marks))
    if not shipped:
        return ""
    parts = [f"{path} ({', '.join(marks[:MAX_REPORTED])})" for path, marks in shipped[:3]]
    return ("\n\n(Not finished: " + "; ".join(parts)
            + ". What I wrote still carries its own placeholders, so it does not do the real thing yet. "
              "Say the word and I will replace them.)")
