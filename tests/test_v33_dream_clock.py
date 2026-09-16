"""Phase 62 — dream clock: persisted turn counter + tension trigger that fires only on growth."""

from __future__ import annotations

from hmgfu import config
from tests.test_v2_agent import make_agent


def test_turn_count_survives_restart(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "ok", "tool_calls": []}] * 3)
    for _ in range(3):
        engine.agent_chat("hello there", explicit=False)
    assert engine.turn_count == 3
    assert engine.learned_params.get("state:turn_count", 0) == 3
    engine2, _ = make_agent(tmp_path, [])   # helper bypasses __init__; call the restore step it runs
    engine2._restore_turn_count()
    assert engine2.turn_count == 3          # was 0 after every process start before Phase 62


def test_tension_trigger_only_when_tension_grew(tmp_path, monkeypatch):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("mini_dream_every_n_turns", 0)          # isolate the tension path
    import hmgfu.agent as agent_mod
    counts = {"n": config.MINI_DREAM_TENSION_TRIGGER + 10}
    monkeypatch.setattr("hmgfu.dream.unresolved_tension_count", lambda g: counts["n"])
    assert engine._should_run_mini_dream()                       # never dreamed: stale tension fires once
    engine.learned_params.set_bounded("state:tension_seen", counts["n"], 0, 10**6)   # what the turn records
    assert not engine._should_run_mini_dream()                   # same stale tension: NOT every turn
    counts["n"] += 1
    assert engine._should_run_mini_dream()                       # tension grew: fires again
    assert agent_mod is not None
