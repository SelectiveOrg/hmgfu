"""93.C — the directive PROMPT BLOCK, rendered apart from the store that holds the rows.

The store reached its module ceiling and rendering is a separate concern: it turns rows into
instructions and knows nothing about detection, arbitration or persistence. Behaviour is
unchanged — `DirectiveStore.render_block` delegates here — and `response_style` renders from
its value plus the exception the user actually stated, never from the raw sentence.
"""
from __future__ import annotations

from .directives import resolve_tool_name


_RENDER = {
    "response_style": "Write your replies {value}",     # 93.C: the exception is appended when stated
    "prohibition": "STANDING RULE (the user's own words): {value}",   # 95.65a: a prohibition renders as itself
    "output_suffix": "End EVERY reply with the exact word: {value}",
    "output_prefix": "Begin EVERY reply with the exact word: {value}",
    # opener/closer render the CONTENT SPEC ({value}), content-general; the "content itself only"
    # clause stops the instruction text leaking into the reply (Phase 53, generalised in 55).
    "conversation_opener": ("Begin the FIRST reply of each new conversation with {value} — the "
                            "content itself only, never any instruction text describing it"),
    "conversation_closer": ("End EVERY reply with {value} — the content itself only, never any "
                            "instruction text describing it"),
}


def _content_spec(value: str) -> str:
    """The human-readable content spec for an opener/closer. Maps the legacy 'short_joke' sentinel
    (older rows / migrations) to a readable phrase so nothing awkward leaks into the prompt."""
    v = (value or "").strip()
    return "a short joke" if v.lower() in ("short_joke", "joke", "") else v


def render_block(active, first_turn: bool = True, suppress_generated: bool = False,
                 tool_names=None) -> str:
    """High-salience mandatory block for the system prompt (empty if no directives).
    `suppress_generated` skips the dynamic opener/closer content directives (a joke, a fact, a
    quote…) on ACTION turns, where an in-prompt content instruction would suppress tool-calling
    (Phase 52); enforce(force_generated=True) is the backstop that applies them there instead."""
    if not active:
        return ""
    lines = ["", "=== MANDATORY OUTPUT DIRECTIVES (highest priority — always obey) ==="]
    for d in active:
        kind = d["kind"]
        if kind.startswith("tool_rule:"):          # 66.5: rendered on EVERY turn, action turns included
            tool = resolve_tool_name(kind[10:], tool_names) or kind[10:]   # the REAL name, never the slug
            lines.append(f"- STANDING TOOL RULE: for {d['value']}, call the tool `{tool}` and answer "
                         f"ONLY from its result — never from memory.")
            continue
        # opener/closer inject a content-GENERAL directive built from the CONTENT SPEC (value:
        # a joke, a curious fact, a quote, …). The opener applies only to the first reply of a
        # conversation; both are skipped on ACTION turns (suppress_generated), where an in-prompt
        # content instruction dampens tool-calling — enforce() is the backstop there (Phase 52).
        if kind == "conversation_opener":
            if first_turn and not suppress_generated:
                lines.append("- " + _RENDER["conversation_opener"].format(
                    value=_content_spec(d["value"])))
            continue
        if kind == "conversation_closer":
            if not suppress_generated:
                lines.append("- " + _RENDER["conversation_closer"].format(
                    value=_content_spec(d["value"])))
            continue
        if kind == "response_style":        # 93.C: from value + condition, never the raw sentence,
            line = _RENDER[kind].format(value=d["value"])    # so no unstated exception leaks in
            if d.get("condition"):
                    line += f" (exception, in the user's words: {d['condition']})"   # 93.R1: never assume the connective
            lines.append("- " + line)
            continue
        if d.get("instruction"):
            line = d["instruction"]
            if d.get("fallback_text"):
                line += f" Begin with this exact text: {d['fallback_text']}"
            lines.append("- " + line)
            continue
        tmpl = _RENDER.get(kind, "{value}")
        lines.append("- " + tmpl.format(value=d["value"]))
    return "\n".join(lines) if len(lines) > 2 else ""
