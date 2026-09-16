"""95.65 -- a STANDING PROHIBITION on an effect ("Under no circumstances write to a file called chaves.env."):
detected by the directive store itself (the perceiver's directive is not relied on) and enforced by the authority
on every later turn (a write whose target a stored prohibition names is refused). One place for both readers."""
from __future__ import annotations

import re
from typing import List, Optional

# a prohibition is STANDING when it says so: never / an absolute-negation adverbial / from now on (73.4's symmetric)
_STANDING_NEG = re.compile(r"\b(?:never|nunca|jamais|from now on|a partir de agora|de agora em diante|de hoje em diante|"
                           r"under no circumstances|in no case|on no account|by no means|em circunst[a\u00e2]ncia alguma|"
                           r"em caso algum|de forma alguma|de maneira nenhuma|de modo algum)\b", re.IGNORECASE)
_TARGET = re.compile(r"\b([\w][\w.-]*\.[A-Za-z0-9]{1,5})\b")   # a file name, the authority's own shape


def named_files(text: str) -> set:
    return {m.lower() for m in _TARGET.findall(text or "")}


def detect_prohibition(text: str) -> Optional[dict]:
    """{kind: "prohibition", value, instruction} when `text` prohibits an effect (speech_act.prohibits_effect), states
    it as standing, and names a file; None otherwise ("don't write x.env now" is the turn's own rule, 70.5)."""
    from .speech_act import prohibits_effect
    t = " ".join((text or "").split())
    if not t or not prohibits_effect(t) or not _STANDING_NEG.search(t) or not named_files(t):
        return None
    return {"kind": "prohibition", "value": t[:300], "instruction": t[:500]}


_PERMITS = re.compile(r"\b(?:may|can|are allowed to|are free to|podes|pode|podem|est[a\u00e1]s? autorizad[oa]s?|"
                      r"permitido|permito|autorizo|lift(?:ing|ed)?|levanto|retiro|fica sem efeito|sem efeito)\b", re.IGNORECASE)   # 95.65c


def detect_lift(text: str, rows) -> Optional[dict]:
    """95.65c: the message LIFTS a stored prohibition -- it names a file an active prohibition names and states the
    lift (a standing cue, a stop cue or a permissive modal). {kind, clear: True, files} for the first such row, or
    None. A bare "write x" is an insistence and lifts nothing (95.3)."""
    from .speech_act import has_standing_cue, prohibits_effect
    t = " ".join((text or "").split())
    if not t or prohibits_effect(t):
        return None
    hits = rows_forbidding(rows, named_files(t))
    if not hits:
        return None
    low = t.lower()
    if not (has_standing_cue(t) or _PERMITS.search(t) or any(c in low for c in ("stop", "no longer", "cease"))):
        return None
    return {"kind": hits[0]["kind"], "clear": True, "files": sorted(named_files(t) & named_files(str(hits[0].get("instruction") or hits[0].get("value") or "")))}


def rows_forbidding(rows, targets) -> List[dict]:
    """The active directive rows that prohibit an effect and name one of `targets` -- any kind (the perceiver used
    to store these as response_style), so a rule kept under another name still counts."""
    from .speech_act import prohibits_effect
    targets = {t.lower() for t in (targets or set())}
    out = []
    for r in rows or []:
        text = str(r.get("instruction") or r.get("value") or "")
        if targets and prohibits_effect(text) and (named_files(text) & targets):
            out.append(r)
    return out


def forbidden_target(rows, name: str, args) -> Optional[str]:
    """95.65b: the file a stored prohibition names that this call would write -- its path argument, or a file named
    in its shell command -- or None."""
    args = args or {}
    named = set()
    for k in ("path", "filename", "file", "command", "code"):
        named |= named_files(str(args.get(k) or ""))
    hits = rows_forbidding(rows, named) if named else []
    for r in hits:
        for t in named_files(str(r.get("instruction") or r.get("value") or "")):
            if t in named:
                return t
    return None
