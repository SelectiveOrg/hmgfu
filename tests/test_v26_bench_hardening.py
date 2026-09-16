"""Phase 56 bench round-2 hardening — both failures fixed at their system layer.

L24: on a TOOL-ACTION turn the router may re-emit an ACTIVE directive TRANSLATED into the
turn's language ('a short joke' → 'uma piada curta'); the exact-value echo guard can't catch
that lexically, and the spurious apply polluted the directive's instruction with the action
text. Invariant: an action turn never changes an already-active directive kind.

L4: memory-search results are RECORDS — episodic history legitimately mentions corrected
values (old names). The tool result now carries the canonical facts + guidance at the point of
use, so the model can tell history from current values.
"""

from __future__ import annotations

import json

from hmgfu.directives import DirectiveStore, is_blocked_directive_change
from tests.test_v2_agent import make_agent


def test_changing_an_active_kind_requires_a_nonaction_instruction_turn():
    active = [{"kind": "conversation_opener", "value": "a short joke"}]
    translated_echo = {"kind": "conversation_opener", "value": "uma piada curta"}
    new_kind = {"kind": "output_prefix", "value": "hi"}
    clear = {"kind": "conversation_opener", "clear": True}
    # round 2: echo on an ACTION turn → blocked
    assert is_blocked_directive_change(translated_echo, active, True, "instruction") is True
    # round 3: echo on a non-action QUESTION turn (the PT clock probe) → blocked
    assert is_blocked_directive_change(translated_echo, active, False, "question") is True
    assert is_blocked_directive_change(translated_echo, active, False, "greeting") is True
    # the REAL change applies on a directive-bearing act — instruction OR statement (a weaker
    # model like ornith labels a PT directive-set 'statement'; that must NOT be blocked)
    assert is_blocked_directive_change(translated_echo, active, False, "instruction") is False
    assert is_blocked_directive_change(translated_echo, active, False, "statement") is False
    # a brand-new kind applies anywhere; CLEAR is never blocked
    assert is_blocked_directive_change(new_kind, active, True, "question") is False
    assert is_blocked_directive_change(clear, active, True, "question") is False
    assert is_blocked_directive_change(None, active, True, "question") is False


def test_agent_action_turn_keeps_directive_instruction_clean(tmp_path, monkeypatch):
    """The L24 sequence end-to-end: an action turn carrying a translated echo must NOT rewrite
    the standing directive; the real (non-action) change afterwards must apply fully."""
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo hi"}}]},
        {"content": "done", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    engine.directives.apply("start conversations with a short joke",
                            detected={"kind": "conversation_opener", "value": "a short joke",
                                      "instruction": "From now on, open with a short joke.",
                                      "fallback_text": "Why did X? Because Y!"})
    real = engine.retrieve
    def routed_action(text, **kw):     # action turn where the router ALSO echoes, translated
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["bash"]
        q.directive = {"kind": "conversation_opener", "value": "uma piada curta",
                       "instruction": text, "fallback_text": "Nova piada gerada?"}
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed_action)
    engine.agent_chat("Pesquise na sua memoria pelo codigo ORCA-7")
    d = next(x for x in engine.directives.active() if x["kind"] == "conversation_opener")
    assert d["value"] == "a short joke"                          # unchanged by the action turn
    assert d["instruction"] == "From now on, open with a short joke."
    assert d["fallback_text"] == "Why did X? Because Y!"

    # the REAL change arrives on a non-action turn → applies fully, instruction correct
    monkeypatch.setattr(engine, "retrieve", real)
    fake.script = [{"content": "ok", "tool_calls": []}]
    engine.agent_chat("De agora em diante, comece cada nova conversa com uma piada curta.",
                      explicit=True)
    # the deterministic regex can't parse PT; simulate the router path directly via apply
    engine.directives.apply("De agora em diante, comece cada nova conversa com uma piada curta.",
                            detected={"kind": "conversation_opener", "value": "uma piada curta",
                                      "instruction": "De agora em diante, comece cada nova "
                                                     "conversa com uma piada curta.",
                                      "fallback_text": "Por que o jacare? Porque sim!"})
    d = next(x for x in engine.directives.active() if x["kind"] == "conversation_opener")
    assert d["value"] == "uma piada curta"
    assert "De agora" in d["instruction"]                        # self-heals with the real change


def test_directive_set_misclassified_as_action_still_applies(tmp_path, monkeypatch):
    """Bench L24 root cause: the router labels a PT directive-set action_requested=True (the
    imperative reads like an action) but pins NO genuine tool. The old guard used the forced-tool
    flag and BLOCKED the change; the fix uses the genuine-tool signal, so the PT change supersedes."""
    import hmgfu.agent as agentmod
    engine, fake = make_agent(tmp_path, [{"content": "ok", "tool_calls": []},
                                         {"content": "ok2", "tool_calls": []}])
    engine.directives.apply("start with a joke",
                            detected={"kind": "conversation_opener", "value": "a short joke",
                                      "instruction": "From now on open with a short joke.",
                                      "fallback_text": "Why? Because!"})
    real = engine.retrieve
    def routed(text, **kw):
        q, r, ms = real(text, **kw)
        q.action_requested = True            # router reads the imperative as an action...
        q.requested_tools = []               # ...but pins NO genuine tool
        q.conversation_act = "instruction"
        q.directive = {"kind": "conversation_opener", "value": "uma piada curta",
                       "instruction": "De agora em diante, comece com uma piada curta.",
                       "fallback_text": "Por que? Porque sim!"}
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)
    # tools ARE offered (so the OLD code force-picks one and blocks the directive as an echo)
    monkeypatch.setattr(agentmod, "retrieve_tools_for_turn", lambda *a, **k: [
        {"name": "bash", "parameters": {"type": "object",
         "properties": {"command": {"type": "string"}}, "required": ["command"]}}])
    engine.agent_chat("De agora em diante, comece cada nova conversa com uma piada curta.")
    d = next(x for x in engine.directives.active() if x["kind"] == "conversation_opener")
    assert d["value"] == "uma piada curta"                    # PT change applied (not blocked)
    assert "De agora" in d["instruction"]


def test_memory_search_result_carries_canonical_frame(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("retrieval_min_score", 0.05)   # payload-contract test, not ranking quality
    engine.facts.apply("My name is Teodoro H. Ferreira.", "user_explicit")
    engine.ingest("User corrected their name from Sebastian to Teodoro years ago", source="user")
    out = json.loads(engine.tools.execute_tool("memory_search", {"query": "what is my name"}))
    assert out["results"]                                        # the historical record IS returned
    assert any("Teodoro" in line for line in out["canonical_facts"])
    assert "HISTORICAL" in out["guidance"]                       # …with the frame to read it right


def test_memory_search_without_facts_has_no_guidance(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("a plain note about hexagons and memory grids", source="user")
    out = json.loads(engine.tools.execute_tool("memory_search", {"query": "hexagons"}))
    assert "guidance" not in out and "canonical_facts" not in out
