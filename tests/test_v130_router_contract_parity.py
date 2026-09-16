"""92.E5R — the router contract must not contradict itself, and the baseline must stay the baseline.

Two findings from `reports/codex_review_92e5/REVIEW.md`, both about the contract rather than the
model:

  * the prompt tells the model that `memory_update` is OPTIONAL and to *omit the field entirely* when
    the turn teaches nothing, while the grammar makes it REQUIRED. An instruction the grammar forbids
    is not an instruction; the honest form is "always present, `null` when the turn teaches nothing",
    and `null` has to remain expressible so no_update stays a valid answer. Nothing here asks the
    model to extract a fact from every message.
  * with the mode OFF, the schema and the prompt still carried the envelope, so arm S -- the control
    the whole comparison is measured against -- was silently running a different perception contract
    from B0. A control that moved is not a control.
"""
from __future__ import annotations

import json

from hmgfu.turn_router import ROUTE_PROMPT, classify_turn, router_schema

CATALOG = ["bash", "memory_search"]


def _system_message(**kw) -> str:
    seen = {}

    def chat(role, messages, **kwargs):
        seen["sys"] = messages[0]["content"]
        return "{}"

    classify_turn(chat, json.loads, "hello", "clock", "[]", **kw)
    return seen["sys"]


def test_the_envelope_is_absent_from_the_contract_when_learning_is_off():
    """Baseline parity: with the protocol off the router must see the contract it saw at B0."""
    schema = router_schema(CATALOG)
    assert "memory_update" not in schema["properties"]
    assert "memory_update" not in schema["required"]


def test_the_envelope_is_present_and_required_when_learning_is_on():
    schema = router_schema(CATALOG, learning=True)
    assert "memory_update" in schema["properties"]
    assert "memory_update" in schema["required"], (
        "an optional field was omitted every time, which left the protocol wired and inert")


def test_no_update_stays_expressible():
    """The gate against the opposite error: requiring the field must not force a fact out of every
    message."""
    prop = router_schema(CATALOG, learning=True)["properties"]["memory_update"]
    assert any(branch.get("type") == "null" for branch in prop["anyOf"])


def test_the_prompt_does_not_ask_for_a_field_the_grammar_requires_to_be_omitted():
    """The paragraph follows the SCHEMA rather than a second flag, so the two cannot disagree."""
    sys_msg = _system_message(format_schema=router_schema(CATALOG, learning=True))
    assert "memory_update" in sys_msg
    assert "omit the field entirely" not in sys_msg.lower()


def test_the_prompt_says_nothing_about_the_envelope_when_learning_is_off():
    sys_msg = _system_message(format_schema=router_schema(CATALOG))
    assert "memory_update" not in sys_msg


def test_the_base_prompt_itself_carries_no_envelope_paragraph():
    """So that every existing caller of ROUTE_PROMPT keeps the pre-92 contract by default."""
    assert "memory_update" not in ROUTE_PROMPT


def test_the_paragraph_carries_no_new_prior_wherever_it_sits():
    """Reconciling a contradiction must not become a behaviour change.

    This test used to also assert the paragraph's POSITION, and its docstring recorded why: *"moving
    the paragraph to the end AND adding 'most messages teach nothing and null is the expected answer'
    cost the whole transfer gain in one campaign."*

    93.W: those were two variables, and the prior was the one that did the damage. Measured on the real
    router with the position changed ALONE and no prior added, same sentence and same schema: the
    contract ahead of 22 tools and 3,793 characters of catalogue produced `memory_update: null`, and
    the same words at the end produced the correct `domain_definition` proposal -- 1/3 to 2/3 on three
    teachings, with undue proposals on three negatives unchanged at 0/3, and `diag_definition_write`
    went from 0/6 to 6/6 end to end. The position assertion is therefore replaced by v157, which pins
    the new position and the reason for it.

    What this test still guards is the half that was never in doubt: no new prior, the null clause
    intact, and no unfilled slot. A prior that tells a 12B model to expect nothing is how you buy a
    clean negative set by giving up the positives."""
    sys_msg = _system_message(format_schema=router_schema(CATALOG, learning=True))
    assert "[[LEARNING]]" not in sys_msg, "the slot must be filled or removed, never shown"
    assert "expected answer" not in sys_msg
    assert "most messages" not in sys_msg.lower()
    flat = " ".join(sys_msg.lower().split())
    assert "set the field to null when the turn teaches nothing" in flat


def test_the_slot_leaves_no_trace_when_learning_is_off():
    assert "[[LEARNING]]" not in _system_message(format_schema=router_schema(CATALOG))
