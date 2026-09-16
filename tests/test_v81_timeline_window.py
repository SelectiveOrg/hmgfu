"""Phase 85.2 — the subject-timeline branch renders the query-matched window when the excerpt window is on (85.1 named it:
four golds sat beyond character 160 of long user turns retrieved with a history reason). Byte-identical when the window
is off. Failing first."""
from __future__ import annotations

from types import SimpleNamespace

from hmgfu.retrieve import organise_for_injection


def _point(pid, content, ts="2023-05-01T10:00:00+00:00", status="active"):
    return SimpleNamespace(id=pid, content=content, summary="", title="", timestamp=ts, status=status, source="user",
                           keywords=[], layer="L0_raw", type="message", embedding=[0.0])


def _query(text):
    return SimpleNamespace(text=text, embedding=[0.0])


LONG = ("user: I'm interested in renewable energy resources, can you recommend documentaries? " * 3 +
        "By the way, I just finished reading up to page 220 of A Short History of Nearly Everything.")


def test_timeline_entry_uses_the_query_window_when_on():
    item = SimpleNamespace(point=_point("p1", LONG), edge=None, score=1.0, reason="history[active]")
    graph = SimpleNamespace(points={})
    inj = organise_for_injection([item], graph, query=_query("How many pages of A Short History of Nearly Everything have I read?"),
                                 excerpt_chars=480)
    line = inj["subjectTimeline"][0]
    assert line.startswith("[2023-05-01]") and "page 220" in line


def test_timeline_entry_unchanged_when_the_window_is_off():
    item = SimpleNamespace(point=_point("p1", LONG), edge=None, score=1.0, reason="history[active]")
    inj = organise_for_injection([item], SimpleNamespace(points={}), query=_query("How many pages have I read?"), excerpt_chars=0)
    line = inj["subjectTimeline"][0]
    assert line == "[2023-05-01] " + LONG[:160]                        # today's head cut, byte-identical


def test_superseded_tag_survives_the_window():
    item = SimpleNamespace(point=_point("p2", LONG, status="superseded"), edge=None, score=1.0, reason="history[superseded]")
    inj = organise_for_injection([item], SimpleNamespace(points={}), query=_query("pages read"), excerpt_chars=480)
    assert inj["subjectTimeline"][0].startswith("[2023-05-01] [superseded] ")
