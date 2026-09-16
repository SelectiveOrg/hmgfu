"""93.B — a promise about something the turn already did is not an unkept promise.

The DEV replay reproduces the zombie task exactly. On the correction turn the prefix directive IS
removed — the ledger shows `output_prefix: none → null` — and the reply says "I will ensure that my
responses are direct and free of any unnecessary prefixes". `classify` computes `acted` from the TOOL
TRACE alone, so a turn whose only action was deterministic (a directive removal, a ledger write, a
protocol commit) counts as having done nothing. The promise then becomes a proposal, the user's next
"yes" approves it, and the task outlives its own purpose by thirteen turns.

The fix reuses what 93.A already built: the transaction summary knows which operations really
happened. A turn that removed a directive acted.

The discriminating half is the whole point — a promise on a turn that genuinely did nothing must
STILL become a proposal, because that is the behaviour protecting the user from silent promises. And
summaries built by hand, which carry no operations, keep the pre-93 rule.
"""
from __future__ import annotations

from hmgfu.saydo import classify, transactions_of

PROMISE = "I will ensure that my responses are direct and free of any unnecessary prefixes."


def test_a_promise_on_a_turn_that_removed_a_directive_is_not_an_unkept_promise():
    tx = transactions_of([], [], {"kind": "output_prefix", "cleared": True})
    assert classify(PROMISE, [], tx)["intent_no_action"] is False


def test_a_promise_on_a_turn_that_wrote_a_fact_is_not_an_unkept_promise():
    tx = transactions_of([], [{"key": "pet.dog.name", "value": "Green"}], None)
    assert classify(PROMISE, [], tx)["intent_no_action"] is False


def test_a_promise_on_a_turn_that_committed_through_the_protocol_counts_too():
    tx = transactions_of([], [], None, learning_effects=[
        {"kind": "behavior_policy", "target": "response_style", "applied": True}])
    assert classify(PROMISE, [], tx)["intent_no_action"] is False


def test_a_promise_on_a_turn_that_did_nothing_is_still_an_unkept_promise():
    """The behaviour that must survive: this is what turns into a proposal the user can refuse."""
    tx = transactions_of([], [], None)
    assert classify(PROMISE, [], tx)["intent_no_action"] is True


def test_an_effect_that_did_not_apply_is_not_an_action():
    tx = transactions_of([], [], None, learning_effects=[
        {"kind": "personal_fact", "target": "x", "applied": False}])
    assert classify(PROMISE, [], tx)["intent_no_action"] is True


def test_a_blocked_tool_is_still_not_an_action():
    trace = [{"name": "create_widget", "arguments": {}, "blocked": True}]
    assert classify(PROMISE, trace, transactions_of(trace, [], None))["intent_no_action"] is True


def test_the_episode_alone_is_not_an_action():
    """Every turn is ingested as an episode; if that counted, no promise would ever be caught."""
    tx = transactions_of([], [], None, episode=True)
    assert classify(PROMISE, [], tx)["intent_no_action"] is True


def test_a_hand_built_summary_keeps_the_old_rule():
    assert classify(PROMISE, [], {"facts": 1, "directive": True})["intent_no_action"] is True
