"""Argument grounding for search-class tools (Phase 66.3) — deterministic deixis completion.

Live failure: `brave_web_search("tell me whats todays weather")` — the raw sentence, no place, although the
ledger knows the user lives in Valencia — returned a generic US snippet. Small models drop the deictic
context ("today", "here") when they copy the request into a query. The harness completes it from the
turn's runtime clock and the canonical ledger, only when the query lacks it and the request is local/
time-bound, and never when the user named a place themselves ("weather in Aveiro").
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

_LOCAL_CUES = re.compile(r"\b(weather|forecast|temperature|tempo|clima|previs[aã]o|temperatura|news|"
                         r"not[ií]cias|traffic|tr[aâ]nsito|events?|eventos?|near me|perto de mim|"
                         r"restaurants?|restaurantes?|pharmac\w+|farm[aá]cias?)\b", re.IGNORECASE)
_TIME_CUES = re.compile(r"\b(today(?:'s|s)?|tonight|tomorrow|now|current(?:ly)?|latest|hoje|amanh[aã]|agora|atual)\b",
                        re.IGNORECASE)
_PLACE_PREP = re.compile(r"\b(?:in|at|em|no|na|para)\s+[A-Za-zÀ-ÿ]{3,}", re.IGNORECASE)
_YEAR = re.compile(r"\b20\d\d\b")
# 69.6: a capitalised word that is not sentence-initial names a place ("Weather for Lisbon tomorrow")
_NAMED = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-ZÀ-Ý][a-zà-ÿ]{2,}(?:\s+[A-ZÀ-Ý][a-zà-ÿ]{2,})?)\b")
_RELATIVE_DAYS = {"tomorrow": 1, "amanha": 1, "amanhã": 1, "yesterday": -1, "ontem": -1}
_TODAY_CUES = re.compile(r"\b(today(?:'s|s)?|tonight|now|current(?:ly)?|latest|hoje|agora|atual)\b", re.IGNORECASE)


def _names_a_place(text: str) -> bool:
    if _PLACE_PREP.search(text or ""):
        return True
    for m in _NAMED.finditer(text or ""):
        if m.start() > 0 and not _LOCAL_CUES.match(m.group(1)) and not _TIME_CUES.match(m.group(1)):
            return True
    return False


def _relative_date(local_date: str, text: str) -> Optional[str]:
    """today's date for 'today/now', the shifted date for 'tomorrow'/'amanhã'; None when no cue."""
    low = (text or "").lower()
    for word, shift in _RELATIVE_DAYS.items():
        if re.search(r"\b" + word + r"\b", low):
            try:
                from datetime import date, timedelta
                return (date.fromisoformat(local_date) + timedelta(days=shift)).isoformat()
            except ValueError:
                return None
    return local_date if _TODAY_CUES.search(text or "") else None


def _city(location: str) -> str:
    return (location or "").split(",")[0].strip()


def complete_query(query: str, user_message: str, runtime, facts: List[dict]) -> Tuple[str, List[str]]:
    """Return (completed_query, what_was_added). `facts` = FactStore.active() rows; `runtime` = the
    turn's RuntimeContext (or None). Adds the user's city when the request is local and names no
    place; adds the local date when the request is time-bound and carries no year."""
    q = (query or "").strip()
    text = f"{q} {user_message or ''}"
    added: List[str] = []
    loc = next((f["value"] for f in (facts or []) if f.get("key") == "identity.location"), "")
    city = _city(loc)
    if city and _LOCAL_CUES.search(text) and not _names_a_place(user_message or "") and not _names_a_place(q) \
            and city.lower() not in q.lower():
        q = f"{q} {city}".strip()
        added.append("location")
    local_date: Optional[str] = getattr(runtime, "local_date", None)
    if local_date and _TIME_CUES.search(text) and not _YEAR.search(q):
        when = _relative_date(local_date, text)         # 69.6: "tomorrow" is tomorrow's date, not today's
        if when:
            q = f"{q} {when}".strip()
            added.append("date")
    return q, added


def memory_lines(user_message: str, facts: List[dict]) -> List[str]:
    """67.6: the ledger values whose slot LABEL the user's request mentions ("keep links", "car location") —
    a widget/file built for them must carry the real values, not a placeholder."""
    text = (user_message or "").lower()
    out = []
    for f in facts or []:
        if not f.get("slot"):
            continue
        label = (f.get("label") or "").lower()
        toks = [t for t in re.findall(r"[a-z]{4,}", label)]
        generic = re.search(r"\blinks?\b", text) and re.match(r"https?://", f.get("value") or "")
        if generic or (toks and any(t in text for t in toks)):
            out.append(f"{f['label']}: {f['value']}")
    return out


def ground_widget_props(props: dict, lines: List[str]) -> bool:
    """67.10: put the ledger lines INTO the widget the user asked for — a note's text or a table's rows —
    unless the values are already there. Returns True when something was added."""
    if not isinstance(props, dict) or not lines:
        return False
    values = [ln.split(": ", 1)[-1] for ln in lines]
    if isinstance(props.get("text"), str):
        missing = [ln for ln, v in zip(lines, values) if v not in props["text"]]   # 69.6: add what is MISSING
        if not missing:
            return False
        props["text"] = (props["text"].rstrip() + "\n\n" + "\n".join(missing)).strip()
        return True
    rows = props.get("rows")
    if isinstance(rows, list):
        present = json.dumps(rows, ensure_ascii=False)
        missing = [ln for ln, v in zip(lines, values) if v not in present]
        if not missing:
            return False
        first = next((r for r in rows if isinstance(r, dict)), None)
        keys = [k for k in (first or {}).keys()][:2]
        for ln in missing:
            label, value = ln.split(": ", 1) if ": " in ln else (ln, "")
            if len(keys) == 2:
                rows.append({keys[0]: label, keys[1]: value})
            elif first is None and rows and isinstance(rows[0], list):
                rows.append([label, value])
            else:
                rows.append({"name": label, "url": value})
        return True
    return False


def grounded_props(wtype: str, props, lines: List[str]):
    """67.11: the props a widget call should carry. A sparse call ({type:'table', title:'Links'} with no props)
    would FAIL validation; when the ledger has the values the user asked for, the harness builds the props."""
    if isinstance(props, dict):
        ground_widget_props(props, lines)
        return props
    if not lines:
        return props
    if wtype == "table":
        rows = []
        for ln in lines:
            label, value = ln.split(": ", 1) if ": " in ln else (ln, "")
            rows.append({"name": label, "url": value})
        return {"rows": rows}
    if wtype in ("note", None, ""):
        return {"text": "\n".join(lines)}
    return props
