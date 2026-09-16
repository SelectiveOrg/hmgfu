"""93.Q4 — the tool meant to look further could see no further than the context that already failed.

Found by constructing the `related_only` condition properly and then asking WHY it failed, instead of
stopping at the model. With the venue stored but outside the injected context, the system did the
right thing 3/3 — it searched — and then answered "I don't have a specific venue name in my records"
3/3. The artefact says why: `search returned the venue: False` in all three.

`_memory_search` calls `engine.retrieve(q)` with no limit, and `AgentEngine.retrieve` fills the gap
from `retrieval_limit` — the PER-TURN INJECTION budget. So under a narrow budget the deliberate act of
looking further retrieved exactly as few memories as the automatic pass that had already missed it,
and a second identical-reach call is the loop the review warned about: *"a mesma pergunta ampla pode
devolver a mesma memória insuficiente"*.

The two limits are not the same quantity and should never have shared a number. One says how much
memory to put in front of the model unasked, and it is a cost paid on every turn. The other says how
far to look when the model has decided something is missing, and it is paid only when asked for.

The tool has always taken a `limit` argument, defaulting to 8; it simply never passed it down. So it
does now, and 93.Q3's `should_search` keeps its meaning: a search is warranted exactly once, and it
has to be able to find something the context did not.
"""
from __future__ import annotations

import json


class _Recording:
    """An engine that records the limit the tool asked retrieval for."""

    def __init__(self):
        self.asked = None

        class _Facts:
            def render_lines(self):
                return []

        self.facts = _Facts()

    def retrieve(self, text, **overrides):
        self.asked = overrides.get("limit")
        return ({}, [], 1.0)


def _search(args):
    from hmgfu.memory_tools import memory_search

    engine = _Recording()
    out = json.loads(memory_search(engine, args))
    return engine.asked, out


def test_the_search_asks_retrieval_for_the_limit_it_was_given():
    asked, _ = _search({"query": "where is the launch party", "limit": 20})
    assert asked == 20


def test_the_default_reach_is_the_tool_s_own_default_not_the_injection_budget():
    """The whole defect: with retrieval_limit=1 the search used to see exactly one memory."""
    asked, _ = _search({"query": "where is the launch party"})
    assert asked == 8


def test_the_slice_and_the_reach_agree():
    """Asking retrieval for 8 and then keeping 20 would be a limit that means nothing."""
    asked, _ = _search({"query": "x", "limit": 3})
    assert asked == 3


def test_an_empty_query_still_never_reaches_retrieval():
    """62.14's guard survives: nothing here loosens what may be embedded."""
    asked, out = _search({"query": "   "})
    assert asked is None and "error" in out
