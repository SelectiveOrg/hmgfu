"""J5 — reinforcement can only be measured below saturation (guide §7 "mede reforço com utilidades
abaixo da saturação"); today it cannot be measured at all.

Located: `ingest.py:204` gives a new point `utility=extracted["utility"]` — the NANO's rating of the
sentence at extraction (0..1, default 0.5). In every learning-chain run the teaching sentence and the
assistant's echo were born at 1.0, so the grader's EMA (α=0.3) had nothing to move and 94.6's
`reward_withheld` had nothing to withhold. A rating is an opinion; utility is what a memory EARNS by
being used and graded (grader.py: "Usefulness EMA on utility").

Invariant: a point is born at the default utility; the nano's rating feeds `importance` (which already
exists for exactly that judgement) and never `utility`. Retrieval benches are the regression gate,
because utility feeds density feeds ranking.
"""
from __future__ import annotations

import pytest

from hmgfu.extraction_schema import _DEFAULTS, _sanitise
from tests.test_v2_agent import make_agent


def test_a_new_point_is_born_at_the_default_utility_whatever_the_nano_rated(tmp_path):
    """THE CONTRACT — fails before: the nano's 1.0 becomes the point's utility."""
    engine, _ = make_agent(tmp_path, [])
    real = engine.sensitizer.extract

    def rated_high(text, *a, **k):
        out = real(text, *a, **k)
        out["utility"] = 1.0
        out["importance"] = 0.9
        return out

    engine.sensitizer.extract = rated_high
    p = engine.ingest("In this project, ACME-7 means Atlas Control Mesh.", source="user")
    assert p.utility == pytest.approx(_DEFAULTS["utility"]), p.utility
    assert p.importance == pytest.approx(0.9)          # the rating still counts, where it belongs


def test_use_can_still_raise_utility_from_the_default(tmp_path):
    """PRESERVE — the grader's EMA moves an active point that was cited (94.6's own control)."""
    from hmgfu.grader import _apply_memory_grades
    from hmgfu.models import RetrievedMemory
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("the project is HMG", source="user")
    before = p.utility
    _apply_memory_grades(engine, [RetrievedMemory(point=p, score=0.9, reason="")], [{"index": 0, "grade": "cited"}])
    assert p.utility > before


def test_sanitise_still_reads_the_nano_utility_field():
    """The extraction schema is unchanged: the field exists, is clamped, and defaults to 0.5."""
    assert _sanitise({"utility": 2.0})["utility"] == 1.0
    assert _sanitise({})["utility"] == _DEFAULTS["utility"]
