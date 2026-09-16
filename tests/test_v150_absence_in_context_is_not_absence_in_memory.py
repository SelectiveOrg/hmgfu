"""93.Q3 (F3) — "I have nothing recorded" is a claim about the MEMORY, not about the context.

The live run reported `I don't have a specific location recorded in our conversation yet` while the
location was stored and merely outside the retrieved context. Not inventing a location is right; the
sentence that followed is a stronger claim than anything the turn could support.

Four states have to be told apart, and the existing pieces already know them — what was missing is
saying which one is which:

  1. the retrieved evidence ANSWERS the question — answer it;
  2. there are memories on the topic but not the relation asked for — do not conclude absence; a
     focused search is warranted;
  3. a search ran and found nothing — say that, with the limit of what was searched;
  4. the tool was unavailable or failed — a limitation, not an empty memory.

The last test is the one that keeps this from becoming a rule that searches on every turn: when the
evidence does answer, nothing is proposed.
"""
from __future__ import annotations

import pytest

from hmgfu.recall_state import RECALL_STATES, describe, recall_state

def test_evidence_the_model_says_is_enough_needs_nothing_more():
    assert recall_state(needs_memory=False, searched=False) == "answered"


def test_the_model_saying_the_context_does_not_answer_is_not_absence():
    """The reproduction: memories about the party, none of them about where it is."""
    assert recall_state(needs_memory=True, searched=False) == "related_only"


def test_a_search_that_found_nothing_says_so():
    assert recall_state(needs_memory=True, searched=True, found=False) == "searched_without_result"


def test_a_search_that_found_something_answers():
    assert recall_state(needs_memory=True, searched=True, found=True) == "answered"


def test_a_failed_tool_is_a_limitation_not_an_empty_memory():
    assert recall_state(needs_memory=True, searched=True, tool_failed=True) == "tool_unavailable"


@pytest.mark.parametrize("state", RECALL_STATES)
def test_every_state_has_a_sentence_that_does_not_overclaim(state):
    said = describe(state).lower()
    if state in ("related_only", "searched_without_result", "tool_unavailable"):
        assert "not recorded" not in said and "no memory" not in said, (
            "absence from the context is not absence from the memory")


def test_only_the_unanswered_states_suggest_looking_further():
    from hmgfu.recall_state import should_search

    assert should_search("related_only") is True
    assert should_search("answered") is False, "a search on every turn is a cost, not a virtue"
    assert should_search("searched_without_result") is False, "asking again the same way is a loop"
    assert should_search("tool_unavailable") is False
