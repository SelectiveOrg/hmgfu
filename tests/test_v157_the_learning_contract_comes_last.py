"""93.W — the learning contract was being crowded out by the tool catalogue.

The clearest defect left after 93.V was that a definition could be taught, answered correctly in a new
session, and never written. `scripts/diag_definition_write.py` localised it: **0/6, always "no
envelope"** — the protocol refused nothing, because nothing reached it.

Then a single-variable bisect on the router call itself, with the same sentence and the same schema:

    empty catalogue   -> {"proposals": [{"kind": "domain_definition", "value": "Atlas Control Mesh",
                                         "subject_ref": "ACME-7", ...}]}
    real catalogue    -> memory_update: null

22 tools and 3,793 characters of catalogue between the learning contract and the message it is about,
and a 12B model stops applying the contract. Nothing was wrong with the contract's words.

So the same words move to the END of the system prompt, nearest the message they are about. Measured
against the real router on three teachings and three negatives: taught **1/3 -> 2/3**, undue proposals
on the negatives **0/3 in both**. Position, not vocabulary, and no list of phrases anywhere.

These tests are deterministic and need no model: they check the ORDER, which is the thing that was
wrong, and they check that the negative half of the contract — the instruction that a turn teaching
nothing must yield null — travels with it rather than being left behind.
"""
from __future__ import annotations

import json

from hmgfu.turn_router import LEARNING_PROMPT, ROUTE_PROMPT, classify_turn, router_schema

CATALOG = json.dumps([{"name": f"tool_{i}", "description": "x" * 120} for i in range(22)])


def _system(learning: bool = True) -> str:
    seen = {}

    def chat(role, messages, **kwargs):
        seen["sys"] = messages[0]["content"]
        return "{}"

    classify_turn(chat, json.loads, "In this project, ACME-7 means Atlas Control Mesh.", "clock",
                  CATALOG, format_schema=router_schema([], learning=learning))
    return seen["sys"]


def test_the_learning_contract_is_present_when_learning_is_on():
    assert "memory_update describes what the user is TEACHING" in _system()


def test_it_comes_after_the_tool_catalogue():
    """The defect, as a position: 3,793 characters of tools between the contract and the message."""
    block = _system()
    assert block.index("RUNTIME TOOL CATALOG") < block.index("memory_update describes what the user")


def test_it_is_the_last_thing_before_the_message():
    """Nearest the turn it is about. Anything appended after it puts the tools back in between."""
    block = _system()
    tail = block[block.index("memory_update describes what the user"):]
    assert "RUNTIME TOOL CATALOG" not in tail


def test_the_placeholder_leaves_nothing_behind_in_the_route_prompt():
    """A half-moved contract would be worse than either position: it must appear exactly once."""
    block = _system()
    assert block.count("memory_update describes what the user is TEACHING") == 1
    assert "[[LEARNING]]" not in block


def test_the_negative_half_moves_with_it():
    """The instruction that a turn teaching nothing yields null is what keeps the negatives at 0/3."""
    tail = _system()
    tail = tail[tail.index("memory_update describes what the user"):]
    # the contract is wrapped, so "teaches nothing" straddles a newline: normalise before matching,
    # or the test passes and fails on line width rather than on content.
    flat = " ".join(tail.split())
    assert "null" in flat and "teaches nothing" in flat


def test_nothing_is_added_when_learning_is_off():
    block = _system(learning=False)
    assert "memory_update" not in block and "[[LEARNING]]" not in block


def test_the_route_prompt_itself_still_carries_the_placeholder():
    """So the two positions stay one decision in one place, not a copy in each."""
    assert ROUTE_PROMPT.count("[[LEARNING]]") == 1
    assert LEARNING_PROMPT.strip()
