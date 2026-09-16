"""Phase 90.G1 (H-A2) — the router's own contract: `runtime_context_sufficient=true` means "the runtime clock fully answers this;
list the exact keys, request no tool". A response that says sufficient=true while naming NO runtime key and REQUESTING tools is
internally inconsistent, and the sanitiser must not turn it into "no action, no tools" — that wiped plan_task/write_file on the live
shape 'Plan and create three text files…' (router raw: action_requested true, tools [plan_task, write_file], keys [], sufficient true)
and left the model with no tool to act with. A genuine clock answer (keys named) is still tool-free."""
from __future__ import annotations

from hmgfu.extraction_schema import _sanitise

TOOLS = ["plan_task", "write_file", "list_files"]


def test_sufficient_without_keys_does_not_wipe_a_requested_action():
    out = _sanitise({"conversation_act": "instruction", "action_requested": True, "requested_tools": ["plan_task", "write_file"],
                     "runtime_context_keys": [], "runtime_context_sufficient": True}, TOOLS)
    assert out["requested_tools"] == ["plan_task", "write_file"] and out["action_requested"] is True
    assert out["runtime_context_sufficient"] is False          # the claim was inconsistent; it is not carried forward


def test_genuine_clock_answer_stays_tool_free():
    out = _sanitise({"conversation_act": "question", "action_requested": False, "requested_tools": [],
                     "runtime_context_keys": ["local_time"], "runtime_context_sufficient": True}, TOOLS)
    assert out["requested_tools"] == [] and out["action_requested"] is False and out["runtime_context_sufficient"] is True
    out = _sanitise({"conversation_act": "question", "action_requested": True, "requested_tools": ["brave_web_search"],
                     "runtime_context_keys": ["now_local"], "runtime_context_sufficient": True}, TOOLS + ["brave_web_search"])
    assert out["requested_tools"] == [] and out["action_requested"] is False    # keys named: the clock answers, no tool (unchanged)
