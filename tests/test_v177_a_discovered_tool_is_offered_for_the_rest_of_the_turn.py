"""95.8 — discovery → the schema is put in front of the model → authorise → execute → verify (§8).

Reproduced live (X6: 2/3, the failing run had `bash` never in `offered` and its calls failing).
Located in `tool_loop.run_tool_loop`: `offered` and `schemas` are computed once from the turn's
`tool_schemas`, and that same list goes to the model on every iteration (`tools=tool_schemas`) and to
the fenced-call recovery. So after `tool_search` returns `bash`, nothing ever offers `bash`'s schema:
the model has to guess the call shape blind — which is what happened, once successfully and once not.

Invariant: discovery makes the capability AVAILABLE for the rest of this turn (its schema is offered);
it authorises nothing — every call still goes through `authority_guard`. The change extends the turn's
schema set, in place, with the tools `tool_search` actually returned, and says so in the trace.
"""
from __future__ import annotations

import json

import pytest

import hmgfu.authority as _auth_mod
from hmgfu.tool_loop import run_tool_loop
from tests.test_v2_agent import make_agent


def _script():
    return [
        {"content": "", "tool_calls": [{"id": "t1", "name": "tool_search",
                                        "arguments": {"query": "run a shell command"}}]},
        {"content": "", "tool_calls": [{"id": "t2", "name": "bash",
                                        "arguments": {"command": "echo VEGA-OK"}}]},
        {"content": "done", "tool_calls": []},
    ]


def _run(engine, provider):
    # The fake provider records the `tools` LIST BY REFERENCE, and the change appends to that list in
    # place -- so a later append would show up in call 0's record. Snapshot the names at call time.
    provider.offered_at_call = []
    real_chat = provider.chat

    def chat(model, messages, **kw):
        provider.offered_at_call.append(sorted(t.get("name") for t in (kw.get("tools") or [])))
        return real_chat(model, messages, **kw)

    provider.chat = chat
    only_search = [engine.tools.schemas["tool_search"]]
    engine._turn_user_message = "I need the forecast and you have no weather tool - find a way."
    engine._turn_plan = None
    engine._turn_effects_allowed = True
    engine._turn_prohibited = False
    messages = [{"role": "user", "content": engine._turn_user_message}]
    return run_tool_loop(engine, messages, only_search, native=True, turn_seq=1)


def _offered_on(provider, call_index):
    return set(provider.offered_at_call[call_index])


def test_the_search_finds_the_shell(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    assert any(r["name"] == "bash" for r in engine.tools.search("run a shell command"))


def test_a_discovered_tool_is_offered_on_the_next_model_call(tmp_path):
    """THE CONTRACT — fails before: the second call still sees only tool_search."""
    engine, provider = make_agent(tmp_path, _script())
    _run(engine, provider)
    assert "tool_search" in _offered_on(provider, 0) and "bash" not in _offered_on(provider, 0)
    assert "bash" in _offered_on(provider, 1), _offered_on(provider, 1)


def test_a_tool_the_search_did_not_return_is_not_offered(tmp_path):
    """NEGATIVE — discovery is not 'offer everything' (94.5's failure mode)."""
    engine, provider = make_agent(tmp_path, _script())
    _run(engine, provider)
    returned = {r["name"] for r in engine.tools.search("run a shell command")}
    extra = _offered_on(provider, 1) - {"tool_search"}
    assert extra and extra <= returned, (extra, returned)


def test_the_discovery_is_in_the_trace(tmp_path):
    """Rule 10: the turn's events say which tools discovery made available."""
    engine, provider = make_agent(tmp_path, _script())
    seen = []
    engine._turn_emit = seen.append
    _run(engine, provider)
    ev = [e for e in seen if e.get("type") == "tools_discovered"]
    assert ev and "bash" in ev[0]["names"], seen


def test_a_discovered_tool_still_passes_the_authority_guard(tmp_path, monkeypatch):
    """PRESERVE — availability is not permission: a prohibited call to the discovered tool stays blocked."""
    engine, provider = make_agent(tmp_path, _script())
    real = _auth_mod.guard          # tool_loop imports `guard as authority_guard`

    def guard(eng, name, args):
        if name == "bash":
            return json.dumps({"blocked": True, "reason": "prohibited this turn"})
        return real(eng, name, args)

    monkeypatch.setattr(_auth_mod, "guard", guard)
    _reply, trace, _forced = _run(engine, provider)
    bash_calls = [t for t in trace if t["name"] == "bash"]
    assert bash_calls and all(t["blocked"] for t in bash_calls), trace
