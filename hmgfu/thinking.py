"""Thinking modes (PA3: dynamic | always | off) — directive + reply parsing."""

from __future__ import annotations

import re

# Both the HMG-Fu prompt convention <thinking> AND the native reasoning tag <think> some models
# emit inline (Qwen/gemma) — either is captured as reasoning and stripped from the answer.
_THINK_RE = re.compile(r"<think(?:ing)?>(.*?)</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
# Leaked model special tokens (<|mask|>, <|mask_first_thinking_block|>, <|im_end|>, …) must never
# appear in a user-facing answer — strip any that bleed through the template.
_SPECIAL_RE = re.compile(r"<\|[^|>]{0,48}\|>")


def thinking_directive(mode: str) -> str:
    """Prompt-based reasoning directive — FALLBACK for models WITHOUT native thinking (the nano).
    Native-thinking models are driven via the Ollama `think` param (thinking.resolve_think), so this
    returns empty for them at the call site; kept here for the non-native path only."""
    if mode == "off":
        return ""
    if mode == "always":
        return ("\n\nAlways begin your reply with a <thinking>…</thinking> block laying out your "
                "reasoning, THEN give the answer outside the block.")
    return ("\n\nFor non-trivial requests, begin with a brief <thinking>…</thinking> block "
            "(your plan/reasoning), then answer outside the block. Skip it for simple replies.")


def resolve_think(mode: str, is_action_turn: bool, supports_native: bool):
    """Native Ollama `think` value for a MAIN chat turn (Phase 58). None = OMIT the param.
    - model without native thinking → None (omit; the <thinking> prompt directive applies instead).
    - ACTION turn → False: on a turn that MUST call a tool, native reasoning BURIES the tool call
      and the model stops early (ornith/Qwen3.5) — disabling thinking for the emission is the fix.
      (The router is separate and keeps thinking on — proven to help classification accuracy.)
    - else map thinking_mode: off→False, always→True, dynamic→None (the model's own default, which
      for gemma/ornith is thinking on; the reasoning is surfaced to the UI via message.thinking)."""
    if not supports_native:
        return None
    if is_action_turn:
        return False
    if mode == "off":
        return False
    if mode == "always":
        return True
    return None


def turn_thinking(mode: str, is_action_turn: bool, provider, chat_model, client) -> tuple:
    """(think_value, prompt_directive) for a MAIN chat turn (Phase 58). A native-thinking Ollama
    model is driven by the `think` param (prompt directive empty); any other model falls back to
    the <thinking> prompt convention. Model-agnostic — capability probed from /api/show."""
    thinks_natively = (getattr(provider, "name", "") == "ollama"
                       and "thinking" in client.capabilities(chat_model))
    think = resolve_think(mode, is_action_turn, thinks_natively)
    directive = "" if thinks_natively else thinking_directive(mode)
    return think, directive


def extract_thinking(reply: str) -> tuple:
    """Split reasoning out of the reply → (clean_reply, thoughts_or_empty). Handles both
    <thinking> and <think> blocks and scrubs leaked <|special|> tokens."""
    thoughts = "\n".join(m.strip() for m in _THINK_RE.findall(reply or "")).strip()
    clean = _SPECIAL_RE.sub("", _THINK_RE.sub("", reply or "")).strip()
    return clean, thoughts


def _describe(name: str, args: dict) -> str:
    """One honest action sentence derived from the tool call itself."""
    args = args or {}
    if name == "memory_search":
        return f"Searching memory for \"{str(args.get('query', ''))[:60]}\""
    if name == "memory_timeline":
        return "Reviewing the memory timeline"
    if name == "bash":
        return f"Running `{str(args.get('command', ''))[:60]}`"
    if name == "read_file":
        return f"Reading {args.get('path', 'a file')}"
    if name == "write_file":
        return f"Writing {args.get('path', 'a file')}"
    if name == "create_widget":
        return f"Creating a {args.get('type', '')} widget \"{str(args.get('title', ''))[:40]}\""
    if name == "update_widget":
        return "Updating a canvas widget"
    if name == "remove_widget":
        return "Removing a canvas widget"
    if name == "create_skill":
        return f"Building a new skill \"{str(args.get('name', ''))[:40]}\""
    if name == "plan_task":
        return f"Planning: {str(args.get('title', 'the task'))[:60]}"
    if name == "update_plan":
        return "Marking plan progress"
    if name == "tool_search":
        return f"Looking for a tool to {str(args.get('query', ''))[:50]}"
    if name.startswith("mcp__"):
        return f"Calling {name.split('__')[1]} · {name.split('__')[-1]}"
    return f"Using {name}"


def narrate_tool_calls(tool_calls: list, plan: dict | None) -> str:
    """Doctrine backstop: when a tool round arrives WITHOUT model reasoning, the system
    narrates the action deterministically (it knows the tool, args and plan step) — so the
    execution flow ALWAYS opens with a thinking block, never a silent jump to tools."""
    parts = [_describe(tc.get("name", ""), tc.get("arguments")) for tc in tool_calls[:3]]
    text = "; ".join(p for p in parts if p)
    if plan:
        active = next((i for i, s in enumerate(plan["steps"]) if s["status"] == "active"), None)
        if active is not None:
            step = plan["steps"][active]
            text = f"Step {active + 1}/{len(plan['steps'])} — {step['text'][:60]}: {text}"
    return text
