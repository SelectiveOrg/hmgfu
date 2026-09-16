"""Prompt-based tool protocol for providers without native tool calling (gemma via ollama:
a native tools payload returns tool_calls=null and EMPTY content — verified live)."""

from __future__ import annotations

import json
import re
from typing import List, Optional


def render_tool_protocol(tool_schemas: List[dict]) -> str:
    lines = ["", "AVAILABLE TOOLS:"]
    for t in tool_schemas:
        props = (t.get("parameters") or {}).get("properties") or {}
        args = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in props.items()) or "no arguments"
        lines.append(f"- {t['name']} — {t.get('description', '')} ({args})")
    lines += [
        "",
        'To call a tool, reply with ONLY this JSON on its own (no prose, no code fences):',
        '{"tool_call": {"name": "<tool_name>", "arguments": {...}}}',
        "You will receive the result and can then call another tool or answer the user normally.",
    ]
    return "\n".join(lines)


def _first_json_object(s: str) -> Optional[dict]:
    """First balanced {...} in s, json-parsed, or None (tolerates trailing prose)."""
    start = s.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(s[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
        start = s.find("{", start + 1)
    return None


def parse_hermes_tool_call(content: str, tool_schemas: Optional[List[dict]] = None) -> Optional[dict]:
    """The Hermes/Qwen `<tool_call>{"name":…,"arguments":{…}}</tool_call>` envelope (Phase 57).
    This is the EXACT text shape ornith:9b (Qwen3.5) emits when it narrates a call instead of using
    the native path — the vLLM Hermes2ProToolParser convention. Order-agnostic (Qwen is name-first,
    Hermes args-first), tolerant of an open/truncated tag and a leading <scratch_pad> reasoning
    block, and of `arguments` arriving as a JSON string. Gated to OFFERED tools when a catalog is
    given so a normal reply can never be misread as a call."""
    if not content or "<tool_call>" not in content:
        return None
    text = re.sub(r"<scratch_pad>.*?</scratch_pad>", "", content, flags=re.DOTALL)
    m = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>|<tool_call>\s*(.*)", text, re.DOTALL)
    if not m:
        return None
    inner = (m.group(1) or m.group(2) or "").strip()
    obj = None
    try:
        obj = json.loads(inner)
    except (json.JSONDecodeError, ValueError):
        obj = _first_json_object(inner)
    if not isinstance(obj, dict) or not obj.get("name"):
        return None
    name = str(obj["name"])
    if tool_schemas is not None and not any(t.get("name") == name for t in tool_schemas):
        return None
    args = obj.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            args = {}
    return {"name": name, "arguments": args if isinstance(args, dict) else {}}


_SHELL_FENCE = re.compile(r"```(?:bash|sh|shell|zsh|console)\b[^\n]*\n(.*?)```", re.DOTALL)
_JSON_FENCE = re.compile(r"```(?:json|tool_call)?\b[^\n]*\n\s*(\{.*?\})\s*```", re.DOTALL)


def parse_fenced_tool_call(content: str, tool_schemas: Optional[List[dict]] = None) -> Optional[dict]:
    """Recover a tool call a model emitted as a MARKDOWN CODE FENCE — a ```bash …``` shell block or a
    ```json {"name",…}``` block. Coding/reasoning models (ornith/Qwen3.5) narrate the action as a
    code block instead of a native function-call. Gated to OFFERED tools so an illustrative snippet
    in a conversational reply (where the tool isn't on offer) is never executed."""
    if not content or "```" not in content or not tool_schemas:
        return None
    offered = {t.get("name") for t in tool_schemas}
    if "bash" in offered:                                    # a shell fence → the shell tool
        m = _SHELL_FENCE.search(content)
        if m:
            cmd = re.sub(r"(?m)^\s*\$\s?", "", m.group(1)).strip()   # drop a leading `$ ` prompt
            if cmd:
                return {"name": "bash", "arguments": {"command": cmd}}
    m = _JSON_FENCE.search(content)                          # a JSON fence carrying {name, arguments}
    if m:
        obj = _first_json_object(m.group(1))
        if isinstance(obj, dict) and obj.get("name") in offered:
            args = obj.get("arguments") or obj.get("parameters") or {}
            return {"name": str(obj["name"]), "arguments": args if isinstance(args, dict) else {}}
    return None


def parse_text_tool_call(content: str, tool_schemas: Optional[List[dict]] = None) -> Optional[dict]:
    """Recover a tool call a model emitted as TEXT instead of a native function-call. Chain (first
    match wins): (1) the Hermes/Qwen `<tool_call>{name,arguments}</tool_call>` envelope; (2) the
    JSON protocol `{"tool_call":…}`; (3) a markdown code fence (```bash …``` / ```json{name,…}```);
    (4) a single-string-arg `<offered_tool>inner</offered_tool>` tag (bash→command,
    memory_search→query; multi-arg tools left to native calling). General, not model-specific — any
    model that texts a tool call is recovered."""
    hermes = parse_hermes_tool_call(content, tool_schemas)
    if hermes is not None:
        return hermes
    js = parse_protocol_tool_call(content)
    if js is not None:
        return js
    fenced = parse_fenced_tool_call(content, tool_schemas)
    if fenced is not None:
        return fenced
    if not content or not tool_schemas:
        return None
    for t in tool_schemas:
        name = t.get("name")
        if not name:
            continue
        m = re.search(rf"<{re.escape(name)}\s*>(.*?)</{re.escape(name)}\s*>", content, re.DOTALL)
        if not m:
            continue
        inner = m.group(1).strip()
        props = (t.get("parameters") or {}).get("properties") or {}
        keys = (t.get("parameters") or {}).get("required") or list(props)
        # a bare inner text can only fill a SINGLE string argument; multi-arg tools (create_widget
        # needs type+title) are left to native calling rather than guessed at.
        if inner and len(keys) == 1 and (props.get(keys[0]) or {}).get("type", "string") == "string":
            return {"name": str(name), "arguments": {keys[0]: inner}}
    return None


def parse_protocol_tool_call(content: str) -> Optional[dict]:
    """Extract {"tool_call": {...}} from a reply (tolerates code fences and surrounding prose)."""
    if "tool_call" not in content:
        return None
    text = content.replace("```json", "```").replace("```", "")
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        call = obj.get("tool_call") if isinstance(obj, dict) else None
                        if isinstance(call, dict) and call.get("name"):
                            return {"name": str(call["name"]),
                                    "arguments": call.get("arguments") or {}}
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
        start = text.find("{", start + 1)
    return None
