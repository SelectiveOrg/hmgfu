"""Context RENDERING (Phase 78.2, split from retrieve.py at the 400-line ceiling): the section order and the greedy budget
renderer (moved verbatim), plus the long-form excerpt policy the 77.2 attribution asked for.

`excerpt_for_query(text, query, max_chars)` — a long memory renders the sentence WINDOW that shares the most salient words
with the question (contiguous sentences, greedy around the best one, up to max_chars, "…" at a cut) instead of its first
200 characters; with no overlap the head is kept. The setting's default 0 = OFF: the head cut, byte-identical to today.
`is_echo(point, query, pairs)` — an assistant memory is an ECHO when it restates a ledger value of an attribute the question
names (the 73.3 guard's real target); an assistant memory carrying new information is not."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from . import config
from .textnorm import norm, salient

_SENT = re.compile(r"(?<=[.!?;:])\s+|\n+")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT.split((text or "").strip()) if s.strip()]


def excerpt_for_query(text: str, query: str, max_chars: int) -> str:
    """The query-matched sentence window of `text`, at most `max_chars` characters (see module doc)."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    sents = _sentences(text)
    qwords = set(salient(query or ""))
    if not sents or not qwords:
        return text[:max_chars - 1].rstrip() + "…"
    scores = [len(qwords & set(salient(s))) for s in sents]
    best = max(range(len(sents)), key=lambda k: (scores[k], -k))
    if scores[best] == 0:
        return text[:max_chars - 1].rstrip() + "…"                     # no overlap anywhere → the head (today's behaviour)
    lo = hi = best
    used = len(sents[best])
    while True:                                                        # grow around the best sentence, better neighbour first
        cand = []
        if lo > 0:
            cand.append((scores[lo - 1], -1, lo - 1))
        if hi < len(sents) - 1:
            cand.append((scores[hi + 1], 0, hi + 1))
        if not cand:
            break
        cand.sort(reverse=True)
        _, _, k = cand[0]
        if used + 1 + len(sents[k]) > max_chars:
            break
        used += 1 + len(sents[k])
        lo, hi = min(lo, k), max(hi, k)
    window = " ".join(sents[lo:hi + 1])
    if len(window) > max_chars:                                        # the best sentence alone is longer than the budget
        window = window[:max_chars - 1].rstrip() + "…"
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(sents) - 1 and not window.endswith("…") else ""
    return f"{prefix}{window}{suffix}"


def is_echo(point, query: str, pairs: List[Tuple[str, str]]) -> bool:
    """True when the memory restates a ledger value of an attribute the question names."""
    from .slots import mentions_attribute, value_in_text
    blob = f"{getattr(point, 'summary', '')} {getattr(point, 'title', '')} {getattr(point, 'content', '')}"
    for key, value in pairs or []:
        if value and len(value) >= 2 and mentions_attribute(key, query or "") and value_in_text(value, blob):
            return True
    return False


_SECTION_ORDER = [
    ("userIdentity", "User identity and stable preferences"),
    ("warnings", "Warnings or constraints"),
    ("subjectTimeline", "Subject timeline (oldest → newest; [superseded] entries are PAST values "
                        "— the last entry is the current one)"),
    ("contradictions", "Potential contradictions"),
    ("activeProjects", "Active projects and goals"),
    ("proposals", "Proposals, wishes and plans the user has voiced (NOT current state and NOT active work — "
                  "the user proposed, wanted or planned these; never present them as what the user does or has)"),
    ("relevantFacts", "Relevant facts for this request"),
    ("recentContext", "Recent context"),
    ("likelyNextActions", "Likely next actions"),
    # 92.E2: what the assistant itself produced is kept and LABELLED, never silently deleted and
    # never mixed into the authoritative sections above. Placed after them so the budget spends
    # on evidence first.
    ("assistantSaid", "What the assistant itself said or summarised earlier (DERIVED, not confirmed by "
                      "the user; may be wrong or outdated. Never state these as facts about the user or "
                      "the project, and never use one to expand a term the user has defined)"),
]


def render_injection(injection: dict, token_budget: int = config.TOKEN_BUDGET) -> str:
    """Greedy budget fill, priority order per issue 12; ~4 chars per token."""
    char_budget = token_budget * 4
    header = ("Relevant memory context (from HMG-Fu relational memory). Each memory is tagged "
              "with its age; when two memories conflict, TRUST THE MOST RECENT and treat older "
              "ones as superseded. When stating facts about the user, state ONLY the current "
              "values — memories may narrate old, corrected values (past names, changed "
              "preferences); those are HISTORY and must never be listed as facts.")
    lines = [header]
    used = len(header)
    if injection.get("_ephemeral"):
        note = ("\nTIME-SENSITIVE: some recalled memories are stale observations (weather, "
                "prices, status, 'now'). For anything current, you MUST call brave_web_search "
                "and answer ONLY from its result — never state a value from these memories.")
        lines.append(note)
        used += len(note)
    for key, heading in _SECTION_ORDER:
        items = injection.get(key) or []
        if not items:
            continue
        section = [f"\n{heading}:"] + [f"- {item}" for item in items]
        section_len = sum(len(s) + 1 for s in section)
        if used + section_len <= char_budget:
            lines.extend(section)
            used += section_len
            continue
        # 85.2: this section does not fit whole — keep the items that fit, in order, and go on to the NEXT section. Before,
        # the renderer broke out here and every later section was dropped whole while the context sat under budget (the
        # "greedy break" the 85.1 diagnosis named); the budget itself is unchanged.
        heading_len = len(heading) + 3
        kept, sec_used = [], heading_len
        for item in items:
            cost = len(item) + 3
            if used + sec_used + cost > char_budget:
                continue
            kept.append(f"- {item}")
            sec_used += cost
        if kept:
            lines.append(f"\n{heading}:")
            lines.extend(kept)
            used += sec_used
    return "\n".join(lines)
