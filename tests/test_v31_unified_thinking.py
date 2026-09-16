"""Phase 58 — unified, model-agnostic thinking control (the user's request).

One `thinking_mode` setting drives the NATIVE reasoning of any thinking-capable model via the
Ollama `think` param; reasoning surfaces in the UI; it is disabled on ACTION turns so it never
buries the tool call (the ornith fix); the router keeps it on (accuracy). Deterministic — no Ollama.
"""

from __future__ import annotations

from hmgfu.thinking import extract_thinking, resolve_think
from tests.test_v2_agent import make_agent


def test_resolve_think_mapping():
    # model without native thinking → always omit (None); the <thinking> prompt fallback applies
    for mode in ("off", "always", "dynamic"):
        assert resolve_think(mode, False, supports_native=False) is None
        assert resolve_think(mode, True, supports_native=False) is None
    # ACTION turn on a native model → False (never bury the tool call), regardless of mode
    for mode in ("off", "always", "dynamic"):
        assert resolve_think(mode, True, supports_native=True) is False
    # conversational turn maps the mode
    assert resolve_think("off", False, supports_native=True) is False
    assert resolve_think("always", False, supports_native=True) is True
    assert resolve_think("dynamic", False, supports_native=True) is None   # model default (on)


def test_extract_thinking_handles_native_tags_and_leaks():
    # HMG-Fu prompt convention
    clean, th = extract_thinking("<thinking>plan A</thinking>The answer is 4.")
    assert clean == "The answer is 4." and "plan A" in th
    # native <think> tag some models emit inline
    clean, th = extract_thinking("<think>let me reason</think>Hello!")
    assert clean == "Hello!" and "let me reason" in th
    # leaked special tokens scrubbed from the answer
    clean, _ = extract_thinking("<|mask_first_thinking_block|>Olá!<|im_end|>")
    assert clean == "Olá!"
    clean, _ = extract_thinking("Result <|mask|> ready")
    assert "<|mask|>" not in clean and "Result" in clean and "ready" in clean
    # a normal answer is untouched
    assert extract_thinking("just a plain answer") == ("just a plain answer", "")


def _native(engine, monkeypatch, fake):
    fake.name = "ollama"                                             # pretend it's the ollama provider
    monkeypatch.setattr(engine.client, "capabilities",
                        lambda m: ["completion", "tools", "thinking"])


def test_agent_passes_think_false_on_action_turns(tmp_path, monkeypatch):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo hi"}}]},
        {"content": "The output is hi.", "tool_calls": []},
    ])
    _native(engine, monkeypatch, fake)
    engine.settings.set("thinking_mode", "always")                  # even 'always'...
    real = engine.retrieve
    def routed(text, **kw):
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["bash"]
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)
    engine.agent_chat("run echo hi")
    assert False in [c["think"] for c in fake.calls]               # ...action turn forced think=False


def test_agent_passes_think_true_on_conversational_always(tmp_path, monkeypatch):
    engine, fake = make_agent(tmp_path, [{"content": "Hello!", "tool_calls": []}])
    _native(engine, monkeypatch, fake)
    engine.settings.set("thinking_mode", "always")
    engine.settings.set("tool_points_enabled", False)              # pure conversational, no action
    engine.agent_chat("hello")
    # the main chat call carried think=True (native reasoning on for a conversational turn)
    assert True in [c["think"] for c in fake.calls]


def test_non_native_model_gets_omitted_think(tmp_path, monkeypatch):
    engine, fake = make_agent(tmp_path, [{"content": "hi", "tool_calls": []}])
    # default fake provider name != 'ollama' AND capabilities [] → never native → think omitted
    engine.settings.set("thinking_mode", "always")
    engine.agent_chat("hello")
    assert all(c["think"] is None for c in fake.calls)             # prompt <thinking> fallback path
