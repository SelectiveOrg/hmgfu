"""73.3 — the retrieval weight learner re-balances instead of shrinking, and 'unused' needs a contrast."""
from __future__ import annotations

from hmgfu import config
from hmgfu.learning import LearnedParams, WeightLearner


def _learner(tmp_path):
    return WeightLearner(LearnedParams(str(tmp_path / "p.db")))


def test_stock_multipliers_give_the_baseline(tmp_path):
    w = _learner(tmp_path).weights()
    for k, base in config.MEMORY_SCORE_WEIGHTS.items():
        assert abs(w[k] - base) < 1e-9


def test_uniformly_shrunk_multipliers_are_rebalanced_to_the_baseline_mass(tmp_path):
    wl = _learner(tmp_path)
    for k in config.MEMORY_SCORE_WEIGHTS:
        if not k.endswith("Penalty"):
            wl._params.set_bounded(WeightLearner.PREFIX + k, 0.5, 0.0, 10.0)      # the production collapse
    w = wl.weights()
    pos = [k for k in w if not k.endswith("Penalty")]
    assert abs(sum(w[k] for k in pos) - sum(config.MEMORY_SCORE_WEIGHTS[k] for k in pos)) < 1e-9
    assert abs(w["semantic"] - config.MEMORY_SCORE_WEIGHTS["semantic"]) < 1e-9     # uniform shrink = no preference


def test_relative_preferences_survive_rebalancing(tmp_path):
    wl = _learner(tmp_path)
    wl._params.set_bounded(WeightLearner.PREFIX + "semantic", 0.5, 0.0, 10.0)
    w = wl.weights()
    assert w["semantic"] < config.MEMORY_SCORE_WEIGHTS["semantic"]                  # learned: trust semantic less
    assert w["kappa"] > config.MEMORY_SCORE_WEIGHTS["kappa"]                        # mass moved to the others
    pos = [k for k in w if not k.endswith("Penalty")]
    assert abs(sum(w[k] for k in pos) - sum(config.MEMORY_SCORE_WEIGHTS[k] for k in pos)) < 1e-9
    assert wl.snapshot()["weights"]["semantic"]["effective"] == round(w["semantic"], 4)


def test_unused_without_any_cited_memory_assigns_no_blame(tmp_path):
    from hmgfu.models import MemoryPoint, QueryPoint, RetrievedMemory
    wl = _learner(tmp_path)
    q = QueryPoint(text="what is my name?", embedding=[0.1] * 4, entities=["name"])
    p = MemoryPoint(type="message", content="my name is Ana", summary="", source="user", embedding=[0.1] * 4)
    retrieved = [RetrievedMemory(point=p, edge=None, score=0.9, reason="semantic")]
    before = wl.multipliers()
    assert wl.learn_from_grades(q, retrieved, [{"index": 0, "grade": "unused"}]) == 0
    assert wl.multipliers() == before                                              # a ledger-answered turn teaches nothing
    assert wl.learn_from_grades(q, retrieved, [{"index": 0, "grade": "cited"}]) == 1
    assert wl.multipliers()["semantic"] > 1.0
