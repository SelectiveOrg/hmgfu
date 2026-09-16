"""93.R5 — an internal recall is a request with a cost, not a reflex that may repeat forever.

Priority 7 of the standing goal asks for "limits against repeated searches", and nothing in the tool
layer had one: `execute_tool` counted calls but never noticed that the same search had already been
answered this turn. A model that decides it must "check memory" can therefore issue the same query
three times in one turn, pay for it three times, and read the same rows three times.

The rule is deliberately not a refusal. Refusing would make the model believe the memory is
unavailable, which is a false statement about the state; and an error invites a retry loop. A repeat
gets the SAME answer it already received, marked as a repeat, so the turn can continue while the cost
is paid once.

The discriminating cases are what keep this from becoming a gag: a DIFFERENT query is not a repeat, a
new turn starts fresh because the world may have changed between turns, and a search that returned
nothing is still answered — "nothing" is a result, and asking twice for it is still a repeat.
"""
from __future__ import annotations

from hmgfu.recall_budget import RecallBudget

QUERY = {"query": "what is my dog called"}
RESULT = '{"results": [{"summary": "the dog is called Green"}]}'


def test_the_first_search_goes_through():
    b = RecallBudget()
    assert b.seen("memory_search", QUERY) is None


def test_the_same_search_again_returns_the_same_answer_marked_as_a_repeat():
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    again = b.seen("memory_search", QUERY)
    assert again is not None
    assert "the dog is called Green" in again, "the model must still get the rows it asked for"
    assert "already" in again.lower(), "and must be told it is reading a repeat"


def test_a_different_query_is_not_a_repeat():
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    assert b.seen("memory_search", {"query": "what is my cat called"}) is None


def test_only_spacing_and_case_differing_is_still_a_repeat():
    """Otherwise the limit is defeated by a capital letter."""
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    assert b.seen("memory_search", {"query": "  What Is My Dog Called  "}) is not None


def test_an_empty_result_is_still_an_answer():
    """'Nothing found' is a result; asking again does not make it more true."""
    b = RecallBudget()
    b.record("memory_search", QUERY, '{"results": []}')
    assert b.seen("memory_search", QUERY) is not None


def test_a_new_turn_starts_fresh():
    """Between turns the world may have changed — the limit is per turn, not per session."""
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    b.begin_turn()
    assert b.seen("memory_search", QUERY) is None


def test_another_tool_is_not_affected():
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    assert b.seen("brave_web_search", QUERY) is None


def test_a_failed_search_is_not_remembered_as_an_answer():
    """A repeat after a failure is a legitimate retry, not a loop."""
    b = RecallBudget()
    b.record("memory_search", QUERY, '{"error": "database is locked"}')
    assert b.seen("memory_search", QUERY) is None


def test_the_ledger_reports_what_was_searched_this_turn():
    """So a receipt can say a search really happened, rather than that one was intended."""
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    b.record("memory_search", {"query": "where do I live"}, RESULT)
    assert b.queries() == ["what is my dog called", "where do I live"]


def test_repeats_are_counted_so_the_cost_is_visible():
    b = RecallBudget()
    b.record("memory_search", QUERY, RESULT)
    b.seen("memory_search", QUERY)
    b.seen("memory_search", QUERY)
    assert b.repeats == 2
