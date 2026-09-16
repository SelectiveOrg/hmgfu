"""Answer grounding (Phase 66.2) — an AgentLTL-style runtime trace check, deterministic.

Live failure: after a web search that returned a generic snippet, the model replied "26°C with clear
skies" — a value present in NO tool output and NO memory. Prompts cannot fix that; a trace constraint
can: every NUMBER (with its unit) and every URL in a reply that followed a tool round must be traceable
to a tool output, the injected memory context, the runtime block, or the user's own message.

Conservative by design: only numbers/units and URLs are checked (entities are too ambiguous to police
deterministically on a small model). The measurement that made this gate necessary lives in
`scripts/bench_tool_precision.py` (`answer_grounded`).
"""

from __future__ import annotations

import re
from typing import Iterable, List

_NUM = re.compile(r"(?<![\w/.-])(\d+(?:[.,]\d+)?)\s*(°\s*[cf]|º\s*[cf]|%|km/h|mph|mm|cm|km|kg|h\b|:\d{2})?", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
_SAFE_NUMBERS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100", "0"}   # counting/list numbers


def _claims(text: str) -> List[str]:
    out: List[str] = []
    text = text or ""
    out.extend(_TIME_OF_DAY.findall(text))          # a time of day is ONE claim ("14:26"), not two numbers
    text = _TIME_OF_DAY.sub(" ", text)
    for m in _NUM.finditer(text):
        num = m.group(1).replace(",", ".")
        unit = (m.group(2) or "").strip()
        if num in _SAFE_NUMBERS and not unit:
            continue
        out.append(num + unit if unit and not unit.startswith(":") else num)   # 69.3: the unit travels with the number
    # 90.1: markdown emphasis and closing punctuation are not part of the address ("**url**", "(url)", "url." — a correct
    # URL found by memory_search was stripped from a live reply because "url**" matched no evidence)
    out.extend(u.rstrip(".,;:)]>*_`'\"") for u in _URL.findall(text or ""))
    return out


_JSON_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _norm(s: str) -> str:
    """Lower-case, decimal comma → point, and DECODE what tool results carry as JSON text: '\\u00b0F' and
    '&deg;F' are '°F' (69.8: real weather values were flagged because the degree sign arrived escaped)."""
    s = _JSON_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), s or "")
    return s.lower().replace(",", ".").replace("&deg;", "°")


_TIME_OF_DAY = re.compile(r"(?<![\d.])\d{1,2}:\d{2}(?::\d{2})?(?![\d])")


_UNIT_SPLIT = re.compile(r"^(\d+(?:\.\d+)?)\s*(.+)$")


def _needle_pattern(needle: str) -> str:
    """'26°c' must be found as 26 followed by °C/ºC — '26%' in the evidence does not ground it (69.3)."""
    m = _UNIT_SPLIT.match(needle)
    if not m:
        return r"(?<![\d.])" + re.escape(needle) + r"(?![\d])"
    num, unit = m.group(1), re.sub(r"\s+", "", m.group(2))
    unit_pat = r"(?:°|º)\s*" + re.escape(unit[-1]) if unit[0] in "°º" else re.escape(unit)
    return r"(?<![\d.])" + re.escape(num) + r"\s*" + unit_pat + r"(?![a-z\d])"


def ungrounded_claims(reply: str, evidence: Iterable[str]) -> List[str]:
    """Numbers/URLs in `reply` that appear in none of the evidence texts. Numbers match as WHOLE
    tokens: "26" is not grounded by the "2026" in the runtime clock."""
    blob = " ".join(_norm(e) for e in evidence)
    # a clock reading (14:26:32) grounds only a time-shaped claim — never a bare "26" (67.13: the suite
    # failed whenever the wall clock's minute equalled the fabricated value)
    blob_plain = _TIME_OF_DAY.sub(" ", blob)
    bad = []
    for c in _claims(reply):
        needle = _norm(c)
        if needle.startswith("http"):
            found = needle in blob
        else:
            hay = blob if ":" in needle else blob_plain
            found = re.search(_needle_pattern(needle), hay) is not None
        if not found:
            bad.append(c)
    return bad


def unsupported_answer_terms(reply: str, question: str, evidence: Iterable[str]) -> tuple:
    """77.4: (unsupported, novel) — the reply's salient words that are not in the question (novel) and, of those, the
    ones found nowhere in the evidence. A fabricated name, date or value shows up here; a paraphrase of supported
    content mostly does not. Accent-stripped, stop words out (textnorm — the same normaliser the other gates use)."""
    from .textnorm import norm, salient
    q_words = set(salient(question or "", min_len=4))
    novel = [w for w in salient(reply or "", min_len=4) if w not in q_words]
    blob = norm(" ".join(evidence))
    unsupported = [w for w in novel if w not in blob]
    return unsupported, novel


def unsupported_share(reply: str, question: str, evidence: Iterable[str]) -> float:
    unsupported, novel = unsupported_answer_terms(reply, question, evidence)
    return len(unsupported) / len(novel) if novel else 0.0


NO_RECORD = ("I have no record of that in my memory — nothing stored says it, so I will not guess. "
             "If you tell me, I will remember it.")

CLAIM_REASK = (
    "CLAIM CHECK: your reply asserts things that appear in NO memory, ledger line or tool result: {terms}. "
    "Rewrite using ONLY what the context states. If the context does not contain the answer, say plainly that "
    "there is no record of it — do not guess."
)


def verify_claims(engine, reply: str, question: str, evidence, messages, provider, chat_model, turn_seq: int):
    """77.4 gate (turns without tools). Returns (reply, report|None)."""
    if not engine.settings.get("claim_gate_enabled"):
        return reply, None
    floor = float(engine.settings.get("claim_gate_floor") or 0.0)
    unsupported, novel = unsupported_answer_terms(reply, question, evidence)
    share = len(unsupported) / len(novel) if novel else 0.0
    if not novel or share <= floor:
        return reply, None
    fixed = ""
    try:
        out = provider.chat(chat_model, list(messages) + [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": CLAIM_REASK.format(terms=", ".join(unsupported[:6]))}],
            temperature=0.2, think=False)
        fixed = (out.get("content") or "").strip() if isinstance(out, dict) else str(out or "").strip()
    except Exception:
        fixed = ""
    if fixed:
        u2, n2 = unsupported_answer_terms(fixed, question, evidence)
        share2 = len(u2) / len(n2) if n2 else 0.0
        if share2 <= floor or "no record" in fixed.lower():
            engine._emit({"type": "grounding", "turn_seq": turn_seq, "ok": True, "repaired": unsupported, "kind": "claim"})
            return fixed, {"repaired": unsupported, "share": round(share, 3)}
    engine._emit({"type": "grounding", "turn_seq": turn_seq, "ok": False, "unverified": unsupported, "kind": "claim", "abstained": True})
    return NO_RECORD, {"abstained": unsupported, "share": round(share, 3)}


GROUNDING_REASK = (
    "GROUNDING CHECK: your reply states values that appear in NO tool result and NO memory: {claims}. "
    "Rewrite the answer using ONLY values present in the tool results or the memory context. If the "
    "results do not actually contain the answer, say clearly that you could not verify it — never invent "
    "a number. Keep the rest of the reply."
)


def grounding_note(claims: List[str]) -> str:
    return " (unverified: " + ", ".join(claims[:4]) + " — not found in any tool result)"


def verify_grounding(engine, reply: str, tool_trace, evidence, messages, provider, chat_model, turn_seq: int):
    """Phase 66.2 gate. After a tool round: numbers/URLs in the reply must trace to a tool output, the
    memory context, the runtime block or the user's words. One corrective re-ask (tools disabled);
    if still ungrounded, the values are flagged visibly. Returns (reply, report|None)."""
    if not tool_trace or not engine.settings.get("grounding_gate_enabled"):
        return reply, None
    bad = ungrounded_claims(reply, evidence)
    if not bad:
        return reply, None
    fixed = ""
    try:
        out = provider.chat(chat_model, list(messages) + [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": GROUNDING_REASK.format(claims=", ".join(bad[:5]))}],
            temperature=0.2, think=False)                 # 73.2: a corrective rewrite, not a new problem
        fixed = (out.get("content") or "").strip() if isinstance(out, dict) else str(out or "").strip()
    except Exception:            # the gate is advisory infrastructure — never a dead turn
        fixed = ""
    if fixed:
        still = ungrounded_claims(fixed, evidence)
        if not still:
            engine._emit({"type": "grounding", "turn_seq": turn_seq, "ok": True, "repaired": bad})
            return fixed, {"repaired": bad}
        reply, bad = fixed, still
    engine._emit({"type": "grounding", "turn_seq": turn_seq, "ok": False, "unverified": bad})
    return reply.rstrip() + grounding_note(bad), {"unverified": bad}
