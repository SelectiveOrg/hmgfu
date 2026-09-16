"""Phase 85.2 — the context renderer fills EVERY section under the budget: an item that does not fit is skipped, a later
short section is never dropped whole because an earlier section overflowed (the greedy break). Failing first."""
from __future__ import annotations

from hmgfu.context_render import render_injection


def _inj(**sections):
    base = {"userIdentity": [], "warnings": [], "subjectTimeline": [], "contradictions": [], "activeProjects": [],
            "relevantFacts": [], "recentContext": [], "likelyNextActions": []}
    base.update(sections)
    return base


def test_later_section_survives_an_earlier_overflow():
    long_items = ["x" * 300 for _ in range(30)]                      # relevantFacts alone exceeds the budget
    inj = _inj(relevantFacts=long_items, recentContext=["THE GOLD ANSWER 42"])
    out = render_injection(inj, token_budget=1000)                    # 4000 chars
    assert "THE GOLD ANSWER 42" in out                                 # today: dropped whole by the break after relevantFacts
    assert len(out) <= 4000 + 200                                      # still under the budget (header slack)


def test_no_overflow_is_byte_identical_to_before():
    inj = _inj(userIdentity=["name: Ana  (confirmed)"], relevantFacts=["likes amber  (2 days ago)"], recentContext=["said hi  (today)"])
    out = render_injection(inj, token_budget=1800)
    assert out.count("\n- ") == 3 and "User identity" in out and "Recent context" in out


def test_items_skipped_not_truncated():
    inj = _inj(relevantFacts=["a" * 5000, "short fact  (today)"], recentContext=["recent one  (today)"])
    out = render_injection(inj, token_budget=1000)
    assert "short fact" in out and "recent one" in out and "a" * 5000 not in out
