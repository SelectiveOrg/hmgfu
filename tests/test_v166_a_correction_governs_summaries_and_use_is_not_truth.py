"""94.6 — a correction that never reached the summaries, and a contradicted memory rewarded for being repeated.

Two defects, both from the manual sessions, both located exactly.

**Summaries outlive the correction.** `fact_nodes.supersede_stale_nodes` demotes episodic nodes that
carry a now-superseded value — and skips macros outright:

    if p.status != "active" or p.type in ("skill", "macro"):
        continue

A macro is the L1/L2 digest that gets injected into later sessions. So the user corrects the project
to HMG, the episodic nodes are demoted, and the digest still says ACME-7 — which is how ACME-7 kept
coming back in a NEW session after four corrections.

The exclusion is not replaced with a blunt rule. The test that already governs episodic nodes is
conservative and stays conservative: demote only when the text mentions THAT attribute, carries the
OLD value, and does NOT carry the current one. A digest that mentions both is a history and is left
alone; a digest about something else is untouched. Skills are still never demoted.

**Repetition rewarded as truth.** `grader._apply_memory_grades` raises `point.utility` by EMA whenever
the nano grades a memory "cited" or "implied". Utility feeds density, and density feeds retrieval — so
a contradicted memory that gets used is made *more* likely to be used again. Measured in the manual
session: the turn that called the user "trailblazer" AFTER he had corrected it moved a memory
0.5 → 0.65.

The file already draws the right distinction one line below, for a different consumer:

    # a memory the reply actually used (cited/implied) is a silent_use signal — the weakest,
    # CAPPED tier (use is ambiguous, not user verification)

That is exactly the principle; it simply never reached `utility`. A superseded point can no longer
GAIN utility from being used. It can still LOSE it — a correction must always be able to push down.
"""
from __future__ import annotations

import threading

import pytest

from hmgfu.models import MemoryPoint


# --------------------------------------------------------------------------------------------------
# a correction governs the summaries
# --------------------------------------------------------------------------------------------------

def _Point(pid, ptype, content, summary="", status="active"):
    """The REAL MemoryPoint, not a stand-in.

    A hand-built fake has to track the dataclass field by field -- mine was missing five of the seven
    `compute_density` reads -- and a fake that drifts proves nothing about what production grades.
    `utility` starts at the dataclass default (0.5), which is the value measured in the session.
    """
    return MemoryPoint(id=pid, type=ptype, content=content, summary=summary, status=status)


class _Graph:
    def __init__(self, points):
        self._points = points
        self.saved = []

    def all_points(self):
        return list(self._points)

    def save_point(self, p):
        self.saved.append(p.id)

    def centrality(self, pid):
        return 0.0


class _Store:
    """Only what `supersede_stale_nodes` reads."""

    def __init__(self, superseded, active):
        self._superseded = superseded
        self._active = active

    def active(self):
        return list(self._active)

    def superseded_values(self):
        return list(self._superseded)

    def reverted_values(self):
        return []


def _run(points):
    from hmgfu.fact_nodes import supersede_stale_nodes
    graph = _Graph(points)
    store = _Store(superseded=[("project.main", "ACME-7")],
                   active=[{"key": "project.main", "value": "HMG"}])
    supersede_stale_nodes(store, graph)
    return {p.id: p.status for p in points}


def test_a_digest_still_claiming_the_old_project_is_demoted():
    """The one that kept bringing ACME-7 back in a new session."""
    macro = _Point("m1", "macro", "The user's main project is ACME-7, the Atlas Control Mesh.")
    assert _run([macro])["m1"] == "superseded"


def test_a_digest_that_carries_both_is_left_alone():
    """Old AND new together is a history, not a stale claim."""
    macro = _Point("m2", "macro",
                   "The main project moved from ACME-7 to HMG, the Hex memory Grid.")
    assert _run([macro])["m2"] == "active"


def test_a_digest_about_something_else_is_untouched():
    macro = _Point("m3", "macro", "The user lives in Valencia and likes chartreuse.")
    assert _run([macro])["m3"] == "active"


def test_skills_are_still_never_demoted():
    skill = _Point("s1", "skill", "tool: brave_web_search — searches the web for ACME-7 and anything else")
    assert _run([skill])["s1"] == "active"


def test_an_episodic_node_is_still_demoted_as_before():
    """The behaviour that already worked must not change."""
    node = _Point("e1", "episodic", "my main project is ACME-7")
    assert _run([node])["e1"] == "superseded"


# --------------------------------------------------------------------------------------------------
# being used is not being true
# --------------------------------------------------------------------------------------------------

class _Retrieved:
    def __init__(self, point):
        self.point = point


class _Engine:
    def __init__(self):
        self.graph = _Graph([])
        self.regulator = None

    def _noop(self, *a, **k):
        return None


def _grade(point, grade="cited"):
    from hmgfu.grader import _apply_memory_grades
    engine = _Engine()
    details = _apply_memory_grades(engine, [_Retrieved(point)], [{"index": 0, "grade": grade}])
    return point.utility, details


def test_an_active_memory_still_gains_from_being_used():
    """The control: reinforcement must keep working for memories that are still true."""
    point = _Point("p1", "episodic", "the project is HMG")
    after, _ = _grade(point)
    assert after > 0.5


def test_a_superseded_memory_does_not_gain_from_being_repeated():
    """0.5 -> 0.65 on the turn that called him trailblazer after the correction."""
    point = _Point("p2", "episodic", "the user is trailblazer", status="superseded")
    after, _ = _grade(point)
    assert after <= 0.5, "repetition was treated as confirmation of truth"


def test_a_superseded_memory_can_still_be_pushed_down():
    """A correction must always be able to lower it; only the REWARD is withheld."""
    point = _Point("p3", "episodic", "the user is trailblazer", status="superseded")
    point.utility = 0.8
    after, details = _grade(point, grade="unused")
    assert after < 0.8
    assert details[0]["reward_withheld"] is False, "a decrease is not a withheld reward"


def test_a_dormant_memory_is_still_revived_by_use():
    """Dormancy is decay, not contradiction. Being used again is exactly what should revive it."""
    point = _Point("p5", "episodic", "the project is HMG", status="dormant")
    after, _ = _grade(point)
    assert after > 0.5


def test_the_card_still_reports_what_it_saw():
    """Withholding the reward must not hide the fact that a stale memory was used (Rule 10)."""
    point = _Point("p4", "episodic", "the user is trailblazer", status="superseded")
    _after, details = _grade(point)
    assert details and details[0]["id"] == "p4"
    assert details[0]["reward_withheld"] is True


# --------------------------------------------------------------------------------------------------
# 94.6b - demoting the summary must not hide the detail underneath it
# --------------------------------------------------------------------------------------------------
#
# Found by wiring the fix through the layers, not by a failing test. `root_frontier` shows a point only
# when nothing covers it; `parent_index` counted a macro as a parent whatever its status. So the moment
# a correction retired the stale digest, the nodes it summarised went with it -- the summary AND the
# evidence under it. That would have made the fix a net loss of memory.

def _graph_with_macro(macro_status):
    from hmgfu.store import HMGGraph
    g = HMGGraph.__new__(HMGGraph)
    macro = _Point("mm", "macro", "digest: the project is ACME-7", status=macro_status)
    kid = _Point("kk", "episodic", "we shipped the parser on Tuesday")
    g.points = {p.id: p for p in (macro, kid)}
    g.macro_sources = {"mm": ["kk"]}
    g._lock = threading.RLock()          # active_points() materialises under it (H-04)
    return g


def test_an_active_macro_still_covers_its_child():
    from hmgfu.hierarchy import parent_index, root_frontier
    g = _graph_with_macro("active")
    assert parent_index(g) == {"kk": "mm"}
    assert [p.id for p in root_frontier(g)] == ["mm"]


def test_a_superseded_macro_covers_nothing_and_its_child_resurfaces():
    from hmgfu.hierarchy import parent_index, root_frontier
    g = _graph_with_macro("superseded")
    assert parent_index(g) == {}, "a retired digest still counted as cover"
    assert [p.id for p in root_frontier(g)] == ["kk"], "the correction took the detail with it"
