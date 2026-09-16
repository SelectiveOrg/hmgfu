"""Gate 2, third reserved set (v5) — shape, expressibility both ways, no relevant overlap, binding.

v4 was consulted once and became DEV by the user's standing directive; v5 exists so the next gate-2
attempt is a real one, drafted blind while wave 13 ran. This file proves the set can be judged fairly
BEFORE it is frozen: every `answer` is satisfiable by its worked example through the judge's own
oracle; no worked example trips its own `answer_absent`; no proper value is shared with v2, the chains,
v3 or v4; the judge and the runner bind "v5" by name and the other bindings do not see it.
"""
from __future__ import annotations

import pytest

from scripts import judge_validation_v2 as jv2  # noqa: E402
from scripts import validation_episodes_v5 as v5  # noqa: E402
from scripts.answer_oracle import answered


@pytest.fixture(autouse=True)
def _restore():
    yield
    jv2.use_set("v2")


def test_the_shape_is_clean_and_balanced():
    r = v5.check()
    assert r["ok"] and r["episodes"] == 24, r
    assert r["per_axis"] == {"retention": 6, "transfer": 6, "execution": 8, "safety": 4}


def test_every_answer_post_condition_is_satisfiable_by_its_worked_example():
    for ep in v5.EPISODES:
        want = ep["expect"]
        if want.get("answer"):
            got = answered(want["answer_example"], **want["answer"])
            assert got["ok"], f"{ep['id']}: no correct reply can pass -- {got['why']} -- {want['answer_example']!r}"


def test_no_worked_example_trips_its_own_negative_post_condition():
    for ep in v5.EPISODES:
        want = ep["expect"]
        if want.get("answer_example") and want.get("answer_absent"):
            got = answered(want["answer_example"], **want["answer_absent"])
            assert not got["ok"], f"{ep['id']}: the worked example asserts what must be absent -- {got}"


def test_no_relevant_overlap_with_the_earlier_sets():
    shared = {k: [w for w in v if w not in ("You",)] for k, v in v5.overlap().items()}
    assert all(not v for v in shared.values()), shared


def test_the_judge_binds_v5_by_name_and_the_others_do_not_see_it():
    jv2.use_set("v5")
    assert set(jv2.BY_ID) == {e["id"] for e in v5.EPISODES} and len(jv2.BY_ID) == 24
    assert jv2.BY_ID["N1"]["steps"][0].startswith("Heads-up:")
    jv2.use_set("v4")
    assert jv2.BY_ID["N1"]["steps"][0].startswith("Update:")
    jv2.use_set("chains")
    assert "N1" not in jv2.BY_ID


def test_the_runner_names_v5_as_a_set():
    import inspect
    from scripts import run_validation_v2 as rv
    assert 'SET == "v5"' in inspect.getsource(rv)
