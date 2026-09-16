"""Phase 52 — a conversation_opener directive must not suppress proactive tool execution.

Root cause of the L6/L7 'not proactive' failure: an opener instruction in the SYSTEM PROMPT
forced the model into text-generation mode (it told a joke + 'I will run it' and never emitted
the tool call). Fix: for action-required turns the opener is kept OUT of the prompt (the model
can act); the deterministic enforce() still prepends the opener to the final answer. No Ollama —
the fake provider is scripted; we assert the prompt contents + the tool trace.
"""

from __future__ import annotations

from tests.test_v2_agent import make_agent

_OPENER = {"kind": "conversation_opener", "value": "short_joke",
           "instruction": "Begin every reply with a short joke.",
           "fallback_text": "Why did the node cross the grid? To connect!"}


def test_opener_kept_out_of_prompt_for_action_turns(tmp_path, monkeypatch):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo HI"}}]},
        {"content": "The output is HI.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    engine.directives.apply("start with a joke", detected=_OPENER)

    real = engine.retrieve
    def routed(text, **kw):                 # live router detected an explicit action this turn
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["memory_search"]   # an always-offered escape-hatch tool
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)

    result = engine.agent_chat("run echo HI")
    used = [t["name"] for t in result["tool_trace"]]
    assert "bash" in used                                          # action NOT suppressed
    assert "connect" in result["response"].lower()                # opener still honoured (enforce)
    system_prompts = [c["messages"][0]["content"] for c in fake.calls if c.get("messages")]
    assert system_prompts
    assert not any("Begin every reply with a short joke" in sp for sp in system_prompts)


def test_opener_applied_via_enforce_never_in_prompt(tmp_path):
    """The opener is NEVER injected into the prompt (it suppresses actions and dominates
    substantive turns); the deterministic enforce() prepends it to the final answer instead."""
    engine, fake = make_agent(tmp_path, [{"content": "Hello there.", "tool_calls": []}])
    engine.directives.apply("start with a joke", detected=_OPENER)
    result = engine.agent_chat("hi")                               # plain first turn, no action
    assert "connect" in result["response"].lower()                 # opener applied (enforce)
    system_prompts = [c["messages"][0]["content"] for c in fake.calls if c.get("messages")]
    assert not any("Begin every reply with a short joke" in sp for sp in system_prompts)
