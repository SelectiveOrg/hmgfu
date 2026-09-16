"""95.9c (E7 c95c rep1/rep3) — the schema says what `command` is.

The bash tool's `command` parameter carried no description ({"type": "string"}) while the tool's own
description talks about the TASK ("inspect the project folder... carry out a task"); the model filled
`command` with the task — the user's sentence — and put the shell line under `code` or `description`
(rep3: six calls, all shaped that way). 95.9 refuses the echo, 95.9b folds a named alias; the contract
itself is the layer that invites the drift. Positive: the parameter is described as the shell command
line. Preserve: it stays required, a string, next to the timeout.
"""
from __future__ import annotations

from hmgfu.tool_builtins import BUILTIN_TOOLS


def _bash():
    return next(t for t in BUILTIN_TOOLS if t["name"] == "bash")


def test_the_command_parameter_is_described_as_the_shell_line():
    """THE CONTRACT — fails before: no description at all."""
    desc = _bash()["parameters"]["properties"]["command"].get("description", "")
    assert "shell command" in desc.casefold() and "request" in desc.casefold(), desc


def test_the_parameter_is_still_required_and_a_string():
    params = _bash()["parameters"]
    assert params["required"] == ["command"] and params["properties"]["command"]["type"] == "string"
    assert "timeout" in params["properties"]
