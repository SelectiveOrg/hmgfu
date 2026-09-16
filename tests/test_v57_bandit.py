"""Phase 75.5 — bounded Thompson-sampling bandit: converges to the better arm in an offline simulation with a fixed
seed, persists in learned_params, stays bounded, is visible and resettable, and is inert when disabled."""
from __future__ import annotations

import random

from hmgfu.bandit import MAX_COUNT, PREFIX, Bandit
from hmgfu.learning import LearnedParams


def test_converges_to_the_better_arm_within_40_pulls(tmp_path):
    params = LearnedParams(str(tmp_path / "lp.db"))
    b = Bandit(params, rng=random.Random(75))
    truth = {"offer": 0.8, "skip": 0.3}                 # the real payoff of each arm
    world = random.Random(5)
    picks = []
    for _ in range(40):
        arm = b.choose("runbook_hint", ["offer", "skip"])
        picks.append(arm)
        b.reward("runbook_hint", arm, 1.0 if world.random() < truth[arm] else 0.0)
    assert picks[-10:].count("offer") >= 8                 # the last ten pulls are (almost) all the better arm
    assert b.estimate("runbook_hint", "offer") > b.estimate("runbook_hint", "skip")
    snap = b.snapshot()
    assert set(snap["runbook_hint"]) == {"offer", "skip"} and snap["runbook_hint"]["offer"]["pulls"] > snap["runbook_hint"]["skip"]["pulls"]
    params.close()


def test_persists_bounded_visible_resettable_and_inert_when_disabled(tmp_path):
    db = str(tmp_path / "lp.db")
    params = LearnedParams(db)
    b = Bandit(params, rng=random.Random(1))
    for _ in range(int(MAX_COUNT) + 50):
        b.reward("site", "x", 1.0)
    a = params.get(f"{PREFIX}site:x:a", 0.0); bb = params.get(f"{PREFIX}site:x:b", 0.0)
    assert a + bb <= MAX_COUNT + 1e-6 and b.estimate("site", "x") > 0.95   # bounded, still confident
    params.close()
    params2 = LearnedParams(db)                              # persisted across processes
    b2 = Bandit(params2, rng=random.Random(2))
    assert b2.estimate("site", "x") > 0.95
    assert b2.choose("site", ["x", "y"], default="y", enabled=False) == "y"   # OFF → default, nothing recorded
    assert b2.choose("site", ["x", "y"], enabled=False) == "x"
    assert b2.reset() >= 2 and b2.estimate("site", "x") == 0.5 and b2.snapshot() == {}
    params2.close()
