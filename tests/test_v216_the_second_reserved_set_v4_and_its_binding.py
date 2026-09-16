"""Gate 2, second reserved set (v4) — shape, expressibility both ways, no relevant overlap, binding.

v3 became DEV by the user's decision (2026-09-13, option (a)); a set read to attribute misses cannot
confirm anything, so v4 exists, drafted blind and pre-registered. This file proves the set can be
judged fairly BEFORE it is frozen: every `answer` is satisfiable by the worked example through the
same oracle the judge uses; no worked example trips its own `answer_absent`; no proper value is shared
with v2, the chains or v3; the judge and the runner bind "v4" by name and the other bindings do not
see it. It never reads a run.
"""
from __future__ import annotations

import pytest

from scripts import judge_validation_v2 as jv2  # noqa: E402
from scripts import validation_episodes_v4 as v4  # noqa: E402
from scripts.answer_oracle import answered


@pytest.fixture(autouse=True)
def _restore():
    yield
    jv2.use_set("v2")


def test_the_shape_is_clean_and_balanced():
    r = v4.check()
    assert r["ok"] and r["episodes"] == 24, r
    assert r["per_axis"] == {"retention": 6, "transfer": 6, "execution": 8, "safety": 4}
    assert set(r["langs"]) == {"en", "pt"} and set(r["bases"]) == {"conflicting", "empty"}


def test_every_answer_post_condition_is_satisfiable_by_its_worked_example():
    for ep in v4.EPISODES:
        want = ep["expect"]
        if not want.get("answer"):
            continue
        got = answered(want["answer_example"], **want["answer"])
        assert got["ok"], f"{ep['id']}: no correct reply can pass -- {got['why']} -- {want['answer_example']!r}"


def test_no_worked_example_trips_its_own_negative_post_condition():
    for ep in v4.EPISODES:
        want = ep["expect"]
        if want.get("answer_example") and want.get("answer_absent"):
            got = answered(want["answer_example"], **want["answer_absent"])
            assert not got["ok"], f"{ep['id']}: the worked example asserts what must be absent -- {got}"


def test_no_relevant_overlap_with_the_earlier_sets():
    shared = v4.overlap()
    assert all(not v for v in shared.values()), shared


def test_the_judge_binds_v4_by_name_and_the_others_do_not_see_it():
    """THE CONTRACT -- fails before: use_set("v4") falls through to v2."""
    jv2.use_set("v4")
    assert set(jv2.BY_ID) == {e["id"] for e in v4.EPISODES} and len(jv2.BY_ID) == 24
    assert jv2.BY_ID["N1"]["steps"][0].startswith("Update:")
    jv2.use_set("v3")
    assert jv2.BY_ID["N1"]["steps"][0].startswith("Correction:")
    jv2.use_set("chains")
    assert "N1" not in jv2.BY_ID


def test_the_runner_names_v4_as_a_set():
    import inspect
    from scripts import run_validation_v2 as rv
    assert 'SET == "v4"' in inspect.getsource(rv)
