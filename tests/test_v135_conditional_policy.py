"""93.C — a policy that holds only in some cases needs somewhere to be written down.

The DEV replay of the real conversation (`scripts/diag_sequence_20260911.py`) settled the question
the analysis left open. On every turn the router WAS given the envelope contract
(`envelope_contract_sent=yes`) and answered `null` anyway, so the empty `learning_cases` is not a
missing contract. For "I prefer short snippets unless I ask for the full context" the reason is a
representation limitation in the shared contract, which the guide asks to fix there rather than by
adding a rule for the sentence:

  * the directive vocabulary is `output_prefix`, `output_suffix`, `conversation_opener`,
    `conversation_closer` and `tool_rule:<tool>`. None of them is "how replies should be written", so
    a style policy has nowhere to land — the adapter was sending it to `tool_rule:memory_search`;
  * nothing anywhere can hold the EXCEPTION. A policy stored without "unless I ask for the full
    context" is not the policy the user stated, so a model that refuses to state it is not wrong.

So `response_style` joins the vocabulary and a proposal may carry a `condition`. The discriminating
tests are the ones that keep this from becoming a licence: an unconditional policy must not grow an
exception, a proposal with no value is not a policy, the existing kinds must behave exactly as
before, and a condition must reach the prompt rather than being stored and forgotten.
"""
from __future__ import annotations

import pytest

from hmgfu.directives import DirectiveStore, sanitize_router_directive
from hmgfu.turn_router import router_schema

STYLE = "short snippets"
UNLESS = "the user asks for the full context"


@pytest.fixture()
def store(tmp_path):
    return DirectiveStore(str(tmp_path / "d.db"))


def _apply(store, value=STYLE, condition=UNLESS, text="I prefer short snippets unless I ask for the full context."):
    det = {"kind": "response_style", "value": value, "condition": condition, "instruction": text}
    return store.apply(text, "user_explicit", detected=det)


# --- the contract ---------------------------------------------------------------------------------

def test_a_proposal_can_carry_a_condition():
    props = router_schema([], learning=True)["properties"]["memory_update"]["anyOf"][1]
    item = props["properties"]["proposals"]["items"]
    assert "condition" in item["properties"], "an exception the user stated must be representable"


def test_a_proposal_must_name_a_kind_and_a_value():
    """Without this, 'proposals: [{}]' satisfies the grammar and means nothing."""
    item = router_schema([], learning=True)["properties"]["memory_update"]["anyOf"][1][
        "properties"]["proposals"]["items"]
    assert set(item.get("required") or []) >= {"kind", "value"}


def test_the_prompt_says_what_a_condition_is_for():
    from hmgfu.turn_router import LEARNING_PROMPT

    assert "condition" in LEARNING_PROMPT.lower()


# --- the store ------------------------------------------------------------------------------------

def test_a_style_policy_is_stored_with_its_exception(store):
    assert _apply(store) is not None
    row = next(d for d in store.active() if d["kind"] == "response_style")
    assert row["value"] == STYLE and UNLESS in (row.get("condition") or "")


def test_the_exception_reaches_the_prompt(store):
    _apply(store)
    block = store.render_block()
    assert STYLE in block and UNLESS in block
    # the requirement is that the exception REACHES the prompt, not which connective the user chose:
    # the model returns conditions like "unless I ask for the full context", and a template that
    # assumes the word renders "unless unless ...".
    assert "exception" in block.lower()


def test_an_unconditional_policy_does_not_grow_an_exception(store):
    """The discriminating half: no condition stated, none invented."""
    _apply(store, condition="")
    block = store.render_block()
    assert STYLE in block and "exception" not in block.lower()


def test_a_policy_without_a_value_is_not_a_policy(store):
    assert sanitize_router_directive({"kind": "response_style", "value": ""}) is None


def test_a_style_policy_can_be_cleared_like_any_other(store):
    _apply(store)
    store.apply("forget that", "user_explicit", detected={"kind": "response_style", "clear": True})
    assert all(d["kind"] != "response_style" for d in store.active())


def test_the_existing_kinds_are_untouched(store):
    store.apply("always start replies with Ready:", "user_explicit",
                detected={"kind": "output_prefix", "value": "Ready:", "instruction": "x"})
    row = next(d for d in store.active() if d["kind"] == "output_prefix")
    assert row["value"] == "Ready:" and not (row.get("condition") or "")


# --- the adapter ----------------------------------------------------------------------------------

def test_a_behaviour_policy_proposal_lands_in_the_style_directive(store):
    """End of the chain: what the protocol commits must be what the store holds."""
    from hmgfu.learning_state import apply_decision

    effects = apply_decision({"action": "commit"},
                             [{"kind": "behavior_policy", "relation": "response_style",
                               "value": STYLE, "condition": UNLESS}],
                             directives=store,
                             text="I prefer short snippets unless I ask for the full context.")
    assert effects and effects[0]["applied"]
    row = next(d for d in store.active() if d["kind"] == "response_style")
    assert row["value"] == STYLE and UNLESS in (row.get("condition") or "")


def test_a_behaviour_policy_without_a_relation_is_not_filed_as_a_tool_rule(store):
    """The old default sent every policy to `tool_rule:memory_search`, which is not a style."""
    from hmgfu.learning_state import apply_decision

    apply_decision({"action": "commit"},
                   [{"kind": "behavior_policy", "value": STYLE}],
                   directives=store, text="I prefer short snippets.")
    kinds = {d["kind"] for d in store.active()}
    assert "tool_rule:memory_search" not in kinds, kinds
