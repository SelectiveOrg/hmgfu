"""Phase 56 gap 3 — wormhole gates self-calibrate from real near-miss evidence.

Production showed 0 wormholes after 59 dreams (gates tuned on synthetic data). Instead of
hand-picking new constants, the calibrator relaxes the most-binding relaxable gate (bounded)
after consecutive dry dreams WITH near-misses, and tightens back toward the config baseline
when over-firing. Deterministic — hand-set embeddings, sensitizer disabled (nano veto absent).
"""

from __future__ import annotations

import pytest

from hmgfu import config
from hmgfu.dream import dream_loop, find_distant_analogical_pairs, should_create_wormhole
from hmgfu.learning import (WH_BOUNDS, WH_RELAX_AFTER, WH_STEP, LearnedParams,
                            WormholeCalibrator)
from hmgfu.models import Hex, MemoryPoint


def _pair(graph):
    """Two distant, dense, lexically-dissimilar points whose analogy (≈0.66) fails ONLY the
    baseline minAnalogy gate (0.70) — a pure near-miss that one relax step turns into a hit."""
    a = MemoryPoint(content="alpha system balances load across many small workers steadily",
                    type="fact", embedding=[1.0, 0.0], entities=["alpha"], topics=[],
                    density=0.55, utility=0.6, hex=Hex(0, 0, 0))
    b = MemoryPoint(content="beta colony distributes foraging across many small ants steadily",
                    type="fact", embedding=[0.66, 0.7513], entities=["beta"], topics=[],
                    density=0.55, utility=0.6, hex=Hex(6, -6, 0))
    graph.save_point(a)
    graph.save_point(b)
    return a, b


def test_effective_defaults_to_config_baseline(tmp_path):
    cal = WormholeCalibrator(LearnedParams(str(tmp_path / "c.db")))
    assert cal.effective() == config.WORMHOLE


def test_near_miss_instrumentation_tallies_single_failed_gate(graph, sensitizer):
    _pair(graph)
    near = {}
    pairs = find_distant_analogical_pairs(graph, sensitizer, near_misses=near)
    assert pairs == []                                   # baseline gates: no wormhole
    assert near == {"minAnalogy": 1}                     # and the binding gate is identified


def test_calibrator_relaxes_after_dry_streak_and_stays_bounded(tmp_path):
    cal = WormholeCalibrator(LearnedParams(str(tmp_path / "r.db")))
    assert cal.observe({"minAnalogy": 3}, created=0) is None          # dry #1 — observe only
    msg = cal.observe({"minAnalogy": 3}, created=0)                   # dry #2 — relax
    assert msg and "relaxed minAnalogy" in msg
    assert cal.effective()["minAnalogy"] == pytest.approx(
        config.WORMHOLE["minAnalogy"] - WH_STEP["minAnalogy"])
    # sustained dryness can never cross the hard floor
    for _ in range(40):
        cal.observe({"minAnalogy": 1}, created=0)
    assert cal.effective()["minAnalogy"] >= WH_BOUNDS["minAnalogy"][0]


def test_calibrator_tightens_when_over_firing_but_never_beyond_baseline(tmp_path):
    cal = WormholeCalibrator(LearnedParams(str(tmp_path / "t.db")))
    for _ in range(WH_RELAX_AFTER):
        cal.observe({"minAnalogy": 2}, created=0)                     # one relax step down
    relaxed = cal.effective()["minAnalogy"]
    msg = cal.observe({}, created=5)                                  # over target → tighten
    assert msg and "tightened minAnalogy" in msg
    assert cal.effective()["minAnalogy"] == pytest.approx(config.WORMHOLE["minAnalogy"])
    for _ in range(10):                                               # never stricter than baseline
        cal.observe({}, created=5)
    assert cal.effective()["minAnalogy"] <= config.WORMHOLE["minAnalogy"]
    assert relaxed < config.WORMHOLE["minAnalogy"]


def test_dry_dream_without_near_misses_never_relaxes(tmp_path):
    cal = WormholeCalibrator(LearnedParams(str(tmp_path / "n.db")))
    for _ in range(10):
        assert cal.observe({"minAnalogy": 0, "minSemantic": 0, "minDensity": 0}, created=0) is None
    assert cal.effective() == config.WORMHOLE            # no evidence → no adaptation


def test_full_dream_is_actually_scheduled(tmp_path):
    """Root-cause regression (56/59 production dreams were minis): the FULL dream now runs
    automatically every N turns in a background thread — the self-organisation stage cannot
    silently starve again. 0 disables it."""
    from tests.test_v2_agent import make_agent
    engine, fake = make_agent(tmp_path, [{"content": "hi there", "tool_calls": []}])
    engine.settings.set("full_dream_every_n_turns", 1)          # due every turn (test cadence)
    engine.agent_chat("hello")
    thread = getattr(engine, "_dream_thread", None)
    assert thread is not None                                    # scheduled...
    thread.join(timeout=30)
    assert not thread.is_alive()
    fulls = [r for r in engine.graph.dream_reports() if "macros" in (r.summary or "")]
    assert fulls                                                 # ...and a FULL report persisted

    engine.settings.set("full_dream_every_n_turns", 0)          # visible off-switch honoured
    engine._dream_thread = None
    fake.script = [{"content": "hi again", "tool_calls": []}]
    engine.agent_chat("hello again")
    assert engine._dream_thread is None


def test_full_selftuning_loop_dry_relax_fire(graph, sensitizer, embed, tmp_path):
    """The complete loop on a real graph: two dry dreams observe the near-miss, the gate relaxes
    one bounded step, the third dream CREATES the wormhole the baseline was blind to."""
    a, b = _pair(graph)
    cal = WormholeCalibrator(LearnedParams(str(tmp_path / "loop.db")))
    assert not should_create_wormhole(a, b, 0.66)                     # baseline: blind

    r1 = dream_loop(graph, sensitizer, embed, calibrator=cal)
    r2 = dream_loop(graph, sensitizer, embed, calibrator=cal)
    assert r1.wormholes_created == [] and r2.wormholes_created == []
    assert any("relaxed minAnalogy" in i for i in r2.insights)        # adaptation is VISIBLE

    r3 = dream_loop(graph, sensitizer, embed, calibrator=cal)
    assert len(r3.wormholes_created) == 1                             # fires after calibration
    edge = graph.edges[r3.wormholes_created[0]]
    assert edge.relation_type == "wormhole"
    assert {edge.from_id, edge.to_id} == {a.id, b.id}
