"""Language-neutral structural fallback for explicit tool names.

Primary action routing lives in Sensitizer's runtime-catalog classification plus HMG semantic
tool retrieval. This module intentionally contains no natural-language phrase table.
"""

from __future__ import annotations


def explicit_tool_names(text: str, available_names) -> list[str]:
    folded = (text or "").casefold()
    return [name for name in available_names if name.casefold() in folded]


def action_tools(text: str, available_names=()) -> list[str]:
    """Compatibility facade: only exact registered names are structurally detectable."""
    return explicit_tool_names(text, available_names)


def requires_action(text: str, available_names=()) -> bool:
    return bool(action_tools(text, available_names))
