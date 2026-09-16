"""Phase 57 P5 — the bash tool is grounded in the LIVE host OS.

ornith (a Linux-trained coder) emitted Windows-broken shell commands because the tool never told
it the real OS/shell. environment_hint() derives that from platform/shutil each run (dynamic, not
a phrase list) and is appended to the bash tool description. No Ollama.
"""

from __future__ import annotations

import platform

from hmgfu.tool_builtins import BUILTIN_TOOLS, environment_hint
from hmgfu.toolsys import ToolRegistry


def test_environment_hint_reflects_the_running_host():
    hint = environment_hint()
    assert platform.system() in hint          # names the ACTUAL OS (dynamic, not hardcoded)
    if platform.system() == "Windows":
        assert "Git Bash" in hint and "/c/" in hint and "PowerShell" in hint


def test_registry_bash_schema_carries_the_hint_without_mutating_the_constant():
    before = next(t for t in BUILTIN_TOOLS if t["name"] == "bash")["description"]
    reg = ToolRegistry(engine=None)
    bash_desc = reg.schemas["bash"]["description"]
    assert environment_hint() in bash_desc            # the live tool description is grounded
    assert bash_desc != before                        # augmented
    # the module constant is untouched (shallow-copy) — a second registry is identical, not doubled
    after = next(t for t in BUILTIN_TOOLS if t["name"] == "bash")["description"]
    assert after == before
    reg2 = ToolRegistry(engine=None)
    assert reg2.schemas["bash"]["description"] == bash_desc
    assert bash_desc.count("HOST OS") == 1            # not appended twice
