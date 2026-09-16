"""Phase 56 — the self-tuning layer: grader outcomes adapt the retrieval scoring weights.

Closes audit gap 1 ("the parameters don't learn"): LearnedParams is the ONE bounded, persisted
store for every learned tunable; WeightLearner adapts config.MEMORY_SCORE_WEIGHTS multipliers
from memory grades. All deterministic — no Ollama.
"""

from __future__ import annotations

import pytest

from hmgfu import config, fu_math
from hmgfu.learning import (GRADE_SIGNAL, LEARNING_RATE, WEIGHT_MULT_MAX, WEIGHT_MULT_MIN,
                            LearnedParams, WeightLearner)
from hmgfu.models import FuEdge, MemoryPoint, QueryPoint, RetrievedMemory
from tests.conftest import fake_embed


def _q(text="tell me about the HMG memory project"):
    return QueryPoint(text=text, embedding=fake_embed(text),
                      entities=["HMG"], topics=["memory"], intent="question")


def _p(content, **kw):
    kw.setdefault("type", "fact")
    kw.setdefault("density", 0.6)
    kw.setdefault("utility", 0.6)
    return MemoryPoint(content=content, embedding=fake_embed(content), **kw)


def test_memory_score_parity_with_components():
    """memory_score == weighted sum of memory_score_components (same math, one implementation),
    and weights=None reproduces the config baseline exactly."""
    q = _q()
    p = _p("HMG memory project uses hexagons", entities=["HMG"], topics=["memory"])
    edge = FuEdge(kappa=0.5, base_separation=2.0, tension=0.1, relation_type="semantic_similarity")
    for e in (None, edge):
        c = fu_math.memory_score_components(q, p, e)
        manual = sum(config.MEMORY_SCORE_WEIGHTS[k] * c[k]
                     * (-1.0 if k.endswith("Penalty") else 1.0)
                     for k in config.MEMORY_SCORE_WEIGHTS)
        expected = fu_math.clamp(manual * c["_factor"])
        assert fu_math.memory_score(q, p, e) == pytest.approx(expected)
        assert fu_math.memory_score(q, p, e, weights=dict(config.MEMORY_SCORE_WEIGHTS)) == \
            pytest.approx(expected)


def test_learned_params_bounded_persisted_resettable(tmp_path):
    db = str(tmp_path / "lp.db")
    lp = LearnedParams(db)
    assert lp.set_bounded("k", 99.0, 0.5, 1.5) == 1.5          # clamped high
    assert lp.set_bounded("k", -3.0, 0.5, 1.5) == 0.5          # clamped low
    lp.bump("k", 0.25, 0.5, 1.5, default=1.0)                  # 0.5 + 0.25
    assert lp.get("k", 1.0) == pytest.approx(0.75)
    lp2 = LearnedParams(db)                                     # persisted across restart
    assert lp2.get("k", 1.0) == pytest.approx(0.75)
    assert lp2.reset("k") == 1                                  # reset restores baseline
    assert lp2.get("k", 1.0) == 1.0


def test_weight_learner_cited_up_unused_down_bounded(tmp_path):
    lp = LearnedParams(str(tmp_path / "wl.db"))
    wl = WeightLearner(lp)
    q = _q()
    cited = RetrievedMemory(point=_p("HMG memory project uses hexagons", entities=["HMG"],
                                     topics=["memory"]), edge=None, score=0.8, reason="t")
    unused = RetrievedMemory(point=_p("banana pancakes taste great", topics=["food"]),
                             edge=None, score=0.4, reason="t")
    base_sem = wl.multipliers()["semantic"]
    assert base_sem == 1.0                                      # stock until taught
    assert wl.weights() == config.MEMORY_SCORE_WEIGHTS          # exact baseline at 1.0

    wl.learn_from_grades(q, [cited], [{"index": 0, "grade": "cited"}])
    up = wl.multipliers()["semantic"]
    assert up > 1.0                                             # cited memory credits its components

    # 73.3: 'unused' is informative only in CONTRAST with something cited/implied in the same turn (a turn answered
    # from the ledger cites nothing and teaches nothing); with a contrast the unused memory's nonzero semantic
    # component moves the multiplier back down
    wl.learn_from_grades(q, [unused], [{"index": 0, "grade": "unused"}])
    assert wl.multipliers()["semantic"] == up                   # no contrast → no blame
    wl.learn_from_grades(q, [cited, unused], [{"index": 0, "grade": "implied"}, {"index": 1, "grade": "unused"}])
    with_blame = wl.multipliers()["semantic"] - up             # implied credit minus the unused memory's blame
    wl.learn_from_grades(q, [cited], [{"index": 0, "grade": "implied"}])
    implied_only = wl.multipliers()["semantic"] - up - with_blame
    assert with_blame < implied_only                             # the blame counted (the increments differ by it)

    # bounded under sustained one-sided teaching: hammer 500 cited updates
    for _ in range(500):
        wl.learn_from_grades(q, [cited], [{"index": 0, "grade": "cited"}])
    mults = wl.multipliers()
    assert all(WEIGHT_MULT_MIN <= m <= WEIGHT_MULT_MAX for m in mults.values())
    assert mults["semantic"] == pytest.approx(WEIGHT_MULT_MAX)  # saturated at the hard bound
    assert wl.update_count() >= 500

    # learned weights actually change the score (semantic-heavy memory scores higher now)
    assert fu_math.memory_score(q, cited.point, weights=wl.weights()) > \
        fu_math.memory_score(q, cited.point)


def test_weight_learner_ignores_invalid_grades(tmp_path):
    wl = WeightLearner(LearnedParams(str(tmp_path / "wg.db")))
    q = _q()
    item = RetrievedMemory(point=_p("HMG hexagons"), edge=None, score=0.5, reason="t")
    n = wl.learn_from_grades(q, [item], [
        {"index": 99, "grade": "cited"},        # out of range
        {"index": -1, "grade": "cited"},        # negative must not grade the last item
        {"index": 0, "grade": "banana"},        # unknown grade
        {"index": "x", "grade": "cited"},       # unparsable
    ])
    assert n == 0
    assert wl.multipliers()["semantic"] == 1.0                  # untouched


def test_grade_turn_teaches_weights_and_respects_toggle(tmp_path):
    """Full-stack: agent_chat → grader (heuristic fallback) → weight learner. Toggle off → no
    learning. The fake provider returns non-JSON, so the deterministic heuristic grades run."""
    from tests.test_v2_agent import make_agent
    engine, fake = make_agent(tmp_path, [{"content": "The dog is Baltazar.", "tool_calls": []}])
    engine.ingest("My dog is called Baltazar and he is a golden retriever", source="user")
    fake.script = [{"content": "Your dog is Baltazar, a golden retriever.", "tool_calls": []},
                   {"content": "not json", "tool_calls": []}]   # reply + grader call
    engine.agent_chat("what is my dog's name?")
    taught = engine.weight_learner.update_count()
    assert taught >= 1                                          # heuristic 'cited' taught weights

    engine.settings.set("learning_enabled", False)
    fake.script = [{"content": "Baltazar again.", "tool_calls": []},
                   {"content": "not json", "tool_calls": []}]
    engine.agent_chat("and my dog is called?")
    assert engine.weight_learner.update_count() == taught       # frozen while disabled
