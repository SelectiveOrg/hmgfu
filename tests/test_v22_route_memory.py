"""Phase 56 gap 5 — the router learns from its own confirmed misroute recoveries.

A semantic-recovery rescue that EXECUTES successfully is persisted as a routing exemplar;
future routing injects the most similar exemplars as learned few-shots. Deterministic (fake
embedder, scripted provider) — no Ollama.
"""

from __future__ import annotations

from hmgfu.route_memory import MAX_EXEMPLARS, RouteMemory
from hmgfu.turn_router import classify_turn
from tests.conftest import fake_embed
from tests.test_v2_agent import make_agent


def test_record_dedup_and_selection(tmp_path):
    rm = RouteMemory(str(tmp_path / "rm.db"), fake_embed)
    assert rm.exemplars_for("run the shell command echo hello") == ""   # empty store → no block

    ex1 = rm.record_confirmed_recovery("run the shell command echo hello", "instruction", ["bash"])
    assert ex1 is not None
    # identical text reinforces the SAME exemplar (dedup by embedding), store does not grow
    assert rm.record_confirmed_recovery("run the shell command echo hello",
                                        "instruction", ["bash"]) == ex1
    assert rm.stats() == {"exemplars": 1, "confirmations": 2}

    # only a NEAR-REPHRASING selects the learned exemplar (round-3 lesson: high floor, an
    # exemplar must never fire on merely-topical turns)
    block = rm.exemplars_for("run the shell command echo hi")
    assert "run the shell command echo hello" in block
    assert "requested_tools=['bash']" in block and "action_requested=true" in block
    assert rm.exemplars_for("run that build script again for me") == ""   # topical ≠ rephrasing
    assert rm.exemplars_for("qual a previsao do tempo hoje?") == ""       # unrelated


def test_store_is_capped_and_evicts_least_confirmed(tmp_path):
    rm = RouteMemory(str(tmp_path / "cap.db"), fake_embed)
    keeper = rm.record_confirmed_recovery("deploy the staging build now", "instruction", ["bash"])
    for _ in range(4):                                    # keeper earns 5 confirmations
        rm.record_confirmed_recovery("deploy the staging build now", "instruction", ["bash"])
    for i in range(MAX_EXEMPLARS + 10):                   # flood with distinct one-hit exemplars
        rm.record_confirmed_recovery(f"unique probe number {i} with token{i} filler{i}",
                                     "instruction", ["bash"])
    stats = rm.stats()
    assert stats["exemplars"] <= MAX_EXEMPLARS            # capped
    assert "deploy the staging build" in rm.exemplars_for("deploy the staging build now")  # survivor


def test_classify_turn_injects_learned_examples():
    captured = {}
    def chat(role, messages, **kw):
        captured["system"] = messages[0]["content"]
        return "{}"
    classify_turn(chat, lambda s: {}, "run echo", "clock", "[]",
                  exemplars_text='- "run the shell command echo hello" -> conversation_act=instruction')
    assert "LEARNED ROUTING EXAMPLES" in captured["system"]
    assert "run the shell command echo hello" in captured["system"]
    captured.clear()
    classify_turn(chat, lambda s: {}, "run echo", "clock", "[]", exemplars_text="")
    assert "LEARNED ROUTING EXAMPLES" not in captured["system"]      # absent when nothing learned


def test_agent_confirms_recovery_only_on_success(tmp_path, monkeypatch):
    """End-to-end write path: a recovery rescue is persisted ONLY when the rescued tool actually
    ran successfully; a turn without recovery persists nothing."""
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo HI"}}]},
        {"content": "The output is HI.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)

    real = engine.retrieve
    def routed(text, **kw):                       # simulate the semantic recovery having fired
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["bash"]
        q.recovered_action = "bash"
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)
    engine.agent_chat("run echo HI")
    assert engine.route_memory.stats()["exemplars"] == 1             # confirmed → learned

    # recovered tool NEVER executed (model answered in prose) → NOT confirmed, nothing learned
    fake.script = [{"content": "I would run it.", "tool_calls": []}]
    engine.agent_chat("run echo BYE")
    assert engine.route_memory.stats()["exemplars"] == 1

    # learning disabled → even a successful rescue is not persisted
    engine.settings.set("learning_enabled", False)
    fake.script = [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo X"}}]},
        {"content": "Done: X.", "tool_calls": []},
    ]
    engine.agent_chat("execute the shell print X routine")
    assert engine.route_memory.stats()["exemplars"] == 1
