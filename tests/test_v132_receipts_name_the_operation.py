"""93.A — a receipt has to say WHICH operation on WHICH target, not that something happened.

Reproduced from the real conversation of 2026-09-11 (`reports/codex_latest_conversation_20260911/`):
turn 5 removed the `output_prefix` directive — the tombstone is in the ledger and the prefix stops
appearing — and the assistant was then told it had made a false execution claim for saying so. The
cause is deterministic and needs no model: `transactions_of` collapses a directive change to
`directive: bool`, so a REMOVAL arrives indistinguishable from a write, and `_supported("remove")`,
which asks for `retractions` or `effects_remove`, sees neither.

The trap in fixing it is stated in the analysis and is what most of these tests defend: widening
`remove` to accept "a directive changed" would make ANY write prove ANY removal. So the summary
carries operations with targets, and each claim class is supported only by an operation of its own
kind. The learning protocol's effects go through the same summary — a committed fact is an update, a
retraction is a removal — because a receipt that only knows about tools cannot describe a turn whose
only effect was a protocol write.
"""
from __future__ import annotations

from hmgfu.saydo import classify, transactions_of

REMOVED = "I have removed the directive."
CREATED = "I have created the widget."


def _tx(**kw):
    kw.setdefault("tool_trace", [])
    kw.setdefault("fact_changes", [])
    kw.setdefault("directive_change", None)
    return transactions_of(kw["tool_trace"], kw["fact_changes"], kw["directive_change"],
                           learning_effects=kw.get("learning_effects"))


def test_removing_a_directive_supports_saying_so():
    """The exact reproduction: the tombstone is real, so the sentence is true."""
    tx = _tx(directive_change={"kind": "output_prefix", "cleared": True})
    out = classify(REMOVED, [], tx)
    assert out["false_exec_claim"] is False, out


def test_setting_a_directive_does_not_support_a_removal_claim():
    """The discriminating half: a write is not a removal, however loudly it happened."""
    tx = _tx(directive_change={"kind": "output_prefix", "value": "Ready:"})
    assert classify(REMOVED, [], tx)["unsupported_claims"] == ["remove"]


def test_a_removal_elsewhere_does_not_prove_this_one():
    """Operations carry targets, so a receipt names what it removed."""
    tx = _tx(directive_change={"kind": "output_prefix", "cleared": True})
    assert any(op["op"] == "remove" and "output_prefix" in op["target"] for op in tx["operations"])
    assert all(op["target"] for op in tx["operations"]), "an operation without a target proves nothing"


def test_a_retracted_fact_still_supports_a_removal():
    """Behaviour that already worked must keep working (no regression on the old path)."""
    tx = _tx(fact_changes=[{"key": "pet.dog.name", "cleared": True}])
    assert classify(REMOVED, [], tx)["false_exec_claim"] is False


def test_a_written_fact_does_not_support_a_removal():
    tx = _tx(fact_changes=[{"key": "pet.dog.name", "value": "Green"}])
    assert classify(REMOVED, [], tx)["unsupported_claims"] == ["remove"]


def test_a_protocol_commit_is_an_update_not_a_removal():
    """The learning protocol's effects belong in the same summary, with the same discipline."""
    tx = _tx(learning_effects=[{"kind": "domain_definition", "target": "definition:abc",
                                "applied": True}])
    assert classify("I have updated my records.", [], tx)["false_exec_claim"] is False
    assert classify(REMOVED, [], tx)["unsupported_claims"] == ["remove"]


def test_a_protocol_retraction_is_a_removal():
    tx = _tx(learning_effects=[{"kind": "domain_definition", "target": "definition:abc",
                                "operation": "retract", "applied": True}])
    assert classify(REMOVED, [], tx)["false_exec_claim"] is False


def test_an_effect_that_did_not_apply_proves_nothing():
    tx = _tx(learning_effects=[{"kind": "personal_fact", "target": "pet.dog.name", "applied": False}])
    assert tx["operations"] == []
    assert classify("I have updated my records.", [], tx)["unsupported_claims"] == ["update"]


def test_a_blocked_tool_is_not_an_operation():
    trace = [{"name": "create_widget", "arguments": {}, "blocked": True}]
    tx = _tx(tool_trace=trace)
    assert classify(CREATED, trace, tx)["unsupported_claims"] == ["create"]


def test_the_old_keys_still_read_the_same():
    """Compatibility: existing callers read facts/retractions/directive/effects and must not break."""
    tx = _tx(fact_changes=[{"key": "a", "value": "1"}, {"key": "b", "cleared": True}],
             directive_change={"kind": "output_prefix", "cleared": True})
    assert tx["facts"] == 1 and tx["retractions"] == 1 and tx["directive"] is True
    assert tx["effects"] == 0 and tx["plan_ops"] == 0
