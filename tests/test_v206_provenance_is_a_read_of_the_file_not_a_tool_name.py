"""E7 instrument — provenance is a read of the source file, not a tool name.

The judge's `widget_value_traceable` demanded `read_file` by name, so a read-only shell read of the
file ("cat inventory.txt", "grep widget-B inventory.txt") failed the provenance check even when the
number came from the file; the DEV chain declared `tools_ran: ["read_file"]` on top. The contract is
where the number came from. Positive: a read-only shell command naming the file is a read of it.
Negative: a shell command that does not name the file, or a writing one, is not; the VALUE criterion is
untouched (a widget with 1 still fails). Preserve: read_file on the path still counts.
"""
from __future__ import annotations

import json

import pytest

from scripts import judge_validation_v2 as jv2  # noqa: E402


@pytest.fixture(autouse=True)
def _bind():
    jv2.use_set("chains")
    yield


def _step(calls, ok, reply=""):
    trace = [{"type": "tool_call", "data": json.dumps({"type": "tool_call", "name": n, "arguments": a})} for n, a in calls]
    return {"message": "", "reply": reply, "tools": [n for n, _ in calls], "tools_ok": ok, "tool_failures": [],
            "tools_blocked": [], "offered": [], "withheld": [], "registered": 0, "plan": {}, "secs": 1.0,
            "changes": [], "names": {}, "trace": trace}


def _row(steps, value):
    ep = jv2.BY_ID["E7"]
    return {"id": "E7", "axis": ep["axis"], "lang": ep["lang"], "base": ep["base"], "steps": steps,
            "artifacts": {"inventory.txt": "widget-B 11\n"}, "widgets": [{"title": "W", "type": "metric", "props": json.dumps({"value": value})}],
            "receipts": [], "utility_before": {}, "utility_after": {}, "secs": 3.0}


def test_a_read_only_shell_read_of_the_file_is_provenance():
    """THE CONTRACT — fails before: only read_file counted."""
    steps = [_step([("bash", {"command": "cat inventory.txt"}), ("create_widget", {"type": "metric"})], ["bash", "create_widget"]),
             _step([], [], reply="The number 11 comes from inventory.txt.")]
    why = jv2.judge(_row(steps, "11"))["why"]
    assert not [w for w in why if "without reading" in w], why


def test_read_file_on_the_path_still_counts():
    steps = [_step([("read_file", {"path": "inventory.txt"})], ["read_file"]),
             _step([], [], reply="The number 11 comes from inventory.txt.")]
    assert not [w for w in jv2.judge(_row(steps, "11"))["why"] if "without reading" in w]


def test_a_command_not_naming_the_file_or_writing_is_not_provenance():
    steps = [_step([("bash", {"command": "ls -R | grep -c widget-B"})], ["bash"]), _step([], [], reply="inventory.txt")]
    assert [w for w in jv2.judge(_row(steps, "11"))["why"] if "without reading" in w]
    steps = [_step([("bash", {"command": "cat inventory.txt > copy.txt"})], ["bash"]), _step([], [], reply="inventory.txt")]
    assert [w for w in jv2.judge(_row(steps, "11"))["why"] if "without reading" in w]


def test_the_value_criterion_is_untouched():
    steps = [_step([("bash", {"command": "grep -c widget-B inventory.txt"})], ["bash"]), _step([], [], reply="From inventory.txt.")]
    why = jv2.judge(_row(steps, "1"))["why"]
    assert [w for w in why if "no widget carries the value '11'" in w], why
