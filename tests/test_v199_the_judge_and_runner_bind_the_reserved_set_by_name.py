"""Gate 2 plumbing — the judge (and the runner) bind the RESERVED v3 set by name, as they bind "chains".

The set itself is frozen (57a8918) and is not read here for anything but its shape: this file proves
the binding, not the set. Positive: use_set("v3") judges v3 ids. Negative: use_set("chains") does not
see them. Preserve: the default binding is v2, and the v3 shape check is still clean.
"""
from __future__ import annotations

import pytest

from scripts import judge_validation_v2 as jv2  # noqa: E402
from scripts import validation_episodes_v3 as v3  # noqa: E402


@pytest.fixture(autouse=True)
def _restore():
    yield
    jv2.use_set("v2")


def test_the_judge_binds_v3_by_name():
    """THE CONTRACT — fails before: use_set("v3") falls through to v2."""
    jv2.use_set("v3")
    assert set(jv2.BY_ID) == {e["id"] for e in v3.EPISODES} and len(jv2.BY_ID) == 24


def test_chains_does_not_see_v3_ids():
    jv2.use_set("chains")
    assert "N1" not in jv2.BY_ID


def test_the_default_is_v2_and_the_v3_shape_is_clean():
    jv2.use_set("v2")
    assert "R1" in jv2.BY_ID and "N1" not in jv2.BY_ID
    assert v3.check()["ok"] and v3.check()["episodes"] == 24


def test_the_runner_names_v3_as_a_set():
    import inspect
    from scripts import run_validation_v2 as rv
    assert 'SET == "v3"' in inspect.getsource(rv)
